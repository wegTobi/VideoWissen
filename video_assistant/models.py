"""Explizite Modelldownloads und rein lokale Verfügbarkeitsprüfung."""
from pathlib import Path
import io
import threading

from .core import Cancelled, ProcessingError, check_cancel
from .paths import APP_ROOT, MODEL_ROOT

MODEL_REPOS = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v3": "Systran/faster-whisper-large-v3",
    "turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}
MODEL_SIZES = {"tiny": "ca. 75 MB", "base": "ca. 150 MB", "small": "ca. 500 MB",
               "medium": "ca. 1,5 GB", "large-v3": "ca. 3 GB", "turbo": "ca. 1,6 GB"}


def model_complete(path: Path) -> bool:
    required = ("model.bin", "config.json", "tokenizer.json")
    return all((path / name).is_file() and (path / name).stat().st_size > 0 for name in required) and any(
        (path / name).is_file() and (path / name).stat().st_size > 0
        for name in ("vocabulary.json", "vocabulary.txt"))


def discover_models(root: Path = MODEL_ROOT) -> dict[str, str]:
    """Kein Netzwerkzugriff; erkennt auch bereits vorhandene Hugging-Face-Caches."""
    from huggingface_hub import try_to_load_from_cache
    found = {}
    for name, repo in MODEL_REPOS.items():
        local = root / name
        if model_complete(local):
            found[name] = str(local.resolve())
            continue
        cached = try_to_load_from_cache(repo, "model.bin")
        if isinstance(cached, str) and model_complete(Path(cached).parent):
            found[name] = str(Path(cached).parent)
    return found


def download_model(name: str, cancel: threading.Event, progress, root: Path = MODEL_ROOT) -> str:
    if name not in MODEL_REPOS:
        raise ProcessingError("Für eigene Modelle bitte einen vorhandenen Modellordner auswählen.")
    check_cancel(cancel)
    from huggingface_hub import HfApi, hf_hub_download
    from tqdm.auto import tqdm

    total_bytes = completed_bytes = current_bytes = 0
    last_percent = -1
    progress_lock = threading.Lock()

    def report_bytes(count):
        nonlocal current_bytes, last_percent
        check_cancel(cancel)
        with progress_lock:
            # Retries may restart a counter; keep the overall display monotonic.
            current_bytes = max(current_bytes, count)
            if total_bytes:
                percent = min(99, int(100 * (completed_bytes + current_bytes) / total_bytes))
                if percent != last_percent:
                    last_percent = percent
                    progress(percent, f"{name} herunterladen · {percent} %")

    class DownloadProgress(tqdm):
        def __init__(self, *args, **kwargs):
            kwargs["disable"] = False
            # Windowed EXEs have no stderr. tqdm still writes once when closing.
            kwargs["file"] = io.StringIO()
            super().__init__(*args, **kwargs)
            report_bytes(self.n)

        def display(self, *args, **kwargs):
            # No console in the windowed EXE; send byte progress to the GUI instead.
            return None

        def update(self, n=1):
            check_cancel(cancel)
            result = super().update(n)
            report_bytes(self.n)
            return result

        def update_transfer(self, n):
            # Xet also reports compressed network bytes. Count reconstructed file
            # bytes only, so those bytes aren't counted twice.
            check_cancel(cancel)

        def set_transfer_postfix_str(self, *args, **kwargs):
            pass

    target = root / name
    target.mkdir(parents=True, exist_ok=True)
    progress(0, f"{name} herunterladen · 0 % · Dateigrößen ermitteln …")
    try:
        info = HfApi().model_info(MODEL_REPOS[name], files_metadata=True)
        check_cancel(cancel)
        allowed = {"config.json", "preprocessor_config.json", "model.bin",
                   "tokenizer.json", "vocabulary.json", "vocabulary.txt"}
        files = [file for file in info.siblings if file.rfilename in allowed]
        if not files or any(not file.size or file.size < 0 for file in files):
            raise ProcessingError("Dateigrößen des Modells konnten nicht ermittelt werden. Bitte erneut versuchen.")
        total_bytes = sum(file.size for file in files)
        for file in files:
            check_cancel(cancel)
            current_bytes = 0
            hf_hub_download(MODEL_REPOS[name], file.rfilename, revision=info.sha,
                            local_dir=target, tqdm_class=DownloadProgress)
            # Cache hits need no tqdm callback, but still count as available bytes.
            completed_bytes += file.size
            current_bytes = 0
            report_bytes(0)
        check_cancel(cancel)
        if not model_complete(target):
            raise ProcessingError("Modelldownload unvollständig. Bitte erneut herunterladen.")
    except Exception as exc:
        if cancel.is_set():
            raise Cancelled("Modelldownload abgebrochen. Bereits geladene Dateien werden beim nächsten Versuch weiterverwendet.") from exc
        if isinstance(exc, ProcessingError):
            raise
        raise ProcessingError(f"Download für {name} fehlgeschlagen. Internetverbindung und freien Speicher prüfen.\n{exc}") from exc
    progress(100, f"{name} herunterladen · 100 % · lokal verfügbar.")
    return str(target.resolve())
