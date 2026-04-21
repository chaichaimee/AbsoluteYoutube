# playlist.py

import wx
import gui
import threading
import subprocess
import json
import os
import time
import webbrowser
import ui
import addonHandler
import api
from .Download_core import log, YouTubeEXE, convertToMP, getINI, DownloadPath, PlayWave
from .channel_utils import create_short_youtube_url, update_video_cache, get_video_from_cache
from .channel_dialogs import VirtualVideoList

addonHandler.initTranslation()


class PlaylistVideosDialog(wx.Dialog):
	def __init__(self, parent, playlist_url, playlist_title, plugin):
		super().__init__(parent, title=_("Videos in {title}").format(title=playlist_title), size=(800, 500),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
		self.playlist_url = playlist_url
		self.playlist_title = playlist_title
		self.plugin = plugin
		self.videos = []
		self.filtered_indices = []
		self.page_size = 50
		self.current_page = 0
		self.total_pages = 0
		self._stop_fetch = False
		self._is_fetching = False
		self._background_title_fetch_running = False
		self._tap_count = 0
		self._last_tap_time = 0
		self._tap_timer = None

		self._create_ui()
		self._start_fetch()
		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
		self.Bind(wx.EVT_CLOSE, self._on_close)

		if self.plugin:
			self.plugin.playlist_dialog = self

	def _create_ui(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)

		self.status_label = wx.StaticText(self, label=_("Loading playlist videos..."))
		mainSizer.Add(self.status_label, 0, wx.ALL | wx.CENTER, 5)

		self.list_ctrl = VirtualVideoList(
			self,
			lambda: self.videos,
			lambda: self._get_current_page_indices()
		)
		self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_item_selected)
		self.list_ctrl.Bind(wx.EVT_CONTEXT_MENU, self._on_list_context_menu)
		self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_item_activated)

		mainSizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 5)

		pageSizer = wx.BoxSizer(wx.HORIZONTAL)
		pageLabel = wx.StaticText(self, label=_("Show items:"))
		pageSizer.Add(pageLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

		self.pageSizeCombo = wx.ComboBox(self, choices=[str(x) for x in [10,20,40,50,100]], style=wx.CB_READONLY)
		self.pageSizeCombo.SetStringSelection(str(self.page_size))
		self.pageSizeCombo.Bind(wx.EVT_COMBOBOX, self._on_page_size_change)
		pageSizer.Add(self.pageSizeCombo, 0, wx.RIGHT, 10)

		self.prevPageBtn = wx.Button(self, label=_("PreviousPage"))
		self.prevPageBtn.Bind(wx.EVT_BUTTON, self._on_prev_page)
		pageSizer.Add(self.prevPageBtn, 0, wx.RIGHT, 5)

		self.nextPageBtn = wx.Button(self, label=_("NextPage"))
		self.nextPageBtn.Bind(wx.EVT_BUTTON, self._on_next_page)
		pageSizer.Add(self.nextPageBtn, 0, wx.RIGHT, 5)

		mainSizer.Add(pageSizer, 0, wx.ALIGN_LEFT | wx.ALL, 5)

		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.download_all_btn = wx.Button(self, label=_("&Download All Videos in Playlist"))
		self.download_all_btn.Bind(wx.EVT_BUTTON, self._on_download_all)
		btn_sizer.Add(self.download_all_btn, 0, wx.ALL, 5)

		self.close_btn = wx.Button(self, wx.ID_CLOSE, label=_("&Close"))
		self.close_btn.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
		btn_sizer.Add(self.close_btn, 0, wx.ALL, 5)

		mainSizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

		self.SetSizer(mainSizer)
		self.CentreOnScreen()

	def _get_page_indices(self, page_num):
		start = page_num * self.page_size
		end = start + self.page_size
		return list(range(start, min(end, len(self.videos))))

	def _get_current_page_indices(self):
		return self._get_page_indices(self.current_page)

	def _update_paging(self):
		total = len(self.videos)
		self.total_pages = (total + self.page_size - 1) // self.page_size if total > 0 else 1
		if self.current_page >= self.total_pages:
			self.current_page = max(0, self.total_pages - 1)

		self.prevPageBtn.Enable(self.current_page > 0)
		self.nextPageBtn.Enable(self.current_page < self.total_pages - 1)

		page_indices = self._get_current_page_indices()
		self.list_ctrl.SetItemCount(len(page_indices))
		if page_indices:
			self.list_ctrl.RefreshItems(0, len(page_indices)-1)

		shown = len(page_indices)
		total = len(self.videos)
		page_info = _("Page {}/{}").format(self.current_page+1, self.total_pages)
		self.status_label.SetLabel(_("{}, showing {} of {} videos").format(page_info, shown, total))

	def _on_page_size_change(self, event):
		try:
			self.page_size = int(self.pageSizeCombo.GetStringSelection())
		except:
			self.page_size = 50
		self.current_page = 0
		self._update_paging()

	def _on_prev_page(self, event):
		if self.current_page > 0:
			self.current_page -= 1
			self._update_paging()

	def _on_next_page(self, event):
		if self.current_page < self.total_pages - 1:
			self.current_page += 1
			self._update_paging()

	def _on_item_selected(self, event):
		event.Skip()

	def _start_fetch(self):
		if self._is_fetching:
			return
		self._is_fetching = True
		self._stop_fetch = False
		thread = threading.Thread(target=self._fetch_videos, daemon=True)
		thread.start()

	def _fetch_videos(self):
		if not os.path.exists(YouTubeEXE):
			wx.CallAfter(self._show_info_message, f"yt-dlp.exe not found at {YouTubeEXE}")
			return

		cmd = [
			YouTubeEXE,
			"--flat-playlist",
			"--dump-json",
			"--ignore-errors",
			"--no-warnings",
			"--quiet",
			"--extractor-args", "youtubetab:max_results=999999,youtubetab:lang=th,youtube:lang=th",
			self.playlist_url
		]
		log(f"Fetching playlist videos: {cmd}")

		try:
			process = subprocess.Popen(
				cmd,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				text=True,
				encoding='utf-8',
				errors='replace',
				creationflags=subprocess.CREATE_NO_WINDOW
			)

			video_list = []
			for line in process.stdout:
				if self._stop_fetch:
					process.terminate()
					return
				if line.strip():
					try:
						info = json.loads(line)
						video_url = info.get('webpage_url') or f"https://youtu.be/{info.get('id')}"
						title = info.get('title', 'Untitled')
						duration = info.get('duration')
						duration_str = ""
						if duration:
							duration_sec = int(duration)
							hours = duration_sec // 3600
							minutes = (duration_sec % 3600) // 60
							seconds = duration_sec % 60
							if hours > 0:
								duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
							else:
								duration_str = f"{minutes:02d}:{seconds:02d}"
						video_list.append({
							'url': video_url,
							'title': title,
							'duration': duration_str,
							'title_finalized': False
						})
					except json.JSONDecodeError:
						continue

			stderr = process.stderr.read()
			if stderr:
				log(f"yt-dlp stderr: {stderr}")

			wx.CallAfter(self._on_fetch_complete, video_list)
		except Exception as e:
			log(f"Error fetching playlist videos: {e}")
			wx.CallAfter(self._show_info_message, str(e))

	def _on_fetch_complete(self, videos):
		self.videos = videos
		self._refresh_display()
		self._is_fetching = False
		self.status_label.SetLabel(_("Loaded {count} videos.").format(count=len(videos)))
		self._start_background_title_fetch()

	def _start_background_title_fetch(self):
		if self._background_title_fetch_running:
			return
		videos_to_fetch = [i for i, v in enumerate(self.videos) if not v.get('title_finalized', False)]
		if not videos_to_fetch:
			return
		self._background_title_fetch_running = True
		threading.Thread(target=self._background_title_fetch_worker, args=(videos_to_fetch,), daemon=True).start()

	def _background_title_fetch_worker(self, indices):
		for idx in indices:
			if idx >= len(self.videos):
				continue
			video = self.videos[idx]
			if video.get('title_finalized', False):
				continue
			success = self._fetch_video_details(video)
			if success:
				wx.CallAfter(self._update_title_in_ui, idx, video['title'])
			time.sleep(0.5)
		self._background_title_fetch_running = False

	def _fetch_video_details(self, video):
		try:
			cmd = [
				YouTubeEXE, "--dump-json", "--no-playlist",
				"--extractor-args", "youtubetab:lang=th,youtube:lang=th",
				"--ignore-errors", "--no-warnings", "--quiet",
				video['url']
			]
			process = subprocess.run(
				cmd,
				capture_output=True,
				text=True,
				timeout=30,
				creationflags=subprocess.CREATE_NO_WINDOW
			)
			if process.returncode == 0 and process.stdout:
				info = json.loads(process.stdout)
				real_title = info.get('title', '')
				if real_title and real_title != video['title']:
					video['title'] = real_title
					video['title_finalized'] = True
					update_video_cache(video['url'], {
						'title': real_title,
						'duration': video.get('duration', ''),
						'title_finalized': True
					})
					log(f"Updated title for {video['url']} to: {real_title}")
					return True
			return False
		except Exception as e:
			log(f"Error fetching details for {video['url']}: {e}")
			return False

	def _update_title_in_ui(self, idx, new_title):
		if idx < len(self.videos):
			self.videos[idx]['title'] = new_title
			self._refresh_display()

	def _refresh_display(self):
		self.filtered_indices = list(range(len(self.videos)))
		self._update_paging()

	def _show_info_message(self, msg):
		self.status_label.SetLabel(msg)
		ui.message(msg)

	def _on_item_activated(self, event):
		idx = event.GetIndex()
		page_indices = self._get_current_page_indices()
		if 0 <= idx < len(page_indices):
			video_idx = page_indices[idx]
			webbrowser.open(self.videos[video_idx]['url'])

	def _on_list_context_menu(self, event):
		selected_idx = self.list_ctrl.GetFirstSelected()
		if selected_idx == -1:
			return
		page_indices = self._get_current_page_indices()
		if selected_idx >= len(page_indices):
			return
		video_idx = page_indices[selected_idx]
		video = self.videos[video_idx]

		menu = wx.Menu()
		copy_item = menu.Append(wx.ID_ANY, _("Copy video Shorten URL"))
		self.Bind(wx.EVT_MENU, lambda evt: self._on_copy_short_url(video_idx), copy_item)

		play_item = menu.Append(wx.ID_ANY, _("Play on YouTube"))
		self.Bind(wx.EVT_MENU, lambda evt: webbrowser.open(video['url']), play_item)

		correct_item = menu.Append(wx.ID_ANY, _("Correct title now"))
		self.Bind(wx.EVT_MENU, lambda evt: self._on_correct_title_now(video_idx), correct_item)

		dl_mp3 = menu.Append(wx.ID_ANY, _("Download MP3"))
		self.Bind(wx.EVT_MENU, lambda evt: self._download_video(video_idx, "mp3"), dl_mp3)

		dl_mp4 = menu.Append(wx.ID_ANY, _("Download MP4"))
		self.Bind(wx.EVT_MENU, lambda evt: self._download_video(video_idx, "mp4"), dl_mp4)

		dl_wav = menu.Append(wx.ID_ANY, _("Download WAV"))
		self.Bind(wx.EVT_MENU, lambda evt: self._download_video(video_idx, "wav"), dl_wav)

		self.PopupMenu(menu)
		menu.Destroy()

	def _on_correct_title_now(self, video_idx):
		video = self.videos[video_idx]
		ui.message(_("Correcting title for selected video..."))
		def worker():
			success = self._fetch_video_details(video)
			if success:
				wx.CallAfter(self._update_title_in_ui, video_idx, video['title'])
				wx.CallAfter(ui.message, _("Title correction completed and locked."))
			else:
				wx.CallAfter(ui.message, _("Title correction failed."))
		threading.Thread(target=worker, daemon=True).start()

	def _on_copy_short_url(self, video_idx):
		url = self.videos[video_idx]['url']
		short_url = create_short_youtube_url(url)
		if short_url:
			api.copyToClip(short_url)
			ui.message(_("Short URL copied to clipboard"))
		else:
			ui.message(_("Could not create short URL"))

	def _download_video(self, video_idx, format_type):
		video = self.videos[video_idx]
		url = video.get('url')
		title = video.get('title', 'Unknown')
		save_path = getINI("ResultFolder") or DownloadPath
		PlayWave('start')
		if hasattr(self.plugin, 'core_functions') and 'convertToMP' in self.plugin.core_functions:
			self.plugin.core_functions['convertToMP'](format_type, save_path, False, url, title)
			ui.message(_("Adding {title} to download queue.").format(title=title))
		else:
			ui.message(_("Download function not available."))

	def _on_download_all(self, event):
		if not self.videos:
			ui.message(_("No videos to download."))
			return

		dlg = wx.MessageDialog(self, _("Download all {count} videos in this playlist?").format(count=len(self.videos)),
							   _("Confirm Download"), wx.YES_NO | wx.ICON_QUESTION)
		if dlg.ShowModal() == wx.ID_YES:
			dlg.Destroy()
			save_path = getINI("ResultFolder") or DownloadPath
			if hasattr(self.plugin, 'core_functions') and 'convertToMP' in self.plugin.core_functions:
				self.plugin.core_functions['convertToMP']("mp3", save_path, True, self.playlist_url, self.playlist_title)
				ui.message(_("Playlist download started."))
			else:
				ui.message(_("Download function not available."))
		else:
			dlg.Destroy()

	def _on_char_hook(self, event):
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			self.Close()
		event.Skip()

	def _on_close(self, event):
		self._stop_fetch = True
		if self.plugin:
			self.plugin.playlist_dialog = None
		self.Destroy()

	def get_selected_video_info(self):
		selected_idx = self.list_ctrl.GetFirstSelected()
		if selected_idx == -1:
			return None
		page_indices = self._get_current_page_indices()
		if selected_idx >= len(page_indices):
			return None
		video_idx = page_indices[selected_idx]
		video = self.videos[video_idx]
		return (video['url'], video.get('title', ''))