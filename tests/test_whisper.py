"""Optionaler echter Offline-Whisper-Test mit lokal synthetisiertem Sprachbeispiel."""
import zipfile
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from video_assistant.core import Settings, probe_video, process_video, run_ffmpeg
from video_assistant.hardware import benchmark_sample


@unittest.skipUnless(os.environ.get("WHISPER_TEST_MODEL"), "WHISPER_TEST_MODEL nicht gesetzt")
class RealWhisperTests(unittest.TestCase):
    def test_local_speech(self):
        test_root = Path(__file__).resolve().parents[1] / ".test-output"
        test_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=test_root) as temporary:
            folder = Path(temporary)
            audio = folder / "speech.wav"
            if os.environ.get("WHISPER_TEST_AUDIO"):
                audio = Path(os.environ["WHISPER_TEST_AUDIO"])
            elif os.name == "nt":
                env = dict(os.environ, TEST_SPEECH_PATH=str(audio))
                command = ("Add-Type -AssemblyName System.Speech; "
                           "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                           "$voice.SetOutputToWaveFile($env:TEST_SPEECH_PATH); "
                           "$voice.Speak('Welcome to this training video. First open the settings. "
                           "Then select the export folder and save your project.'); $voice.Dispose()")
                subprocess.run(["powershell", "-NoProfile", "-Command", command], env=env, check=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                self.skipTest("WHISPER_TEST_AUDIO für ein lokales Sprachbeispiel setzen")
            video = folder / "spoken.mp4"
            run_ffmpeg(["-loglevel", "error", "-f", "lavfi", "-i", "color=c=navy:s=640x360:r=10",
                        "-i", str(audio), "-shortest", "-c:v", "mpeg4", "-c:a", "aac", str(video)],
                       threading.Event())
            output = process_video(probe_video(video), folder,
                                   Settings(model=os.environ["WHISPER_TEST_MODEL"], language="en"),
                                   threading.Event(), lambda *args: print(*args, flush=True))
            with zipfile.ZipFile(output) as archive:
                text = archive.read("transcript.md").decode("utf-8").lower()
            self.assertTrue(text, "Sprachbeispiel muss erkannt werden")
            self.assertIn("settings", text)
            ratio = benchmark_sample(probe_video(video), os.environ["WHISPER_TEST_MODEL"], "cpu",
                                     threading.Event(), lambda *_: None, folder, "en")
            self.assertGreater(ratio, 0)
            self.assertFalse(list(folder.glob("probe-*")))
            print("Sprachprobe: Laufzeitfaktor", round(ratio, 3))
            print("Erkannt:", text)

