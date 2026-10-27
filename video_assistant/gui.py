"""Deutschsprachige Desktop-Oberfläche mit expliziten Downloads und ZIP-Ausgabe."""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .core import (Cancelled, ProcessingError, Settings, VideoInfo,
                   estimated_count, probe_video, process_video, timestamp)
from .hardware import benchmark_sample, duration_label, estimate_transcription, scan_hardware
from .models import (APP_ROOT, MODEL_REPOS, MODEL_ROOT, MODEL_SIZES, discover_models,
                     download_model, model_complete)
from .prompting import PURPOSES, SCREENSHOT_ROLES, PromptPreferences, build_prompt
from .paths import DATA_ROOT, DEFAULT_EXPORT


class Application:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("VideoWissen")
        root.geometry(f"980x{min(860, max(620, root.winfo_screenheight() - 100))}")
        root.minsize(780, 620)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.operation = None
        self.info: VideoInfo | None = None
        self.output: Path | None = None
        self.hardware = None
        self.available_models = {name: str(MODEL_ROOT / name) for name in MODEL_REPOS
                                 if model_complete(MODEL_ROOT / name)}
        self.calibrations = {}
        self.close_pending = False
        self.preview = None
        self.purpose = tk.StringVar(value=PURPOSES[0])
        self.screenshot_role = tk.StringVar(value=SCREENSHOT_ROLES[0])
        self.relevance = tk.DoubleVar(value=70)
        self.relevance_label = tk.StringVar(value="70 % ungefähr relevant")
        self.audience = tk.StringVar(value=PromptPreferences().audience)
        self.copy_status = tk.StringVar()
        self.video = tk.StringVar(value="Noch kein Video ausgewählt")
        self.details = tk.StringVar(value="Vorlesung, Schulung oder anderes Video auswählen.")
        self.destination = tk.StringVar(value=str(DEFAULT_EXPORT))
        self.rate = tk.StringVar(value="5")
        self.rate_label = tk.StringVar()
        self.estimate = tk.StringVar(value="Voraussichtliche Bilder: —")
        self.model = tk.StringVar(value="small")
        self.model_status = tk.StringVar()
        self.hardware_text = tk.StringVar(value="Hardware wird lokal ermittelt …")
        self.runtime_text = tk.StringVar()
        self.language = tk.StringVar(value="Deutsch")
        self.device = tk.StringVar(value="CPU (empfohlen)")
        self.status = tk.StringVar(value="Bereit")
        self.percent = tk.DoubleVar(value=0)
        self.controls = []
        self._layout()
        self.rate.trace_add("write", lambda *_: self._estimate())
        self.model.trace_add("write", lambda *_: self._update_model())
        self.device.trace_add("write", lambda *_: self._update_model())
        self.language.trace_add("write", lambda *_: self._runtime())
        for var in (self.purpose, self.screenshot_role, self.relevance, self.audience):
            var.trace_add("write", lambda *_: self._refresh_prompt())
        self._refresh_model_labels()
        self._estimate()
        root.protocol("WM_DELETE_WINDOW", self._close)
        root.after(100, self._poll)
        self.scan_after = root.after(150, self._scan)

    def _section(self, parent, title):
        section = ttk.LabelFrame(parent, text=title, padding=12)
        section.pack(fill="x", pady=(0, 12))
        return section

    def _layout(self):
        menu = tk.Menu(self.root)
        self.extras_menu = tk.Menu(menu, tearoff=False)
        self.extras_menu.add_command(label="Eigenes Whisper-Modell wählen …", command=self._choose_model)
        self.extras_menu.add_command(label="Hardware erneut prüfen", command=self._scan)
        menu.add_cascade(label="Extras", menu=self.extras_menu)
        self.root.configure(menu=menu)
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 21, "bold"))
        style.configure("Subtitle.TLabel", foreground="#526276")
        scroll = ttk.Frame(self.root)
        scroll.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(scroll, highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        body = ttk.Frame(self.canvas, padding=(24, 20, 24, 12))
        content = self.canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(content, width=event.width))
        self.root.bind_all("<MouseWheel>", self._scroll)
        ttk.Label(body, text="VideoWissen", style="Title.TLabel").pack(anchor="w")
        ttk.Label(body, text="Transkript und Screenshots – zusammen in einer ZIP-Datei für deine KI.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(4, 18))

        source = self._section(body, "1 · Video")
        source.columnconfigure(0, weight=1)
        ttk.Label(source, textvariable=self.video, wraplength=650).grid(row=0, column=0, sticky="w")
        self._button(source, "Video auswählen …", self._choose_video).grid(row=0, column=1, padx=(12, 0))
        ttk.Label(source, textvariable=self.details, style="Subtitle.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        options = self._section(body, "2 · Verarbeitung")
        options.columnconfigure(1, weight=1)
        ttk.Label(options, text="Screenshots pro Minute").grid(row=0, column=0, sticky="w")
        slider_row = ttk.Frame(options)
        slider_row.grid(row=0, column=1, sticky="ew", padx=(15, 0))
        slider_row.columnconfigure(1, weight=1)
        ttk.Label(slider_row, text="1").grid(row=0, column=0)
        self.rate_slider = ttk.Scale(slider_row, from_=1, to=60, variable=self.rate,
                                     command=lambda value: self.rate.set(str(round(float(value)))))
        self.rate_slider.grid(row=0, column=1, sticky="ew", padx=8)
        self.controls.append(self.rate_slider)
        ttk.Label(slider_row, text="60").grid(row=0, column=2)
        ttk.Label(slider_row, textvariable=self.rate_label, width=12).grid(row=0, column=3, padx=(12, 0))
        ttk.Label(options, textvariable=self.estimate, style="Subtitle.TLabel").grid(
            row=1, column=1, sticky="w", padx=(15, 0), pady=(2, 10))
        ttk.Label(options, text="Whisper-Modell").grid(row=2, column=0, sticky="w", pady=5)
        model_row = ttk.Frame(options)
        model_row.grid(row=2, column=1, sticky="ew", padx=(15, 0))
        model_row.columnconfigure(0, weight=1)
        self.model_combo = self._combo(model_row, self.model, tuple(MODEL_REPOS))
        self.model_combo.grid(row=0, column=0, sticky="ew")
        download_row = ttk.Frame(options)
        download_row.grid(row=3, column=1, sticky="ew", padx=(15, 0), pady=(2, 8))
        ttk.Label(download_row, textvariable=self.model_status, wraplength=430,
                  style="Subtitle.TLabel").pack(side="left", fill="x", expand=True)
        self.download_button = ttk.Button(download_row, text="Modell herunterladen", command=self._download)
        self.download_button.pack(side="right", padx=(8, 0))
        ttk.Label(options, text="Sprache").grid(row=4, column=0, sticky="w", pady=5)
        self._combo(options, self.language, ("Deutsch", "Automatisch", "Englisch")).grid(
            row=4, column=1, sticky="ew", padx=(15, 0))
        ttk.Label(options, text="Berechnung").grid(row=5, column=0, sticky="w", pady=5)
        self._combo(options, self.device, ("CPU (empfohlen)", "NVIDIA GPU (CUDA)")).grid(
            row=5, column=1, sticky="ew", padx=(15, 0))
        ttk.Separator(options).grid(row=6, column=0, columnspan=2, sticky="ew", pady=10)
        ttk.Label(options, textvariable=self.hardware_text, wraplength=790,
                  style="Subtitle.TLabel").grid(row=7, column=0, columnspan=2, sticky="w")
        ttk.Label(options, textvariable=self.runtime_text, wraplength=790).grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(8, 5))
        estimate_actions = ttk.Frame(options)
        estimate_actions.grid(row=9, column=0, columnspan=2, sticky="w")
        self.benchmark_button = ttk.Button(estimate_actions, text="Zeitschätzung mit Sprachprobe verfeinern", command=self._benchmark)
        self.benchmark_button.pack(side="left")
        ttk.Label(options, text="Video und Ton bleiben auf deinem Rechner. Modelle werden nur auf Klick heruntergeladen.",
                  style="Subtitle.TLabel", wraplength=790).grid(row=10, column=0, columnspan=2, sticky="w", pady=(8, 0))

        target = self._section(body, "3 · Ausgabe")
        target.columnconfigure(0, weight=1)
        entry = ttk.Entry(target, textvariable=self.destination)
        entry.grid(row=0, column=0, sticky="ew")
        self.controls.append(entry)
        self._button(target, "Zielordner …", self._choose_destination).grid(row=0, column=1, padx=(8, 0))
        ttk.Label(target, text="Eine ZIP-Datei mit transcript.md und screenshots/.",
                  style="Subtitle.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        prompt = self._section(body, "4 · KI-Auswertung anpassen")
        prompt.columnconfigure(1, weight=1)
        ttk.Label(prompt, text="Was soll die KI erstellen?").grid(row=0, column=0, sticky="w", pady=5)
        self._combo(prompt, self.purpose, PURPOSES).grid(row=0, column=1, sticky="ew", padx=(15, 0))
        ttk.Label(prompt, text="Welche Rolle haben die Bilder?").grid(row=1, column=0, sticky="w", pady=5)
        self._combo(prompt, self.screenshot_role, SCREENSHOT_ROLES).grid(row=1, column=1, sticky="ew", padx=(15, 0))
        ttk.Label(prompt, text="Wie viel Inhalt ist wichtig?").grid(row=2, column=0, sticky="w", pady=5)
        slider_row = ttk.Frame(prompt)
        slider_row.grid(row=2, column=1, sticky="ew", padx=(15, 0))
        slider_row.columnconfigure(1, weight=1)
        ttk.Label(slider_row, text="0 %").grid(row=0, column=0)
        slider = ttk.Scale(slider_row, from_=0, to=100, variable=self.relevance,
                           command=lambda value: self.relevance.set(round(float(value))))
        slider.grid(row=0, column=1, sticky="ew", padx=8)
        self.controls.append(slider)
        ttk.Label(slider_row, text="100 %").grid(row=0, column=2)
        ttk.Label(prompt, textvariable=self.relevance_label, style="Subtitle.TLabel").grid(
            row=3, column=1, sticky="w", padx=(15, 0))
        ttk.Label(prompt, text="Für wen ist die Auswertung?").grid(row=4, column=0, sticky="w", pady=5)
        audience = ttk.Entry(prompt, textvariable=self.audience)
        audience.grid(row=4, column=1, sticky="ew", padx=(15, 0))
        self.controls.append(audience)
        ttk.Label(prompt, text="Zusatzwünsche / Schwerpunkt").grid(row=5, column=0, sticky="nw", pady=5)
        self.notes = tk.Text(prompt, height=3, wrap="word", font=("Segoe UI", 10))
        self.notes.grid(row=5, column=1, sticky="ew", padx=(15, 0), pady=5)
        self.controls.append(self.notes)
        self.notes.bind("<<Modified>>", self._notes_changed)
        self._button(prompt, "Prompt ansehen und kopieren …", self._show_preview).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(prompt, text="Nur zum Kopieren. Der Prompt wird nicht als Datei gespeichert und ist nicht in der ZIP.",
                  style="Subtitle.TLabel", wraplength=790).grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 0))

        footer = ttk.Frame(self.root, padding=(24, 12))
        footer.pack(fill="x")
        actions = ttk.Frame(footer)
        actions.pack(fill="x", pady=(0, 10))
        self.start = ttk.Button(actions, text="Aufbereitung starten", command=self._start, state="disabled")
        self.start.pack(side="left")
        self.abort = ttk.Button(actions, text="Abbrechen", command=self._abort, state="disabled")
        self.abort.pack(side="left", padx=8)
        self.open_button = ttk.Button(actions, text="ZIP anzeigen", command=self._open_output, state="disabled")
        self.open_button.pack(side="right")
        self.progressbar = ttk.Progressbar(footer, variable=self.percent, maximum=100)
        self.progressbar.pack(fill="x")
        ttk.Label(footer, textvariable=self.status, wraplength=850).pack(anchor="w", pady=(5, 4))
        self.show_log = tk.BooleanVar(value=False)
        ttk.Checkbutton(footer, text="Verarbeitungsprotokoll anzeigen", variable=self.show_log,
                        command=self._toggle_log).pack(anchor="w")
        self.log_frame = ttk.LabelFrame(footer, text="Hinweise und Speicherorte", padding=8)
        self.log = tk.Text(self.log_frame, height=4, wrap="word", font=("Segoe UI", 9),
                           relief="flat", padx=8, pady=6)
        self.log.insert("1.0", "Noch keine Verarbeitung gestartet. Hier erscheinen Hinweise und Speicherorte.\n")
        self.log.configure(state="disabled")
        self.has_log_entries = False
        log_scroll = ttk.Scrollbar(self.log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)

    def _toggle_log(self):
        if self.show_log.get():
            self.log_frame.pack(fill="x", pady=(6, 0))
        else:
            self.log_frame.pack_forget()

    def _scroll(self, event):
        if event.widget.winfo_toplevel() == self.root and event.widget.winfo_class() not in ("TCombobox", "Text"):
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=command)
        self.controls.append(button)
        return button

    def _combo(self, parent, variable, values):
        box = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly")
        box._idle_state = "readonly"
        self.controls.append(box)
        return box

    def _selected_model(self):
        value = self.model.get()
        name = value.split(" · ", 1)[0]
        return name if name in MODEL_REPOS else value

    def _model_path(self):
        selected = self._selected_model()
        if selected in self.available_models:
            return self.available_models[selected]
        return selected if model_complete(Path(selected)) else None

    def _refresh_model_labels(self):
        selected = self._selected_model()
        labels = {name: f"{name} · {'vorhanden' if name in self.available_models else 'Download nötig'}" for name in MODEL_REPOS}
        self.model_combo.configure(values=tuple(labels.values()) + ((selected,) if selected not in labels else ()))
        self.model.set(labels.get(selected, selected))

    def _update_model(self):
        name, path = self._selected_model(), self._model_path()
        if path:
            self.model_status.set("Bereit · Modell auf deinem Rechner vorhanden")
        elif name in MODEL_REPOS:
            self.model_status.set(f"Noch nicht installiert · Download {MODEL_SIZES[name]}")
        else:
            self.model_status.set("Kein vollständiges lokales CTranslate2-Modell gefunden.")
        self.download_button.configure(state="normal" if not self.busy and name in MODEL_REPOS and not path else "disabled")
        usable_device = not self.device.get().startswith("NVIDIA") or bool(self.hardware and self.hardware.cuda_available)
        ready = bool(not self.busy and self.info and self.info.has_audio and path and usable_device)
        self.start.configure(state="normal" if ready else "disabled")
        self.benchmark_button.configure(state="normal" if ready else "disabled")
        self._runtime()

    def _runtime(self):
        if not self.info:
            self.runtime_text.set("Videodatei wählen, um die Transkriptionsdauer zu schätzen.")
            return
        if not self.hardware:
            self.runtime_text.set("Zeitschätzung nach dem lokalen Hardware-Scan verfügbar.")
            return
        name = self._selected_model()
        device = "cpu" if self.device.get().startswith("CPU") else "cuda"
        measured = self.calibrations.get((name, device, self.language.get()))
        low, high, warning = estimate_transcription(self.info.duration, name, device, self.hardware, measured)
        if high == 0:
            self.runtime_text.set(warning)
        else:
            origin = "lokale Sprachprobe" if measured is not None else "grobe Hardware-Schätzung"
            self.runtime_text.set(f"Transkription voraussichtlich {duration_label(low)} bis {duration_label(high)}\n"
                                  f"{origin[0].upper() + origin[1:]} · ohne Download und Export. Tatsächliche Dauer kann abweichen.{warning}")

    def _prompt_text(self):
        return build_prompt(PromptPreferences(self.purpose.get(), self.screenshot_role.get(),
                            round(self.relevance.get()), self.audience.get(), self.notes.get("1.0", "end-1c")))

    def _notes_changed(self, _):
        if self.notes.edit_modified():
            self.notes.edit_modified(False)
            self._refresh_prompt()

    def _refresh_prompt(self):
        self.relevance_label.set(f"{round(self.relevance.get())} % ungefähr relevant")
        self.copy_status.set("")
        if self.preview and self.preview.winfo_exists():
            try:
                text = self._prompt_text()
            except ValueError as exc:
                text = str(exc)
            self.preview_text.configure(state="normal")
            self.preview_text.delete("1.0", "end")
            self.preview_text.insert("1.0", text)
            self.preview_text.configure(state="disabled")

    def _copy_prompt(self):
        try:
            text = self._prompt_text()
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.copy_status.set("In die Zwischenablage kopiert.")
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("Prompt kopieren", str(exc))

    def _show_preview(self):
        if not self.preview or not self.preview.winfo_exists():
            self.preview = tk.Toplevel(self.root)
            self.preview.title("VideoWissen · Prompt zum Kopieren")
            self.preview.geometry("860x650")
            ttk.Label(self.preview, text="Kopiere diesen Prompt in deine KI. Er wird nicht mit exportiert.",
                      padding=12).pack(anchor="w")
            frame = ttk.Frame(self.preview)
            frame.pack(fill="both", expand=True, padx=12)
            self.preview_text = tk.Text(frame, wrap="word", font=("Segoe UI", 10), padx=12, pady=12)
            bar = ttk.Scrollbar(frame, command=self.preview_text.yview)
            self.preview_text.configure(yscrollcommand=bar.set)
            bar.pack(side="right", fill="y")
            self.preview_text.pack(fill="both", expand=True)
            actions = ttk.Frame(self.preview, padding=12)
            actions.pack(fill="x")
            ttk.Button(actions, text="Prompt kopieren", command=self._copy_prompt).pack(side="left")
            ttk.Label(actions, textvariable=self.copy_status).pack(side="left", padx=12)
        self._refresh_prompt()
        self.preview.lift()

    def _log(self, text):
        self.log.configure(state="normal")
        if not self.has_log_entries:
            self.log.delete("1.0", "end")
            self.has_log_entries = True
        self.log.insert("end", text + "\n")
        if int(self.log.index("end-1c").split(".")[0]) > 200:
            self.log.delete("1.0", "30.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, value):
        self.busy = value
        for index in (0, 1):
            self.extras_menu.entryconfigure(index, state="disabled" if value else "normal")
        for widget in self.controls:
            widget.configure(state="disabled" if value else getattr(widget, "_idle_state", "normal"))
        self.abort.configure(state="normal" if value else "disabled")
        self.open_button.configure(state="normal" if self.output and not value else "disabled")
        self._update_model()

    def _background(self, operation, kind):
        self.cancel = threading.Event()
        self.operation = kind
        self._set_busy(True)
        if kind in ("download", "benchmark"):
            self.progressbar.stop()
            self.progressbar.configure(mode="determinate")
            self.percent.set(0)
        elif kind in ("scan", "probe"):
            self.progressbar.configure(mode="indeterminate")
            self.progressbar.start(15)

        def work():
            try:
                self.events.put((kind, operation()))
            except Exception as exc:
                self.events.put(("error", exc))
            finally:
                self.events.put(("idle", None))

        threading.Thread(target=work, daemon=True).start()

    def _scan(self):
        if self.busy:
            self.scan_after = self.root.after(500, self._scan)
            return
        self.status.set("Hardware und lokale Modelle prüfen …")
        self._background(lambda: (scan_hardware(), discover_models()), "scan")

    def _download(self):
        name = self._selected_model()
        self.status.set(f"{name} wird heruntergeladen …")
        self._background(lambda: (name, download_model(name, self.cancel, self._progress)), "download")

    def _benchmark(self):
        info, model_path = self.info, self._model_path()
        device = "cpu" if self.device.get().startswith("CPU") else "cuda"
        key = (self._selected_model(), device, self.language.get())
        language = {"Deutsch": "de", "Englisch": "en", "Automatisch": None}[self.language.get()]
        self.status.set("Lokale Sprachprobe vorbereiten …")
        self._background(lambda: (key, benchmark_sample(info, model_path, device, self.cancel,
                                                       self._progress, DATA_ROOT, language)), "benchmark")

    def _choose_video(self):
        name = filedialog.askopenfilename(title="Video auswählen", filetypes=[
            ("Videodateien", "*.mkv *.mp4 *.mov *.avi *.webm *.flv *.m4v *.ts"), ("Alle Dateien", "*.*")])
        if name:
            self.info = None
            self.calibrations.clear()
            self.video.set(name)
            self.details.set("Videodatei wird geprüft …")
            self.status.set("Dauer und Tonspur prüfen …")
            self._estimate()
            self._background(lambda: probe_video(Path(name), self.cancel), "probe")

    def _choose_model(self):
        name = filedialog.askdirectory(title="Lokales CTranslate2-Whisper-Modell")
        if name:
            self.model.set(name)
            self._refresh_model_labels()

    def _choose_destination(self):
        name = filedialog.askdirectory(title="Ausgabeordner wählen")
        if name:
            self.destination.set(name)

    def _estimate(self):
        try:
            rate = round(float(self.rate.get()))
            Settings(rate=rate).validate()
            self.rate_label.set(f"{rate} / Min.")
            count = estimated_count(self.info.duration, rate) if self.info else None
            self.estimate.set(f"Voraussichtlich {count:,} Bilder · alle {60 / rate:g} Sekunden".replace(",", ".")
                              if count is not None else "Voraussichtliche Bilder: —")
        except (ValueError, ProcessingError):
            self.estimate.set("Bitte 1 bis 60 Bilder pro Minute wählen.")
        self._runtime()

    def _start(self):
        try:
            model_path = self._model_path()
            if not model_path:
                raise ProcessingError("Bitte das ausgewählte Modell zuerst über 'Modell herunterladen' installieren.")
            settings = Settings(rate=round(float(self.rate.get())), model=model_path,
                                language={"Deutsch": "de", "Englisch": "en", "Automatisch": None}[self.language.get()],
                                device="cpu" if self.device.get().startswith("CPU") else "cuda")
            settings.validate()
            if not self.destination.get().strip():
                raise ProcessingError("Bitte einen Ausgabeordner wählen.")
            destination = Path(self.destination.get()).expanduser().resolve()
        except (ValueError, ProcessingError) as exc:
            messagebox.showerror("Einstellungen prüfen", str(exc))
            return
        self.output = None
        self.percent.set(0)
        self._log("Verarbeitung gestartet. Das Modell ist bereits lokal vorhanden.")
        info = self.info
        self._background(lambda: process_video(info, destination, settings, self.cancel, self._progress), "done")

    def _progress(self, value, message):
        self.events.put(("progress", (value, message)))

    def _abort(self):
        self.cancel.set()
        self.abort.configure(state="disabled")
        self.status.set("Abbruch angefordert. Warten auf aktuellen Modellaufruf / Download …")
        self._log("Abbruch angefordert; laufende Modell-/Netzwerkaufrufe können erst danach beendet werden.")

    def _open_output(self):
        if self.output:
            try:
                if os.name == "nt":
                    subprocess.Popen(["explorer.exe", "/select,", str(self.output)])
                else:
                    subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(self.output.parent)])
            except OSError as exc:
                messagebox.showerror("ZIP anzeigen", str(exc))

    def _poll(self):
        for _ in range(100):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                if self.operation in ("done", "download", "benchmark"):
                    self.percent.set(value[0])
                if self.operation == "download" and not self.cancel.is_set():
                    self.model_status.set(value[1])
                if not self.cancel.is_set():
                    self.status.set(value[1])
                if value[0] == 2:
                    self._log(value[1])
            elif kind == "scan":
                self.hardware, found = value
                self.available_models = found
                self.hardware_text.set(self.hardware.description())
                self._refresh_model_labels()
                self.status.set("Hardware und lokale Modelle geprüft.")
            elif kind == "download":
                name, path = value
                self.available_models[name] = path
                self._refresh_model_labels()
                self.percent.set(100)
                self.status.set(f"{name} ist heruntergeladen und lokal verfügbar · 100 %")
                self._log(f"Modell gespeichert: {path}")
            elif kind == "benchmark":
                key, ratio = value
                self.calibrations[key] = ratio
                self._runtime()
                self.percent.set(100)
                self.status.set("Sprachprobe · 100 % · Zeitschätzung aktualisiert. Die Probe kann vom übrigen Video abweichen.")
            elif kind == "probe":
                self.info = value
                audio = "Tonspur vorhanden" if value.has_audio else "Keine Tonspur gefunden"
                self.details.set(f"Dauer {timestamp(value.duration)} · {value.size_bytes / 1024**3:.2f} GiB · {audio}")
                self.status.set("Bereit" if value.has_audio else "Video ohne Tonspur kann nicht transkribiert werden.")
                self._estimate()
            elif kind == "done":
                self.output = value
                self.status.set("Fertig. Die ZIP-Datei enthält das Transkript und alle Screenshots.")
                self._log(f"Gespeichert: {value}")
                if not self.close_pending:
                    messagebox.showinfo("Aufbereitung abgeschlossen", f"ZIP-Datei:\n{value}")
            elif kind == "error":
                self.status.set("Abgebrochen" if isinstance(value, Cancelled) else "Vorgang fehlgeschlagen")
                self._log(str(value))
                if not isinstance(value, Cancelled) and not self.close_pending:
                    messagebox.showerror("Vorgang fehlgeschlagen", str(value))
            elif kind == "idle":
                self.progressbar.stop()
                self.progressbar.configure(mode="determinate")
                if self.operation not in ("done", "download", "benchmark"):
                    self.percent.set(0)
                self.operation = None
                self._set_busy(False)
                if self.close_pending:
                    self.root.destroy()
                    return
        self.root.after(100, self._poll)

    def _close(self):
        self.root.after_cancel(self.scan_after)
        if self.busy:
            self.close_pending = True
            self._abort()
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    Application(root)
    root.mainloop()
