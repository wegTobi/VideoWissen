import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from video_assistant.core import Cancelled, Settings, VideoInfo, collect_transcript, transcribe
from video_assistant.prompting import PromptPreferences, build_prompt
from video_assistant.quality import flag_adjacent_repetitions, repetition, review_windows, warnings

TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-output"


def segment(text, start, end, **extra):
    words = text.split()
    step = (end - start) / max(1, len(words))
    return NS(start=start, end=end, text=text,
              words=[NS(word=" " + word, start=start + i * step, end=start + (i + .8) * step,
                        probability=.95) for i, word in enumerate(words)],
              avg_logprob=-.1, compression_ratio=1.2, no_speech_prob=.01, **extra)


class QualityTests(unittest.TestCase):
    def test_repetition_and_legitimate_language(self):
        for text in ("Zwei! " * 10, "5,5,5,5,5", "Ab da einfach! " * 5):
            self.assertTrue(repetition(text), text)
        for text in ("Nein, nein, das ist ein anderes Beispiel.", "This is not a test. 中文 heißt Chinesisch.",
                     "Die Werte sind 1, 2, 3, 4, 5, 6.", "Sehr sehr gut erklärt."):
            record = {"start": 0, "end": 10, "text": text, "avg_logprob": -.2}
            self.assertFalse(warnings(record, "de"), text)

    def test_signals_and_adjacent_loops(self):
        record = {"start": 0, "end": 65, "text": "Ich kann nicht schief gehen!",
                  "avg_logprob": -1.2, "compression_ratio": 3, "no_speech_prob": .9,
                  "word_probabilities": [.1, .2]}
        self.assertGreaterEqual(len(warnings(record, "de")), 4)
        foreign = {"start": 0, "end": 1, "text": "境", "avg_logprob": -.8}
        self.assertTrue(warnings(foreign, "de"))
        records = [{"start": i, "end": i + 1, "text": "Zwei!", "warnings": []} for i in range(4)]
        flag_adjacent_repetitions(records)
        self.assertTrue(all(record["warnings"] for record in records))
        self.assertEqual(review_windows(records), [(0, 4)])

    def test_missing_word_timestamps_preserves_text_and_source_span(self):
        raw = NS(start=0, end=65, text="Erhaltener Text", words=None)
        records = collect_transcript(iter([raw]), 0, 0, 90, "de", threading.Event())
        self.assertEqual(records[0]["text"], "Erhaltener Text")
        self.assertTrue(records[0]["warnings"])
        self.assertEqual(review_windows(records), [(0, 30), (30, 60), (60, 65)])
        raw = segment("Wenige Wörter", 0, 1)
        raw.end = 65
        records = collect_transcript(iter([raw]), 0, 0, 90, "de", threading.Event())
        self.assertEqual(len(review_windows(records)), 3)

    def test_retry_keeps_original_and_handles_empty_error_and_cancel(self):
        for outcome in ("success", "empty", "error", "cancel"):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory(dir=TEST_ROOT) as temporary:
                cancel = threading.Event()
                calls, ffmpeg_calls, progress = [], [], []

                class Model:
                    def __init__(self, *args, **kwargs):
                        pass

                    def transcribe(self, audio, **kwargs):
                        calls.append(kwargs)
                        if len(calls) == 1:
                            return iter([segment("Zwei! " * 10, 0, 65)]), NS(language="de")
                        if outcome == "cancel":
                            cancel.set()
                            raise Cancelled("Test")
                        if outcome == "error":
                            raise RuntimeError("Netterweise nur ein Testfehler")
                        if outcome == "empty":
                            return iter([]), NS(language="de")
                        return iter([segment("Andere Wörter zum Test der lokalen alternativen Erkennung", 2, 8)]), NS(language="de")

                output = Path(temporary)
                with patch("video_assistant.core.run_ffmpeg", side_effect=lambda args, _: ffmpeg_calls.append(args)):
                    def run():
                        return transcribe(VideoInfo("test.mp4", 90, 100, True), output, Settings(),
                                          cancel, lambda value, text: progress.append(value), Model)
                    if outcome == "cancel":
                        with self.assertRaises(Cancelled):
                            run()
                        self.assertEqual(list(output.iterdir()), [])
                        continue
                    result = run()
                text = (output / "transcript.md").read_text(encoding="utf-8")
                self.assertIn("Zwei! " * 9, text)
                self.assertIn("Transkription unsicher", text)
                self.assertIn("Nachprüfung unsicherer Stellen", text)
                self.assertEqual(len(result["reviews"]), 3)
                self.assertEqual(len(calls), 4)  # one initial pass, one retry per bounded window
                self.assertEqual(progress, sorted(progress))
                for options in calls[1:]:
                    self.assertFalse(options["condition_on_previous_text"])
                    self.assertEqual(options["temperature"], 0)
                    self.assertTrue(options["vad_filter"])
                for args in ffmpeg_calls[1:]:
                    self.assertLessEqual(float(args[args.index("-t") + 1]), 34)
                self.assertFalse(list(output.glob("audio-*")))
                if outcome == "success":
                    self.assertIn("Andere Wörter", text)
                elif outcome == "empty":
                    self.assertIn("beweist nicht", text)
                else:
                    self.assertIn("Zweiterkennung fehlgeschlagen", text)

    def test_no_text_despite_speech_is_not_silently_exported_as_silence(self):
        class Model:
            def __init__(self, *args, **kwargs):
                pass

            def transcribe(self, *args, **kwargs):
                return iter([]), NS(language="de", duration_after_vad=10)

        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as temporary, patch("video_assistant.core.run_ffmpeg"):
            result = transcribe(VideoInfo("test.mp4", 20, 100, True), Path(temporary), Settings(),
                                threading.Event(), lambda *_: None, Model)
            self.assertIn("Sprachaktivität", result["segments"][0]["warnings"][0])
            self.assertEqual(len(result["reviews"]), 1)

    def test_prompt_treats_alternatives_as_uncertain_same_source(self):
        text = build_prompt(PromptPreferences())
        self.assertIn("keine unabhängigen", text)
        self.assertIn("nicht als zwei Ereignisse", text)
        self.assertIn("Screenshots beweisen nicht", text)
