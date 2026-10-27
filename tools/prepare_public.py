"""Build a fresh public folder from an explicit allowlist, never the workspace wholesale."""
import argparse
import hashlib
import importlib.metadata
import json
import shutil
from pathlib import Path


def prepare(target: Path):
    root = Path(__file__).resolve().parents[1]
    if target.exists():
        raise SystemExit("Ziel muss ein neuer, leerer Pfad sein. Bestehende Verzeichnisse werden nicht gelöscht.")
    bundle = root / ".build/dist/VideoWissen"
    if not (bundle / "VideoWissen.exe").is_file():
        raise SystemExit("Zuerst den Windows-Build erstellen.")
    shutil.copytree(bundle, target)
    for name in ("README.md", "LICENSE", "SECURITY.md", "THIRD_PARTY_NOTICES.md", "PUBLISHING.md",
                 ".gitattributes", ".editorconfig", "app.py", "start.bat", "install.ps1", "requirements.txt",
                 "requirements-lock.txt", "requirements-build.txt"):
        shutil.copy2(root / name, target / name)
    shutil.copy2(root / "tools/public.gitignore", target / ".gitignore")
    for folder in ("video_assistant", "tests", "tools", ".github"):
        for path in (root / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix in (
                    ".py", ".ps1", ".spec", ".json", ".yml", ".gitignore"):
                relative = path.relative_to(root)
                (target / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target / relative)
    third_party = target / "third_party"
    licenses = third_party / "licenses"
    licenses.mkdir(parents=True)
    excluded = {"pip", "setuptools", "av", "imageio-ffmpeg", "altgraph", "pefile",
                "pyinstaller-hooks-contrib", "pywin32-ctypes"}
    inventory = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name", "unknown")
        if name.lower() in excluded:
            continue
        inventory.append({"name": name, "version": distribution.version})
        for file in distribution.files or []:
            parts = [part.lower() for part in file.parts]
            if "licenses" in parts or file.name.lower().startswith(("license", "copying", "notice")):
                original = Path(distribution.locate_file(file))
                if original.is_file() and original.suffix not in (".pyc", ".pyd", ".dll", ".exe"):
                    destination = licenses / name / Path(*file.parts[1:])
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(original, destination)
    source_folder = root / ".build/vendor-sources"
    if not source_folder.is_dir():
        source_folder = root / "third_party"
    for path in source_folder.iterdir():
        if path.is_file() and (path.suffix == ".zip" or path.name.endswith("-LICENSE")):
            shutil.copy2(path, third_party / path.name)
    ffmpeg_license = next((root / ".build/vendor/ffmpeg").glob("*/LICENSE.txt"))
    shutil.copy2(ffmpeg_license, licenses / "FFmpeg-LGPL-3.0.txt")
    # CPython and Tcl/Tk license texts are also present in the bundled runtime.
    import sys
    for path in (Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "LICENSE"):
        if path.is_file():
            shutil.copy2(path, licenses / "CPython-LICENSE.txt")
    (third_party / "inventory.json").write_text(json.dumps(sorted(inventory, key=lambda x: x["name"].lower()),
                                                        indent=2), encoding="utf-8")
    sums = []
    for path in sorted(target.rglob("*")):
        if path.is_file():
            with path.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            sums.append(f"{digest}  {path.relative_to(target).as_posix()}")
    (target / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(f"Public folder prepared: {len(sums)} files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    prepare(parser.parse_args().output.resolve())
