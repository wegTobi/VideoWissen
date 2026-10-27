"""Lokaler Pakettest; schreibt nur auf ausdrücklichen Aufruf einen Diagnosebericht."""
import json
import tempfile
import threading
import traceback
import zipfile
from pathlib import Path


def run_self_test(report_path: str, model_path: str | None = None, audio_path: str | None = None,
                  download_name: str | None = None) -> int:
    target = Path(report_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    report = {"ok": False}
    try:
        import tkinter as tk
        import faster_whisper
        import ctranslate2
        import onnxruntime
        from .core import Settings, ffmpeg_executable, probe_video, process_video, run_ffmpeg
        from .models import discover_models, download_model
        from .prompting import PromptPreferences, build_prompt
        root = tk.Tk()
        root.withdraw()
        report["tk"] = str(root.tk.call("info", "patchlevel"))
        root.destroy()
        report["dependencies"] = {"faster_whisper": faster_whisper.__version__,
                                  "ctranslate2": ctranslate2.__version__, "onnxruntime": onnxruntime.__version__}
        report["ffmpeg"] = Path(ffmpeg_executable()).name
        if download_name:
            percentages = []
            model_path = download_model(download_name, threading.Event(),
                                        lambda value, _: percentages.append(value))
            report["download_model"] = download_name
            report["download_percentages"] = percentages
            assert percentages == sorted(percentages) and percentages[-1] == 100
        report["models_detected"] = sorted(discover_models())
        report["prompt_ok"] = "transcript.md" in build_prompt(PromptPreferences())
        with tempfile.TemporaryDirectory(prefix="selftest-", dir=target.parent) as temporary:
            folder = Path(temporary)
            video = folder / "sample.mp4"
            args = ["-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=5"]
            args += ["-i", str(Path(audio_path).resolve())] if audio_path else [
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000"]
            args += ["-t", "10", "-shortest", "-c:v", "mpeg4", "-c:a", "aac", str(video)]
            run_ffmpeg(args, threading.Event())
            info = probe_video(video)
            report["video_duration"] = info.duration
            if model_path:
                output = process_video(info, folder / "export", Settings(model=str(Path(model_path).resolve()),
                                       language="en", rate=20), threading.Event(), lambda *_: None)
                with zipfile.ZipFile(output) as archive:
                    names = archive.namelist()
                    assert "transcript.md" in names
                    assert all(name == "transcript.md" or (name.startswith("screenshots/") and name.endswith(".jpg"))
                               for name in names)
                    assert archive.testzip() is None
                    transcript = archive.read("transcript.md").decode("utf-8")
                    report["speech_recognized"] = "settings" in transcript.lower() if audio_path else None
                    if audio_path:
                        assert report["speech_recognized"], "Sprachbeispiel wurde nicht erkannt"
                assert list((folder / "export").iterdir()) == [output]
                report["zip_entries"] = names
                report["inference"] = "passed"
            else:
                report["inference"] = "not_tested_no_model"
        report["ok"] = True
    except Exception:
        report["error"] = traceback.format_exc()
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1
