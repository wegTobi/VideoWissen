"""Lädt ausschließlich den festgelegten offiziellen FFmpeg-Build mit Hashprüfung."""
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    lock = json.loads((root / "tools/ffmpeg-lock.json").read_text(encoding="utf-8-sig"))
    vendor = root / ".build/vendor"
    vendor.mkdir(parents=True, exist_ok=True)
    archive = vendor / "ffmpeg.zip"
    if not archive.exists() or hashlib.file_digest(archive.open("rb"), "sha256").hexdigest() != lock["sha256"]:
        with urllib.request.urlopen(lock["url"], timeout=60) as source, archive.open("wb") as target:
            while block := source.read(1024 * 1024):
                target.write(block)
    with archive.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != lock["sha256"]:
            raise RuntimeError("FFmpeg-Prüfsumme stimmt nicht; Build wird abgebrochen.")
    destination = vendor / "ffmpeg"
    with zipfile.ZipFile(archive) as zipped:
        for item in zipped.infolist():
            resolved = (destination / item.filename).resolve()
            if not resolved.is_relative_to(destination.resolve()):
                raise RuntimeError("Unsicherer Pfad im FFmpeg-Archiv.")
        zipped.extractall(destination)
    print("FFmpeg-Build geprüft und bereitgestellt.")


if __name__ == "__main__":
    main()
