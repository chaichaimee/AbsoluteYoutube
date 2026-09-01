<p align="center">
  <img src="https://www.nvaccess.org/files/nvda/documentation/userGuide/images/nvda.ico" alt="NVDA Logo" width="120">
</p>

# Absolute YouTube

<p align="center">Your ears, your hands, your YouTube -- download, trim, and manage videos without ever touching a mouse.</p>

<p align="center">
  <b>author:</b> chai chaimee<br>
  <b>url:</b> <a href="https://github.com/chaichaimee/AbsoluteYoutube">https://github.com/chaichaimee/AbsoluteYoutube</a>
</p>

---

## Introduction

Absolute YouTube is an NVDA add-on that lets you download, search, and manage YouTube content entirely from the keyboard.

While browsing YouTube in your browser, you can grab the video or link under your cursor and send it straight to MP3, MP4, or WAV -- no mouse, no separate downloader window required. Beyond simple downloads, the add-on can trim a clip to just the part you want, snapshot a video's thumbnail, keep a personal list of favorite channels and playlists you can browse and bulk-download offline, search YouTube directly from a dialog, and retry anything that failed. A full settings panel lets you control the destination folder, download speed, concurrent downloads, and a set of anti-blocking options to keep YouTube from throttling or blocking your downloads.

---

### Hot Keys

**NVDA+Y**
* **Single Tap:** Download or queue the current video/link as MP3
* **Double Tap:** Download or queue the current video/link as MP4
* **Triple Tap:** Download or queue the current video/link as WAV

> All three taps must land within roughly 0.6 seconds of each other for NVDA to count them as one multi-tap sequence; taking longer resets the tap counter to a fresh single tap. This one shortcut works whether your cursor is on a YouTube video page, on a link to a video, or on a channel/playlist link when playlist mode is on.

**Control+Shift+Y**
* **Single Tap:** Open the Absolute YouTube context menu
* **Double Tap:** Open the current download destination folder
* **Triple Tap:** Open the Search YouTube dialog

> Same 0.6-second multi-tap window as NVDA+Y. The context menu it opens (single tap) gives you quick access to every dialog in the add-on: Download list manager, Download fail manager, Favorite channel, Snapshot and Trim setting (only shown while on a YouTube video page), Search Youtube, and Absolute YouTube setting.

**NVDA+Control+Y**
* Toggles Immediate Download mode on or off

> When Immediate Download is on, pressing NVDA+Y starts downloading right away. When it is off, the same key instead adds the item to the Download List Manager's queue so you can review, reorder, or bulk-start downloads later.

**NVDA+Shift+Y**
* Toggles Playlist Mode on or off

> With Playlist Mode on, downloading a link that belongs to a real playlist (not a YouTube auto-generated Mix/Radio, channel-uploads feed, Liked Videos, or Watch Later list) downloads the whole playlist instead of just the single video.

**Alt+Windows+Y**
* Cycles the MP3 quality setting

> Each press moves to the next quality in the cycle: 128, 192, 256, then back around to 320 kbps, and NVDA announces the new value. This changes the same "MP3 quality" setting found in the Absolute YouTube settings panel.

---

## Features

### 1. One-Key Download (NVDA+Y)

Move your NVDA cursor onto a YouTube video page, a link to a YouTube video, or (with Playlist Mode on) a channel/playlist link, then press NVDA+Y.

Step by step:

1. The add-on looks at your current navigator or focus object, and if that fails, at the link under NVDA's older "review" position, to find a YouTube URL.
2. It cleans the URL, stripping tracking parameters such as `si`, `feature`, or an auto-attached `list` parameter that does not represent a playlist you deliberately chose.
3. Depending on how many times you tapped NVDA+Y within the tap window, it picks MP3 (1 tap), MP4 (2 taps), or WAV (3 taps).
4. If Immediate Download mode is on, the file starts downloading right away and NVDA announces its status; otherwise it is added to the Download List Manager's queue for later.

### 2. Context Menu, Folder, and Search (Control+Shift+Y)

This one hotkey opens three different things depending on how many times you tap it, letting you reach almost every part of the add-on without digging through the NVDA menus.

Single tap opens a right-click-style menu built for wherever you currently are: it always offers the Download list manager, Download fail manager, Favorite channel, Search Youtube, and Absolute YouTube setting, and adds Copy video Shorten URL when a YouTube link is available, plus Snapshot and Trim setting whenever you are actually on a YouTube video page.

Double tap jumps straight to opening your current download destination folder in File Explorer.

Triple tap opens the Search YouTube dialog directly, skipping the menu.

### 3. Multi-Part / Accelerated Downloading

When the "Use download section" option is enabled in settings (this is the default), Absolute YouTube hands the download off to the external tool **aria2c**, which can pull a file over several simultaneous connections instead of one, generally finishing faster than a single-connection download. The number of connections (1-16) is configurable in the settings panel.

> **Network-usage disclosure:** Multi-part downloading is turned on by default. The very first time you use the add-on (or any time afterward if `aria2c.exe` is not yet present on your machine), Absolute YouTube automatically contacts GitHub in the background and downloads the official aria2 release for Windows, without asking for confirmation first. This happens once -- the downloaded file is kept in the add-on's own configuration folder and is not re-downloaded on future updates. If you would rather the add-on never reach out to the network on its own, turn off "Use download section" in the settings panel before first use, or use the "Reset to safe settings" button described below.

### 4. Snapshot

Available from the context menu (or the Snapshot menu item) while you are on a YouTube video page. It downloads that video's full-size thumbnail image and saves it into your download folder as `Snapshot 1.jpg`, `Snapshot 2.jpg`, and so on, automatically numbering each new snapshot so nothing gets overwritten.

### 5. Trim Setting

Available from the context menu while on a YouTube video page. This opens a dialog where you can download only a portion of a video instead of the whole thing.

Step by step:

1. Enter (or confirm) the video URL, then set a Start time and End time in `HH:MM:SS` format. A live label shows the overall clip length as you type.
2. Optionally press "Preview start" to open the video in your browser at the chosen start time, so you can double-check the point before downloading.
3. Choose MP3, MP4, or WAV, and (for MP3) a quality from 128 to 320 kbps.
4. Press "Start download" to queue the trimmed clip, which is saved as `Trimmed Clip 1`, `Trimmed Clip 2`, and so on. Your last-used URL, times, format, and quality are remembered for next time.

### 6. Favorite Channel / Playlist Manager

Opens a dialog for browsing and bulk-downloading a YouTube channel or playlist's content. Pick a saved channel from the drop-down, or add a new one by URL, then choose a content type -- Videos, Shorts, Live, Podcasts, or Playlists -- to fetch and cache that list locally.

Once loaded, you can filter the list with the search box, page through large channels (10 to 300 items per page, with a "go to page" box for jumping directly), and use "Download All" to queue every listed item at once in your chosen format and quality.

### 7. Search YouTube

Opens a dialog where you can type a search term and get back a paged, sortable list of matching videos with titles and durations, without leaving NVDA or opening a browser. From there you can select individual results or use "Download All" to queue everything that was found, and "Download folder" to jump straight to where the files will be saved.

### 8. Download List Manager and Download Fail Manager

The Download List Manager shows everything waiting in your queue (title, format, status, and time added) when Immediate Download mode is off. You can delete, download, or bulk-download/clear items, and pressing Delete on a selected row removes it directly.

The Download Fail Manager keeps a separate list of downloads that previously failed, along with their duration and URL, so you can retry a single item, retry everything, or clear the list -- rather than having to find and re-paste the original link yourself.

### 9. Absolute YouTube Settings Panel

Found under NVDA's own settings dialog (or via the context menu). It is organized into clearly labeled groups:

* **Destination folder** -- where finished downloads and clips are saved.
* **Download Behavior** -- immediate download on/off, playlist mode by default, skip existing files, resume interrupted downloads on NVDA restart, logging, default MP3 quality, and max concurrent downloads (1-4).
* **Speed & Connections** -- the multi-part/aria2c toggle and connection count described above, a throttle rate in KB/s (0 = unlimited, adjustable in steps of 5), sleep time between requests, retry count, fragment retries, and whether to skip fragments that are unavailable.
* **Sound & Status Announcements** -- a beep while converting (with its own volume and repeat interval), announcing when a download completes, and announcing ongoing download progress.
* **Anti-blocking settings** -- using cookies (either a manually supplied cookies.txt file or automatic export from Chrome, Edge, Firefox, Brave, or Opera) so YouTube treats you as a logged-in user, a custom user agent, an optional proxy, geo-bypass with a chosen country code, forcing IPv4 or IPv6, marking videos as watched, and a one-click "Reset to safe settings" button that dials speed and concurrency back down if YouTube starts blocking you.
* **yt-dlp Update** -- an auto-update-on-startup toggle plus a manual "Update yt-dlp now" button, since YouTube periodically changes its site in ways that require a newer version of the underlying download engine.

---

## Support Me

If this tool has made your life easier, consider fueling the next update with a small donation.

<p align="center">
  <a href="https://buy.stripe.com/dRm9AU1xQ3Ds22N6VK1VK01">
    <img src="https://img.shields.io/badge/Donate-Support%20Me-blue?style=for-the-badge&logo=stripe" alt="Support me">
  </a>
</p>

Your support means the world. Let's build something great together.

<p align="center">
  <small>&copy; 2026 Chai Chaimee NVDA Add-on Released under GNU GPL</small>
</p>