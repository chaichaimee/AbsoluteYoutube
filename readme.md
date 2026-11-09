# Absolute YouTube

Download, search and manage YouTube audio and video with a single keystroke, hear subtitles read aloud, and skip ads with one key.

**author:** chai chaimee

**url:** https://github.com/chaichaimee/AbsoluteYoutube

## Introduction

Absolute YouTube turns NVDA into a complete YouTube companion. While you browse YouTube, you can save any video or playlist as MP3, MP4 or WAV with one keystroke, search YouTube without leaving the keyboard, keep a personal library of favorite channels, cut a clip out of a video, capture a video's thumbnail as a picture, save a video's description and subtitles as text files, have the subtitles read aloud while the video plays, and skip an ad with the Z key.

Every download is tracked for you. Waiting downloads sit in a download list, failed downloads can be retried with one press, and everything you have ever sent to the add-on is kept in a video history. All of this is presented in simple, fully accessible dialogs, with spoken messages and sounds that tell you what is happening while a download runs.

The tools the add-on needs (yt-dlp, Deno, aria2c and ffmpeg) are prepared automatically, so there is nothing extra to install. An internet connection is needed the first time they are fetched.

## Hot Keys

> **NVDA+Y**  
> Single Tap : Download as MP3  
> Double Tap : Download as MP4  
> Triple Tap : Download as WAV  

> **Ctrl+Shift+Y**  
> Single Tap : Open the Absolute YouTube context menu  
> Double Tap : Open the download folder  
> Triple Tap : Open the Search YouTube dialog  

> **NVDA+Ctrl+Y**  
> Single Tap : Open the Download List Manager  
> Double Tap : Open the Download Fail Manager  
> Triple Tap : Open the Video History Report  

> **NVDA+Shift+Y**  
> Single Tap : Turn Save description on or off  
> Double Tap : Turn Save subtitles on or off  
> Triple Tap : Turn Read YouTube subtitles automatically on or off  

> **Alt+Windows+Y**  
> Single Tap : Cycle the MP3 quality (128, 192, 256 and 320 kbps)  
> Double Tap : Turn Download Immediately on or off  
> Triple Tap : Turn Playlist Mode on or off  

> **Z** (on YouTube pages in a browser)  
> Skip the ad that is playing  

> **Commands without a key:** "Toggle download immediately", "Toggle playlist mode" and "Cycle MP3 quality settings" are also available as separate commands. They have no key assigned by default. You can give them a key in NVDA's Input Gestures dialog, under the Absolute YouTube category. The Z key for skipping ads is listed there too, as "Skip the YouTube ad that is playing".

## Features

### Download a Video or Playlist

Press NVDA+Y on a YouTube video link, on a video page, or inside one of the add-on's own lists (search results, channel videos, playlist videos or video history). The add-on finds the video you are on and downloads it in the format that matches your tap count. MP3 uses the quality chosen in settings, MP4 gives a ready-to-play video file, and WAV gives uncompressed audio.

**How to download a video:**

1. Open a YouTube page in your browser.
2. Move to the video you want, or stay on the video's own page.
3. Press NVDA+Y: one tap for MP3, two taps for MP4, three taps for WAV.
4. If Download Immediately is on, you hear a start sound and the message "Starting download", followed by the format and title. If it is off, you hear "Added to download list" instead.
5. While the file is being prepared, you hear progress beeps. When it finishes you hear a completion sound and, if enabled, "Download complete".
6. Press Ctrl+Shift+Y twice to open the folder that holds your files.

**Immediate and queued downloads.** With Download Immediately on, a download starts at once when nothing else is downloading. If another download is already running, the new one joins the queue ("Added to download queue") and starts when its turn comes. With Download Immediately off, every request is only added to the Download List Manager, and you decide when to start it. Whenever a download finishes, the next waiting item starts automatically. If the same video and format is already waiting, you hear "Already in download list" or "Already in download queue".

**Playlist Mode.** When Playlist Mode is on and you are on a playlist link or a playlist page, the whole playlist is downloaded instead of a single video. The files are placed in a folder named after the playlist inside your download folder. If "Add item numbers to file names in playlist mode" is on (it is by default), each file starts with its position in the playlist, for example 01 and 02, so the files keep the playlist order. With Playlist Mode off, only the single video is downloaded.

**Skip existing files.** When this setting is on, a single video whose file already exists is not downloaded again, and you hear "File exists".

**Pages that cannot be downloaded.** The YouTube home page and the subscriptions and trending feeds are refused with a spoken explanation. Move to a specific video or playlist first. If no YouTube address can be found at all, you hear "No YouTube URL found".

### Context Menu

Press Ctrl+Shift+Y once to open a small menu. Use the Up and Down arrows and press Enter to choose an item, or press Escape to close it. The menu contains:

- Copy video Shorten URL (shown when a YouTube link is under focus)
- Download list manager
- Download fail manager (shown as "no failed" when the list is empty)
- Video History Report
- Favorite channel
- Snapshot (only on a video page)
- Trim setting (only on a video page)
- Search Youtube
- Absolute YouTube setting

**Copy video Shorten URL** places a short youtu.be address for the video on the clipboard. If the link belongs to a playlist, the playlist part is kept.

### Download List Manager

This is where waiting and running downloads are listed. Each row shows the video title, the format, the status (Waiting or Downloading) and the time it was added. Press NVDA+Ctrl+Y once to open it.

Buttons: Delete Selected, Download Selected, Download All, Clear All and OK. You can select several rows at once. Download Selected moves the chosen items to the front of the queue and starts them. Download All starts the queue from the top. Pressing Delete removes the selected rows, and Escape closes the dialog. A right-click or Applications key menu offers the same actions for the selected rows.

If NVDA is restarted while downloads are unfinished and "Resume interrupted downloads on restart" is on, the add-on tells you how many interrupted downloads it found and asks whether to resume them all, so you can continue or discard them.

### Download Fail Manager

When a download cannot be completed, it is saved in the Download Fail Manager instead of being lost. Press NVDA+Ctrl+Y twice to open it. If there are no failures you hear "No failed downloads".

Each row shows the title, the video length and the address. The buttons are Delete Selected, Download Selected, Download All, Clear All, OK and Cancel. Retrying an item adds it to the queue again using your current settings and removes it from the failed list.

The add-on also explains many failures in plain words, for example: the video has not premiered yet or the live stream has not started (with the time remaining), YouTube blocked the request (try exporting cookies), the video is unavailable, or yt-dlp is out of date (with the current and latest versions). Temporary network problems are retried automatically before a download is declared failed.

**How to retry failed downloads:**

1. Press NVDA+Ctrl+Y twice to open the Download Fail Manager.
2. Select one or more items, or choose Download All to retry everything.
3. Press Download Selected or Download All. You hear how many downloads were started.
4. If failures continue, open settings and use Update yt-dlp now or export fresh cookies, then try again.

### Video History Report

Every video you send to the add-on is recorded in the Video History Report, up to 500 entries. Press NVDA+Ctrl+Y three times to open it. Each row shows the title, format, date, whether it is pinned, and the address.

Buttons: Download, Open URL, Pin or unpin, Remove, Clear all and Close. Pinned items stay at the top of the list and are the last to be removed when the history is full. Pressing Delete removes the selected item, and Clear all asks for confirmation first. While the history is in focus, NVDA+Y downloads the selected entry.

### Favorite Channel

Favorite Channel is your personal library of YouTube channels. Choose "Favorite channel" from the context menu (Ctrl+Shift+Y). If you are on a channel or playlist page, that page is loaded for you. The list of videos is saved on your computer, so it opens instantly, and the add-on then quietly checks for new videos and announces how many were added.

The dialog contains a channel list, Add new channel and Edit channel buttons, a Content type list (Videos, Shorts, Live, Podcasts, Playlists), a Search box that filters the list as you type, the list of items, paging controls, and the buttons Download All, Source and Close. Titles are corrected in the background so that the list shows the real video names. The other saved channels are also refreshed in the background while the dialog is open.

**How to add a favorite channel:**

1. Open a channel page on YouTube in your browser.
2. Press Ctrl+Shift+Y and choose "Favorite channel".
3. Press Add new channel. The name and address of the channel are filled in for you; change them if you wish and press OK.
4. Wait while the items are fetched. You hear "Channel added successfully" when the channel is saved.
5. Next time, open Favorite channel from anywhere and pick the channel from the Channel list.

**Working with the list.** Press Enter on a video to open it in your browser. Press Enter on a playlist to see the videos inside it. A right-click or Applications key menu on a video offers Copy URL, Open in browser, Correct title now, Download MP3, Download MP4, Download WAV and Remove from list. On a playlist it offers Download entire playlist instead of the three formats. Download All asks which format you want and queues every video in the list (playlist entries are skipped). The Source button opens the folder where your channel data is stored.

**Managing channels.** Open the menu on the Channel list to Pin or Unpin a channel, Move Up or Move Down a pinned channel, Edit the channel name and address, or Delete the saved channel. Pinned channels are shown first, in the order you choose.

**Paging.** Choose how many items to show per page (10, 20, 40, 50, 100, 150, 200, 250 or 300), move with PreviousPage and NextPage, or type a page number and press Go.

### Playlist Videos

When you press Enter on a playlist inside Favorite Channel, a dialog lists all the videos in that playlist with their lengths. You can show 10, 20, 40, 50 or 100 items per page. Press Enter on a video to open it in the browser. The menu on a video offers Copy video Shorten URL, Play on YouTube, Correct title now, Download MP3, Download MP4 and Download WAV. The button "Download All Videos in Playlist" asks for confirmation and then downloads the whole playlist as MP3.

### Search YouTube

Search YouTube lets you find videos without opening a web page. Press Ctrl+Shift+Y three times, or choose "Search Youtube" from the context menu.

**How to search and download:**

1. Type what you are looking for in the Search YouTube box and press Enter.
2. Results appear as they are found, and the length of each video fills in a moment later.
3. Use the Up and Down arrows to move through the results. Choose how many items to show per page (10 to 300, or All), and use PreviousPage, NextPage or Go to move between pages.
4. Press NVDA+Y on a result to download it, or open the menu on it and choose Download MP3, Download MP4 or Download WAV.
5. To save everything found, press Download All and choose MP3, MP4 or WAV.

The menu on a result also offers Copy video Shorten URL, Play on YouTube and Remove from list. Press Enter on a result to play it in the browser. The Download folder button opens your download folder, and Escape closes the dialog and stops the search.

### Snapshot

While you are on a YouTube video page, choose "Snapshot" from the context menu (Ctrl+Shift+Y). The add-on downloads the full-size thumbnail of the video and saves it as a JPG picture in your download folder. Files are numbered one after another, for example Snapshot 1.jpg and Snapshot 2.jpg. You hear "Capturing full-size snapshot..." and, when it is saved, "Full-size snapshot complete". If you are not on a video page you hear "You must be on a YouTube page to use this feature".

### Trim

Trim cuts a section out of a video and saves only that part. It is available from the context menu while you are on a YouTube video page, as "Trim setting".

**How to cut a clip:**

1. Open the YouTube video page, press Ctrl+Shift+Y and choose "Trim setting".
2. The video address is already filled in. The dialog shows the video's length and the length of the period you have selected.
3. Type the Start time and the End time in the form hours:minutes:seconds, for example 00:01:30. If the End time is empty, it is filled with the full length of the video.
4. Press Preview start to open the video in your browser at the start time and check the position.
5. Choose the file format: MP3, MP4 or WAV. The Audio Quality list (320, 256, 192 or 128 kbps) is available only for MP3.
6. Press Start download. The clip is saved in your download folder as "Trimmed Clip 1", "Trimmed Clip 2" and so on.

The start time must be earlier than the end time, otherwise you hear "Start time must be less than end time". The dialog remembers your last format, quality and times. Press Escape to close it without downloading.

### Save Description and Subtitles as Text

Absolute YouTube can save the description and the subtitles of every video you download as plain text files, so you can read them with any text editor. Both options are off by default.

**How to turn them on:**

1. Press NVDA+Shift+Y once to turn Save description on or off. You hear "Save description enabled" or "Save description disabled".
2. Press NVDA+Shift+Y twice to turn Save subtitles on or off. You hear "Save subtitles enabled" or "Save subtitles disabled".
3. Download a video as usual with NVDA+Y. The text files are created together with the audio or video file.

You can also turn both options on or off in the settings, with the checkboxes "Save video description as a text file" and "Save subtitles as a text file". Pressing the key and changing the checkbox do the same thing.

**Where the files go.** Descriptions are saved in a folder named Descriptions and subtitles in a folder named Subtitles, both inside your download folder. For a playlist, these folders are inside the playlist's own folder. Each text file has the same name as the video it belongs to.

**Subtitle languages.** Type the languages you want in the setting "Subtitle languages, comma separated", for example th,en. The default is th,en. Both subtitles written by the video's author and automatic subtitles are requested. Use only letters, digits, commas, dots, hyphens, underscores and asterisks; if the entry is not valid, th,en is used. If a video has no subtitles in your languages, no subtitle file is created and the download itself is not affected.

**Clean text.** Subtitles are saved as readable text only. The numbers, the time codes and the formatting marks are removed, and a line that is repeated straight after itself is written once.

These options also apply to downloads started from the Download List Manager, from the Download Fail Manager and from Favorite Channel, Search YouTube and Video History.

### Read YouTube Subtitles Automatically

While a YouTube video plays in your browser, NVDA can speak the subtitles for you as they appear, so you can follow a video in any language that has captions, including Thai. The option is off by default.

**How to use it:**

1. Press NVDA+Shift+Y three times. You hear "Automatic subtitle reading enabled". Press the same keys again to turn it off.
2. Open a YouTube video page in Chrome, Edge, Firefox or Brave.
3. Turn on the captions in the YouTube player.
4. Play the video. Each new subtitle is spoken, and it is also shown on your braille display.

You can also use the setting "Read YouTube subtitles automatically (Chrome, Edge, Firefox)".

**How it reads.** The add-on reads the caption text that YouTube shows on the page and speaks only the words that are new, so a sentence is not repeated when YouTube rewrites it. Captions that grow word by word are spoken once the text has settled. Sound descriptions in brackets, such as [Music], and music symbols are left out. When a subtitle is long, it is spoken a little faster, up to 1.6 times the normal rate, so that the speech keeps up with the video. A very long subtitle is cut short and ends with "truncated".

**Good to know.** It works on video pages and Shorts, and only in a browser. The captions must be switched on in the player, because the add-on reads what the page displays. It does not run while NVDA is on a secure screen.

### Skip YouTube Ads

When an ad plays before or during a video, press Z to skip it. The add-on finds the Skip button on the page and activates it for you. You hear "Ad skipped".

**How to skip an ad:**

1. Open a YouTube video page in your browser.
2. When an ad starts and the Skip button appears, press Z.
3. You hear "Ad skipped" and the video continues.
4. If you hear "No skip button found.", the ad cannot be skipped yet. Wait a moment and press Z again.

**Automatic skipping.** You do not always need to press Z. When you open a video, Shorts or live page, the add-on watches the page for one minute and presses the Skip button as soon as it appears. After each skip it keeps looking for another 30 seconds, so two ads in a row are both handled. It never skips more than six times in one go.

**Z stays Z everywhere else.** The key is taken over only while a browser (Chrome, Edge, Firefox, Brave, Opera, Vivaldi or Thorium) shows a YouTube page. In any other program, Z types a normal letter. On YouTube, Z also types normally when you are in a text box such as the search field, and a text field that happens to contain the word skip is never clicked. If the add-on cannot click the button, you hear "Could not click the skip button."

**Settings.** In the YouTube ad skipping group, the checkbox "Skip YouTube ads automatically (Z skips the ad that is playing)" turns the whole feature on or off. It is on by default. When it is off, both the automatic skipping and the Z key are disabled, and Z goes to the page as usual. The setting "Skip button text for other YouTube languages, comma separated" is for people whose YouTube is not in English. The button named Skip is always recognized. Type the words your YouTube uses on its Skip button, for example ข้าม for Thai. Separate several words with commas. The text must match the whole button name, capital letters do not matter, and up to 20 words are kept.

### Settings

Open NVDA's Settings and choose the Absolute YouTube category, or choose "Absolute YouTube setting" from the context menu. Changes are saved when you press OK.

**Destination folder.** The folder where all downloads, snapshots and clips are saved. If you leave it empty, a folder named AbsoluteYoutube in your Roaming AppData folder is used.

**Download Behavior**

- Start download immediately (NVDA+Y)
- Enable playlist mode by default
- Add item numbers to file names in playlist mode
- Skip existing files
- Resume interrupted downloads on restart
- Enable logging
- Save video description as a text file
- Save subtitles as a text file
- Subtitle languages, comma separated (for example th,en)
- Read YouTube subtitles automatically (Chrome, Edge, Firefox)
- MP3 quality (320, 256, 192 or 128 kbps)
- Max concurrent downloads (1 to 4)

**YouTube ad skipping**

- Skip YouTube ads automatically (Z skips the ad that is playing)
- Skip button text for other YouTube languages, comma separated, available when the option above is on

**Speed & Connections**

- Use download section: splits a download into several parts to make it faster
- Number of connections (1 to 16), available when the option above is on
- Throttle rate in KB/s: 0 means unlimited, and each step changes the value by 5
- Sleep between requests (0 to 60 seconds)
- Retry count (1 to 20)
- Fragment retries (1 to 50)
- Skip unavailable fragments

When several downloads run at the same time, or when your connection is slow, the add-on automatically lowers the number of connections so that the download stays reliable.

**Sound & Status Announcements**

- Beep while converting
- Beep volume in percent (0 to 100, in steps of 5), shown only when the beep is on
- Beep every (1 to 120 seconds), shown only when the beep is on
- Say download complete
- Announce download progress: speaks the percentage while downloading and "Converting" while the file is being converted

**Anti-blocking settings**

- Use cookies (recommended to avoid block, on by default)
- Cookies file, with a "How to get cookies?" button that explains the manual method
- Browser for automatic cookies (Google Chrome, Microsoft Edge, Mozilla Firefox, Brave or Opera), used when the cookies file is off
- Export YouTube Cookies (Anti-Block)
- Use custom user agent, with a text box for the user agent
- Use proxy, with a text box for the proxy address
- Force IPv4
- Force IPv6
- Mark as watched
- Reset to safe settings (recommended if blocked)

**yt-dlp Update.** Choose "Auto-update yt-dlp on startup" to keep the downloader current automatically, or press "Update yt-dlp now" at any time. If auto-update is off, the add-on tells you when a newer version is available.

**JavaScript Runtime (Deno).** Press "Update Deno now" to refresh the component that YouTube downloads depend on.

**How to export your YouTube cookies (if YouTube blocks downloads):**

1. Log in to YouTube in your browser, then close the browser completely.
2. Open the Absolute YouTube settings and press "Export YouTube Cookies (Anti-Block)".
3. Choose the browser you are logged in with and press OK. If the browser is still running, you are warned and can close it first.
4. Wait for the message "Cookies exported successfully". Cookies are switched on and the new cookies file is selected for you.
5. If the export fails, press "Update yt-dlp now" and try again, try Firefox, or use the manual method described under "How to get cookies?".

**How to use Reset to safe settings:**

1. Open the Absolute YouTube settings.
2. Press "Reset to safe settings (recommended if blocked)". This sets one download at a time, turns off download sections, uses one connection, limits the speed to 100 KB/s, waits 10 seconds between requests, uses 3 retries and 10 fragment retries.
3. Make sure cookies are on, then press OK to save.

### Automatic Update Check

About half a minute after NVDA starts, and at most once a day, Absolute YouTube quietly checks whether a newer version has been released on its GitHub page. If there is one, a dialog tells you which version is available and which one you have, and asks "Update now?" with the buttons Update now and Later. Escape does the same as Later.

Choose Update now to download the new version. You hear "Downloading" followed by the add-on name and version, and then NVDA's own add-on installer takes over, asking for your confirmation and offering to restart NVDA. The download is checked against its checksum when one is published. If the download fails, you hear "Could not download the update. Opening the releases page." and the page opens in your browser so you can get the file yourself.

If the add-on was installed from the NVDA Add-on Store, this check is not used, because the Add-on Store looks after updates. If there is no internet connection, the check tries again a few times and then waits until the next day.

### Sounds and Spoken Feedback

You always know what the add-on is doing. A start sound plays when a download begins, regular beeps tell you the download is still working, a higher beep marks completion, and a low beep marks failure. You can switch the beeps off, change their volume and interval, and choose whether progress percentages are spoken, all in the settings.

## Support Me

If this tool has made your life easier, consider fueling the next update with a small donation.

[![Support me](https://img.shields.io/badge/Donate-Support%20Me-blue?style=for-the-badge&logo=stripe)](https://buy.stripe.com/dRm9AU1xQ3Ds22N6VK1VK01)

Your support means the world. Let's build something great together

---

© 2026 Chai Chaimee NVDA Add-on Released under GNU GPL
