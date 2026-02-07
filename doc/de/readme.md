# AbsoluteYoutube

Leistungsstarker YouTube-Downloader für NVDA-Nutzer

![NVDA Logo](https://www.nvaccess.org/files/nvda/documentation/userGuide/images/nvda.ico)

**Autor:** chai chaimee  
**GitHub:** https://github.com/chaichaimee/AbsoluteYoutube

## Beschreibung

AbsoluteYoutube ist ein fortschrittliches NVDA-Add-on, mit dem Sie YouTube-Videos und Medien direkt aus Ihrem Browser im MP3-, MP4- oder WAV-Format herunterladen können. Es enthält intelligente Hintergrundsysteme für effiziente, wiederaufnahmbare Downloads, Videobearbeitung, Screenshots, Kopieren kurzer URLs und einen vollständigen Manager für fehlgeschlagene Downloads – alles zugänglich mit einfachen Gesten und Menüs.

## Hotkeys

- **NVDA+Y** – Download-Geste (Tippen-Erkennung)  
  - Einzel-Tipp: Als MP3 herunterladen  
  - Doppel-Tipp: Als MP4 herunterladen  
  - Dreifach-Tipp: Als WAV herunterladen  

- **CTRL+Shift+Y** – Kontextmenü / Ordner  
  - Einzel-Tipp: Kontextmenü öffnen (mit allen Optionen)  
  - Doppel-Tipp: Zielordner öffnen  

- **NVDA+Shift+Y** : Playlist-Modus ein-/ausschalten  

- **ALT+Windows+Y** : MP3-Qualität zyklisch wechseln (128 → 192 → 256 → 320 kbps)  

Alle Tastenkombinationen nutzen Tippen-Erkennung (~0,4 Sekunden). Ändern Sie sie in NVDA → Eingabegesten.

## Funktionen

- **Multi-Format-Download (MP3 / MP4 / WAV)**  
  Drücken Sie NVDA+Y einmal, zweimal oder dreimal, um das aktuelle YouTube-Video im gewünschten Format herunterzuladen. Unterstützt Einzelvideos und Playlists. Im Playlist-Modus wird automatisch ein Unterordner mit dem Playlist-Namen erstellt und alle Dateien darin gespeichert – Einzeldateien bleiben separat und organisiert.

- **Intelligentes Hintergrund-Download-System**  
  - Warteschlangen-Manager: Downloads laufen nacheinander oder mit begrenzter Parallelität (bis 4 einstellbar).  
  - Wiederaufnahme nach Neustart: Unterbrochene Downloads werden gespeichert und können automatisch oder per Abfrage fortgesetzt werden.  
  - Automatische Dateireparatur: Bereinigt beschädigte Temporärdateien vor neuen Downloads.  
  - Vorhandene überspringen: Überspringt bereits existierende Dateien automatisch.  
  - Multi-Part-Download: Teilt Dateien in bis zu 16 Teile für mehr Geschwindigkeit (optional).  
  Alle Funktionen in NVDA-Einstellungen → AbsoluteYoutube ein-/ausschalten.

- **Videoclips zuschneiden**  
  Auf einer YouTube-Seite → Kontextmenü (CTRL+Shift+Y Einzel-Tipp) → Trim-Einstellung.  
  Start- und Endzeit festlegen → MP3 (Qualität 128–320 kbps), MP4 (H.265) oder WAV (beste Qualität) wählen → Startpunkt vorab testen → Zugeschnittenen Clip herunterladen.  
  Gespeichert als „Trimmed Clip 1.mp3“, „Trimmed Clip 2.mp4“ usw.

- **Screenshot-Aufnahme**  
  Kontextmenü → Snapshot.  
  Lädt das höchstqualitative Vorschaubild als vollwertiges .jpg herunter (Snapshot 1.jpg, Snapshot 2.jpg usw.) – ideal für Cover oder schnelle Bilder.

- **Kurze URL kopieren**  
  Kontextmenü → Copy video Shorten URL.  
  Wandelt vollständigen YouTube-Link in kurzes youtu.be/...-Format um und kopiert es in die Zwischenablage – perfekt zum Teilen.

- **Download-Fehler-Manager**  
  Kontextmenü → Download fail manager (erscheint nur bei Fehlern).  
  Zeigt Liste mit Titel, Dauer, URL.  
  Rechtsklick auf Eintrag für:  
  - Ausgewählte löschen  
  - Datei jetzt erneut herunterladen  
  - Alle verbleibenden herunterladen  
  - Alles löschen  
  Fehlgeschlagene Einträge bleiben gespeichert – jederzeit erneut versuchen.

- **yt-dlp Auto-/Manuelles Update**  
  Hält Downloads trotz YouTube-Änderungen am Laufen.  
  Manuell: Einstellungen → Update yt-dlp now.  
  Automatisch: „Auto-update yt-dlp on startup“ aktivieren.

**Hinweis**  
Alle Funktionen sind in NVDA-Einstellungen → AbsoluteYoutube konfigurierbar. Tastenkombinationen können in Eingabegesten geändert werden.