import tempfile
import threading
import unittest
import wave
import zipfile
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

from video_assistant.core import (Cancelled, ProcessingError, Settings,
    estimated_count, export_zip, probe_video, process_video, run_ffmpeg, timestamp)

TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-output"
TEST_ROOT.mkdir(exist_ok=True)

def make_video(path, duration=64, audio=True):
    args = ["-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=2"]
    if audio:
        args += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000", "-c:a", "aac"]
    args += ["-t", str(duration), "-c:v", "mpeg4", "-q:v", "10", str(path)]
    run_ffmpeg(args, threading.Event())


class FakeModel:
    calls = []
    options = {}

    def __init__(self, *args, **kwargs):
        self.constructor = (args, kwargs)
        FakeModel.options = kwargs

    def transcribe(self, audio, **kwargs):
        with wave.open(audio) as wav:
            duration = wav.getnframes() / wav.getframerate()
            assert wav.getnchannels() == 1
            assert wav.getframerate() == 16000
        self.calls.append(duration)
        words = [SimpleNamespace(start=i + .1, end=i + .9, word=" Schritt")
                 for i in range(int(duration))]
        return iter([SimpleNamespace(words=words)]), SimpleNamespace(language="de")


class CoreTests(unittest.TestCase):
    def test_time_and_counts(self):
        self.assertEqual(timestamp(7200.125), "02:00:00.125")
        self.assertEqual(timestamp(3599.9998, True), "01-00-00.000")
        self.assertEqual([estimated_count(7200, r) for r in (2, 5, 10, 20)], [240, 600, 1200, 2400])
        self.assertEqual(estimated_count(12.01, 5), 2)
        for rate in (0, -2, 61, float("nan"), float("inf")):
            with self.assertRaises(ProcessingError):
                Settings(rate=rate).validate()

    def test_cancel_before_process(self):
        event = threading.Event()
        event.set()
        with self.assertRaises(Cancelled):
            run_ffmpeg([], event)

    def test_zip_contains_transcript_prompt_and_screenshots(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as temp:
            output = Path(temp) / "Projekt Ä"
            (output / "screenshots").mkdir(parents=True)
            (output / "screenshots" / "001.jpg").write_bytes(b"test")
            (output / "transcript.md").write_text("# Gespräch\\nHallo", encoding="utf-8")
            (output / "prompt.md").write_bytes("# Arbeitsauftrag\nFür Studierende".encode("utf-8"))
            (output / "project.json").write_text("{}")
            (output / "ai_instructions.md").write_text("Nicht exportieren")
            (output / "screenshots" / "private.txt").write_text("Nicht exportieren")
            target = Path(temp) / "export.zip"
            archive = export_zip(output, target, threading.Event())
            with zipfile.ZipFile(archive) as zipped:
                self.assertEqual(set(zipped.namelist()), {"transcript.md", "prompt.md", "screenshots/001.jpg"})
                self.assertEqual(zipped.read("prompt.md").decode("utf-8"), "# Arbeitsauftrag\nFür Studierende")
                self.assertEqual(zipped.read("screenshots/001.jpg"), b"test")
                self.assertIn("Gespräch", zipped.read("transcript.md").decode("utf-8"))
            with self.assertRaises(ProcessingError):
                export_zip(output, target, threading.Event())
            archive.unlink()
            event = threading.Event()
            event.set()
            with self.assertRaises(Cancelled):
                export_zip(output, target, event)
            self.assertFalse(target.exists())
            self.assertFalse(target.with_suffix(".zip.part").exists())
            with patch("video_assistant.core.check_cancel", side_effect=[None, None, Cancelled("Abbruch im ZIP")]):
                with self.assertRaises(Cancelled):
                    export_zip(output, target, threading.Event())
            self.assertFalse(target.exists())
            self.assertFalse(target.with_suffix(".zip.part").exists())


class FFmpegIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=TEST_ROOT)
        cls.root = Path(cls.temp.name)
        cls.video = cls.root / "Schulung ä & Test.mkv"
        make_video(cls.video)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_complete_pipeline_with_chunked_audio(self):
        info = probe_video(self.video)
        self.assertAlmostEqual(info.duration, 64, delta=.2)
        self.assertTrue(info.has_audio)
        FakeModel.calls = []
        destination = self.root / "complete"
        output = process_video(info, destination, Settings(rate=2, chunk_seconds=30),
                               threading.Event(), lambda *_: None, FakeModel, prompt_text="# Mein Prompt\nBegriffe erklären.")
        self.assertEqual(output.suffix, ".zip")
        self.assertEqual(list(destination.iterdir()), [output])
        self.assertEqual(len(FakeModel.calls), 3)
        self.assertTrue(FakeModel.options["local_files_only"])
        self.assertLessEqual(FakeModel.options["cpu_threads"], 8)
        self.assertLessEqual(max(FakeModel.calls), 34.1)
        with zipfile.ZipFile(output) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(len(archive.namelist()), 5)
            self.assertEqual(archive.read("prompt.md").decode("utf-8"), "# Mein Prompt\nBegriffe erklären.")
            text = archive.read("transcript.md").decode("utf-8")
            self.assertEqual(text.count("Schritt"), 64)
            self.assertIn("## 00:00:00 – 00:00:29", text)
            self.assertNotRegex(text, r"\d{2}:\d{2}:\d{2}\.\d+")
            images = sorted(name for name in archive.namelist() if name.startswith("screenshots/"))
            self.assertEqual(len(images), 3)
            for image in images:
                self.assertEqual(archive.read(image)[:2], b"\xff\xd8")
            for image, time in zip(images, ("00-00-00", "00-00-30", "00-01-00")):
                self.assertIn(time, image)

    def test_no_audio_and_corrupt_video(self):
        silent = self.root / "no_audio.mp4"
        make_video(silent, 1, False)
        info = probe_video(silent)
        self.assertFalse(info.has_audio)
        with self.assertRaisesRegex(ProcessingError, "Tonspur"):
            process_video(info, self.root, Settings(), threading.Event(), lambda *_: None, FakeModel)
        corrupt = self.root / "corrupt.mp4"
        corrupt.write_text("kein Video")
        with self.assertRaises(ProcessingError):
            probe_video(corrupt)
        with self.assertRaises(ProcessingError):
            probe_video(self.root / "missing.mp4")

    def test_failure_cleans_working_files(self):
        def broken(*args, **kwargs):
            raise RuntimeError("Modell fehlt")
        dest = self.root / "failure"
        with self.assertRaisesRegex(ProcessingError, "Whisper-Modell"):
            process_video(probe_video(self.video), dest, Settings(rate=2), threading.Event(), lambda *_: None, broken)
        self.assertEqual(list(dest.iterdir()), [])

    def test_cancel_during_screenshots(self):
        cancel = threading.Event()
        dest = self.root / "cancel"

        def update(percent, text):
            if text.startswith("Screenshot"):
                cancel.set()

        with self.assertRaises(Cancelled):
            process_video(probe_video(self.video), dest, Settings(rate=20), cancel, update, FakeModel)
        self.assertEqual(list(dest.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

