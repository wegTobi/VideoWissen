# VideoWissen

**Aus einer Videoaufnahme wird die Grundlage für ausführliche Mitschriften, verständliche Zusammenfassungen und Schritt-für-Schritt-Anleitungen.**

Du hast eine Vorlesung aufgenommen, eine Schulung besucht oder möchtest ein Meeting später in Ruhe nachvollziehen? VideoWissen schreibt das Gesprochene auf und speichert regelmäßig Bilder aus dem Video. So bleiben neben den Erklärungen auch Folien, Tafelbilder oder gezeigte Arbeitsschritte verfügbar.

Die deutschsprachige App läuft auf deinem Windows-PC. Du brauchst keine Programmierkenntnisse und kein GitHub-Konto. Die Transkription erfolgt lokal auf deinem Rechner.

## Wofür kann ich das verwenden?

- **Im Studium:** Vorlesungen und Seminare nacharbeiten, Lernzettel vorbereiten, Erklärungen zu Folien nachvollziehen oder Übungsfragen erstellen lassen.
- **Bei der Arbeit:** Besprechungen nachbereiten, Entscheidungen und Aufgaben herausarbeiten oder eine interne Schulung dokumentieren.
- **Beim Lernen und Einarbeiten:** Aus Tutorials, Workshops und Bildschirmaufnahmen eine Anleitung erstellen, die du später Schritt für Schritt durchgehen kannst.

### Beispiel: Mit dem Handy aufnehmen, später besser lernen

Du nimmst mit dem Handy eine Vorlesung als Video auf. Zu Hause überträgst du die Datei auf deinen PC und öffnest sie in VideoWissen. Die App erstellt ein Transkript mit Zeitstempeln und Bilder aus der Aufnahme.

Anschließend gibst du diese Dateien zusammen mit einem passenden Arbeitsauftrag an eine KI, die Texte und Bilder verarbeiten kann. Daraus kannst du dir beispielsweise eine ausführliche Mitschrift mit Begriffserklärungen, Beispielen und Fragen zur Prüfungsvorbereitung erstellen lassen. Die KI kann dabei sowohl das Gesprochene als auch sichtbare Folien berücksichtigen. Das ermöglicht deutlich mehr Detail als eine kurze Zusammenfassung allein aus Stichpunkten.

**Für gute Ergebnisse:** Nimm möglichst verständlichen Ton auf und achte darauf, dass Folien oder Tafelbilder lesbar sind. Halte vor einer Aufnahme die nötigen Einwilligungen und geltenden Regeln ein.

VideoWissen selbst erstellt das Transkript und die Bilder. Die ausgearbeitete Mitschrift entsteht erst bei der anschließenden KI-Auswertung. Ein perfektes oder vollständiges Ergebnis lässt sich nicht garantieren: Namen, Zahlen und Fachbegriffe solltest du anhand der Aufnahme prüfen.

## In wenigen Minuten starten – ohne Installation

Du brauchst einen **Windows-PC mit Windows 10 oder 11, 64 Bit**. Eine besondere Grafikkarte ist nicht erforderlich.

1. **[VideoWissen als ZIP herunterladen](https://github.com/wegTobi/VideoWissen/archive/refs/heads/main.zip).** Alternativ auf dieser GitHub-Seite oben auf den grünen Button **Code** und dann **Download ZIP** klicken. Eine Anmeldung ist dafür nicht nötig.
2. Im Download-Ordner mit der rechten Maustaste auf die heruntergeladene ZIP-Datei klicken und **Alle extrahieren …** wählen.
3. Den entpackten Ordner öffnen und **VideoWissen.exe** doppelt anklicken. Falls Dateiendungen ausgeblendet sind, heißt die Datei möglicherweise nur **VideoWissen** und hat den Typ „Anwendung“.

**Wichtig:** Die App aus dem entpackten Ordner starten. Den Ordner **_internal** neben der Anwendung lassen und die EXE nicht einzeln herauskopieren. Python und die nötigen Werkzeuge sind bereits enthalten.

Die Anwendung ist nicht digital signiert. Windows kann deshalb einen Hinweis zur unbekannten Herkunft anzeigen. Verwende den Download aus diesem Repository; schalte die Sicherheitseinstellungen deines PCs nicht aus.

## Deine erste Aufnahme verarbeiten

### 1. Video auswählen

Übertrage die Aufnahme vom Handy auf deinen PC oder verwende eine vorhandene Videodatei, zum Beispiel eine Bildschirmaufnahme aus OBS. Wähle sie in der App aus. VideoWissen zeigt dir Dauer und Dateigröße an. Die App nimmt selbst keine Videos auf.

### 2. Einstellungen wählen

Für den ersten Versuch kannst du mit diesen Einstellungen beginnen:

| Einstellung | Einfacher Einstieg |
| --- | --- |
| Sprache | **Deutsch** für deutsche Aufnahmen; außerdem gibt es Englisch und Automatisch. |
| Berechnung | **CPU (empfohlen)** – funktioniert ohne besondere Grafikkarte. |
| Whisper-Modell | **small** als Ausgangspunkt. Ein Modell ist das Sprachpaket, mit dem die App Gesprochenes erkennt. |
| Screenshots pro Minute | **5** – ungefähr alle zwölf Sekunden ein Bild. |

Beim Modell steht, ob es bereits vorhanden ist oder noch heruntergeladen werden muss. Klicke bei Bedarf auf **Modell herunterladen**. Während des Downloads zeigen ein Fortschrittsbalken und ein **Prozentsatz von 0 bis 100 %**, wie viel der benötigten Modelldaten bereits verfügbar ist. 100 % erscheint nach erfolgreicher Prüfung der benötigten Dateien. Dafür brauchst du Internet. Danach kannst du dieses Modell auch ohne Internet verwenden. Beim Start der Verarbeitung wird kein Modell automatisch heruntergeladen.

Größere Modelle brauchen mehr Arbeitsspeicher und können auf der CPU deutlich länger rechnen; sie können bei schwierigen Aufnahmen bessere Ergebnisse liefern. Du kannst später verschiedene Modelle ausprobieren.

Mit dem Screenshot-Regler wählst du **1 bis 60 Bilder pro Minute**. Die App zeigt vorab, wie viele Bilder ungefähr entstehen. Häufig wechselnde Folien oder schnelle Arbeitsschritte brauchen eher mehr Bilder. Bei einer Aufnahme von 90 Minuten ergeben 5 Bilder pro Minute ungefähr **450 Bilder** – für eine spätere KI kann es sinnvoll sein, die Aufnahme in mehrere Teile aufzuteilen.

Die angezeigte Dauer ist eine grobe Schätzung anhand von Videolänge, Modell und Hardware. Mit **Zeitschätzung mit Sprachprobe verfeinern** kannst du eine kurze Probe verarbeiten lassen, bevor du das gesamte Video startest. Auch dabei siehst du einen **Fortschrittsbalken mit Prozentanzeige**: erst wird das Modell geladen, dann das Audio vorbereitet und anschließend die Probe transkribiert. Die Prozentzahl beschreibt den Verarbeitungsstand, keine verbleibende Zeit; bei kurzen Proben oder Sprechpausen kann sie springen.

### 3. Zielordner wählen und starten

Wähle, wo das Ergebnis gespeichert werden soll, und klicke auf **Aufbereitung starten**. Längere Aufnahmen können je nach Rechner und Modell viel Zeit benötigen. Die App zeigt den Fortschritt an.

Wenn alles fertig ist, findest du über **ZIP anzeigen** die Ergebnisdatei im Windows-Explorer. Standardmäßig wird unter **Dokumente/VideoWissen** gespeichert.

## Aus dem Ergebnis Mitschriften und Lernmaterial erstellen

1. Stelle in der App unter **KI-Auswertung anpassen** ein, was entstehen soll: zum Beispiel Lernmaterial, eine Zusammenfassung oder eine Anleitung. Gib an, ob die Bilder wichtige Details zeigen oder eher zur Orientierung dienen, wie viel vom Gespräch relevant war und für wen der Text gedacht ist. Du kannst den relevanten Anteil nicht abschätzen? Aktiviere **Kann ich nicht einschätzen**: Der Regler wird ausgegraut und die KI erhält keine Prozentvorgabe. Sie soll die Relevanz anhand deines Ausgabeziels und des Materials beurteilen. Wenn du das Häkchen wieder entfernst, bleibt dein vorheriger Reglerwert erhalten.
2. Klicke auf **Prompt ansehen und kopieren …** und im geöffneten Fenster auf **Prompt kopieren**. Ein „Prompt“ ist einfach der Arbeitsauftrag an die spätere KI.
3. Öffne eine KI deiner Wahl, die Dateien und Bilder auswerten kann. Lade die fertige Ergebnis-ZIP hoch, sofern sie ZIP-Dateien unterstützt. Andernfalls entpacke die ZIP und füge das Transkript und die gewünschten Bilder einzeln oder in mehreren Teilen hinzu. Beachte die Datei- und Bildgrenzen des jeweiligen Dienstes.
4. Füge den kopierten Arbeitsauftrag ins Eingabefeld der KI ein. Ergänze bei Bedarf eigene Wünsche und starte die Auswertung.

**Beispiel für eine Vorlesung:**

> Erstelle eine ausführliche, gut gegliederte Mitschrift zur Prüfungsvorbereitung. Erkläre die Fachbegriffe, übernimm die besprochenen Beispiele und berücksichtige lesbare Inhalte der Folien. Verweise bei wichtigen Punkten auf die Zeitstempel. Kennzeichne unklare Stellen und ergänze am Ende Verständnisfragen mit Antworten. Erfinde keine Inhalte, die aus den Dateien nicht hervorgehen.

**Beispiel für ein berufliches Meeting:**

> Erstelle ein übersichtliches Besprechungsprotokoll mit Themen, Entscheidungen, offenen Fragen und nächsten Schritten. Nenne Verantwortliche und Termine nur, wenn sie aus dem Material eindeutig hervorgehen. Nutze die Screenshots, wenn sie für das Verständnis relevant sind, und kennzeichne Unsicherheiten.

Der Prompt wird **nur zum Kopieren angezeigt**. Er wird weder als Datei gespeichert noch in die ZIP aufgenommen.

## Was steckt in der Ergebnis-ZIP?

```text
Aufnahme_20261027_120000.zip
├── transcript.md
└── screenshots/
    ├── 000001_00-00-00.000.jpg
    ├── 000002_00-00-12.000.jpg
    └── …
```

- **transcript.md:** Das Gesprochene als Text mit Zeitstempeln im Format **HH:MM:SS**, ohne Millisekunden. Du kannst die Datei auch mit einem normalen Texteditor öffnen.
- **screenshots/:** Bilder aus dem Video in zeitlicher Reihenfolge. Die Dateinamen enthalten jeweils die Position im Video.

Die ZIP enthält ausschließlich das Transkript und die Bilder. Das Originalvideo und der Prompt werden nicht mit eingepackt. Bewahre die ursprüngliche Aufnahme auf, wenn du später Stellen nachprüfen möchtest.

## Bleiben meine Aufnahmen privat?

**VideoWissen lädt deine Videos, Tonaufnahmen, Transkripte und Screenshots nicht hoch.** Die Verarbeitung erfolgt auf deinem PC. Internet wird für den ausdrücklich gestarteten Modelldownload benötigt.

Wenn du das Ergebnis anschließend selbst bei einem KI-Dienst hochlädst, gibst du die enthaltenen Informationen an diesen Dienst weiter. Prüfe deshalb vorher, ob du die Inhalte teilen darfst – gerade bei persönlichen Gesprächen, vertraulichen Meetings oder nicht öffentlichen Vorlesungen.

## Wenn etwas nicht klappt

| Problem | Das kannst du tun |
| --- | --- |
| Das Modell fehlt. | Auf **Modell herunterladen** klicken und den Download abwarten. |
| Die Verarbeitung dauert lange. | Ein kleineres Modell ausprobieren und die Zeitschätzung beachten. Ein zweistündiges Video kann längere Rechenzeit brauchen. |
| Eine Fehlermeldung erwähnt CUDA oder die Grafikkarte. | Bei Berechnung **CPU (empfohlen)** auswählen. |
| Die Aufnahme hat keinen Ton oder das Transkript ist leer. | Das Originalvideo abspielen und prüfen, ob die Sprache hörbar ist. |
| Folien oder Tafelbilder sind nicht lesbar. | Die Aufnahme prüfen. Mehr Screenshots können häufigere Bilder liefern, aber unscharfe Schrift nicht wiederherstellen. |
| Die ZIP lässt sich nicht speichern. | Einen beschreibbaren Zielordner wählen und freien Speicherplatz prüfen. |
| Die KI nimmt die ZIP nicht an. | ZIP entpacken und Transkript sowie Bilder in kleineren Teilen hinzufügen. |

Für weitere Hinweise kannst du unter der Statusmeldung **Verarbeitungsprotokoll anzeigen** einschalten.

## Grenzen, die du kennen solltest

- Die Qualität hängt von Ton, Aufnahme und gewähltem Modell ab. Whisper kann Wörter, Namen oder Zahlen falsch erkennen. Die App trennt Sprecher nicht automatisch voneinander.
- Screenshots entstehen in festen Abständen. Dazwischen eingeblendete Inhalte können fehlen. Die App liest Text in Bildern nicht selbst aus; dafür muss die spätere KI Bilder verstehen können.
- Auch lange Videos von etwa zwei Stunden lassen sich verarbeiten, ohne das gesamte Video in den Arbeitsspeicher zu laden. Genügend Speicherplatz für Arbeitsdateien und die fertige ZIP muss trotzdem vorhanden sein.
- Die appseitige Bildbreite ist auf maximal 1600 Pixel begrenzt. Es werden die erste Video- und die erste Audiospur verwendet.
- Transkription und KI-Auswertung können Fehler enthalten. Prüfe wichtige Aussagen und verwende die Ergebnisse als Unterstützung beim Lernen oder Nacharbeiten.

## An Freunde weitergeben

Teile einfach den **[Download-Link](https://github.com/wegTobi/VideoWissen/archive/refs/heads/main.zip)** oder den **[Link zu dieser Anleitung](https://github.com/wegTobi/VideoWissen#readme)**. Jede Person lädt bei der ersten Einrichtung ihr gewünschtes Sprachmodell selbst herunter. Ein GitHub-Konto oder eine Python-Installation ist nicht nötig.

<details>
<summary><strong>Technische Informationen, Quellcode und Entwicklung</strong></summary>

### Quellcode ausführen

1. [Python für Windows](https://www.python.org/downloads/windows/) **3.10 bis 3.13, 64 Bit**, mit pip, Tcl/Tk und Python Launcher installieren.
2. PowerShell im entpackten Projektordner öffnen und ausführen:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```

   Mit dem Parameter `-Python` lässt sich ein bestimmter Interpreter angeben.
3. Zum Starten **start.bat** doppelklicken.

FFmpeg wird bei der Quellcode-Installation über imageio-ffmpeg mitinstalliert. Ein FFmpeg im PATH hat Vorrang; `FFMPEG_BINARY` erlaubt einen eigenen vollständigen Pfad. Mindestens FFmpeg 5 wird benötigt, ein separates ffprobe nicht. Getestete Paketversionen stehen in `requirements-lock.txt`.

### Lokale Daten und Verarbeitung

Bei der EXE liegen Modelle und temporäre Sprachproben unter `%LOCALAPPDATA%/VideoWissen/`; beim Quellcode-Start liegen Modelle unter `models/`. Vorhandene vollständige Hugging-Face-Caches werden ebenfalls erkannt. Eigene CTranslate2-Modelle lassen sich über **Extras → Eigenes Whisper-Modell wählen** einbinden.

FFmpeg dekodiert das Video fortlaufend. Audio wird in fünfminütigen Mono-WAV-Blöcken mit 16 kHz und je zwei Sekunden Kontextüberlappung verarbeitet. Nur Modell und aktueller Audioblock liegen im RAM. Variable Bildraten und fehlende Frames können die geschätzte Bildanzahl verändern.

Arbeitsdateien liegen vorübergehend im Zielordner und werden bei regulärem Abschluss, Fehler und Abbruch entfernt. Die ZIP wird erst vollständig veröffentlicht; bestehende ZIPs werden nicht überschrieben. Nach einem Prozessabsturz können temporäre Arbeitsdateien verbleiben. Ältere Exporte bleiben erhalten. Modell- und Netzwerkaufrufe können erst bei ihrer Rückkehr abgebrochen werden; eine automatische Wiederaufnahme gibt es nicht.

### Hardware und Dauer

Beim Start werden CPU, Kerne, RAM und gegebenenfalls NVIDIA-GPU, VRAM und CUDA lokal geprüft. **Extras → Hardware erneut prüfen** wiederholt den Scan. Die Zeitspanne ist eine Heuristik für die Transkription ohne Download und Export, keine garantierte Laufzeit.

Die optionale Sprachprobe verarbeitet bis zu 30 Sekunden aus der Videomitte. Das Modell muss lokal vorliegen. Bei zu wenig Sprache bleibt die Hardware-Schätzung aktiv. Das Probenergebnis gilt nur für das aktuelle Video, Modell, Gerät und die Sprache in dieser Sitzung.

CPU/INT8 benötigt kein CUDA. Die optionale GPU-Verarbeitung erfordert passende NVIDIA-/CUDA-/cuDNN-Bibliotheken. GPU-Erkennung allein garantiert deren Kompatibilität nicht. Bei allgemeinen DLL-Fehlern gegebenenfalls das Visual C++ Redistributable x64 prüfen.

### Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Optional mit lokalem Modell und synthetischem Zweistundenvideo:

```powershell
$env:WHISPER_TEST_MODEL = (Resolve-Path models\tiny).Path
$env:RUN_LONG_VIDEO_TEST = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Der Sprachtest erzeugt unter Windows per System.Speech ein lokales Beispiel; `WHISPER_TEST_AUDIO` erlaubt eine eigene WAV-Datei. Der Zweistundentest verwendet echte FFmpeg-Verarbeitung und eine Modellattrappe.

Für neue Windows-Builds und die Veröffentlichung siehe [PUBLISHING.md](PUBLISHING.md). Lizenztexte und Hinweise zu mitgelieferten Komponenten stehen in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Technische Referenz: [faster-whisper](https://github.com/SYSTRAN/faster-whisper).

</details>
