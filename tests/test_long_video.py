"""Optionaler Zweistundentest mit echter FFmpeg-Verarbeitung und Modellattrappe."""
import zipfile
import os
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace

from video_assistant.core import Settings, probe_video, process_video, run_ffmpeg


@unittest.skipUnless(os.environ.get("RUN_LONG_VIDEO_TEST"), "Optionaler Zweistundentest")
class LongVideoTests(unittest.TestCase):
    def test_two_hours_bounded_audio(self):
        root = Path(__file__).resolve().parents[1] / ".test-output"
        root.mkdir(exist_ok=True)
        calls = []

        class SilentModel:
            def __init__(self, *args, **kwargs):
                pass

            def transcribe(self, audio, **kwargs):
                with wave.open(audio) as wav:
                    duration = wav.getnframes() / wav.getframerate()
                calls.append(duration)
                if duration > 304.1:
                    raise AssertionError("Audioblock ist zu groß")
                return iter(()), SimpleNamespace(language="de")

        with tempfile.TemporaryDirectory(dir=root) as temporary:
            folder = Path(temporary)
            video = folder / "two-hours.mkv"
            run_ffmpeg(["-loglevel", "error", "-f", "lavfi", "-i", "color=c=navy:s=160x90:r=1",
                        "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-t", "7200",
                        "-c:v", "mpeg4", "-c:a", "flac", str(video)], threading.Event())
            info = probe_video(video)
            self.assertAlmostEqual(info.duration, 7200, delta=.1)
            output = process_video(info, folder, Settings(rate=2), threading.Event(), lambda *_: None, SilentModel)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(len(archive.namelist()), 242)
                self.assertIn("Keine Sprache erkannt.", archive.read("transcript.md").decode("utf-8"))
            self.assertEqual(len(calls), 24)
            self.assertFalse(list(folder.glob(".videowissen-*")))
            print("Zweistundentest: 240 Bilder, 24 Audioblöcke, größter Block", max(calls), "Sekunden")
