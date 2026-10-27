# Fremdkomponenten

VideoWissens eigener Quellcode steht unter MIT (LICENSE). Die portable Windows-Version
enthält unveränderte Fremdkomponenten mit eigenen Lizenzen. Deren Lizenztexte liegen
unter third_party/licenses/ und gegebenenfalls zusätzlich in _internal/.

Wesentliche Komponenten:

| Komponente | Projekt / Quellcode | Lizenz |
|---|---|---|
| CPython | https://github.com/python/cpython | PSF |
| Tcl/Tk | https://www.tcl.tk/software/tcltk/ | Tcl/Tk |
| faster-whisper | https://github.com/SYSTRAN/faster-whisper | MIT |
| CTranslate2 | https://github.com/OpenNMT/CTranslate2 | MIT, eingebundene Laufzeiten separat |
| ONNX Runtime | https://github.com/microsoft/onnxruntime | MIT |
| Silero VAD | https://github.com/snakers4/silero-vad | MIT |
| OpenMP-Laufzeit | https://github.com/llvm/llvm-project/tree/main/openmp | Apache-2.0 mit LLVM-Ausnahme, ergänzende Hinweise siehe Lizenztext |
| Tokenizers / Hugging Face Hub | https://github.com/huggingface | Apache-2.0 |
| NumPy | https://github.com/numpy/numpy | BSD-3-Clause, eingebundene Bibliotheken separat |
| FFmpeg (separater Prozess) | https://github.com/FFmpeg/FFmpeg | LGPL-3.0-or-later für den ausgewählten Build |
| FFmpeg-Buildskripte | https://github.com/BtbN/FFmpeg-Builds | siehe zugehöriger Quellcode |
| PyInstaller-Bootloader | https://github.com/pyinstaller/pyinstaller | GPL mit Bootloader-Ausnahme |

Der separate FFmpeg-Build ist über tools/ffmpeg-lock.json auf eine unveränderliche
Release-URL und SHA-256 festgelegt. Er verwendet Shared Libraries und deaktiviert GPL-
und Nonfree-Komponenten. ffmpeg.exe und seine DLLs können durch kompatible eigene
Builds im Verzeichnis _internal/ffmpeg/ ersetzt werden. Keine Einschränkung der
gesetzlich bzw. lizenzrechtlich erlaubten Untersuchung oder Änderung dieser Bibliotheken.

third_party/ enthält verfügbare Lizenztexte, Versionsinventar und Quellenhinweise.
Quellcode und Buildanweisungen der Fremdprojekte unterliegen ihren jeweiligen Lizenzen.
Nicht mitgeliefert: Whisper-Modellgewichte. Diese werden ausschließlich auf Nutzerwunsch
von den in video_assistant/models.py benannten Anbietern bezogen.
NVIDIA-CUDA-/cuDNN-Laufzeiten werden ebenfalls nicht mitgeliefert; die optionale
GPU-Verarbeitung setzt eine passende separate Installation voraus.

Die portable Anwendung verwendet tools/runtime_pcm_audio.py für die von FFmpeg bereits
dekodierten Mono-WAV-Blöcke. Die beiden benötigten faster-whisper-Audiofunktionen werden
dabei durch den offenliegenden PCM-Adapter bereitgestellt. PyAV und dessen zusätzlicher
FFmpeg-/Codec-Build werden nicht in der EXE-Distribution mitgeliefert.
