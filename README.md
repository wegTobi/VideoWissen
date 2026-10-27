# VideoWissen

VideoWissen erstellt aus Vorlesungen, Schulungen und anderen lokalen Videos ein
Transkript mit Zeitstempeln und regelmäßige Screenshots. Die deutsche Desktop-App
transkribiert mit faster-whisper auf deinem Rechner, ohne Cloud-API.

## Windows: direkt starten

Im veröffentlichten Repository: **Code → Download ZIP**, das gesamte Archiv entpacken
und **VideoWissen.exe** im entpackten Ordner doppelklicken. Python und FFmpeg sind
bereits mitgeliefert. Der Ordner **_internal/** muss neben der EXE bleiben; die EXE
nicht einzeln herauskopieren und nicht direkt aus der ZIP starten.

Die portable Version ist für **Windows 10/11 x64** gedacht. CPU-Verarbeitung benötigt
keine NVIDIA-GPU. Internet wird nur für den ausdrücklich gestarteten ersten
Modelldownload benötigt. Danach ist lokale Offline-Verarbeitung möglich. GPU ist
optional und benötigt passende NVIDIA-/CUDA-Laufzeitbibliotheken.

Modelle und temporäre Sprachproben der EXE liegen unter **%LOCALAPPDATA%/VideoWissen/**.
Der Standard-Zielordner für Exporte ist **Dokumente/VideoWissen/** und kann geändert
werden. Standardmäßig landen persönliche Laufzeitdaten außerhalb des App-Ordners.

Die EXE ist nicht digital signiert. Windows kann die unbekannte Herkunft melden.
Herkunft und SHA256SUMS.txt prüfen; Sicherheitseinstellungen nicht abschalten.

## Quellcode ausführen / entwickeln

1. Python **3.10 bis 3.13, 64 Bit**, mit pip, Tcl/Tk und Python Launcher installieren:
   https://www.python.org/downloads/windows/
2. PowerShell im entpackten Projektordner öffnen:

       powershell -ExecutionPolicy Bypass -File .\install.ps1

   Ein bestimmter Interpreter lässt sich mit dem Parameter -Python angeben.
3. Zum Starten **start.bat** doppelklicken.

FFmpeg wird über imageio-ffmpeg mitinstalliert. Ein FFmpeg im PATH hat Vorrang;
FFMPEG_BINARY erlaubt einen eigenen vollständigen Pfad. Mindestens FFmpeg 5 wird
benötigt, ein separates ffprobe nicht. Getestete Paketversionen: requirements-lock.txt.

## Verwendung

1. **Video auswählen.** Dauer, Dateigröße und Tonspur werden angezeigt.
2. **Verarbeitung einstellen.** Der Screenshot-Slider reicht von 1 bis 60 Bildern pro
   Minute; die voraussichtliche Anzahl erscheint vor dem Start. Sprache: Deutsch,
   Automatisch oder Englisch. Berechnung: CPU oder NVIDIA-GPU.
3. **Modell bereitstellen.** Das Dropdown zeigt vorhandene und fehlende Modelle.
   Fehlende Modelle ausdrücklich über **Modell herunterladen** installieren. Beim
   Verarbeitungsstart wird niemals automatisch ein Modell heruntergeladen. Eigene
   CTranslate2-Modelle: **Extras → Eigenes Whisper-Modell wählen**.
4. **Zielordner wählen** und **Aufbereitung starten**.
5. **ZIP anzeigen** zeigt die fertige Datei im Explorer.
   Unter der Statusmeldung lässt sich bei Bedarf **Verarbeitungsprotokoll anzeigen**
   einschalten. Dort stehen Hinweise, Speicherorte und Fehlermeldungen. Das Protokoll
   ist standardmäßig eingeklappt und wird nicht exportiert.
6. Unter **KI-Auswertung anpassen** Ausgabeziel, Rolle der Bilder, relevanten
   Inhaltsanteil, Zielgruppe und Zusatzwünsche wählen. **Prompt ansehen und kopieren**
   öffnet den generierten Prompt in einem separaten Fenster. Dort kopiert **Prompt
   kopieren** den Text in die Zwischenablage. Den Prompt anschließend manuell in
   deiner KI einfügen. Er wird ausschließlich im Arbeitsspeicher gehalten und weder
   als Datei gespeichert noch in das ZIP aufgenommen.

Installation und Modelldownload brauchen Internet. Danach funktioniert die Verarbeitung
auch offline. Videos und Ton werden nicht hochgeladen. Modelle liegen unter models/;
vorhandene vollständige Hugging-Face-Caches werden ebenfalls erkannt.

## Export: genau eine ZIP-Datei

Im Zielordner entsteht ausschließlich die fertige ZIP-Datei:

    Aufnahme_20261027_120000.zip
      transcript.md
      screenshots/
        000001_00-00-00.000.jpg
        000002_00-00-12.000.jpg
        ...

Das Archiv enthält **nur das lesbare Transkript und die JPEG-Screenshots**.
Keine Prompts, KI-Anweisungen, README, JSON-Metadaten oder Originalvideos.
Transkript und Bilddateinamen tragen Zeitstempel ab Videobeginn. Prompts werden
manuell bei der späteren KI eingegeben.

Arbeitsdateien liegen vorübergehend im Zielordner und werden bei regulärem Abschluss,
Fehler und Abbruch entfernt. Eine ZIP wird erst vollständig veröffentlicht.
Bestehende ZIPs werden nicht überschrieben. Bei Fehler oder Abbruch bleibt kein neuer
Teil-Export. Nach einem Prozessabsturz können temporäre Arbeitsdateien verbleiben.
Ältere Exporte werden nicht verändert oder gelöscht.

## Hardware und Dauer

Beim Start werden CPU, Kerne, RAM und gegebenenfalls NVIDIA-GPU/VRAM/CUDA lokal geprüft.
**Extras → Hardware erneut prüfen** wiederholt den Scan. Die Zeitspanne berücksichtigt
Videolänge, Modell und Hardware. Sie betrifft die Transkription ohne Download und Export
und ist eine grobe Heuristik, keine garantierte Laufzeit.

**Zeitschätzung mit Sprachprobe verfeinern** verarbeitet bis zu 30 Sekunden aus der
Videomitte. Das Modell muss bereits lokal vorliegen. Bei zu wenig Sprache bleibt die
Hardware-Schätzung aktiv. Die Probe kann vom übrigen Video abweichen und gilt nur für
das aktuelle Video, Modell, Gerät und die Sprache in dieser Sitzung.

CPU/INT8 benötigt kein CUDA. Die GPU-Option erfordert passende NVIDIA-/CUDA-/cuDNN-
Bibliotheken. GPU-Erkennung allein garantiert deren Kompatibilität nicht.

## Lange Videos und Grenzen

- FFmpeg dekodiert fortlaufend; das gesamte Video wird nicht in den RAM geladen.
- Audio wird in fünfminütigen Mono-WAV-Blöcken mit 16 kHz und je zwei Sekunden
  Kontextüberlappung verarbeitet. Nur Modell und aktueller Audioblock liegen im RAM.
- Bildbreite maximal 1600 Pixel. Die Bildanzahl ist eine Schätzung; fehlende Frames
  und variable Bildraten können Abweichungen verursachen.
- Erste Video- und erste Audiospur; mehrere Tonspuren bei Bedarf vorher zusammenmischen.
  Keine Sprechertrennung oder OCR. Whisper kann Begriffe und Zahlen falsch erkennen.
- Abbrechen beendet FFmpeg zeitnah. Modell-/Netzwerkaufrufe können erst bei ihrer
  Rückkehr beendet werden. Keine automatische Wiederaufnahme.
- Ausreichend Speicherplatz für temporäre Bilder und die ZIP vorsehen.

## Tests

    .\.venv\Scripts\python.exe -m unittest discover -s tests -v

Optional mit lokalem Modell und synthetischem Zweistundenvideo:

    $env:WHISPER_TEST_MODEL = (Resolve-Path models\tiny).Path
    $env:RUN_LONG_VIDEO_TEST = '1'
    .\.venv\Scripts\python.exe -m unittest discover -s tests -v

Der Sprachtest erzeugt unter Windows per System.Speech ein lokales Beispiel;
WHISPER_TEST_AUDIO erlaubt eine eigene WAV-Datei. Der Zweistundentest verwendet
echte FFmpeg-Verarbeitung und eine Modellattrappe.

## An Freunde weitergeben

Das vollständig entpackte öffentliche Repository kann inklusive VideoWissen.exe und
_internal/ weitergegeben werden. Es ist keine Python-Installation erforderlich.
Eigene Modelle, Videos und Exporte nicht mitgeben. Für neue Builds oder den ersten
GitHub-Push siehe **PUBLISHING.md**; Lizenztexte stehen in **THIRD_PARTY_NOTICES.md**.

## Fehlerbehebung

- **Modell fehlt:** Download-Button oder vollständigen lokalen CTranslate2-Modellordner verwenden.
- **Keine Tonspur:** Aufnahme und Audiospuren prüfen. Stille kann ein leeres Transkript ergeben.
- **CUDA-/DLL-Fehler:** CPU wählen; bei allgemeinen DLL-Fehlern Visual C++ Redistributable x64 prüfen.
- **FFmpeg-Fehler:** Datei prüfen oder neu exportieren; OBS-Aufnahmen gegebenenfalls remuxen.
- **Schreibfehler/Speicher voll:** Beschreibbaren Zielordner mit ausreichend Platz wählen.

Technische Referenz: https://github.com/SYSTRAN/faster-whisper
