"""Trennt mitgelieferte Dateien von persönlichen Laufzeitdaten."""
import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
APP_ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parents[1]
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", APP_ROOT))
DATA_ROOT = Path(os.environ.get("VIDEOWISSEN_DATA_DIR", "")) if os.environ.get("VIDEOWISSEN_DATA_DIR") else (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share"))) / "VideoWissen"
    if FROZEN else APP_ROOT / ".app_state")
MODEL_ROOT = DATA_ROOT / "models" if FROZEN else APP_ROOT / "models"
DEFAULT_EXPORT = Path.home() / "Documents" / "VideoWissen" if FROZEN else APP_ROOT / "exports"
