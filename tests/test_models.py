import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from video_assistant.core import Cancelled, ProcessingError
from video_assistant.hardware import HardwareInfo, estimate_transcription
from video_assistant.models import discover_models, download_model, model_complete

TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-output"
TEST_ROOT.mkdir(exist_ok=True)


def populate(folder):
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt"):
        (folder / name).write_bytes(b"test")


class ModelTests(unittest.TestCase):
    def test_model_discovery_never_downloads(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as temporary:
            folder = Path(temporary)
            populate(folder / "tiny")
            (folder / "small").mkdir()
            (folder / "small" / "model.bin").touch()
            with patch("huggingface_hub.try_to_load_from_cache", return_value=None), \
                 patch("huggingface_hub.snapshot_download") as network:
                found = discover_models(folder)
                self.assertEqual(set(found), {"tiny"})
                self.assertFalse(model_complete(folder / "small"))
                network.assert_not_called()

    def test_explicit_download_success_failure_cancel(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as temporary:
            folder = Path(temporary)

            def download(repo, **kwargs):
                self.assertIn("faster-whisper-base", repo)
                with kwargs["tqdm_class"](total=1) as bar:
                    bar.update(1)
                populate(Path(kwargs["local_dir"]))

            with patch("huggingface_hub.snapshot_download", side_effect=download) as network, patch("sys.stderr", None):
                path = download_model("base", threading.Event(), lambda *_: None, folder)
                self.assertTrue(model_complete(Path(path)))
                self.assertEqual(network.call_count, 1)
            with patch("huggingface_hub.snapshot_download", side_effect=OSError("Netzwerk")):
                with self.assertRaisesRegex(ProcessingError, "Internetverbindung"):
                    download_model("small", threading.Event(), lambda *_: None, folder)
            cancel = threading.Event()
            cancel.set()
            with patch("huggingface_hub.snapshot_download") as network:
                with self.assertRaises(Cancelled):
                    download_model("small", cancel, lambda *_: None, folder)
                network.assert_not_called()

    def test_estimate_respects_video_model_and_hardware(self):
        fast = HardwareInfo("Fast", 8, 32, 3600, "NVIDIA", 12, True)
        slow = HardwareInfo("Slow", 2, 4, 1800)
        a = estimate_transcription(3600, "small", "cpu", fast)
        b = estimate_transcription(7200, "small", "cpu", fast)
        c = estimate_transcription(3600, "large-v3", "cpu", fast)
        d = estimate_transcription(3600, "small", "cpu", slow)
        self.assertGreater(b[0], a[0])
        self.assertGreater(c[0], a[0])
        self.assertGreater(d[0], a[0])
        self.assertEqual(estimate_transcription(3600, "small", "cuda", slow)[:2], (0, 0))
        measured = estimate_transcription(3600, "small", "cpu", fast, .2)
        self.assertLess(measured[0], 720)
        self.assertGreater(measured[1], 720)
        self.assertIn("unbekannt", estimate_transcription(3600, "custom", "cpu", fast)[2])
