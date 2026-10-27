import tkinter as tk
import unittest
from unittest.mock import patch

from video_assistant.core import VideoInfo
from video_assistant.gui import Application
from video_assistant.hardware import HardwareInfo
from video_assistant.prompting import PURPOSES, SCREENSHOT_ROLES


class GuiSmokeTest(unittest.TestCase):
    def test_export_uses_prompt_settings_captured_at_start(self):
        root = tk.Tk()
        root.withdraw()
        app = Application(root)
        try:
            root.after_cancel(app.scan_after)
            app.info = VideoInfo("example.mp4", 120, 123, True)
            app.relevance_unknown.set(True)
            app.notes.insert("1.0", "Für die Prüfung aufbereiten")
            expected = app._prompt_text()
            with patch.object(app, "_model_path", return_value="test-model"), \
                 patch.object(app, "_background") as background, \
                 patch("video_assistant.gui.process_video") as process:
                app._start()
                operation, kind = background.call_args.args
                self.assertEqual(kind, "done")
                app.notes.insert("end", " Spätere Änderung")
                operation()
                self.assertEqual(process.call_args.kwargs["prompt_text"], expected)
                self.assertNotIn("Spätere Änderung", process.call_args.kwargs["prompt_text"])
        finally:
            root.destroy()

    def test_unknown_relevance_disables_slider_and_omits_percentage_from_prompt(self):
        root = tk.Tk()
        root.withdraw()
        app = Application(root)
        try:
            root.after_cancel(app.scan_after)
            app.relevance.set(23)
            app._show_preview()
            app.relevance_unknown.set(True)
            self.assertTrue(app.relevance_slider.instate(["disabled"]))
            self.assertEqual(app.relevance_label.get(), "Keine Einschätzung")
            text = app.preview_text.get("1.0", "end-1c")
            self.assertIn("Es gibt keine Prozentvorgabe", text)
            self.assertNotIn("%", text)
            self.assertNotIn("None", text)
            with patch.object(root, "clipboard_clear"), patch.object(root, "clipboard_append") as append:
                app._copy_prompt()
                append.assert_called_once_with(text)
            app._set_busy(True)
            app._set_busy(False)
            self.assertTrue(app.relevance_slider.instate(["disabled"]))
            app.relevance_unknown.set(False)
            self.assertTrue(app.relevance_slider.instate(["!disabled"]))
            self.assertEqual(app.relevance.get(), 23)
            self.assertIn("23 %", app.preview_text.get("1.0", "end-1c"))
        finally:
            root.destroy()

    def test_benchmark_shows_percentage_and_keeps_completed_progress(self):
        root = tk.Tk()
        root.withdraw()
        app = Application(root)
        try:
            root.after_cancel(app.scan_after)
            with patch("video_assistant.gui.threading.Thread"):
                app._background(lambda: None, "benchmark")
            self.assertEqual(str(app.progressbar["mode"]), "determinate")
            self.assertEqual(app.percent.get(), 0)
            app._progress(46, "Sprachprobe · 46 % · lokal transkribieren …")
            app._poll()
            self.assertEqual(app.percent.get(), 46)
            self.assertIn("46 %", app.status.get())
            app.events.put(("benchmark", (("test",), .2)))
            app.events.put(("idle", None))
            app._poll()
            self.assertEqual(app.percent.get(), 100)
            self.assertIn("100 %", app.status.get())
        finally:
            root.destroy()

    def test_download_shows_percentage_and_determinate_bar(self):
        root = tk.Tk()
        root.withdraw()
        app = Application(root)
        try:
            root.after_cancel(app.scan_after)
            with patch("video_assistant.gui.threading.Thread"):
                app._background(lambda: None, "download")
            self.assertEqual(str(app.progressbar["mode"]), "determinate")
            self.assertEqual(app.percent.get(), 0)
            app._progress(45, "tiny herunterladen · 45 %")
            app._poll()
            self.assertEqual(app.percent.get(), 45)
            self.assertIn("45 %", app.model_status.get())
            self.assertIn("45 %", app.status.get())
            app.events.put(("download", ("tiny", "test-model")))
            app.events.put(("idle", None))
            app._poll()
            self.assertEqual(app.percent.get(), 100)
            self.assertIn("100 %", app.status.get())
        finally:
            root.destroy()

    def test_initial_state_and_estimate(self):
        root = tk.Tk()
        root.withdraw()
        try:
            app = Application(root)
            root.update_idletasks()
            self.assertEqual(str(app.start["state"]), "disabled")
            self.assertFalse(hasattr(app, "zip_enabled"))
            self.assertFalse(hasattr(app, "offline"))
            self.assertEqual(float(app.rate_slider["from"]), 1)
            self.assertEqual(float(app.rate_slider["to"]), 60)
            app.info = VideoInfo("example.mp4", 7200, 123, True)
            app.hardware = HardwareInfo("Test CPU", 8, 16, 3600)
            app.available_models["small"] = "local-test-model"
            app.rate.set("20")
            self.assertIn("2.400", app.estimate.get())
            app._set_busy(False)
            self.assertEqual(str(app.start["state"]), "normal")
            self.assertIn("Hardware-Schätzung", app.runtime_text.get())
            app.model.set("turbo · Download nötig")
            self.assertEqual(str(app.start["state"]), "disabled")
            self.assertEqual(str(app.download_button["state"]), "normal")
            self.assertIn("Noch nicht installiert", app.model_status.get())
            app.model.set("small · vorhanden")
            app._show_preview()
            app.purpose.set(PURPOSES[3])
            app.screenshot_role.set(SCREENSHOT_ROLES[1])
            app.relevance.set(20)
            app.audience.set("Studierende")
            app.notes.insert("1.0", "Diagramme erklären")
            app._refresh_prompt()
            expected = app.preview_text.get("1.0", "end-1c")
            self.assertIn("20 %", expected)
            self.assertIn("Lernzettel", expected)
            self.assertIn("Studierende", expected)
            self.assertIn("Diagramme erklären", expected)
            self.assertIn("ausschließlich der zeitlichen Orientierung", expected)
            self.assertIn("transcript.md", expected)
            self.assertNotIn("timeline.json", expected)
            with patch.object(root, "clipboard_clear") as clear, patch.object(root, "clipboard_append") as append:
                app._copy_prompt()
                clear.assert_called_once()
                append.assert_called_once_with(expected)
            self.assertIn("kopiert", app.copy_status.get())
            app.preview.destroy()
            app._show_preview()
            self.assertEqual(app.preview_text.get("1.0", "end-1c"), expected)
            app.device.set("NVIDIA GPU (CUDA)")
            self.assertEqual(str(app.start["state"]), "disabled")
            self.assertIn("CUDA ist nicht verfügbar", app.runtime_text.get())
            app.device.set("CPU (empfohlen)")
            app._set_busy(True)
            self.assertEqual(str(app.start["state"]), "disabled")
            app._set_busy(False)
        finally:
            root.after_cancel(app.scan_after)
            root.destroy()
