param([string]$Python = "py")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
if ($Python -eq "py") {
    & $Python -3 -m venv .venv
} else {
    & $Python -m venv .venv
}
if ($LASTEXITCODE -ne 0) { throw "Python 3.10–3.13 mit pip und Tkinter installieren oder -Python mit dem vollständigen Python-Pfad angeben." }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Installation fehlgeschlagen. Internetverbindung und pip prüfen." }
& .\.venv\Scripts\python.exe -c "import tkinter, faster_whisper, imageio_ffmpeg; print('Installation erfolgreich. FFmpeg:', imageio_ffmpeg.get_ffmpeg_exe())"
if ($LASTEXITCODE -ne 0) { throw "Abhängigkeiten konnten nicht geladen werden." }
Write-Host "Bereit. Anwendung mit start.bat öffnen."

