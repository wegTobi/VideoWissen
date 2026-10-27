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

from .quality import finite, flag_adjacent_repetitions, review_windows, warnings as quality_warnings



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


def collect_transcript(iterator, offset, start, end, language, cancel, on_record=None):
    records = []
    for segment in iterator:
        check_cancel(cancel)
        all_words = getattr(segment, "words", None) or []
        words = [word for word in all_words if finite(word.start) and finite(word.end)
                 and start <= offset + (word.start + word.end) / 2 < end]
        missing_words = not all_words
        if words:
            text = "".join(word.word for word in words).strip()
            left, right = offset + words[0].start, offset + words[-1].end
        elif missing_words:
            text = getattr(segment, "text", "").strip()
            left = offset + getattr(segment, "start", 0)
            right = offset + getattr(segment, "end", 0)
            if not finite(left) or not finite(right) or not start <= (left + right) / 2 < end:
                continue
        else:
            continue  # Words belong to the adjacent audio block.
        if not text:
            continue
        left = max(start, left, records[-1]["end"] if records else start)
        right = min(end, right)
        if right <= left:
            continue
        record = {"start": round(left, 3), "end": round(right, 3), "text": text,
                  "word_probabilities": [word.probability for word in words
                                         if finite(getattr(word, "probability", None))]}
        source_start, source_end = getattr(segment, "start", None), getattr(segment, "end", None)
        record["review_start"] = max(start, min(left, offset + source_start)) if finite(source_start) else left
        record["review_end"] = min(end, max(right, offset + source_end)) if finite(source_end) else right
        for key in ("avg_logprob", "compression_ratio", "no_speech_prob"):
            record[key] = getattr(segment, key, None)
        record["warnings"] = quality_warnings(record, language)
        if missing_words:
            record["warnings"].append("Wortzeitstempel fehlen; Text anhand der Abschnittszeiten erhalten")
        records.append(record)
        if on_record:
            on_record(record)
    flag_adjacent_repetitions(records)
    return records


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
    result = {"schema_version": 2, "language": detected_language, "segments": segments, "reviews": []}
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
            # Midpoint ownership still prevents duplicate words in overlapping blocks.
            records = collect_transcript(
                iterator, audio_start, start, end, detected_language, cancel,
                lambda record: progress(36 + 59 * (start + .8 * (record["end"] - start)) / info.duration,
                                        f"Transkription {timestamp(int(record['end'])).split('.')[0]}"))
            if not records and getattr(language_info, "duration_after_vad", 0) > 2:
                records = [{"start": start, "end": end, "text": "[Kein Text erkannt.]",
                            "warnings": ["Sprachaktivität erkannt, aber kein Transkript ausgegeben"]}]
            # Catch loops crossing a five-minute boundary. Older parts remain
            # marked for source review; retry only the current block.
            flag_adjacent_repetitions(segments[-2:] + records)
            for record in records:
                record["id"] = f"segment_{len(segments) + 1:06d}"
                segments.append(record)
            windows = review_windows(records)
            for index, (left, right) in enumerate(windows):
                check_cancel(cancel)
                progress(36 + 59 * (start + (end - start) * (.8 + .2 * index / len(windows))) / info.duration,
                         f"Qualitätsprüfung: {timestamp(int(left)).split('.')[0]} – {timestamp(int(right)).split('.')[0]} erneut erkennen …")
                review = {"start": left, "end": right, "segments": [], "error": False}
                result["reviews"].append(review)
                try:
                    retry_start, retry_end = max(0, left - 2), min(info.duration, right + 2)
                    retry_audio = Path(temporary) / "retry.wav"
                    run_ffmpeg(["-loglevel", "error", "-ss", str(retry_start), "-i", info.path,
                                "-t", str(retry_end - retry_start), "-map", "0:a:0", "-vn", "-ac", "1",
                                "-ar", "16000", "-c:a", "pcm_s16le", str(retry_audio)], cancel)
                    retry_iterator, _ = model.transcribe(str(retry_audio), language=detected_language,
                                                        beam_size=5, vad_filter=True, word_timestamps=True,
                                                        condition_on_previous_text=False, temperature=0.0)
                    review["segments"] = collect_transcript(retry_iterator, retry_start, left, right,
                                                             detected_language, cancel)
                except Cancelled:
                    raise
                except Exception:
                    # A failed optional retry must never discard the first result.
                    check_cancel(cancel)
                    review["error"] = True
            progress(36 + 59 * end / info.duration,
                     f"Transkription und Qualitätsprüfung bis {timestamp(int(end)).split('.')[0]}")
            write_transcript(output, result)
    count = sum(bool(segment.get("warnings")) for segment in segments)
    progress(95, f"Qualitätsprüfung abgeschlossen: {count} auffällige Abschnitte im Transkript markiert.")
    return result


def write_transcript(output: Path, result: dict):
    paragraphs = ["# Transkript", "", f"Sprache: {result['language'] or 'unbekannt'}", ""]
    count = sum(bool(segment.get("warnings")) for segment in result["segments"])
    if count:
        paragraphs.extend([f"> **Qualitätshinweis: {count} Abschnitte sind als unsicher markiert.**",
                           "> Das sind automatische Verdachtsmeldungen, keine bewiesenen Fehler. Prüfe den Originalton. "
                           "Erst- und Zweiterkennung sind keine gesicherten Aussagen; die Zweiterkennung steht am Ende.", ""])
    for segment in result["segments"]:
        start = timestamp(int(segment["start"])).split(".", 1)[0]
        end = timestamp(int(segment["end"])).split(".", 1)[0]
        paragraphs.extend([f"## {start} – {end}", ""])
        if segment.get("warnings"):
            paragraphs.extend(["> **Transkription unsicher:** " + "; ".join(segment["warnings"]) + ".", ""])
        paragraphs.extend([segment["text"], ""])
    if not result["segments"]:
        paragraphs.append("Keine Sprache erkannt.")
    if result.get("reviews"):
        paragraphs.extend(["# Nachprüfung unsicherer Stellen", "",
                           "Die folgenden Alternativen wurden einmalig ohne vorherigen Textkontext erkannt. "
                           "Sie ersetzen den ursprünglichen Text nicht. Auch unauffällige Alternativen können falsch sein. "
                           "Widersprüche und fehlenden Inhalt nur anhand der Originalaufnahme klären.", ""])
        for review in result["reviews"]:
            left = timestamp(int(review["start"])).split(".", 1)[0]
            right = timestamp(int(review["end"])).split(".", 1)[0]
            paragraphs.extend([f"## {left} – {right} · Alternative Erkennung (unsicher)", ""])
            if review["error"]:
                paragraphs.extend(["Zweiterkennung fehlgeschlagen. Ursprünglichen Text und Originalton prüfen.", ""])
            elif not review["segments"]:
                paragraphs.extend(["Zweiterkennung lieferte keinen Text. Das beweist nicht, dass hier nicht gesprochen wurde.", ""])
            for candidate in review["segments"]:
                timecode = timestamp(int(candidate["start"])).split(".", 1)[0]
                paragraphs.extend([f"**{timecode}:** {candidate['text']}", ""])
                if candidate.get("warnings"):
                    paragraphs.extend(["> Weiterhin auffällig: " + "; ".join(candidate["warnings"]) + ".", ""])
    (output / "transcript.md").write_text("\n".join(paragraphs), encoding="utf-8")


def export_zip(output: Path, target: Path, cancel: threading.Event) -> Path:
    """Exportiert Transkript, den eingestellten KI-Prompt und JPEG-Screenshots."""
    if target.exists():
        raise ProcessingError(f"ZIP existiert bereits: {target}")
    transcript = output / "transcript.md"
    prompt = output / "prompt.md"
    images = sorted((output / "screenshots").glob("*.jpg"))
    if not transcript.is_file() or not prompt.is_file() or not images:
        raise ProcessingError("Transkript, Prompt oder Screenshots fehlen; kein ZIP-Export möglich.")
    temporary = target.with_suffix(".zip.part")
    try:
        check_cancel(cancel)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
            for path in [transcript, prompt, *images]:
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
                  progress: Callable, model_factory=None, *, prompt_text: str | None = None) -> Path:
    from .prompting import PromptPreferences, build_prompt
    prompt_text = build_prompt(PromptPreferences()) if prompt_text is None else prompt_text
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
        (output / "prompt.md").write_bytes(prompt_text.encode("utf-8"))
        progress(97, "ZIP-Datei erstellen …")
        export_zip(output, target, cancel)
    progress(100, f"Fertig: {target}")
    return target
