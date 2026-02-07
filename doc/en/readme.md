# AbsoluteYoutube

Powerful YouTube downloader for NVDA users

![NVDA Logo](https://www.nvaccess.org/files/nvda/documentation/userGuide/images/nvda.ico)

**Author:** chai chaimee  
**GitHub:** https://github.com/chaichaimee/AbsoluteYoutube

## Description

AbsoluteYoutube is an advanced NVDA add-on that lets you download YouTube videos and media in MP3, MP4, or WAV formats directly from your browser. It includes smart background systems for efficient, resumable downloads, video trimming, snapshots, short URL copying, and a full failed download manager – all accessible with simple gestures and menus.

## Hot Keys

- **NVDA+Y** – Download gesture (tap detection)  
  - Single Tap: Download as MP3  
  - Double Tap: Download as MP4  
  - Triple Tap: Download as WAV  

- **CTRL+Shift+Y** – Context menu / Folder  
  - Single Tap: Open context menu (with all options)  
  - Double Tap: Open download destination folder  

- **NVDA+Shift+Y** : Toggle playlist mode on/off  

- **ALT+Windows+Y** : Cycle MP3 quality (128 → 192 → 256 → 320 kbps)  

All shortcuts use tap detection (~0.4 seconds window). Remap them in NVDA → Input Gestures.

## Features

- **Multi-Format Download (MP3 / MP4 / WAV)**  
  Press NVDA+Y once, twice, or three times to download the current YouTube video (or media link) in your preferred format. Supports single videos and playlists. When playlist mode is enabled, it automatically creates a subfolder named after the playlist title and stores all files inside – keeping single-file downloads separate and organized.

- **Smart Background Download System**  
  - Queue Manager: Downloads run sequentially or with limited concurrency (configurable up to 4) to avoid overloading CPU/RAM.  
  - Resume on Restart: Interrupted downloads (NVDA restart, PC shutdown) are saved and can resume automatically or via prompt.  
  - Auto File Repair: Cleans up corrupted .part / .aria2 temp files before new downloads.  
  - Skip Existing: Automatically skips already downloaded files to prevent duplicates.  
  - Multi-Part Download: Splits files into up to 16 parts for faster speed (optional, configurable in settings).  
  All features can be toggled in NVDA Settings → Absolute YouTube.

- **Trim Video Clips**  
  On any YouTube page → Context menu (CTRL+Shift+Y single tap) → Trim setting.  
  Set start/end time → Choose MP3 (128–320 kbps), MP4 (H.265), or WAV (best quality) → Preview start point → Download trimmed clip.  
  Saved as "Trimmed Clip 1.mp3", "Trimmed Clip 2.mp4", etc.

- **Snapshot Capture**  
  Context menu → Snapshot.  
  Downloads highest-quality thumbnail as full-size .jpg (Snapshot 1.jpg, Snapshot 2.jpg, etc.) – great for cover art or quick images.

- **Copy Short URL**  
  Context menu → Copy video Shorten URL.  
  Converts full YouTube link to short youtu.be/... format and copies to clipboard instantly – perfect for sharing.

- **Download Fail Manager**  
  Context menu → Download fail manager (appears only if failures exist).  
  Lists failed downloads with title, duration, URL.  
  Right-click any item to:  
  - Delete selected  
  - Download file (retry now)  
  - Download all remaining  
  - Clear all  
  Failed items persist – retry anytime without losing the list.

- **yt-dlp Auto/Manual Update**  
  Keeps downloads working despite YouTube changes.  
  Manual: Settings → Update yt-dlp now.  
  Auto: Enable "Auto-update yt-dlp on startup" in settings.

**Note**  
All features are highly configurable in NVDA Settings → Absolute YouTube. Shortcuts can be changed in Input Gestures.