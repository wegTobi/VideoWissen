"""Verarbeitung ohne GUI; FFmpeg und Whisper werden nur bei Bedarf geladen."""
from __future__ import annotations

import math
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import zipfile
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable



class ProcessingError(RuntimeError):
    pass


class Cancelled(ProcessingError):
    pass


def check_cancel(cancel: threading.Event):
    if cancel.is_set():
        raise Cancelled("Verarbeitung abgebrochen.")


def timestamp(seconds: float, filename=False) -> str:
    millis = max(0, round(seconds * 1000))
    hours, rest = divmod(millis, 3600000)
    minutes, rest = divmod(rest, 60000)
    secs, ms = divmod(rest, 1000)
    separator = "-" if filename else ":"
    return f"{hours:02d}{separator}{minutes:02d}{separator}{secs:02d}.{ms:03d}"


def estimated_count(duration: float, rate: float) -> int:
    return max(1, math.ceil(duration * rate / 60 - 1e-9))


def ffmpeg_executable() -> str:
    configured = os.environ.get("FFMPEG_BINARY")
    if configured:
        if Path(configured).is_file():
            return configured
        raise ProcessingError("FFMPEG_BINARY verweist auf keine vorhandene Datei.")
    from .paths import BUNDLE_ROOT
    bundled = BUNDLE_ROOT / "ffmpeg" / "ffmpeg.exe"
    if bundled.is_file():
        return str(bundled)
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise ProcessingError("FFmpeg fehlt. Bitte install.ps1 ausführen oder FFmpeg zum PATH hinzufügen.") from exc


def run_ffmpeg(arguments: list[str], cancel: threading.Event,
               on_line: Callable[[str], None] | None = None) -> str:
    """Leert stderr fortlaufend; begrenzter Diagnosepuffer und abbrechbarer Prozess."""
    check_cancel(cancel)
    command = [ffmpeg_executable(), "-hide_banner", "-nostdin", "-y", *arguments]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", errors="replace", creationflags=flags)
    except OSError as exc:
        raise ProcessingError(f"FFmpeg konnte nicht gestartet werden: {exc}") from exc
    lines: queue.Queue = queue.Queue(maxsize=256)
    tail = deque(maxlen=80)
    stop_reader = threading.Event()

    def read():
        try:
            for line in process.stderr:
                # Während eines Abbruchs darf der Leser nicht an einer vollen Queue hängen.
                while not stop_reader.is_set():
                    try:
                        lines.put(line, timeout=0.1)
                        break
                    except queue.Full:
                        if cancel.is_set():
                            return
        finally:
            process.stderr.close()

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        while process.poll() is None or reader.is_alive() or not lines.empty():
            check_cancel(cancel)
            try:
                line = lines.get(timeout=0.1)
            except queue.Empty:
                continue
            tail.append(line.rstrip())
            if on_line:
                on_line(line)
        if process.wait() != 0:
            raise ProcessingError("FFmpeg konnte die Datei nicht verarbeiten:\n" + "\n".join(tail)[-5000:])
        return "\n".join(tail)
    finally:
        stop_reader.set()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        reader.join(timeout=2)


@dataclass(frozen=True)
class VideoInfo:
    path: str
    duration: float
    size_bytes: int
    has_audio: bool


def probe_video(path: Path, cancel: threading.Event | None = None) -> VideoInfo:
    path = path.resolve()
    if not path.is_file():
        raise ProcessingError("Die ausgewählte Videodatei wurde nicht gefunden.")
    # FFmpeg ist ausreichend; damit wird keine separate ffprobe-Installation benötigt.
    found = {"duration": None, "video": False, "audio": False}

    def inspect(line):
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", line)
        if match:
            h, m, s = map(float, match.groups())
            found["duration"] = h * 3600 + m * 60 + s
        if "Stream #" in line:
            found["video"] |= "Video:" in line
            found["audio"] |= "Audio:" in line

    run_ffmpeg(["-i", str(path), "-map", "0:v:0", "-frames:v", "1", "-an", "-f", "null", "-"],
               cancel or threading.Event(), inspect)
    if not found["video"] or not found["duration"] or found["duration"] <= 0:
        raise ProcessingError("Keine Videospur mit gültiger Dauer gefunden. Bitte die Datei prüfen oder neu exportieren.")
    return VideoInfo(str(path), found["duration"], path.stat().st_size, found["audio"])


@dataclass
class Settings:
    rate: float = 5
    model: str = "small"
    language: str | None = "de"
    device: str = "cpu"
    chunk_seconds: int = 300
    max_width: int = 1600

    def validate(self):
        if not math.isfinite(self.rate) or not 1 <= self.rate <= 60:
            raise ProcessingError("Bitte zwischen 1 und 60 Screenshots pro Minute wählen.")
        if self.device not in ("cpu", "cuda"):
            raise ProcessingError("Unbekanntes Rechengerät.")
        if not self.model.strip():
            raise ProcessingError("Bitte ein Modell oder einen lokalen Modellordner angeben.")
        if not 30 <= self.chunk_seconds <= 600:
            raise ProcessingError("Audioblöcke müssen zwischen 30 und 600 Sekunden lang sein.")
        if self.max_width < 320:
            raise ProcessingError("Die Bildbreite muss mindestens 320 Pixel betragen.")


def extract_screenshots(info: VideoInfo, output: Path, settings: Settings,
                        cancel: threading.Event, progress: Callable) -> list[dict]:
    folder = output / "screenshots"
    folder.mkdir()
    shots = []
    expected = estimated_count(info.duration, settings.rate)
    interval = 60 / settings.rate

    def on_line(line):
        # showinfo liefert die tatsächliche Präsentationszeit des ausgewählten Frames.
        match = re.search(r"\bn:\s*(\d+).*?pts_time:\s*([\d.eE+-]+)", line)
        if match:
            index = int(match[1]) + 1
            seconds = float(match[2])
            shots.append({"id": f"shot_{index:06d}", "timestamp": round(seconds, 6),
                          "timecode": timestamp(seconds),
                          "path": f"screenshots/{index:06d}_{timestamp(seconds, True)}.jpg"})
            progress(min(34, 5 + 29 * index / expected), f"Screenshot {index} / ca. {expected}")

    filters = (f"select=gte(t\\,selected_n*{interval:.12f}),"
               f"scale=w='min({settings.max_width},iw)':h=-2,showinfo")
    run_ffmpeg(["-i", info.path, "-map", "0:v:0", "-an", "-sn", "-vf", filters,
                "-fps_mode", "vfr", "-q:v", "3", str(folder / "%06d.jpg")], cancel, on_line)
    if not shots:
        raise ProcessingError("FFmpeg hat keine Screenshots erstellt.")
    for index, shot in enumerate(shots, 1):
        check_cancel(cancel)
        source = folder / f"{index:06d}.jpg"
        if not source.is_file():
            raise ProcessingError(f"Screenshot {index} fehlt; Export unvollständig.")
        source.rename(output / shot["path"])
    return shots


def transcribe(info: VideoInfo, output: Path, settings: Settings, cancel: threading.Event,
               progress: Callable, model_factory=None) -> dict:
    if not info.has_audio:
        raise ProcessingError("Die Videodatei enthält keine Tonspur. Bitte die Aufnahme oder Audiospuren prüfen.")
    if model_factory is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ProcessingError("faster-whisper fehlt. Bitte install.ps1 ausführen.") from exc
        model_factory = WhisperModel
    check_cancel(cancel)
    progress(35, "Lokales Whisper-Modell laden …")
    try:
        from .hardware import cpu_threads
        model = model_factory(settings.model, device=settings.device,
                              compute_type="int8" if settings.device == "cpu" else "float16",
                              local_files_only=True, cpu_threads=cpu_threads())
    except Exception as exc:
        raise ProcessingError("Whisper-Modell konnte nicht geladen werden. Bitte zuerst über 'Modell herunterladen' "
                              "installieren oder einen vollständigen lokalen CTranslate2-Modellordner wählen. "
                              "Bei GPU-Problemen CPU wählen.\n" + str(exc)) from exc
    check_cancel(cancel)
    segments = []
    detected_language = settings.language
    result = {"schema_version": 1, "language": detected_language, "segments": segments}
    # Nur ein Audioblock liegt als WAV/NumPy-Array vor; niemals die gesamte Tonspur.
    with tempfile.TemporaryDirectory(prefix="audio-", dir=output) as temporary:
        for block in range(math.ceil(info.duration / settings.chunk_seconds)):
            check_cancel(cancel)
            start = block * settings.chunk_seconds
            end = min(info.duration, start + settings.chunk_seconds)
            audio_start = max(0, start - 2)
            audio_end = min(info.duration, end + 2)
            audio = Path(temporary) / "chunk.wav"
            progress(36 + 59 * start / info.duration,
                     f"Transkription {timestamp(start)} / {timestamp(info.duration)}")
            run_ffmpeg(["-loglevel", "error", "-ss", str(audio_start), "-i", info.path,
                        "-t", str(audio_end - audio_start), "-map", "0:a:0", "-vn", "-ac", "1",
                        "-ar", "16000", "-c:a", "pcm_s16le", str(audio)], cancel)
            iterator, language_info = model.transcribe(str(audio), language=detected_language,
                                                       beam_size=5, vad_filter=True,
                                                       word_timestamps=True)
            detected_language = detected_language or language_info.language
            result["language"] = detected_language
            for segment in iterator:
                check_cancel(cancel)
                # Überlappung nicht doppelt übernehmen: Wortmittelpunkt entscheidet den Block.
                words = [w for w in (segment.words or [])
                         if start <= audio_start + (w.start + w.end) / 2 < end]
                if not words:
                    continue
                text = "".join(w.word for w in words).strip()
                if not text:
                    continue
                left = max(start, audio_start + words[0].start,
                           segments[-1]["end"] if segments else 0)
                right = min(end, audio_start + words[-1].end)
                if right <= left:
                    continue
                segments.append({"id": f"segment_{len(segments) + 1:06d}",
                                 "start": round(left, 3), "end": round(right, 3), "text": text})
                progress(min(95, 36 + 59 * right / info.duration),
                         f"Transkription {timestamp(right)} / {timestamp(info.duration)}")
            write_transcript(output, result)
    return result


def write_transcript(output: Path, result: dict):
    paragraphs = ["# Transkript", "", f"Sprache: {result['language'] or 'unbekannt'}", ""]
    for segment in result["segments"]:
        start = timestamp(int(segment["start"])).split(".", 1)[0]
        end = timestamp(int(segment["end"])).split(".", 1)[0]
        paragraphs.extend([f"## {start} – {end}",
                           "", segment["text"], ""])
    if not result["segments"]:
        paragraphs.append("Keine Sprache erkannt.")
    (output / "transcript.md").write_text("\n".join(paragraphs), encoding="utf-8")


def export_zip(output: Path, target: Path, cancel: threading.Event) -> Path:
    """Exportiert ausschließlich das Markdown-Transkript und die JPEG-Screenshots."""
    if target.exists():
        raise ProcessingError(f"ZIP existiert bereits: {target}")
    transcript = output / "transcript.md"
    images = sorted((output / "screenshots").glob("*.jpg"))
    if not transcript.is_file() or not images:
        raise ProcessingError("Transkript oder Screenshots fehlen; kein ZIP-Export möglich.")
    temporary = target.with_suffix(".zip.part")
    try:
        check_cancel(cancel)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
            for path in [transcript, *images]:
                check_cancel(cancel)
                archive.write(path, path.relative_to(output))
        check_cancel(cancel)
        if target.exists():
            raise ProcessingError(f"ZIP existiert bereits: {target}")
        temporary.rename(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def process_video(info: VideoInfo, destination: Path, settings: Settings, cancel: threading.Event,
                  progress: Callable, model_factory=None) -> Path:
    settings.validate()
    if not info.has_audio:
        raise ProcessingError("Die Datei enthält keine Tonspur. Bitte die Aufnahme oder Audiospuren prüfen.")
    check_cancel(cancel)
    destination.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^\w -]", "_", Path(info.path).stem)[:70].strip() or "Video"
    basename = f"{slug}_{datetime.now():%Y%m%d_%H%M%S}"
    target = destination / f"{basename}.zip"
    number = 1
    while target.exists() or target.with_suffix(".zip.part").exists():
        target = destination / f"{basename}_{number}.zip"
        number += 1
    # Arbeitsdateien werden auch bei Fehler oder Abbruch entfernt. Im Ziel bleibt nur die fertige ZIP.
    with tempfile.TemporaryDirectory(prefix=".videowissen-", dir=destination) as temporary:
        output = Path(temporary)
        progress(2, f"Ziel: {target}")
        extract_screenshots(info, output, settings, cancel, progress)
        transcribe(info, output, settings, cancel, progress, model_factory)
        check_cancel(cancel)
        progress(97, "ZIP-Datei erstellen …")
        export_zip(output, target, cancel)
    progress(100, f"Fertig: {target}")
    return target
