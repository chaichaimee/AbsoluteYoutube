<div align="center">
  <img src="https://www.nvaccess.org/files/nvda/documentation/userGuide/images/nvda.ico" alt="NVDA Logo" width="120">
  <h1>AbsoluteYoutube</h1>
  <br>
  <p>Leistungsstarker YouTube-Downloader für NVDA-Benutzer</p>
</div>

<br>

<div align="center">
  <p><b>Autor:</b> chai chaimee</p>
  <p><b>URL:</b> https://github.com/chaichaimee/AbsoluteYoutube</p>
</div>

---
<br>

> ## Was ist neu: Das Unbound-Update
> **Beschleunigen Sie Ihren Workflow: Direkte Link-Downloads!**
>
> Warum Zeit damit verschwenden, eine Videoseite zu öffnen, wenn Sie sie sofort herunterladen können? Unser neuestes Update führt die revolutionäre **"Focus & Fetch"** Funktion ein. Fokussieren Sie einfach Ihren Cursor auf einen Videolink und starten Sie Ihren Download sofort – kein Warten mehr auf das Laden von Seiten!
>
> • **Unbound Search:** Entdecken Sie mehr Inhalte als je zuvor. Unsere neue Engine umgeht Standard-YouTube-Algorithmus-Limits und findet Videos, die in regulären Suchen oft verborgen bleiben.
>
> • **Lieblingskanäle-Manager:** Erstellen Sie Ihre eigene Sammlung von Erstellern und erhalten Sie automatisierte Updates zu den neuesten Inhalten.
>
> • **Intelligente Warteschlangensteuerung:** Verwalten Sie Ihre Downloads effizient mit dem neuen Hintergrund-Warteschlangensystem.

<br>

## Beschreibung
AbsoluteYoutube ist ein fortschrittliches NVDA-Add-on, mit dem Sie YouTube-Videos und Medien in den Formaten MP3, MP4 oder WAV direkt aus Ihrem Browser herunterladen können. Es enthält intelligente Hintergrundsysteme für effiziente, fortsetzbare Downloads, Video-Trimming, Schnappschüsse, das Kopieren kurzer URLs und einen vollständigen Manager für fehlgeschlagene Downloads – alles erreichbar über einfache Gesten und Menüs.

<br>

## Tastenkombinationen
**NVDA+Y** – Download-Befehl (Mehrfach-Tipp-Erkennung)  
• Einmal tippen: Als MP3 herunterladen (Hohe Qualität)  
• Zweimal tippen: Als MP4 herunterladen (Video)  
• Dreimal tippen: Als WAV herunterladen (Unkomprimiertes Audio)

**STRG+Umschalt+Y** – Optionen & Werkzeuge  
• Einmal tippen: Kontextmenü öffnen (Zugriff auf alle Tools)  
• Zweimal tippen: Download-Zielordner öffnen  
• **Dreimal tippen: Den neuen Suchdialog öffnen** (Zugriff auf Unbound Search-Ergebnisse)

**NVDA+STRG+Y** – Automatisches Herunterladen umschalten  
• Wechseln Sie zwischen sofortigem Download und dem **Warteschlangen-Modus**. Wenn deaktiviert, werden Links zur späteren Bearbeitung an den Download-Listen-Manager gesendet.

**NVDA+Umschalt+Y** : Playlisten-Modus ein/aus

**ALT+Windows+Y** : MP3-Qualität durchschalten (128 → 192 → 256 → 320 kbps)

> Alle Tastenkürzel verwenden die Tipp-Erkennung (Zeitfenster ~0,4 Sekunden). Sie können sie in NVDA → Eingaben neu zuweisen.

<br>

## Hauptmerkmale erklärt
* **1. Unbound Search Dialog (Dreimal Umschalt+STRG+Y tippen)**  
  Dies ist keine Standard-Suche. Durch das dreifache Tippen rufen Sie eine spezialisierte Suchoberfläche auf. Im Gegensatz zur YouTube-Website, die Ergebnisse basierend auf Ihrem Verlauf einschränkt, ruft dieses Tool Rohdaten ab und bietet Ihnen Zugriff auf eine größere Vielfalt an Videos und Informationen.

<br>

* **2. Lieblingskanal-Sammlung (Schritt-für-Schritt-Anleitung)**  
  Verlieren Sie nie den Überblick über Ihre Lieblings-Ersteller. So erstellen Sie Ihre Sammlung:  
  * **Schritt 1:** Gehen Sie zu YouTube und kopieren Sie die URL des Kanals, dem Sie folgen möchten (z. B. youtube.com/@KanalName).
  * **Schritt 2:** Öffnen Sie das AbsoluteYoutube-Kontextmenü (Einmal STRG+Umschalt+Y tippen) und wählen Sie "Lieblingskanäle".
  * **Schritt 3:** Wählen Sie die Option zum Hinzufügen eines neuen Kanals und fügen Sie Ihre kopierte URL ein.
  * **Der Vorteil:** Einmal hinzugefügt, prüft das System jedes Mal, wenn Sie diesen Kanal über den Dialog öffnen, automatisch auf neue Video-Uploads und zeigt diese sofort in einer Liste an.

<br>

* **3. Download-Listen-Manager & Intelligente Warteschlange (NVDA+STRG+Y)**  
  Wenn Sie beschäftigt sind und nicht sofort herunterladen möchten, drücken Sie **NVDA+STRG+Y**, um den automatischen Download auszuschalten. Alle angeforderten Dateien werden in eine "Warteschlange" gesendet.  
  • Um sie zu bearbeiten, öffnen Sie den **Download-Listen-Manager** aus dem Kontextmenü.  
  • Klicken Sie mit der rechten Maustaste auf ein Element, um den Download zu starten, es zu löschen oder zu wiederholen.

<br>

* **4. Intelligentes Hintergrund-Download-System**  
  • Warteschlangen-Manager: Downloads laufen nacheinander ab, um CPU/RAM zu sparen.  
  • Fortsetzen bei Neustart: Unterbrochene Downloads werden gespeichert und automatisch fortgesetzt, wenn NVDA neu startet.  
  • Automatische Dateireparatur: Bereinigt beschädigte temporäre Dateien vor dem Start.  
  • Vorhandene überspringen: Verhindert, dass dieselbe Datei zweimal heruntergeladen wird.

<br>

* **5. Videoclips zuschneiden (uTubeTrim)**  
  Kontextmenü öffnen → Trim-Einstellung. Start-/Endzeit festlegen und Format wählen. Perfekt, um bestimmte Segmente zu erhalten, ohne das ganze Video zu laden.

<br>

* **6. Manager für fehlgeschlagene Downloads**  
  Dauerhafte Liste fehlgeschlagener Elemente. Rechtsklick auf ein Element zum Wiederholen, Löschen oder Herunterladen aller verbleibenden Aufgaben.

<br>

> **Hinweis:** Alle Funktionen sind in den NVDA-Einstellungen → Absolute YouTube konfigurierbar. Tastenkürzel können in der Eingabegestengestaltung geändert werden.

<br>
<br>

## Unterstütze mich
Wenn dieses Tool Ihr Leben einfacher gemacht hat, ziehen Sie in Erwägung, das nächste Update mit einer kleinen Spende zu unterstützen.

<br>

[![Support me](https://img.shields.io/badge/Donate-Support%20Me-blue?style=for-the-badge&logo=stripe)](https://buy.stripe.com/dRm9AU1xQ3Ds22N6VK1VK01)

<br>

Ihre Unterstützung bedeutet mir viel. Lassen Sie uns gemeinsam etwas Großartiges bauen.

<br>

&copy; 2026 Chai Chaimee NVDA Add-on Veröffentlicht unter GNU