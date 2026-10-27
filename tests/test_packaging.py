import runpy
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_frozen_data_is_outside_application(self):
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", str(ROOT / ".test-output/app/VideoWissen.exe")), \
             patch.object(sys, "_MEIPASS", str(ROOT / ".test-output/app/_internal"), create=True), \
             patch.dict("os.environ", {"LOCALAPPDATA": str(ROOT / ".test-output/user"),
                                       "VIDEOWISSEN_DATA_DIR": ""}):
            paths = runpy.run_path(str(ROOT / "video_assistant/paths.py"))
            self.assertFalse(paths["MODEL_ROOT"].is_relative_to(paths["APP_ROOT"]))
            self.assertFalse(paths["DEFAULT_EXPORT"].is_relative_to(paths["APP_ROOT"]))
            self.assertEqual(paths["BUNDLE_ROOT"].name, "_internal")

    def test_frozen_pcm_decoder_and_features(self):
        # The adapter is installed only inside this temporary module map.
        with patch.dict(sys.modules):
            adapter = runpy.run_path(str(ROOT / "tools/runtime_pcm_audio.py"))
            temporary_root = ROOT / ".test-output"
            temporary_root.mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(dir=temporary_root) as temporary:
                audio = Path(temporary) / "test.wav"
                with wave.open(str(audio), "wb") as output:
                    output.setnchannels(1)
                    output.setsampwidth(2)
                    output.setframerate(16000)
                    output.writeframes(np.full(16000, 1000, dtype="<i2").tobytes())
                result = adapter["decode_audio"](str(audio))
                self.assertEqual(result.dtype, np.float32)
                self.assertEqual(result.shape, (16000,))
                self.assertAlmostEqual(float(result[0]), 1000 / 32768)
                with self.assertRaises(ValueError):
                    adapter["decode_audio"](str(audio), sampling_rate=8000)
            self.assertEqual(adapter["pad_or_trim"](np.ones((2, 5)), 3).shape, (2, 3))
            self.assertEqual(adapter["pad_or_trim"](np.ones((2, 5)), 8).shape, (2, 8))
