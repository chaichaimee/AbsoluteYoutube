# search.py
import wx
import gui
import threading
import subprocess
import json
import os
import time
import re
import urllib.parse
import webbrowser
import api
import ui
import tones
import addonHandler
import globalVars
from gui import guiHelper

from .Download_core import log, getINI, DownloadPath, PlayWave, YouTubeEXE, convertToMP
from .channel_utils import create_short_youtube_url

addonHandler.initTranslation()


class VirtualSearchList(wx.ListCtrl):
	def __init__(self, parent, video_source_callback, filtered_indices_callback):
		style = wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VIRTUAL
		super().__init__(parent, style=style)
		self.InsertColumn(0, _("Video Title"), width=550)
		self.InsertColumn(1, _("Duration"), width=100)
		self.video_source = video_source_callback
		self.filtered_indices = filtered_indices_callback
		self.SetItemCount(0)

	def OnGetItemText(self, item, col):
		filtered = self.filtered_indices()
		if item < 0 or item >= len(filtered):
			return ""
		video_idx = filtered[item]
		videos = self.video_source()
		if video_idx >= len(videos):
			return ""
		video = videos[video_idx]
		if col == 0:
			return video.get('title', '')
		elif col == 1:
			return video.get('duration', _('loading...'))
		return ""


class SearchDialog(wx.Dialog):
	def __init__(self, parent, plugin):
		super().__init__(parent, title=_("Search YouTube"), size=(800, 550),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
		self.plugin = plugin
		self.videos = []
		self.current_query = ""
		self._is_searching = False
		self._stop_search = False
		self._fetch_stop = threading.Event()
		self._fetch_semaphore = threading.BoundedSemaphore(5)

		self._process1 = None
		self._process2 = None

		self.page_size = 50
		self.current_page = 0
		self.total_pages = 0

		self._last_status_count = 0
		self._status_update_threshold = 5

		self._create_ui()
		self._update_paging()

		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
		self.Bind(wx.EVT_CLOSE, self._on_close)

	def _create_ui(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)

		searchSizer = wx.BoxSizer(wx.HORIZONTAL)
		searchLabel = wx.StaticText(self, label=_("Search YouTube:"))
		self.searchCtrl = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
		self.searchCtrl.Bind(wx.EVT_TEXT_ENTER, self._on_search_enter)
		searchBtn = wx.Button(self, label=_("Search"))
		searchBtn.Bind(wx.EVT_BUTTON, self._on_search_enter)

		searchSizer.Add(searchLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		searchSizer.Add(self.searchCtrl, 1, wx.EXPAND | wx.RIGHT, 5)
		searchSizer.Add(searchBtn, 0)

		mainSizer.Add(searchSizer, 0, wx.EXPAND | wx.ALL, 5)

		self.status_label = wx.StaticText(self, label=_("Enter a search query."))
		mainSizer.Add(self.status_label, 0, wx.ALL | wx.CENTER, 5)

		self.list_ctrl = VirtualSearchList(
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

		page_choices = [str(x) for x in [10,20,40,50,100,150,200,250,300]] + [_("All")]
		self.pageSizeCombo = wx.ComboBox(self, choices=page_choices, style=wx.CB_READONLY)
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

		goPageSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.goPageLabel = wx.StaticText(self, label="")
		self.goPageText = wx.TextCtrl(self, size=(60, -1), style=wx.TE_PROCESS_ENTER)
		self.goPageBtn = wx.Button(self, label=_("Go"))
		goPageSizer.Add(self.goPageLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		goPageSizer.Add(self.goPageText, 0, wx.RIGHT, 5)
		goPageSizer.Add(self.goPageBtn, 0)
		mainSizer.Add(goPageSizer, 0, wx.ALIGN_LEFT | wx.ALL, 5)

		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.download_all_btn = wx.Button(self, label=_("&Download All"))
		self.download_all_btn.Bind(wx.EVT_BUTTON, self._on_download_all)
		btn_sizer.Add(self.download_all_btn, 0, wx.ALL, 5)

		self.download_folder_btn = wx.Button(self, label=_("&Download folder"))
		self.download_folder_btn.Bind(wx.EVT_BUTTON, self._on_download_folder)
		btn_sizer.Add(self.download_folder_btn, 0, wx.ALL, 5)

		self.close_btn = wx.Button(self, wx.ID_CLOSE, label=_("&Close"))
		self.close_btn.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
		btn_sizer.Add(self.close_btn, 0, wx.ALL, 5)

		mainSizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

		self.SetSizer(mainSizer)
		self.CentreOnScreen()

		self.goPageBtn.Bind(wx.EVT_BUTTON, self._on_go_to_page)
		self.goPageText.Bind(wx.EVT_TEXT_ENTER, self._on_go_to_page)

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

		self.goPageText.SetValue(str(self.current_page + 1))
		self.goPageLabel.SetLabel(_("Go to page of {}:").format(self.total_pages))

	def _on_page_size_change(self, event):
		selection = self.pageSizeCombo.GetStringSelection()
		if selection == _("All"):
			self.page_size = len(self.videos) if self.videos else 1
		else:
			try:
				self.page_size = int(selection)
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

	def _on_go_to_page(self, event):
		page_str = self.goPageText.GetValue().strip()
		if not page_str:
			return
		try:
			page = int(page_str)
		except ValueError:
			ui.message(_("Please enter a valid number."))
			return
		if 1 <= page <= self.total_pages:
			self.current_page = page - 1
			self._update_paging()
		else:
			ui.message(_("Page number out of range (1-{}).").format(self.total_pages))

	def _on_search_enter(self, event):
		query = self.searchCtrl.GetValue().strip()
		if not query:
			ui.message(_("Please enter a search term."))
			return
		self.current_query = query
		self._perform_search(query)

	def _perform_search(self, query):
		if self._is_searching:
			ui.message(_("Search already in progress."))
			return

		if not os.path.exists(YouTubeEXE):
			ui.message(_("yt-dlp.exe not found."))
			log(f"yt-dlp not found at {YouTubeEXE}")
			return

		self._stop_search = True
		self._fetch_stop.set()
		if self._process1:
			try:
				self._process1.terminate()
			except:
				pass
		if self._process2:
			try:
				self._process2.terminate()
			except:
				pass

		self.videos = []
		self.list_ctrl.SetItemCount(0)
		self._update_paging()

		self._is_searching = True
		self._stop_search = False
		self._fetch_stop.clear()
		self._last_status_count = 0
		self.status_label.SetLabel(_("Searching..."))

		def search_worker():
			try:
				cmd1 = [
					YouTubeEXE,
					"--flat-playlist",
					"--dump-json",
					"--ignore-errors",
					"--no-warnings",
					"--quiet",
					"--extractor-args", "youtubetab:lang=th,youtube:lang=th",
					"--playlist-items", "1-50",
					f"ytsearch1000:{query}"
				]
				log(f"Process1 command: {cmd1}")

				self._process1 = subprocess.Popen(
					cmd1,
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE,
					text=True,
					encoding='utf-8',
					errors='replace',
					bufsize=1,
					creationflags=subprocess.CREATE_NO_WINDOW
				)

				cmd2 = [
					YouTubeEXE,
					"--flat-playlist",
					"--dump-json",
					"--ignore-errors",
					"--no-warnings",
					"--quiet",
					"--extractor-args", "youtubetab:lang=th,youtube:lang=th",
					"--playlist-items", "51-1000",
					f"ytsearch1000:{query}"
				]
				log(f"Process2 command: {cmd2}")

				self._process2 = subprocess.Popen(
					cmd2,
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE,
					text=True,
					encoding='utf-8',
					errors='replace',
					bufsize=1,
					creationflags=subprocess.CREATE_NO_WINDOW
				)

				def read_process(proc, is_first):
					try:
						for line in proc.stdout:
							if self._stop_search:
								proc.terminate()
								return
							if line.strip():
								try:
									info = json.loads(line)
									video_url = info.get('webpage_url')
									video_id = info.get('id')
									if not video_url and video_id:
										video_url = f"https://youtu.be/{video_id}"
									title = info.get('title', 'Untitled')
									video = {
										'url': video_url,
										'id': video_id,
										'title': title,
										'duration': ''
									}
									wx.CallAfter(self._append_single_video, video)
								except json.JSONDecodeError:
									continue
					except Exception as e:
						log(f"Error reading process: {e}")
					finally:
						try:
							stderr = proc.stderr.read()
							if stderr:
								log(f"Process stderr: {stderr}")
						except:
							pass

				t1 = threading.Thread(target=read_process, args=(self._process1, True), daemon=True)
				t2 = threading.Thread(target=read_process, args=(self._process2, False), daemon=True)
				t1.start()
				t2.start()

				t1.join()
				t2.join()

				wx.CallAfter(self._on_search_complete, query)

			except Exception as e:
				log(f"Search error: {e}")
				wx.CallAfter(self._on_search_failed, str(e))

		threading.Thread(target=search_worker, daemon=True).start()

	def _append_single_video(self, video):
		if self._stop_search:
			return

		video_index = len(self.videos)
		self.videos.append(video)
		self.list_ctrl.SetItemCount(len(self.videos))

		start = self.current_page * self.page_size
		end = start + self.page_size - 1
		if start <= video_index <= end:
			display_index = video_index - start
			try:
				self.list_ctrl.RefreshItem(display_index)
			except:
				pass

		count = len(self.videos)
		if count - self._last_status_count >= self._status_update_threshold:
			self.status_label.SetLabel(_("Found {} videos...").format(count))
			self._last_status_count = count

		if not self._fetch_stop.is_set():
			threading.Thread(target=self._fetch_duration, args=(video_index,), daemon=True).start()

	def _fetch_duration(self, video_index):
		with self._fetch_semaphore:
			if self._fetch_stop.is_set() or self._stop_search:
				return
			if video_index >= len(self.videos):
				return
			video = self.videos[video_index]
			url = video.get('url')
			if not url:
				return

			try:
				cmd = [
					YouTubeEXE,
					"--dump-json",
					"--no-playlist",
					"--ignore-errors",
					"--no-warnings",
					"--quiet",
					url
				]
				process = subprocess.Popen(
					cmd,
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE,
					text=True,
					encoding='utf-8',
					errors='replace',
					creationflags=subprocess.CREATE_NO_WINDOW
				)
				stdout, stderr = process.communicate(timeout=30)
				if process.returncode != 0 or not stdout:
					return

				info = json.loads(stdout)
				duration = info.get('duration')
				if duration:
					duration_sec = int(duration)
					hours = duration_sec // 3600
					minutes = (duration_sec % 3600) // 60
					seconds = duration_sec % 60
					if hours > 0:
						duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
					else:
						duration_str = f"{minutes:02d}:{seconds:02d}"
				else:
					duration_str = ""

				wx.CallAfter(self._update_duration, video_index, duration_str)

			except Exception as e:
				log(f"Error fetching duration for {url}: {e}")

	def _update_duration(self, video_index, duration_str):
		if video_index >= len(self.videos):
			return
		self.videos[video_index]['duration'] = duration_str

		start = self.current_page * self.page_size
		end = start + self.page_size - 1
		if start <= video_index <= end:
			display_index = video_index - start
			try:
				self.list_ctrl.RefreshItem(display_index)
			except:
				pass

	def _on_search_complete(self, query):
		if not self or not self.IsShown():
			return
		self._is_searching = False
		self._process1 = None
		self._process2 = None
		self._update_paging()
		if len(self.videos) == 0:
			self.status_label.SetLabel(_("No results found for '{query}'.").format(query=query))
			ui.message(_("No results found."))
		else:
			self.status_label.SetLabel(_("Found {count} videos for '{query}'.").format(
				count=len(self.videos), query=query))
			ui.message(_("Search completed."))

	def _on_search_failed(self, error):
		if not self or not self.IsShown():
			return
		self._is_searching = False
		self._process1 = None
		self._process2 = None
		self.status_label.SetLabel(_("Search failed: {error}").format(error=error))
		ui.message(_("Search failed."))

	def _on_item_selected(self, event):
		event.Skip()

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

		menu = wx.Menu()
		copy_item = menu.Append(wx.ID_ANY, _("Copy video Shorten URL"))
		self.Bind(wx.EVT_MENU, lambda evt: self._on_copy_short_url(video_idx), copy_item)

		play_item = menu.Append(wx.ID_ANY, _("Play on YouTube"))
		self.Bind(wx.EVT_MENU, lambda evt: webbrowser.open(self.videos[video_idx]['url']), play_item)

		dl_mp3 = menu.Append(wx.ID_ANY, _("Download MP3"))
		self.Bind(wx.EVT_MENU, lambda evt: self._download_video(video_idx, "mp3"), dl_mp3)

		dl_mp4 = menu.Append(wx.ID_ANY, _("Download MP4"))
		self.Bind(wx.EVT_MENU, lambda evt: self._download_video(video_idx, "mp4"), dl_mp4)

		dl_wav = menu.Append(wx.ID_ANY, _("Download WAV"))
		self.Bind(wx.EVT_MENU, lambda evt: self._download_video(video_idx, "wav"), dl_wav)

		menu.AppendSeparator()
		remove_item = menu.Append(wx.ID_ANY, _("Remove from list"))
		self.Bind(wx.EVT_MENU, lambda evt: self._on_remove_video(video_idx), remove_item)

		self.PopupMenu(menu)
		menu.Destroy()

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
		if not url and video.get('id'):
			url = f"https://youtu.be/{video['id']}"
		if not url:
			wx.CallAfter(ui.message, _("Cannot determine URL for this video."))
			log(f"Missing URL for video: {video}")
			return
		title = video.get('title', 'Unknown')
		save_path = getINI("ResultFolder") or DownloadPath
		log(f"Downloading {url} as {format_type}")
		PlayWave('start')
		if hasattr(self.plugin, 'core_functions') and 'convertToMP' in self.plugin.core_functions:
			self.plugin.core_functions['convertToMP'](format_type, save_path, False, url, title)
			wx.CallAfter(ui.message, _("Adding {title} to download queue.").format(title=title))
		else:
			convertToMP(format_type, save_path, False, url, title)
			wx.CallAfter(ui.message, _("Adding {title} to download queue.").format(title=title))

	def _on_remove_video(self, video_idx):
		del self.videos[video_idx]
		self._update_paging()
		ui.message(_("Item removed."))

	def _on_download_all(self, event):
		if not self.videos:
			ui.message(_("No videos to download."))
			return

		dlg = DownloadAllFormatDialog(self)
		if dlg.ShowModal() == wx.ID_OK:
			format_ = dlg.format
			count = len(self.videos)
			ui.message(_("Adding {count} videos to download queue...").format(count=count))
			save_path = getINI("ResultFolder") or DownloadPath
			for video in self.videos:
				url = video.get('url')
				if not url and video.get('id'):
					url = f"https://youtu.be/{video['id']}"
				if url:
					if hasattr(self.plugin, 'core_functions') and 'convertToMP' in self.plugin.core_functions:
						self.plugin.core_functions['convertToMP'](format_, save_path, False, url, video['title'])
					else:
						convertToMP(format_, save_path, False, url, video['title'])
				time.sleep(0.1)
			ui.message(_("Downloads started."))
		dlg.Destroy()

	def _on_download_folder(self, event):
		folder = getINI("ResultFolder") or DownloadPath
		if os.path.isdir(folder):
			try:
				os.startfile(folder)
			except Exception as e:
				log(f"Error opening download folder: {e}")
				ui.message(_("Cannot open download folder."))
		else:
			ui.message(_("Download folder does not exist."))

	def _on_char_hook(self, event):
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			self._stop_search = True
			self._fetch_stop.set()
			if self._process1:
				try:
					self._process1.terminate()
				except:
					pass
			if self._process2:
				try:
					self._process2.terminate()
				except:
					pass
			self.Close()
		event.Skip()

	def _on_close(self, event):
		self._stop_search = True
		self._fetch_stop.set()
		if self._process1:
			try:
				self._process1.terminate()
			except:
				pass
		if self._process2:
			try:
				self._process2.terminate()
			except:
				pass
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
		url = video.get('url')
		if not url and video.get('id'):
			url = f"https://youtu.be/{video['id']}"
		return (url, video.get('title', ''))


class DownloadAllFormatDialog(wx.Dialog):
	def __init__(self, parent):
		super().__init__(parent, title=_("Download All Videos"), size=(400, 250))
		self.format = "mp3"

		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		format_box = wx.StaticBox(panel, label=_("File Format"))
		format_sizer = wx.StaticBoxSizer(format_box, wx.VERTICAL)
		self.mp3_radio = wx.RadioButton(panel, label="MP3", style=wx.RB_GROUP)
		self.mp4_radio = wx.RadioButton(panel, label="MP4")
		self.wav_radio = wx.RadioButton(panel, label="WAV")
		format_sizer.Add(self.mp3_radio, 0, wx.ALL, 5)
		format_sizer.Add(self.mp4_radio, 0, wx.ALL, 5)
		format_sizer.Add(self.wav_radio, 0, wx.ALL, 5)
		sizer.Add(format_sizer, 0, wx.EXPAND | wx.ALL, 5)

		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		start_btn = wx.Button(panel, wx.ID_OK, label=_("Start download"))
		cancel_btn = wx.Button(panel, wx.ID_CANCEL, label=_("Cancel"))
		btn_sizer.Add(start_btn, 0, wx.ALL, 5)
		btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
		sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

		panel.SetSizer(sizer)
		self.CentreOnParent()

		self.Bind(wx.EVT_BUTTON, self.on_ok, start_btn)

	def on_ok(self, event):
		if self.mp3_radio.GetValue():
			self.format = "mp3"
		elif self.mp4_radio.GetValue():
			self.format = "mp4"
		else:
			self.format = "wav"
		self.EndModal(wx.ID_OK)