"""Read-only publication audit. Prints filenames/reasons, never matched secrets."""
import argparse
import getpass
import hashlib
import json
import marshal
import re
import subprocess
import types
import zipfile
from pathlib import Path


def audit(root: Path):
    problems = []
    allowlist_file = root / "tools/audit_allowlist.json"
    allowlist = json.loads(allowlist_file.read_text(encoding="utf-8")) if allowlist_file.exists() else {}
    personal = {Path.home().name, getpass.getuser()}
    personal = {name for name in personal if len(name) >= 6}
    needles = [name.lower().encode(encoding) for name in personal for encoding in ("utf-8", "utf-16le")]
    forbidden = {".env", "id_rsa", "id_ed25519", "credentials.json", "token.json"}
    # Crypto libraries legitimately contain parser markers; require an actual key body.
    secret = re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|hf_[A-Za-z0-9]{30,}|sk-(?:proj-)?[A-Za-z0-9_-]{32,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\r\n]+[A-Za-z0-9+/=\r\n]{64,})")
    files = [path for path in root.rglob("*") if path.is_file() and ".git" not in path.relative_to(root).parts]
    if (root / ".git").is_dir():
        tracked = set(subprocess.check_output(["git", "-C", str(root), "ls-files", "-z"]).decode("utf-8").split("\0"))
        for path in files:
            relative = path.relative_to(root)
            if (relative.parts[0] == "_internal" or path.name == "VideoWissen.exe") and relative.as_posix() not in tracked:
                problems.append((str(relative), "runtime file missing from Git index"))
    for path in files:
        relative = path.relative_to(root)
        baseline = allowlist.get(relative.as_posix(), {})
        allowed_fingerprints = set()
        if baseline:
            with path.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            if digest == baseline.get("sha256"):
                allowed_fingerprints = set(baseline.get("credential_fingerprints", []))
        if path.name in forbidden or path.suffix.lower() in (".pem", ".key", ".pfx", ".p12"):
            problems.append((str(relative), "sensitive filename"))
        if path.stat().st_size >= 100 * 1024 * 1024:
            problems.append((str(relative), "GitHub 100-MiB limit"))
        if relative.parts[0] not in ("_internal", "third_party") and path.suffix.lower() in (
                ".mp4", ".mkv", ".wav", ".mp3", ".jpg", ".png", ".pdf", ".xlsx", ".docx"):
            problems.append((str(relative), "unexpected personal media/document"))
        with path.open("rb") as source:
            previous = b""
            while block := source.read(1024 * 1024):
                data = previous + block
                if any(needle in data.lower() for needle in needles):
                    problems.append((str(relative), "local account name embedded"))
                    break
                if any(hashlib.sha256(match.group()).hexdigest() not in allowed_fingerprints
                       for match in secret.finditer(data)):
                    problems.append((str(relative), "credential pattern"))
                    break
                previous = data[-256:]
    # Inspect compressed Python code as well as raw executable bytes.
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(root / "VideoWissen.exe"))
    python_archive = archive.open_embedded_archive("PYZ.pyz")

    def inspect(code, module):
        strings = [code.co_filename] + [value for value in code.co_consts if isinstance(value, str)]
        if any(name.lower() in value.lower() for name in personal for value in strings):
            problems.append((module, "local account name in frozen Python code"))
        if any(secret.search(value.encode("utf-8", errors="replace")) for value in strings):
            problems.append((module, "credential pattern in frozen Python code"))
        for value in code.co_consts:
            if isinstance(value, types.CodeType):
                inspect(value, module)

    for name, entry in archive.toc.items():
        if entry[-1] == "s":
            inspect(marshal.loads(archive.extract(name)), name)

    for name in python_archive.toc:
        code = python_archive.extract(name)
        if isinstance(code, types.CodeType):
            inspect(code, name)
    # base_library.zip contains standard-library bytecode, not user data; still inspect raw entries.
    for path in (root / "_internal").rglob("base_library.zip"):
        with zipfile.ZipFile(path) as zipped:
            for name in zipped.namelist():
                data = zipped.read(name).lower()
                if any(needle in data for needle in needles):
                    problems.append((f"{path.relative_to(root)}:{name}", "local account name in bytecode"))
    return files, sorted(set(problems))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    files, problems = audit(args.directory.resolve())
    for filename, reason in problems:
        print(f"FAIL: {filename}: {reason}")
    print(f"Checked {len(files)} files; {len(problems)} findings.")
    raise SystemExit(bool(problems))
