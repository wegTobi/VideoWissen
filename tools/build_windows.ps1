param([string]$Python = '.\.venv\Scripts\python.exe')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& $Python tools/fetch_ffmpeg.py
if ($LASTEXITCODE -ne 0) { throw 'FFmpeg-Vorbereitung fehlgeschlagen.' }
& $Python -m PyInstaller --noconfirm --clean --distpath .build/dist --workpath .build/work tools/VideoWissen.spec
if ($LASTEXITCODE -ne 0) { throw 'Windows-Build fehlgeschlagen.' }
Write-Host 'Build erstellt: .build/dist/VideoWissen/VideoWissen.exe'
