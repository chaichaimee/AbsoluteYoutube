# downloadFail.py

import wx
import gui
import json
import os
import ui
from gui import guiHelper
import addonHandler

addonHandler.initTranslation()


class DownloadFailDialog(wx.Dialog):
	def __init__(self, parent):
		super().__init__(parent, title=_("Download Fail Manager - Absolute YouTube"), size=(600, 400))
		self.parent = parent

		try:
			from .Download_core import (
				getINI,
				DownloadPath,
				addDownloadToQueue,
				_download_queue,
				get_video_duration,
				log,
				YouTubeEXE,
				load_failed_downloads,
				save_failed_downloads
			)
			self.core_functions = {
				'getINI': getINI,
				'DownloadPath': DownloadPath,
				'addDownloadToQueue': addDownloadToQueue,
				'_download_queue': _download_queue,
				'get_video_duration': get_video_duration,
				'log': log,
				'YouTubeEXE': YouTubeEXE,
				'load_failed_downloads': load_failed_downloads,
				'save_failed_downloads': save_failed_downloads
			}
		except ImportError as e:
			ui.message(_("Error importing core functions: {str}").format(str=str(e)))
			self.core_functions = {'log': lambda x: None}
			self.core_functions['log'](f"ImportError in DownloadFailDialog: {e}")
			raise

		self.failed_downloads = self.core_functions['load_failed_downloads']()
		self.init_ui()
		self.update_list()
		self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)

	def on_char_hook(self, event):
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			self.EndModal(wx.ID_CANCEL)
			return
		event.Skip()

	def init_ui(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT)
		self.list_ctrl.InsertColumn(0, _("Video Title"), width=300)
		self.list_ctrl.InsertColumn(1, _("Duration"), width=100)
		self.list_ctrl.InsertColumn(2, _("URL"), width=200)
		mainSizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 5)

		button_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.delete_btn = wx.Button(self, label=_("&Delete Selected"))
		self.delete_btn.Bind(wx.EVT_BUTTON, self.on_delete_selected)
		button_sizer.Add(self.delete_btn, 0, wx.ALL, 5)

		self.download_selected_btn = wx.Button(self, label=_("&Download Selected"))
		self.download_selected_btn.Bind(wx.EVT_BUTTON, self.on_download_selected)
		button_sizer.Add(self.download_selected_btn, 0, wx.ALL, 5)

		self.download_all_btn = wx.Button(self, label=_("&Download All"))
		self.download_all_btn.Bind(wx.EVT_BUTTON, self.on_download_all)
		button_sizer.Add(self.download_all_btn, 0, wx.ALL, 5)

		self.clear_all_btn = wx.Button(self, label=_("&Clear All"))
		self.clear_all_btn.Bind(wx.EVT_BUTTON, self.on_clear_all)
		button_sizer.Add(self.clear_all_btn, 0, wx.ALL, 5)

		self.ok_btn = wx.Button(self, wx.ID_OK, label=_("&OK"))
		self.ok_btn.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_OK))
		button_sizer.Add(self.ok_btn, 0, wx.ALL, 5)

		self.cancel_btn = wx.Button(self, wx.ID_CANCEL, label=_("&Cancel"))
		self.cancel_btn.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CANCEL))
		button_sizer.Add(self.cancel_btn, 0, wx.ALL, 5)

		mainSizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

		self.list_ctrl.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
		self.SetSizer(mainSizer)
		self.CentreOnScreen()

	def update_list(self):
		self.list_ctrl.DeleteAllItems()
		self.failed_downloads = self.core_functions['load_failed_downloads']()
		for i, item in enumerate(self.failed_downloads):
			index = self.list_ctrl.InsertItem(i, str(item.get('title', _('Unknown'))))
			duration = item.get('duration', _('Unknown'))
			if duration != _('Unknown'):
				try:
					total_seconds = int(duration)
					hours = total_seconds // 3600
					minutes = (total_seconds % 3600) // 60
					seconds = total_seconds % 60
					duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
				except (ValueError, TypeError):
					duration_str = str(duration)
			else:
				duration_str = str(duration)
			self.list_ctrl.SetItem(index, 1, duration_str)
			self.list_ctrl.SetItem(index, 2, str(item.get('url', '')))

	def on_context_menu(self, event):
		if not self.failed_downloads:
			return
		selected_indices = []
		index = self.list_ctrl.GetFirstSelected()
		while index != -1:
			selected_indices.append(index)
			index = self.list_ctrl.GetNextSelected(index)

		menu = wx.Menu()
		if len(selected_indices) == 1:
			delete_item = menu.Append(wx.ID_ANY, _("Delete"))
			self.Bind(wx.EVT_MENU, self.create_delete_handler(selected_indices[0]), delete_item)
			download_item = menu.Append(wx.ID_ANY, _("Download file"))
			self.Bind(wx.EVT_MENU, self.create_download_handler(selected_indices[0]), download_item)
		elif len(selected_indices) > 1:
			delete_selected = menu.Append(wx.ID_ANY, _("Delete selected"))
			self.Bind(wx.EVT_MENU, self.on_delete_selected, delete_selected)
			download_selected = menu.Append(wx.ID_ANY, _("Download selected"))
			self.Bind(wx.EVT_MENU, self.on_download_selected, download_selected)

		menu.AppendSeparator()
		download_all = menu.Append(wx.ID_ANY, _("Download all"))
		self.Bind(wx.EVT_MENU, self.on_download_all, download_all)
		clear_all = menu.Append(wx.ID_ANY, _("Clear all"))
		self.Bind(wx.EVT_MENU, self.on_clear_all, clear_all)

		self.PopupMenu(menu)
		menu.Destroy()

	def create_delete_handler(self, idx):
		def handler(event):
			self.delete_item(idx)
		return handler

	def create_download_handler(self, idx):
		def handler(event):
			self.download_item(idx)
		return handler

	def delete_item(self, idx):
		if 0 <= idx < len(self.failed_downloads):
			del self.failed_downloads[idx]
			self.core_functions['save_failed_downloads'](self.failed_downloads)
			self.update_list()
			ui.message(_("Item deleted"))

	def download_item(self, idx):
		if 0 <= idx < len(self.failed_downloads):
			item = self.failed_downloads[idx]
			del self.failed_downloads[idx]
			self.core_functions['save_failed_downloads'](self.failed_downloads)
			self.start_download(item)
			self.update_list()

	def start_download(self, item):
		try:
			url = item.get('url', '')
			title = item.get('title', 'Unknown')
			format_type = item.get('format', 'mp3')
			save_path = self.core_functions['getINI']("ResultFolder") or self.core_functions['DownloadPath']
			if not os.path.exists(save_path):
				os.makedirs(save_path, exist_ok=True)
			output_template = os.path.join(save_path, "%(title)s.%(ext)s")
			if format_type == "mp3":
				cmd = [
					self.core_functions['YouTubeEXE'], "--no-playlist",
					"-x", "--audio-format", "mp3",
					"--audio-quality", str(self.core_functions['getINI']("MP3Quality")),
					"--ffmpeg-location", os.path.join(os.path.dirname(self.core_functions['YouTubeEXE']), "ffmpeg.exe"),
					"-o", output_template, "--ignore-errors", "--no-warnings", "--quiet", url
				]
			elif format_type == "wav":
				cmd = [
					self.core_functions['YouTubeEXE'], "--no-playlist",
					"-x", "--audio-format", "wav",
					"--audio-quality", "0",
					"--ffmpeg-location", os.path.join(os.path.dirname(self.core_functions['YouTubeEXE']), "ffmpeg.exe"),
					"-o", output_template, "--ignore-errors", "--no-warnings", "--quiet", url
				]
			else:
				cmd = [
					self.core_functions['YouTubeEXE'], "--no-playlist",
					"-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
					"--remux-video", "mp4",
					"--ffmpeg-location", os.path.join(os.path.dirname(self.core_functions['YouTubeEXE']), "ffmpeg.exe"),
					"-o", output_template, "--ignore-errors", "--no-warnings", "--quiet", url
				]
			download_obj = {
				"url": url, "title": title, "format": format_type,
				"path": save_path, "cmd": cmd, "is_playlist": False
			}
			download_id = self.core_functions['addDownloadToQueue'](download_obj)
			self.core_functions['_download_queue'].put(download_obj)
			ui.message(_("Download started for: {title}").format(title=title))
		except Exception as e:
			self.core_functions['log'](f"Error starting download for failed item: {e}")
			ui.message(_("Error starting download"))

	def on_delete_selected(self, event):
		selected_indices = []
		index = self.list_ctrl.GetFirstSelected()
		while index != -1:
			selected_indices.append(index)
			index = self.list_ctrl.GetNextSelected(index)
		if not selected_indices:
			ui.message(_("No items selected"))
			return
		for idx in sorted(selected_indices, reverse=True):
			if 0 <= idx < len(self.failed_downloads):
				del self.failed_downloads[idx]
		self.core_functions['save_failed_downloads'](self.failed_downloads)
		self.update_list()
		ui.message(_("Selected items deleted"))

	def on_download_selected(self, event):
		selected_indices = []
		index = self.list_ctrl.GetFirstSelected()
		while index != -1:
			selected_indices.append(index)
			index = self.list_ctrl.GetNextSelected(index)
		if not selected_indices:
			ui.message(_("No items selected"))
			return
		added_any = False
		for idx in sorted(selected_indices, reverse=True):
			if 0 <= idx < len(self.failed_downloads):
				item = self.failed_downloads[idx]
				del self.failed_downloads[idx]
				self.start_download(item)
				added_any = True
		if added_any:
			self.core_functions['save_failed_downloads'](self.failed_downloads)
			self.update_list()
			ui.message(_("Selected downloads started"))
		else:
			ui.message(_("No valid items selected"))

	def on_download_all(self, event):
		if not self.failed_downloads:
			ui.message(_("No failed downloads to process"))
			return
		items_to_download = self.failed_downloads[:]
		self.core_functions['save_failed_downloads']([])
		self.failed_downloads = []
		self.update_list()
		for item in items_to_download:
			self.start_download(item)
		wx.CallAfter(ui.message, _("All downloads started"))

	def on_clear_all(self, event):
		if not self.failed_downloads:
			ui.message(_("No failed downloads to clear"))
			return
		self.core_functions['save_failed_downloads']([])
		self.failed_downloads = []
		self.update_list()
		ui.message(_("All failed downloads cleared"))