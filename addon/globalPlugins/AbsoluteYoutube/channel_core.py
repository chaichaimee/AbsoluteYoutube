# channel_core.py
import wx
import gui
import threading
import subprocess
import json
import os
import re
import webbrowser
import time
import ui
import tones
import addonHandler
import api
from .Download_core import log, YouTubeEXE, convertToMP, getINI, DownloadPath, PlayWave
from .channel_utils import (
	ensure_channel_dir, sanitize_filename, get_channel_filepath, save_channel_videos,
	get_all_channel_files, merge_videos, create_short_youtube_url, load_pinned_order,
	save_pinned_order, update_pinned_after_rename, update_pinned_after_delete, get_base_channel_url,
	flush_video_cache, get_video_from_cache, update_video_cache
)
from .channel_dialogs import VirtualVideoList, AddChannelDialog, EditChannelDialog, DownloadAllFormatDialog
from .playlist import PlaylistVideosDialog

addonHandler.initTranslation()


class ChannelPlaylistDialog(wx.Dialog):
	def __init__(self, parent, url=None, plugin=None):
		super().__init__(parent, title=_("Your favorite channel"), size=(800, 600),
						 style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
		self.initial_url = url
		self.url = url
		self.plugin = plugin
		self.videos = []
		self.filtered_indices = []
		self._stop_fetch = False
		self._closing = False
		self._beep_active = False
		self._beep_thread = None
		self._is_fetching = False
		self._fetch_complete = False
		self._auto_save_pending = False
		self._pending_save_name = None
		self._pending_save_path = None
		self._save_lock = threading.Lock()
		self._selection_timer = None
		self._pending_channel = None
		self._background_title_fetch_running = False
		self._pending_content_type = None
		self._save_timer = None
		self._save_pending = False
		self._bg_threads = []

		self.page_size = 50
		self.current_page = 0
		self.total_pages = 0

		self.pinned = load_pinned_order()

		self.content_type = "videos"
		self.content_type_map = {
			"videos": ("videos", _("Videos")),
			"shorts": ("shorts", _("Shorts")),
			"streams": ("streams", _("Live")),
			"podcasts": ("podcasts", _("Podcasts")),
			"playlists": ("playlists", _("Playlists")),
		}

		if url:
			match = re.search(r'(?:youtube\.com/(?:@|channel/|c/|user/))([^/?]+)', url)
			self.channel_identifier = match.group(1) if match else 'unknown'
		else:
			self.channel_identifier = 'unknown'
		self.filepath = get_channel_filepath(self.channel_identifier)

		self._create_ui()
		self._populate_channel_combo()

		if os.path.exists(self.filepath):
			self._load_from_file()
			if self.url:
				self._start_fetch(silent=True)
		else:
			self.status_label.SetLabel(_("No saved data for this channel."))

		if self.url and not os.path.exists(self.filepath):
			self._start_fetch(silent=False)

		self._start_background_auto_update()

		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
		self.Bind(wx.EVT_CLOSE, self._on_close)

	def _create_ui(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)

		channelSizer = wx.BoxSizer(wx.VERTICAL)
		topRow = wx.BoxSizer(wx.HORIZONTAL)
		channelLabel = wx.StaticText(self, label=_("Channel:"))
		self.channelCombo = wx.ComboBox(self, style=wx.CB_READONLY)
		self.channelCombo.Bind(wx.EVT_COMBOBOX, self._on_channel_selected)
		self.channelCombo.Bind(wx.EVT_CONTEXT_MENU, self._on_channel_context_menu)
		self.channelCombo.Bind(wx.EVT_KILL_FOCUS, self._on_channel_combo_kill_focus)

		topRow.Add(channelLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		topRow.Add(self.channelCombo, 1, wx.EXPAND)

		channelSizer.Add(topRow, 0, wx.EXPAND | wx.BOTTOM, 5)

		btnRow = wx.BoxSizer(wx.HORIZONTAL)
		self.addBtn = wx.Button(self, label=_("Add new channel"))
		self.addBtn.Bind(wx.EVT_BUTTON, self._on_add_channel)
		btnRow.Add(self.addBtn, 1, wx.RIGHT, 5)

		self.editBtn = wx.Button(self, label=_("Edit channel"))
		self.editBtn.Bind(wx.EVT_BUTTON, self._on_edit_current_channel)
		btnRow.Add(self.editBtn, 1, wx.LEFT, 5)

		channelSizer.Add(btnRow, 0, wx.EXPAND | wx.BOTTOM, 5)

		mainSizer.Add(channelSizer, 0, wx.EXPAND | wx.ALL, 5)

		typeSizer = wx.BoxSizer(wx.HORIZONTAL)
		typeLabel = wx.StaticText(self, label=_("Content type:"))
		self.typeCombo = wx.ComboBox(self, choices=[label for _, label in self.content_type_map.values()], style=wx.CB_READONLY)
		self.typeCombo.SetStringSelection(self.content_type_map[self.content_type][1])
		self.typeCombo.Bind(wx.EVT_COMBOBOX, self._on_content_type_selected)
		self.typeCombo.Bind(wx.EVT_KILL_FOCUS, self._on_content_type_kill_focus)
		typeSizer.Add(typeLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		typeSizer.Add(self.typeCombo, 1, wx.EXPAND)
		mainSizer.Add(typeSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

		searchSizer = wx.BoxSizer(wx.HORIZONTAL)
		searchLabel = wx.StaticText(self, label=_("Search:"))
		self.searchCtrl = wx.TextCtrl(self)
		self.searchCtrl.Bind(wx.EVT_TEXT, self._on_search)
		searchSizer.Add(searchLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		searchSizer.Add(self.searchCtrl, 1, wx.EXPAND)
		mainSizer.Add(searchSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

		self.status_label = wx.StaticText(self, label=_("Ready"))
		mainSizer.Add(self.status_label, 0, wx.ALL | wx.CENTER, 10)

		self.list_ctrl = VirtualVideoList(self, lambda: self.videos, lambda: self._get_current_page_indices())
		self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_item_selected)
		self.list_ctrl.Bind(wx.EVT_CONTEXT_MENU, self._on_list_context_menu)
		self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_item_activated)

		mainSizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 5)

		pageSizer = wx.BoxSizer(wx.HORIZONTAL)
		pageLabel = wx.StaticText(self, label=_("Show items:"))
		pageSizer.Add(pageLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

		self.pageSizeCombo = wx.ComboBox(self, choices=[str(x) for x in [10,20,40,50,100,150,200,250,300]], style=wx.CB_READONLY)
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

		self.source_btn = wx.Button(self, label=_("&Source"))
		self.source_btn.Bind(wx.EVT_BUTTON, self._on_source)
		btn_sizer.Add(self.source_btn, 0, wx.ALL, 5)

		self.close_btn = wx.Button(self, wx.ID_CLOSE, label=_("&Close"))
		self.close_btn.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
		btn_sizer.Add(self.close_btn, 0, wx.ALL, 5)

		mainSizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

		self.SetSizer(mainSizer)
		self.CentreOnScreen()

		self.goPageBtn.Bind(wx.EVT_BUTTON, self._on_go_to_page)
		self.goPageText.Bind(wx.EVT_TEXT_ENTER, self._on_go_to_page)

		self._update_edit_button_state()

	def _on_content_type_selected(self, event):
		if self._closing:
			return
		selected_label = self.typeCombo.GetStringSelection()
		for key, (_, label) in self.content_type_map.items():
			if label == selected_label:
				self._pending_content_type = key
				break
		event.Skip()

	def _on_content_type_kill_focus(self, event):
		if self._closing:
			return
		if self._pending_content_type is not None and self._pending_content_type != self.content_type:
			self.content_type = self._pending_content_type
			self._pending_content_type = None
			if hasattr(self, 'filepath') and self.filepath:
				self._save_content_type_to_file()
			self.videos = []
			self._refresh_display(reset_page=True)
			if self.url:
				self._start_fetch(silent=False)
		else:
			self._pending_content_type = None
		event.Skip()

	def _save_content_type_to_file(self):
		if self._closing or not self.filepath or not os.path.exists(self.filepath):
			return
		try:
			with open(self.filepath, 'r', encoding='utf-8') as f:
				data = json.load(f)
			data['content_type'] = self.content_type
			with open(self.filepath, 'w', encoding='utf-8') as f:
				json.dump(data, f, ensure_ascii=False, indent=2)
		except Exception as e:
			log(f"Error saving content_type: {e}")

	def _update_edit_button_state(self):
		if self._closing:
			return
		sel = self.channelCombo.GetSelection()
		self.editBtn.Enable(sel != wx.NOT_FOUND)

	def _on_edit_current_channel(self, event):
		if self._closing:
			return
		sel = self.channelCombo.GetSelection()
		if sel == wx.NOT_FOUND:
			ui.message(_("No channel selected."))
			return
		channel_name = self.channelCombo.GetString(sel)
		self._on_edit_channel(channel_name)

	def _on_go_to_page(self, event):
		if self._closing:
			return
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

	def _on_download_all(self, event):
		if self._closing:
			return
		if not self.videos:
			ui.message(_("No videos to download."))
			return

		dlg = DownloadAllFormatDialog(self)
		if dlg.ShowModal() == wx.ID_OK:
			format_ = dlg.format
			quality = dlg.quality

			save_path = getINI("ResultFolder") or DownloadPath
			if not os.path.exists(save_path):
				try:
					os.makedirs(save_path, exist_ok=True)
				except Exception as e:
					log(f"Error creating download folder: {e}")
					ui.message(_("Cannot create download folder."))
					dlg.Destroy()
					return

			count = len(self.videos)
			ui.message(_("Adding {count} videos to download queue...").format(count=count))
			for video in self.videos:
				if video.get('is_playlist', False):
					continue
				def download_one(vid):
					try:
						convertToMP(format_, save_path, False, vid['url'], vid['title'])
					except Exception as e:
						log(f"Error downloading {vid['url']}: {e}")

				threading.Thread(target=download_one, args=(video,), daemon=True).start()
				time.sleep(0.1)

			ui.message(_("Downloads started."))
		dlg.Destroy()

	def _on_source(self, event):
		if self._closing:
			return
		try:
			os.startfile(CHANNEL_DATA_DIR)
		except Exception as e:
			log(f"Error opening source folder: {e}")
			ui.message(_("Cannot open source folder."))

	def _get_page_indices(self, page_num):
		start = page_num * self.page_size
		end = start + self.page_size
		return self.filtered_indices[start:end]

	def _get_current_page_indices(self):
		return self._get_page_indices(self.current_page)

	def _update_paging(self):
		if self._closing:
			return
		total_filtered = len(self.filtered_indices)
		self.total_pages = (total_filtered + self.page_size - 1) // self.page_size
		if self.total_pages == 0:
			self.total_pages = 1
		if self.current_page >= self.total_pages:
			self.current_page = max(0, self.total_pages - 1)

		self.prevPageBtn.Enable(self.current_page > 0)
		self.nextPageBtn.Enable(self.current_page < self.total_pages - 1)

		page_indices = self._get_current_page_indices()
		self.list_ctrl.SetItemCount(len(page_indices))
		self.list_ctrl.RefreshItems(0, len(page_indices)-1 if page_indices else 0)

		shown = len(page_indices)
		total = len(self.filtered_indices)
		page_info = _("Page {}/{}").format(self.current_page+1, self.total_pages)
		self.status_label.SetLabel(_("{}, showing {} of {} videos").format(page_info, shown, total))

		self.goPageText.SetValue(str(self.current_page + 1))
		self.goPageLabel.SetLabel(_("Go to page of {}:").format(self.total_pages))

	def _on_page_size_change(self, event):
		if self._closing:
			return
		try:
			self.page_size = int(self.pageSizeCombo.GetStringSelection())
		except:
			self.page_size = 50
		self.current_page = 0
		self._update_paging()

	def _on_prev_page(self, event):
		if self._closing:
			return
		if self.current_page > 0:
			self.current_page -= 1
			self._update_paging()

	def _on_next_page(self, event):
		if self._closing:
			return
		if self.current_page < self.total_pages - 1:
			self.current_page += 1
			self._update_paging()

	def _on_item_selected(self, event):
		event.Skip()

	def _refresh_display(self, reset_page=True):
		if self._closing:
			return
		self.filtered_indices = [i for i, v in enumerate(self.videos) if self._matches_filter(v)]
		if reset_page:
			self.current_page = 0
		self._update_paging()

	def _matches_filter(self, video):
		if self._closing:
			return False
		filter_text = self.searchCtrl.GetValue().lower()
		if not filter_text:
			return True
		title = video.get('title', '').lower()
		return filter_text in title

	def _on_search(self, event):
		if self._closing:
			return
		self._refresh_display(reset_page=True)

	def _populate_channel_combo(self):
		if self._closing:
			return
		files = get_all_channel_files()
		name_to_path = {name: path for name, path in files}
		all_names = set(name for name, _ in files)

		pinned = [name for name in self.pinned if name in all_names]
		unpinned = [name for name in all_names if name not in pinned]
		unpinned.sort(key=str.lower)

		ordered_names = pinned + unpinned

		if self.pinned != pinned:
			self.pinned = pinned
			save_pinned_order(self.pinned)

		self.channelCombo.Clear()
		for name in ordered_names:
			path = name_to_path[name]
			self.channelCombo.Append(name, path)

		current_name = sanitize_filename(self.channel_identifier)
		index = self.channelCombo.FindString(current_name)
		if index != wx.NOT_FOUND:
			self.channelCombo.SetSelection(index)

		self._update_edit_button_state()

	def _fix_channel_url_if_needed(self):
		if self._closing:
			return
		if not self.url and hasattr(self, 'initial_url') and self.initial_url:
			self.url = self.initial_url
			self._save_videos(immediate=True)
			log(f"Fixed missing channel_url for {self.channel_identifier}: set to {self.url}")
		elif self.url and not isinstance(self.url, str):
			pass

	def _on_channel_selected(self, event):
		if self._closing:
			return
		self._update_edit_button_state()
		sel = self.channelCombo.GetSelection()
		if sel == wx.NOT_FOUND:
			self._pending_channel = None
			return
		channel_name = self.channelCombo.GetString(sel)
		filepath = self.channelCombo.GetClientData(sel)
		self._pending_channel = (channel_name, filepath)

	def _on_channel_combo_kill_focus(self, event):
		if self._closing:
			return
		if self._pending_channel:
			channel_name, filepath = self._pending_channel
			self._do_load_selected_channel(channel_name, filepath)
			self._pending_channel = None
		event.Skip()

	def _do_load_selected_channel(self, channel_name, filepath):
		if self._closing or not filepath or not os.path.exists(filepath):
			return

		try:
			with open(filepath, 'r', encoding='utf-8') as f:
				data = json.load(f)

			self.videos = []
			self.filtered_indices = []
			self.list_ctrl.SetItemCount(0)

			self.url = data.get('channel_url')
			self.videos = data.get('videos', [])
			saved_type = data.get('content_type')
			if saved_type and saved_type in self.content_type_map:
				self.content_type = saved_type
				self.typeCombo.SetStringSelection(self.content_type_map[self.content_type][1])

			for v in self.videos:
				if 'title_finalized' not in v:
					v['title_finalized'] = False
			self._fix_channel_url_if_needed()
			self._refresh_display(reset_page=True)
			self.status_label.SetLabel(_("Loaded {count} videos from {name}.").format(
				count=len(self.videos), name=channel_name))
			self.channel_identifier = channel_name
			self.filepath = filepath
			self._fetch_complete = True
			self._is_fetching = False

			self._start_background_title_fetch()

			if self.url:
				self._start_fetch(silent=True)

			self._update_edit_button_state()
		except Exception as e:
			log(f"Error loading {filepath}: {e}")
			ui.message(_("Error loading channel data."))

	def _start_background_title_fetch(self):
		if self._closing or self._background_title_fetch_running:
			return
		videos_to_fetch = [i for i, v in enumerate(self.videos) if not v.get('title_finalized', False) and not v.get('is_playlist', False)]
		if not videos_to_fetch:
			return
		self._background_title_fetch_running = True
		thread = threading.Thread(target=self._background_title_fetch_worker, args=(videos_to_fetch,), daemon=True)
		self._bg_threads.append(thread)
		thread.start()

	def _background_title_fetch_worker(self, indices):
		batch_size = 20
		updated_count = 0
		for i, idx in enumerate(indices):
			if self._closing or self._stop_fetch:
				break
			if idx >= len(self.videos):
				continue
			video = self.videos[idx]
			if video.get('title_finalized', False) or video.get('is_playlist', False):
				continue
			success = self._fetch_video_details(video)
			if success:
				updated_count += 1
				if not self._closing:
					wx.CallAfter(self._refresh_display, False)
			time.sleep(0.3)
			if (i+1) % batch_size == 0 or i == len(indices)-1:
				if not self._closing:
					wx.CallAfter(self._save_videos, False)
		self._background_title_fetch_running = False
		if updated_count > 0 and not self._closing:
			wx.CallAfter(ui.message, _("Title correction completed for {count} videos.").format(count=updated_count))

	def _fetch_video_details(self, video):
		if self._closing or video.get('title_finalized', False):
			return False
		cached = get_video_from_cache(video['url'])
		if cached and cached.get('title_finalized', False):
			video['title'] = cached['title']
			video['title_finalized'] = True
			return True
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

	def _on_channel_context_menu(self, event):
		if self._closing:
			return
		sel = self.channelCombo.GetSelection()
		if sel == wx.NOT_FOUND:
			return
		channel_name = self.channelCombo.GetString(sel)

		menu = wx.Menu()
		is_pinned = channel_name in self.pinned

		pin_label = _("Unpin") if is_pinned else _("Pin")
		pin_item = menu.Append(wx.ID_ANY, pin_label)
		self.Bind(wx.EVT_MENU, lambda evt: self._on_toggle_pin(channel_name), pin_item)

		up_item = menu.Append(wx.ID_ANY, _("Move Up"))
		up_item.Enable(is_pinned and self._can_move_up(channel_name))
		self.Bind(wx.EVT_MENU, lambda evt: self._on_move_up(channel_name), up_item)

		down_item = menu.Append(wx.ID_ANY, _("Move Down"))
		down_item.Enable(is_pinned and self._can_move_down(channel_name))
		self.Bind(wx.EVT_MENU, lambda evt: self._on_move_down(channel_name), down_item)

		menu.AppendSeparator()
		edit_item = menu.Append(wx.ID_ANY, _("Edit channel..."))
		self.Bind(wx.EVT_MENU, lambda evt: self._on_edit_channel(channel_name), edit_item)

		delete_item = menu.Append(wx.ID_ANY, _("Delete"))
		self.Bind(wx.EVT_MENU, lambda evt: self._on_delete_channel(channel_name), delete_item)

		self.PopupMenu(menu)
		menu.Destroy()

	def _can_move_up(self, channel_name):
		if channel_name not in self.pinned:
			return False
		idx = self.pinned.index(channel_name)
		return idx > 0

	def _can_move_down(self, channel_name):
		if channel_name not in self.pinned:
			return False
		idx = self.pinned.index(channel_name)
		return idx < len(self.pinned)-1

	def _on_toggle_pin(self, channel_name):
		if self._closing:
			return
		if channel_name in self.pinned:
			self.pinned.remove(channel_name)
			ui.message(_("Channel unpinned."))
		else:
			self.pinned.insert(0, channel_name)
			ui.message(_("Channel pinned."))
		save_pinned_order(self.pinned)
		self._populate_channel_combo()

	def _on_move_up(self, channel_name):
		if self._closing:
			return
		idx = self.pinned.index(channel_name)
		if idx > 0:
			self.pinned[idx], self.pinned[idx-1] = self.pinned[idx-1], self.pinned[idx]
			save_pinned_order(self.pinned)
			self._populate_channel_combo()

	def _on_move_down(self, channel_name):
		if self._closing:
			return
		idx = self.pinned.index(channel_name)
		if idx < len(self.pinned)-1:
			self.pinned[idx], self.pinned[idx+1] = self.pinned[idx+1], self.pinned[idx]
			save_pinned_order(self.pinned)
			self._populate_channel_combo()

	def _on_edit_channel(self, old_name):
		if self._closing:
			return
		old_path = None
		for i in range(self.channelCombo.GetCount()):
			if self.channelCombo.GetString(i) == old_name:
				old_path = self.channelCombo.GetClientData(i)
				break
		if not old_path:
			return

		current_url = ""
		try:
			with open(old_path, 'r', encoding='utf-8') as f:
				data = json.load(f)
			current_url = data.get('channel_url')
			if current_url is None:
				current_url = ""
		except Exception as e:
			log(f"Error loading channel data for edit: {e}")
			ui.message(_("Error loading channel data."))
			return

		dlg = EditChannelDialog(self, old_name, current_url)
		if dlg.ShowModal() == wx.ID_OK:
			new_name = dlg.new_name
			new_url = dlg.new_url
			if new_name and new_url:
				if new_name != old_name:
					new_name_safe = sanitize_filename(new_name)
					new_path = os.path.join(CHANNEL_DATA_DIR, new_name_safe + '.json')
					try:
						os.rename(old_path, new_path)
						log(f"Renamed {old_path} to {new_path}")
						update_pinned_after_rename(old_name, new_name_safe)
						self.pinned = load_pinned_order()
						with open(new_path, 'r', encoding='utf-8') as f:
							data = json.load(f)
						data['channel_url'] = new_url
						with open(new_path, 'w', encoding='utf-8') as f:
							json.dump(data, f, ensure_ascii=False, indent=2)
						if old_path == self.filepath:
							self.channel_identifier = new_name_safe
							self.filepath = new_path
							self.url = new_url
						ui.message(_("Channel updated."))
					except Exception as e:
						log(f"Edit error: {e}")
						ui.message(_("Error updating channel."))
				else:
					try:
						with open(old_path, 'r', encoding='utf-8') as f:
							data = json.load(f)
						data['channel_url'] = new_url
						with open(old_path, 'w', encoding='utf-8') as f:
							json.dump(data, f, ensure_ascii=False, indent=2)
						if old_path == self.filepath:
							self.url = new_url
						ui.message(_("Channel URL updated."))
					except Exception as e:
						log(f"Edit error: {e}")
						ui.message(_("Error updating channel URL."))
				self._populate_channel_combo()
		dlg.Destroy()

	def _on_delete_channel(self, name):
		if self._closing:
			return
		path = None
		for i in range(self.channelCombo.GetCount()):
			if self.channelCombo.GetString(i) == name:
				path = self.channelCombo.GetClientData(i)
				break
		if not path:
			return

		dlg = wx.MessageDialog(self, _("Are you sure you want to delete saved data for '{name}'?").format(name=name),
							   _("Confirm Delete"), wx.YES_NO | wx.ICON_QUESTION)
		if dlg.ShowModal() == wx.ID_YES:
			try:
				os.remove(path)
				log(f"Deleted {path}")
				update_pinned_after_delete(name)
				self.pinned = load_pinned_order()
				self._populate_channel_combo()
				if path == self.filepath:
					self.videos = []
					self._refresh_display(reset_page=True)
					self.status_label.SetLabel(_("Channel deleted."))
					self.url = None
					self.filepath = get_channel_filepath(self.channel_identifier)
				ui.message(_("Channel deleted."))
			except Exception as e:
				log(f"Delete error: {e}")
				ui.message(_("Error deleting channel."))
		dlg.Destroy()

	def _load_from_file(self):
		if self._closing:
			return
		try:
			with open(self.filepath, 'r', encoding='utf-8') as f:
				data = json.load(f)
			if not self.url and data.get('channel_url'):
				self.url = data['channel_url']
			self.videos = data.get('videos', [])
			saved_type = data.get('content_type')
			if saved_type and saved_type in self.content_type_map:
				self.content_type = saved_type
				self.typeCombo.SetStringSelection(self.content_type_map[self.content_type][1])
			for v in self.videos:
				if 'title_finalized' not in v:
					v['title_finalized'] = False
			self._fix_channel_url_if_needed()
			self._refresh_display(reset_page=True)
			self.status_label.SetLabel(_("Loaded {count} videos from cache.").format(count=len(self.videos)))
			self._start_background_title_fetch()
		except Exception as e:
			log(f"Error loading {self.filepath}: {e}")
			self.status_label.SetLabel(_("Error loading cache."))

	def _save_videos(self, immediate=False):
		if self._closing:
			return
		if immediate:
			if self._save_timer:
				self._save_timer.Stop()
				self._save_timer = None
			with self._save_lock:
				save_channel_videos(self.filepath, self.videos, self.url, self.content_type)
			self._save_pending = False
		else:
			if not self._save_pending:
				self._save_pending = True
				if self._save_timer:
					self._save_timer.Stop()
				self._save_timer = wx.CallLater(2000, self._save_videos, True)

	def _start_beep(self):
		if self._closing or self._beep_active:
			return
		self._beep_active = True
		self._beep_thread = threading.Thread(target=self._beep_loop, daemon=True)
		self._bg_threads.append(self._beep_thread)
		self._beep_thread.start()

	def _stop_beep(self):
		self._beep_active = False

	def _beep_loop(self):
		while self._beep_active and not self._closing:
			tones.beep(440, 100)
			time.sleep(2)

	def _fetch_and_save_channel(self, url, name_safe, filepath, content_type="videos"):
		def worker():
			log(f"Fetching new channel: {url} -> {filepath} (type={content_type})")

			wx.CallAfter(self._start_beep)

			if not os.path.exists(YouTubeEXE):
				wx.CallAfter(self._stop_beep)
				wx.CallAfter(ui.message, _("yt-dlp.exe not found."))
				return

			base_url = get_base_channel_url(url)
			if not base_url:
				base_url = url

			if content_type == "playlists":
				fetch_url = f"{base_url}/playlists"
			elif content_type == "shorts":
				fetch_url = f"{base_url}/shorts"
			elif content_type == "streams":
				fetch_url = f"{base_url}/streams"
			elif content_type == "podcasts":
				fetch_url = f"{base_url}/podcasts"
			else:
				fetch_url = f"{base_url}/videos"

			cmd = [
				YouTubeEXE,
				"--flat-playlist",
				"--dump-json",
				"--ignore-errors",
				"--no-warnings",
				"--quiet",
				"--extractor-args", "youtubetab:max_results=999999,youtubetab:lang=th,youtube:lang=th",
				fetch_url
			]

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

				new_items = []
				for line in process.stdout:
					if self._closing or self._stop_fetch:
						process.terminate()
						return
					if line.strip():
						try:
							info = json.loads(line)
							if content_type == "playlists":
								playlist_url = info.get('webpage_url') or info.get('url')
								playlist_title = info.get('title', 'Untitled Playlist')
								item = {
									'is_playlist': True,
									'url': playlist_url,
									'title': playlist_title,
									'duration': '',
									'title_finalized': True
								}
							else:
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
								item = {
									'is_playlist': False,
									'url': video_url,
									'title': title,
									'duration': duration_str,
									'title_finalized': False
								}
							new_items.append(item)
						except json.JSONDecodeError:
							continue

				stderr = process.stderr.read()
				if stderr:
					log(f"yt-dlp stderr: {stderr}")

				if new_items and not self._closing:
					save_channel_videos(filepath, new_items, url, content_type)
					wx.CallAfter(self._on_channel_added, name_safe, filepath, url, new_items, content_type)
					wx.CallAfter(ui.message, _("Channel added successfully."))
				elif not self._closing:
					wx.CallAfter(self._show_info_message, _("No items found for this URL."))
			except Exception as e:
				log(f"Error fetching channel: {e}")
				if not self._closing:
					wx.CallAfter(self._show_info_message, _("Error fetching channel: {str}").format(str=str(e)))
			finally:
				if not self._closing:
					wx.CallAfter(self._stop_beep)

		thread = threading.Thread(target=worker, daemon=True)
		self._bg_threads.append(thread)
		thread.start()

	def _show_info_message(self, msg):
		if self._closing:
			return
		self.status_label.SetLabel(msg)
		ui.message(msg)

	def _on_channel_added(self, name_safe, filepath, url, items, content_type):
		if self._closing:
			return
		self.pinned = load_pinned_order()
		self._populate_channel_combo()
		index = self.channelCombo.FindString(name_safe)
		if index != wx.NOT_FOUND:
			self.channelCombo.SetSelection(index)
			try:
				with open(filepath, 'r', encoding='utf-8') as f:
					data = json.load(f)
				self.url = data.get('channel_url')
				self.videos = data.get('videos', [])
				self.content_type = data.get('content_type', content_type)
				self.typeCombo.SetStringSelection(self.content_type_map[self.content_type][1])
				self._refresh_display(reset_page=True)
				self.status_label.SetLabel(_("Loaded {count} videos from {name}.").format(
					count=len(self.videos), name=name_safe))
				self.channel_identifier = name_safe
				self.filepath = filepath
				self._fetch_complete = True
				self._is_fetching = False
				self._start_background_title_fetch()
			except Exception as e:
				log(f"Error loading new channel: {e}")

	def _start_fetch(self, silent=False):
		if self._closing or not self.url or self._is_fetching:
			return
		self._is_fetching = True
		self._fetch_complete = False
		self._auto_save_pending = False
		self.status_label.SetLabel(_("Checking for new videos...") if silent else _("Fetching channel videos..."))
		self._stop_fetch = False
		thread = threading.Thread(target=self._fetch_videos, args=(silent,), daemon=True)
		self._bg_threads.append(thread)
		thread.start()
		if not silent:
			self._start_beep()

	def _fetch_videos(self, silent):
		log(f"Fetching for content type: {self.content_type}")

		base_url = get_base_channel_url(self.url)
		if not base_url:
			wx.CallAfter(self._show_info_message, "Invalid channel URL")
			return

		if self.content_type == "playlists":
			fetch_url = f"{base_url}/playlists"
		elif self.content_type == "shorts":
			fetch_url = f"{base_url}/shorts"
		elif self.content_type == "streams":
			fetch_url = f"{base_url}/streams"
		elif self.content_type == "podcasts":
			fetch_url = f"{base_url}/podcasts"
		else:
			fetch_url = f"{base_url}/videos"

		log(f"Fetch URL: {fetch_url}")

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
			fetch_url
		]
		log(f"Running command: {cmd}")

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

			new_items = []
			for line in process.stdout:
				if self._closing or self._stop_fetch:
					process.terminate()
					return

				if line.strip():
					try:
						info = json.loads(line)
						if self.content_type == "playlists":
							playlist_url = info.get('webpage_url') or info.get('url')
							playlist_title = info.get('title', 'Untitled Playlist')
							item = {
								'is_playlist': True,
								'url': playlist_url,
								'title': playlist_title,
								'duration': '',
								'title_finalized': True
							}
						else:
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
							item = {
								'is_playlist': False,
								'url': video_url,
								'title': title,
								'duration': duration_str,
								'title_finalized': False
							}
						new_items.append(item)
					except json.JSONDecodeError:
						continue

			stderr = process.stderr.read()
			if stderr:
				log(f"yt-dlp stderr: {stderr}")

			if new_items and not self._closing:
				old_items = self.videos
				self.videos = merge_videos(old_items, new_items)
				wx.CallAfter(self._refresh_display, False)
				wx.CallAfter(self.status_label.SetLabel, _("Fetched {count} items total.").format(count=len(self.videos)))
				wx.CallAfter(self._save_videos, False)
				wx.CallAfter(self._start_background_title_fetch)
			elif not silent and not self._closing:
				wx.CallAfter(self._show_info_message, _("No items found."))
		except Exception as e:
			log(f"Exception in _fetch_videos: {e}")
			if not self._closing:
				wx.CallAfter(self._show_info_message, str(e))
		finally:
			if not silent and not self._closing:
				wx.CallAfter(self._stop_beep)
			self._is_fetching = False
			self._fetch_complete = True
			if self._auto_save_pending and self._pending_save_name and self._pending_save_path:
				wx.CallAfter(self._perform_save, self._pending_save_name, self._pending_save_path)

	def _show_info_message(self, msg):
		if self._closing:
			return
		self.status_label.SetLabel(msg)
		ui.message(msg)

	def _on_add_channel(self, event):
		if self._closing:
			return
		default_name = self.channel_identifier if self.channel_identifier != 'unknown' else ""
		default_url = self.initial_url if self.initial_url else ""
		dlg = AddChannelDialog(self, default_name, default_url)
		if dlg.ShowModal() == wx.ID_OK:
			name = dlg.name
			url = dlg.url
			name_safe = sanitize_filename(name)
			filepath = get_channel_filepath(name_safe)
			content_type = self.content_type

			if os.path.exists(filepath):
				confirm = wx.MessageDialog(self, _("A channel with this name already exists. Overwrite?"),
											_("Confirm Overwrite"), wx.YES_NO | wx.ICON_QUESTION)
				if confirm.ShowModal() != wx.ID_YES:
					confirm.Destroy()
					dlg.Destroy()
					return
				confirm.Destroy()

			ui.message(_("Fetching channel items..."))
			thread = threading.Thread(target=self._fetch_and_save_channel, args=(url, name_safe, filepath, content_type), daemon=True)
			self._bg_threads.append(thread)
			thread.start()

		dlg.Destroy()

	def _perform_save(self, name_safe, filepath):
		if self._closing:
			return
		save_channel_videos(filepath, self.videos, self.url, self.content_type)
		self.channel_identifier = name_safe
		self.filepath = filepath
		ui.message(_("Channel saved."))
		self._auto_save_pending = False
		self._pending_save_name = None
		self._pending_save_path = None

	def _start_background_auto_update(self):
		if self._closing:
			return
		thread = threading.Thread(target=self._background_auto_update, daemon=True)
		self._bg_threads.append(thread)
		thread.start()

	def _background_auto_update(self):
		files = get_all_channel_files()
		for name, filepath in files:
			if self._closing or self._stop_fetch:
				return
			if filepath == self.filepath:
				continue
			try:
				with open(filepath, 'r', encoding='utf-8') as f:
					data = json.load(f)
				channel_url = data.get('channel_url')
				videos = data.get('videos', [])
				content_type = data.get('content_type', 'videos')
				if not channel_url:
					continue

				base_url = get_base_channel_url(channel_url)
				if not base_url:
					continue

				if content_type == "playlists":
					fetch_url = f"{base_url}/playlists"
				elif content_type == "shorts":
					fetch_url = f"{base_url}/shorts"
				elif content_type == "streams":
					fetch_url = f"{base_url}/streams"
				elif content_type == "podcasts":
					fetch_url = f"{base_url}/podcasts"
				else:
					fetch_url = f"{base_url}/videos"

				cmd = [
					YouTubeEXE,
					"--flat-playlist",
					"--dump-json",
					"--ignore-errors",
					"--no-warnings",
					"--quiet",
					"--extractor-args", "youtubetab:max_results=999999,youtubetab:lang=th,youtube:lang=th",
					fetch_url
				]
				process = subprocess.Popen(
					cmd,
					stdout=subprocess.PIPE,
					stderr=subprocess.DEVNULL,
					text=True,
					encoding='utf-8',
					errors='replace',
					creationflags=subprocess.CREATE_NO_WINDOW
				)
				new_items = []
				for line in process.stdout:
					if self._closing or self._stop_fetch:
						process.terminate()
						return
					try:
						info = json.loads(line)
						if content_type == "playlists":
							playlist_url = info.get('webpage_url') or info.get('url')
							playlist_title = info.get('title', 'Untitled Playlist')
							item = {
								'is_playlist': True,
								'url': playlist_url,
								'title': playlist_title,
								'duration': '',
								'title_finalized': True
							}
						else:
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
							item = {
								'is_playlist': False,
								'url': video_url,
								'title': title,
								'duration': duration_str,
								'title_finalized': False
							}
						new_items.append(item)
					except:
						continue

				if new_items and not self._closing:
					merged = merge_videos(videos, new_items)
					if len(merged) != len(videos):
						save_channel_videos(filepath, merged, channel_url, content_type)
						log(f"Background update: {name} now has {len(merged)} items")

				time.sleep(5)
			except Exception as e:
				log(f"Background update error for {name}: {e}")

	def _on_char_hook(self, event):
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			self._stop_fetch = True
			self.Close()
		event.Skip()

	def _on_close(self, event):
		self._closing = True
		self._stop_fetch = True
		if self._save_timer:
			self._save_timer.Stop()
			self._save_timer = None
		self._save_videos(immediate=True)
		for thread in self._bg_threads:
			if thread and thread.is_alive():
				try:
					thread.join(timeout=0.5)
				except:
					pass
		try:
			flush_video_cache()
		except Exception:
			pass
		self.Destroy()

	def _on_cancel(self, event):
		self._stop_fetch = True
		self.Close()

	def _on_item_activated(self, event):
		if self._closing:
			return
		idx = event.GetIndex()
		page_indices = self._get_current_page_indices()
		if 0 <= idx < len(page_indices):
			video_idx = page_indices[idx]
			video = self.videos[video_idx]
			if video.get('is_playlist', False):
				playlist_url = video['url']
				playlist_title = video['title']
				def show_playlist_dialog():
					if self._closing:
						return
					try:
						gui.mainFrame.prePopup()
						dlg = PlaylistVideosDialog(gui.mainFrame, playlist_url, playlist_title, self.plugin)
						dlg.ShowModal()
						dlg.Destroy()
						gui.mainFrame.postPopup()
					except Exception as e:
						log(f"Error opening playlist dialog: {e}")
						ui.message(_("Error opening playlist."))
				wx.CallAfter(show_playlist_dialog)
			else:
				webbrowser.open(video['url'])

	def _on_list_context_menu(self, event):
		if self._closing:
			return
		selected_idx = self.list_ctrl.GetFirstSelected()
		if selected_idx == -1:
			return
		page_indices = self._get_current_page_indices()
		if selected_idx >= len(page_indices):
			return
		video_idx = page_indices[selected_idx]
		video = self.videos[video_idx]

		menu = wx.Menu()
		copy_item = menu.Append(wx.ID_ANY, _("Copy URL"))
		self.Bind(wx.EVT_MENU, lambda evt: self._on_copy_url(video_idx), copy_item)

		play_item = menu.Append(wx.ID_ANY, _("Open in browser"))
		self.Bind(wx.EVT_MENU, lambda evt: webbrowser.open(video['url']), play_item)

		if video.get('is_playlist', False):
			dl_playlist = menu.Append(wx.ID_ANY, _("Download entire playlist"))
			self.Bind(wx.EVT_MENU, lambda evt: self._download_playlist(video['url'], video['title']), dl_playlist)
		else:
			correct_item = menu.Append(wx.ID_ANY, _("Correct title now"))
			self.Bind(wx.EVT_MENU, lambda evt: self._on_correct_title_now(video_idx), correct_item)

			dl_mp3 = menu.Append(wx.ID_ANY, _("Download MP3"))
			self.Bind(wx.EVT_MENU, lambda evt: self._download_video(video_idx, "mp3"), dl_mp3)

			dl_mp4 = menu.Append(wx.ID_ANY, _("Download MP4"))
			self.Bind(wx.EVT_MENU, lambda evt: self._download_video(video_idx, "mp4"), dl_mp4)

			dl_wav = menu.Append(wx.ID_ANY, _("Download WAV"))
			self.Bind(wx.EVT_MENU, lambda evt: self._download_video(video_idx, "wav"), dl_wav)

		delete_item = menu.Append(wx.ID_ANY, _("Remove from list"))
		self.Bind(wx.EVT_MENU, lambda evt: self._on_remove_item(video_idx), delete_item)

		self.PopupMenu(menu)
		menu.Destroy()

	def _on_copy_url(self, video_idx):
		if self._closing:
			return
		url = self.videos[video_idx]['url']
		short_url = create_short_youtube_url(url)
		if short_url:
			api.copyToClip(short_url)
			ui.message(_("Short URL copied to clipboard"))
		else:
			api.copyToClip(url)
			ui.message(_("URL copied to clipboard"))

	def _download_playlist(self, playlist_url, playlist_title):
		if self._closing:
			return
		save_path = getINI("ResultFolder") or DownloadPath
		if hasattr(self.plugin, 'core_functions') and 'convertToMP' in self.plugin.core_functions:
			self.plugin.core_functions['convertToMP']("mp3", save_path, True, playlist_url, playlist_title)
			ui.message(_("Playlist download started."))
		else:
			ui.message(_("Download function not available."))

	def _download_video(self, video_idx, format_type):
		if self._closing:
			return
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

	def _on_correct_title_now(self, video_idx):
		if self._closing:
			return
		video = self.videos[video_idx]
		ui.message(_("Correcting title for selected video..."))
		def worker():
			if self._closing:
				return
			success = self._fetch_video_details(video)
			if success and not self._closing:
				wx.CallAfter(self._save_videos, False)
				wx.CallAfter(self._refresh_display, False)
				wx.CallAfter(ui.message, _("Title correction completed and locked."))
			elif not self._closing:
				wx.CallAfter(ui.message, _("Title correction failed."))
		threading.Thread(target=worker, daemon=True).start()

	def _on_remove_item(self, video_idx):
		if self._closing:
			return
		del self.videos[video_idx]
		self._save_videos(immediate=False)
		self._refresh_display(reset_page=False)
		ui.message(_("Item removed."))

	def get_selected_video_info(self):
		if self._closing:
			return None
		selected = self.list_ctrl.GetFirstSelected()
		if selected == -1:
			return None
		page_indices = self._get_current_page_indices()
		if selected >= len(page_indices):
			return None
		video_idx = page_indices[selected]
		vid = self.videos[video_idx]
		if vid.get('is_playlist', False):
			return (vid['url'], vid['title'])
		return (vid['url'], vid['title'])