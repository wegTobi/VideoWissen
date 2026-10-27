# Veröffentlichung auf GitHub

Der saubere Veröffentlichungsordner enthält VideoWissen.exe direkt im Wurzelverzeichnis
und die zugehörigen Dateien im Ordner _internal/. **Beides muss zusammen in denselben
Branch gepusht werden.** Dann enthält GitHubs Code → Download ZIP ebenfalls die EXE.
Eine nur bei Releases hochgeladene EXE wäre nicht im normalen Quellcode-ZIP enthalten.

Es wird bewusst ein Verzeichnis-Build verwendet: Keine einzelne Datei überschreitet
GitHubs 100-MiB-Grenze. Git LFS ist für diesen vorbereiteten Stand nicht erforderlich.
Nicht über den Browser einzeln hochladen: Dort gilt eine niedrigere Dateigrößengrenze.

## Erster Push

Vor dem ersten Commit unter GitHub → Settings → Emails die persönliche noreply-Adresse
nachsehen und bei Bedarf lokal mit `git config user.email DEINE_NOREPLY_ADRESSE` setzen.
Auch `git config user.name DEIN_ANZEIGENAME` bewusst wählen: Name und E-Mail werden
Teil öffentlicher Commits. Es wurde absichtlich noch kein Commit mit einer automatisch
übernommenen persönlichen Identität erstellt.

Im vorbereiteten, geprüften Ordner ein Terminal öffnen. Falls noch nicht initialisiert:

    git init -b main
    git add .
    git status
    git commit -m "Initial public release"

Ein neues leeres Repository auf GitHub anlegen. Dann dessen tatsächliche URL verwenden:

    git remote add origin DEINE_REPOSITORY_URL
    git push -u origin main

Keine bestehenden privaten Repository-Verläufe kopieren. Der vorbereitete Ordner
enthält nur ausgewählte Projektdateien und die portable Anwendung. Lokale Tests,
Aufnahmen, Transkripte, Modelle und persönliche Entwicklungsumgebungen fehlen.

## Aktualisieren

Nach Codeänderungen immer auch die EXE neu bauen und zusammen mit dem geänderten
Quellcode prüfen. Andernfalls würde Download ZIP eine veraltete EXE liefern.

Eine unveränderte offizielle Python-3.13-x64-Laufzeit verwenden. Die vorbereitete
EXE wird mit Python 3.13 gebaut; die Paketversionen sind in requirements-lock.txt fixiert.

    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements-build.txt
    powershell -File tools/build_windows.ps1

tools/fetch_ffmpeg.py lädt nur den festgelegten, per SHA-256 geprüften FFmpeg-Build.
tools/prepare_public.py erstellt aus dem Build einen neuen sauberen Ordner.
tools/audit_public.py prüft den vorgesehenen Veröffentlichungsordner.

Die Windows-Workflow-Datei kann auf GitHub manuell gestartet werden und baut bei
passenden Pull Requests. Sie lädt ein Build-Artefakt hoch, ändert jedoch keinen Branch
und veröffentlicht nichts automatisch. Für Download ZIP müssen die geprüften
Build-Dateien weiterhin bewusst in den Hauptbranch übernommen werden.

Vor dem Public-Schalten SHA256SUMS.txt und RELEASE_CHECKS.md beachten. Die EXE ist
nicht digital signiert; Sicherheitsfunktionen von Windows nicht abschalten.
