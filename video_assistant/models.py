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
    from huggingface_hub import snapshot_download
    from tqdm.auto import tqdm

    class DownloadProgress(tqdm):
        def __init__(self, *args, **kwargs):
            kwargs["disable"] = False
            # Windowed EXEs have no stderr. tqdm still writes once when closing.
            kwargs["file"] = io.StringIO()
            super().__init__(*args, **kwargs)

        def display(self, *args, **kwargs):
            # Keine Konsole notwendig (pythonw); Indikator statt unzuverlässiger Byte-Prozentzahl.
            return None

        def update(self, n=1):
            check_cancel(cancel)
            return super().update(n)

    target = root / name
    target.mkdir(parents=True, exist_ok=True)
    progress(0, f"{name} herunterladen ({MODEL_SIZES[name]}) …")
    try:
        snapshot_download(MODEL_REPOS[name], local_dir=target,
                          allow_patterns=["config.json", "preprocessor_config.json", "model.bin",
                                          "tokenizer.json", "vocabulary.*"],
                          tqdm_class=DownloadProgress, max_workers=2)
        check_cancel(cancel)
        if not model_complete(target):
            raise ProcessingError("Modelldownload unvollständig. Bitte erneut herunterladen.")
    except Exception as exc:
        if cancel.is_set():
            raise Cancelled("Modelldownload abgebrochen. Bereits geladene Dateien werden beim nächsten Versuch weiterverwendet.") from exc
        if isinstance(exc, ProcessingError):
            raise
        raise ProcessingError(f"Download für {name} fehlgeschlagen. Internetverbindung und freien Speicher prüfen.\n{exc}") from exc
    progress(100, f"{name} ist lokal verfügbar.")
    return str(target.resolve())
