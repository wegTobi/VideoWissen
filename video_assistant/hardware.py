"""Lokaler Hardware-Scan und bewusst als Bandbreite ausgegebene Zeitschätzung."""
from dataclasses import dataclass
import ctypes
import math
import os
import platform
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from .core import ProcessingError, check_cancel, run_ffmpeg


@dataclass
class HardwareInfo:
    cpu: str
    logical_cores: int
    ram_gb: float | None = None
    cpu_mhz: int | None = None
    gpu: str | None = None
    vram_gb: float | None = None
    cuda_available: bool = False

    def description(self):
        text = f"{self.cpu} · {self.logical_cores} logische Kerne"
        text += f" · {self.ram_gb:.0f} GB RAM" if self.ram_gb else " · RAM unbekannt"
        text += f" · {self.gpu}" if self.gpu else " · keine NVIDIA-GPU erkannt"
        if self.vram_gb:
            text += f" ({self.vram_gb:.0f} GB VRAM)"
        return text


def scan_hardware() -> HardwareInfo:
    info = HardwareInfo(platform.processor() or "Unbekannte CPU", os.cpu_count() or 1)
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                info.cpu = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
                info.cpu_mhz = int(winreg.QueryValueEx(key, "~MHz")[0])
        except OSError:
            pass

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in ("total_phys", "available_phys", "total_page",
                                                       "available_page", "total_virtual", "available_virtual", "extended")]
        memory = MemoryStatus()
        memory.length = ctypes.sizeof(memory)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            info.ram_gb = memory.total_phys / 1024**3
    else:
        try:
            info.ram_gb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
        except (ValueError, AttributeError, OSError):
            pass
    executable = shutil.which("nvidia-smi")
    if executable:
        try:
            result = subprocess.run([executable, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                                    capture_output=True, text=True, timeout=6,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if result.returncode == 0 and result.stdout.strip():
                name, memory = result.stdout.splitlines()[0].rsplit(",", 1)
                info.gpu, info.vram_gb = name.strip(), float(memory.strip()) / 1024
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    try:
        import ctranslate2
        info.cuda_available = bool(info.gpu and ctranslate2.get_cuda_device_count() > 0)
    except (ImportError, RuntimeError, OSError):
        pass
    return info


def cpu_threads() -> int:
    return max(1, min(8, os.cpu_count() or 1))


MODEL_FACTORS = {"tiny": .25, "base": .5, "small": 1, "medium": 3,
                 "large-v3": 6, "turbo": 1.8}
RAM_REQUIREMENTS = {"tiny": 1, "base": 1, "small": 2, "medium": 5, "large-v3": 8, "turbo": 4}


def estimate_transcription(duration: float, model: str, device: str, hardware: HardwareInfo,
                           measured_ratio: float | None = None) -> tuple[float, float, str]:
    """Heuristik, kein gemessener Hardwarebenchmark; optional echte lokale Probe."""
    warning = ""
    if device == "cuda" and not hardware.cuda_available:
        return 0, 0, "CUDA ist nicht verfügbar. Bitte CPU wählen."
    known = model in MODEL_FACTORS
    if measured_ratio is not None:
        ratio = measured_ratio
        low, high = .65, 1.7
    elif device == "cpu":
        threads = min(8, max(1, hardware.logical_cores))
        clock = min(1.6, max(.5, (hardware.cpu_mhz or 3000) / 3600))
        ratio = .13 * MODEL_FACTORS.get(model, 3) * math.sqrt(8 / threads) / clock
        low, high = .5, 2.5
    else:
        # GPU-Generation und Auslastung sind nicht aus dem VRAM ableitbar: breite Spanne.
        ratio = .085 * MODEL_FACTORS.get(model, 6) / 6
        low, high = .45, 3.5
    memory = hardware.vram_gb if device == "cuda" else hardware.ram_gb
    if memory and memory < RAM_REQUIREMENTS.get(model, 5):
        warning = " Wenig Speicher für dieses Modell; Verarbeitung kann scheitern oder deutlich länger dauern."
        high *= 2
    if not known and measured_ratio is None:
        warning += " Eigenes Modell: Modellgröße unbekannt; 30-s-Probe empfohlen."
    return max(5, duration * ratio * low + 5), max(15, duration * ratio * high + 30), warning


def duration_label(seconds: float) -> str:
    minutes = max(1, math.ceil(seconds / 60))
    if minutes < 60:
        return f"{minutes} Min."
    hours, minutes = divmod(minutes, 60)
    return f"{hours} Std. {minutes} Min."


def benchmark_sample(info, model_path: str, device: str, cancel: threading.Event, progress,
                     temporary_root: Path, language: str | None = None) -> float:
    """30 Sekunden aus der Videomitte; kein Download und keine dauerhafte Audio-Kopie."""
    from faster_whisper import WhisperModel
    check_cancel(cancel)
    progress(0, "Sprachprobe · 0 % · Modell laden …")
    model = WhisperModel(model_path, device=device, compute_type="int8" if device == "cpu" else "float16",
                         local_files_only=True, cpu_threads=cpu_threads())
    temporary_root.mkdir(parents=True, exist_ok=True)
    sample_duration = min(30, info.duration)
    progress(10, "Sprachprobe · 10 % · Audio vorbereiten …")
    with tempfile.TemporaryDirectory(dir=temporary_root, prefix="probe-") as folder:
        audio = Path(folder) / "sample.wav"
        run_ffmpeg(["-loglevel", "error", "-ss", str(max(0, (info.duration - sample_duration) / 2)),
                    "-i", info.path, "-t", str(sample_duration), "-map", "0:a:0", "-vn",
                    "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio)], cancel)
        progress(20, "Sprachprobe · 20 % · lokal transkribieren …")
        started = time.perf_counter()
        segments, metadata = model.transcribe(str(audio), language=language, beam_size=5,
                                              word_timestamps=True, vad_filter=True)
        percent = 20
        for segment in segments:
            check_cancel(cancel)
            # Content progress, not a wall-clock prediction. Silent/VAD-skipped
            # portions may produce jumps; reserve 100% for a valid result.
            next_percent = min(99, max(percent, 20 + int(79 * segment.end / sample_duration)))
            if next_percent != percent:
                percent = next_percent
                progress(percent, f"Sprachprobe · {percent} % · lokal transkribieren …")
        elapsed = time.perf_counter() - started
        check_cancel(cancel)
        if metadata.duration_after_vad < min(5, sample_duration / 2):
            raise ProcessingError("Die Probe enthält zu wenig Sprache. Die Hardware-Schätzung bleibt aktiv.")
        progress(100, "Sprachprobe · 100 % · Zeitschätzung aktualisieren …")
        return elapsed / sample_duration
