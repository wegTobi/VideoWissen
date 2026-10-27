# Freigabeprüfung: Windows x64

## Aktualisierung: Download-Fortschritt

- Die Modellanzeige und der Fortschrittsbalken zeigen jetzt einen Prozentsatz anhand
  der tatsächlichen Modelldateigrößen. 100 % erscheint erst nach Vollständigkeitsprüfung.
- 17 Tests ausgeführt: 15 erfolgreich, zwei optionale Langvideo-/Modelltests übersprungen.
  Neue Tests prüfen Byte-Gewichtung, fortgesetzte Downloads, Cache-Treffer,
  Xet-Zähler ohne doppelte Anrechnung, Abbruch und die GUI-Prozentanzeige.
- Windows-EXE neu gebaut. Echter Erstdownload von tiny mit Zwischenständen
  13, 26, 40, 53, 67, 80, 93, 96, 99 und 100 % erfolgreich.
  Anschließende Spracherkennung und ZIP mit Transkript und drei JPEGs erfolgreich.

## Ursprüngliche Freigabeprüfung

Stand: 27.10.2026. Öffentliche Vorlage ohne private Entwicklungsdateien.

- Build mit signierter offizieller CPython-3.13.17-Installation, PyInstaller 6.22.3
  und den festgelegten Paketversionen. Keine modifizierte Entwicklungs-Pythonlaufzeit.
- 15 Tests erfolgreich: Kernfunktionen, Exportinhalt, Abbruch/Fehler, GUI/Prompt,
  Modelldownload ohne Konsole, Hardware-Schätzung und Paketierungsadapter.
- Echter Offline-Whisper-Sprachtest sowie synthetischer Zweistundentest erfolgreich.
- EXE mit eingeschränktem PATH getestet: kein separat installiertes Python/FFmpeg nötig.
- Echter Erstdownload von tiny aus der EXE, lokale Erkennung des Sprachbeispiels und
  fertiges Archiv mit ausschließlich transcript.md und drei JPEGs erfolgreich geprüft.
- Persönliche Modelle und Sprachproben der EXE liegen im Benutzerprofil, nicht neben
  der Anwendung. Testvideos, Ergebnisse, Modellgewichte und private Entwicklungsumgebungen
  wurden nicht in die Veröffentlichungsvorlage übernommen.
- Veröffentlichungsscan prüft Dateinamen, Kontonamen, typische Schlüssel-/Tokenmuster,
  gefrorene Python-Codeobjekte und die GitHub-Dateigrößengrenze. Keine entsprechenden
  Funde im vorgesehenen Stand. Diese begrenzte automatisierte Prüfung ersetzt keine
  Prüfung später von Hand hinzugefügter Dateien.
- Zwei rein lexikalische sk-Präfix-Treffer in einer unveränderten öffentlichen
  FFmpeg-Codec-DLL sind per DLL-Hash plus Treffer-Hash eng ausgenommen. Die DLL wurde
  byteweise mit dem originalen, SHA-256-geprüften Release verglichen. Andere Treffer
  und geänderte DLLs bleiben meldepflichtig; es werden keine Tokenwerte protokolliert.
- SHA256SUMS.txt ermöglicht die Integritätsprüfung des unveränderten Ordners.
- Ein direkt aus dem Git-Index erzeugtes ZIP wurde in einen frischen Ordner mit
  Leerzeichen und Umlaut entpackt. Alle Prüfsummen stimmen; die entpackte EXE
  transkribiert das Sprachbeispiel und erzeugt den vorgesehenen ZIP-Inhalt erfolgreich.

Lokal auf Windows 11 x64 geprüft. Windows 10 und weitere fremde Rechner wurden nicht
separat getestet. GPU-Verarbeitung wurde nicht getestet und setzt separate passende
CUDA-/cuDNN-Laufzeiten voraus. EXE nicht digital signiert.

Es wurde kein bestehender privater Git-Verlauf übernommen. Noch kein Commit mit einer
persönlichen Autorenadresse und noch kein GitHub-Push. Vor dem ersten Commit eine
bewusst gewählte öffentliche Identität/noreply-Adresse konfigurieren (PUBLISHING.md).
