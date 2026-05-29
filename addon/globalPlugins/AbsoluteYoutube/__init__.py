# __init__.py
# Copyright (C) 2026 Chai Chaimee
# Licensed under GNU General Public License. See COPYING.txt for details.

import globalPluginHandler
from scriptHandler import script
import ui
import gui
import wx
from gui.settingsDialogs import NVDASettingsDialog
import config
import addonHandler
import os
import time
import datetime
import re
import glob
import uuid
import shutil
import sys
import json
import urllib.request
import subprocess
import threading
import tempfile
import core
import api
import urllib.parse
import controlTypes
import logging

from .utils import (
	getLinkURL, getLinkName, is_youtube_url, is_youtube_video_url,
	is_channel_or_playlist_url, get_focused_youtube_link, remove_playlist_params,
	extract_video_id_from_url, is_youtube_homepage
)
from .channel_core import ChannelPlaylistDialog
from .channel_utils import ensure_channel_dir
from . import search
from .menu import showAbsoluteYoutubeMenu

addonHandler.initTranslation()

AddOnSummary = _("Absolute YouTube")
AddOnName = "AbsoluteYoutube"

AddOnPath = os.path.dirname(__file__)
ToolsPath = os.path.join(AddOnPath, "Tools")
YouTubeEXE = os.path.join(ToolsPath, "yt-dlp.exe")

sectionName = AddOnName

log = logging.getLogger("AbsoluteYoutube")

def initConfiguration():
	confspec = {
		"BeepWhileConverting": "boolean(default=True)",
		"ResultFolder": "string(default='')",
		"MP3Quality": "integer(default=320)",
		"TrimMP3Quality": "integer(default=320)",
		"Logging": "boolean(default=False)",
		"PlaylistMode": "boolean(default=False)",
		"SkipExisting": "boolean(default=True)",
		"ResumeOnRestart": "boolean(default=True)",
		"MaxConcurrentDownloads": "integer(default=1)",
		"TrimLastFormat": "string(default='mp3')",
		"TrimLastStartTime": "string(default='00:00:00')",
		"TrimLastEndTime": "string(default='00:00:00')",
		"TrimLastURL": "string(default='')",
		"TrimLastDuration": "string(default='')",
		"UseMultiPart": "boolean(default=True)",
		"MultiPartConnections": "integer(default=8)",
		"SayDownloadComplete": "boolean(default=True)",
		"AutoUpdateYtDlp": "boolean(default=False)",
		"UseCookies": "boolean(default=False)",
		"CookiesFile": "string(default='')",
		"UseCustomUserAgent": "boolean(default=False)",
		"CustomUserAgent": "string(default='')",
		"ThrottleRate": "integer(default=0)",
		"SleepBetweenRequests": "integer(default=0)",
		"RetryCount": "integer(default=3)",
		"FragmentRetries": "integer(default=10)",
		"SkipUnavailableFragments": "boolean(default=True)",
		"AbortOnError": "boolean(default=False)",
		"UseProxy": "boolean(default=False)",
		"ProxyURL": "string(default='')",
		"MarkWatched": "boolean(default=True)",
		"ForceIpv4": "boolean(default=False)",
		"ForceIpv6": "boolean(default=False)",
		"GeoBypass": "boolean(default=True)",
		"GeoBypassCountry": "string(default='US')",
		"GeoBypassIP": "string(default='')",
		"UseSponsorBlock": "boolean(default=False)",
		"SponsorBlockCategories": "string(default='all')",
		"ImmediateDownload": "boolean(default=True)",
	}
	config.conf.spec[sectionName] = confspec

initConfiguration()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = AddOnSummary

	def __init__(self):
		super().__init__()

		self.core_functions = {
			'log': lambda msg: log.info(msg),
			'YouTubeEXE': YouTubeEXE,
		}

		try:
			from .Download_core import (
				initialize_folders,
				resumeInterruptedDownloads,
				convertToMP,
				getCurrentDocumentURL,
				getCurrentAppName,
				DownloadPath,
				setINI,
				PlayWave,
				start_worker_threads,
				shutdown_workers,
				log as core_log,
				check_yt_dlp_update,
				add_failed_download,
				get_failed_downloads,
				remove_failed_download,
				clear_failed_downloads,
				load_failed_downloads,
				save_failed_downloads,
				add_pending_download,
				get_pending_downloads,
				remove_pending_download_by_index,
				clear_pending_downloads,
				get_pending_file_path,
				is_download_active,
				start_next_pending,
				getINI,
				addDownloadToQueue,
				_download_queue,
				ConverterEXE,
				Aria2cEXE
			)
			self.core_functions.update({
				'initialize_folders': initialize_folders,
				'resumeInterruptedDownloads': resumeInterruptedDownloads,
				'convertToMP': convertToMP,
				'getCurrentDocumentURL': getCurrentDocumentURL,
				'getCurrentAppName': getCurrentAppName,
				'DownloadPath': DownloadPath,
				'setINI': setINI,
				'PlayWave': PlayWave,
				'start_worker_threads': start_worker_threads,
				'shutdown_workers': shutdown_workers,
				'check_yt_dlp_update': check_yt_dlp_update,
				'add_failed_download': add_failed_download,
				'get_failed_downloads': get_failed_downloads,
				'remove_failed_download': remove_failed_download,
				'clear_failed_downloads': clear_failed_downloads,
				'load_failed_downloads': load_failed_downloads,
				'save_failed_downloads': save_failed_downloads,
				'add_pending_download': add_pending_download,
				'get_pending_downloads': get_pending_downloads,
				'remove_pending_download_by_index': remove_pending_download_by_index,
				'clear_pending_downloads': clear_pending_downloads,
				'get_pending_file_path': get_pending_file_path,
				'is_download_active': is_download_active,
				'start_next_pending': start_next_pending,
				'getINI': getINI,
				'addDownloadToQueue': addDownloadToQueue,
				'_download_queue': _download_queue,
				'ConverterEXE': ConverterEXE,
				'Aria2cEXE': Aria2cEXE,
			})
		except ImportError as e:
			ui.message(_("Error importing core functions: {str}").format(str=str(e)))
			self.core_functions['log'](f"ImportError in Download_core: {e}")

		if 'get_pending_file_path' not in self.core_functions:
			self.core_functions['log']("CRITICAL: get_pending_file_path missing from core_functions")
			ui.message(_("Add-on initialization failed: missing pending file path function. Please restart NVDA."))
		if 'getINI' not in self.core_functions:
			self.core_functions['log']("CRITICAL: getINI missing from core_functions")

		try:
			self.core_functions['log']("Initializing AbsoluteYoutube plugin")
			if 'initialize_folders' in self.core_functions:
				self.core_functions['initialize_folders']()
			ensure_channel_dir()
			if 'resumeInterruptedDownloads' in self.core_functions:
				wx.CallAfter(self.core_functions['resumeInterruptedDownloads'])
			if 'start_worker_threads' in self.core_functions:
				wx.CallAfter(self.core_functions['start_worker_threads'])
			if config.conf[sectionName]["AutoUpdateYtDlp"]:
				threading.Thread(target=self._auto_update_yt_dlp, daemon=True).start()
			else:
				threading.Thread(target=self._check_for_yt_dlp_update, daemon=True).start()
		except Exception as e:
			ui.message(_("Error initializing AbsoluteYoutube: {str}").format(str=str(e)))
			self.core_functions['log'](f"Error during initialization: {e}")

		self._add_settings_panel()

		try:
			from .Trim import TrimDialog
			self.TrimDialog = TrimDialog
		except ImportError as e:
			self.core_functions['log'](f"Error importing TrimDialog: {e}")
			self.TrimDialog = None

		try:
			from .downloadFail import DownloadFailDialog
			self.DownloadFailDialog = DownloadFailDialog
		except ImportError as e:
			self.core_functions['log'](f"Error importing DownloadFailDialog: {e}")
			self.DownloadFailDialog = None

		self._tap_count = 0
		self._last_tap_time = 0
		self._tap_timer = None
		self.channel_dialog = None
		self.search_dialog = None
		self.playlist_dialog = None
		self.download_list_dialog = None

	def _add_settings_panel(self):
		try:
			from .Youtube_settings import AudioYoutubeDownloadPanel
			if AudioYoutubeDownloadPanel not in NVDASettingsDialog.categoryClasses:
				NVDASettingsDialog.categoryClasses.append(AudioYoutubeDownloadPanel)
				self.core_functions['log']("Settings panel added successfully")
		except Exception as e:
			self.core_functions['log'](f"Failed to add settings panel: {e}")

	def terminate(self):
		try:
			from .Youtube_settings import AudioYoutubeDownloadPanel
			if AudioYoutubeDownloadPanel in NVDASettingsDialog.categoryClasses:
				NVDASettingsDialog.categoryClasses.remove(AudioYoutubeDownloadPanel)
		except Exception:
			pass
		try:
			if 'shutdown_workers' in self.core_functions:
				self.core_functions['shutdown_workers']()
		except Exception as e:
			self.core_functions['log'](f"Error during shutdown: {e}")

	def _get_current_download_path(self):
		return config.conf[sectionName]["ResultFolder"] or self.core_functions.get('DownloadPath', '')

	def _check_for_yt_dlp_update(self):
		try:
			if 'check_yt_dlp_update' not in self.core_functions:
				return
			current_version, latest_version = self.core_functions['check_yt_dlp_update']()
			if current_version and latest_version and current_version != latest_version:
				wx.CallAfter(ui.message, _("A new version of yt-dlp is available: {latest}. Current: {current}. Please update in settings.").format(
					latest=latest_version, current=current_version
				))
		except Exception as e:
			self.core_functions['log'](f"Error checking yt-dlp update: {e}")

	def _auto_update_yt_dlp(self):
		try:
			if 'check_yt_dlp_update' not in self.core_functions:
				return
			current_version, latest_version = self.core_functions['check_yt_dlp_update']()
			if current_version and latest_version and current_version != latest_version:
				self._download_and_replace_yt_dlp()
		except Exception as e:
			self.core_functions['log'](f"Error during auto-update of yt-dlp: {e}")
			wx.CallAfter(ui.message, _("Error during auto-update of yt-dlp: {str}").format(str=str(e)))

	def _download_and_replace_yt_dlp(self):
		try:
			wx.CallAfter(ui.message, _("Updating yt-dlp..."))
			req = urllib.request.Request(
				"https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
				headers={'User-Agent': 'Mozilla/5.0'}
			)
			temp_file = os.path.join(tempfile.gettempdir(), f"yt-dlp_{uuid.uuid4().hex}.exe")
			with urllib.request.urlopen(req) as response, open(temp_file, 'wb') as out_file:
				out_file.write(response.read())
			shutil.move(temp_file, YouTubeEXE)
			wx.CallAfter(ui.message, _("yt-dlp updated successfully"))
			self.core_functions['log']("yt-dlp updated successfully")
		except Exception as e:
			wx.CallAfter(ui.message, _("Update failed: {str}").format(str=str(e)))
			self.core_functions['log'](f"Error updating yt-dlp: {e}")

	def _get_page_title(self):
		try:
			title = api.getForegroundObject().name
			unwanted_suffixes = [" - YouTube", "| YouTube", " - Google Chrome", " - Brave", " - Microsoft Edge"]
			for suffix in unwanted_suffixes:
				title = title.replace(suffix, "")
			return title.strip()
		except Exception:
			return None

	def _is_on_youtube_video_page(self):
		doc_url = self.core_functions.get('getCurrentDocumentURL', lambda: None)()
		if doc_url and is_youtube_video_url(doc_url):
			return True
		url, _ = get_focused_youtube_link()
		if url and is_youtube_video_url(url):
			return True
		try:
			obj = api.getFocusObject()
			if obj.role == controlTypes.Role.DOCUMENT:
				acc_value = getattr(obj, 'value', None)
				if acc_value and is_youtube_video_url(acc_value):
					return True
		except Exception:
			pass
		return False

	def _get_url_for_download(self):
		if self.channel_dialog and self.channel_dialog.IsShown():
			focused = wx.Window.FindFocus()
			if focused and self.channel_dialog.IsDescendant(focused):
				info = self.channel_dialog.get_selected_video_info()
				if info:
					return info[0], info[1], False

		if self.search_dialog and self.search_dialog.IsShown():
			focused = wx.Window.FindFocus()
			if focused and self.search_dialog.IsDescendant(focused):
				info = self.search_dialog.get_selected_video_info()
				if info:
					return info[0], info[1], False

		if self.playlist_dialog and self.playlist_dialog.IsShown():
			focused = wx.Window.FindFocus()
			if focused and self.playlist_dialog.IsDescendant(focused):
				info = self.playlist_dialog.get_selected_video_info()
				if info:
					return info[0], info[1], False

		focused_url, focused_title = get_focused_youtube_link()
		doc_url = self.core_functions.get('getCurrentDocumentURL', lambda: None)()

		playlist_mode_enabled = config.conf[sectionName]["PlaylistMode"]

		is_focused_playlist = focused_url and ('list=' in focused_url or '/playlist?' in focused_url)
		is_current_page_playlist = doc_url and ('list=' in doc_url or '/playlist?' in doc_url)

		if playlist_mode_enabled and (is_focused_playlist or is_current_page_playlist):
			target_url = doc_url if is_current_page_playlist else focused_url
			page_title = self._get_page_title()
			title = page_title or focused_title or _("Playlist")
			return target_url, title, True

		if focused_url:
			return focused_url, focused_title, False

		if doc_url and is_youtube_url(doc_url):
			page_title = self._get_page_title()
			if page_title:
				return doc_url, page_title, False
			else:
				return doc_url, None, False

		return None, None, False

	def _execute_tap_action(self):
		try:
			url, title, is_playlist = self._get_url_for_download()
			if not url:
				wx.CallAfter(ui.message, _("No YouTube URL found"))
				return

			if not is_playlist and is_youtube_homepage(url):
				wx.CallAfter(ui.message, _("Cannot download from YouTube homepage. Please navigate to a video or playlist."))
				return
			if not is_playlist and url in ["https://www.youtube.com/feed/subscriptions", "https://www.youtube.com/feed/trending"]:
				wx.CallAfter(ui.message, _("Cannot download from this YouTube page. Please select a specific video."))
				return

			if self._tap_count == 1:
				chosen_format = "mp3"
			elif self._tap_count == 2:
				chosen_format = "mp4"
			else:
				chosen_format = "wav"

			immediate_mode = config.conf[sectionName]["ImmediateDownload"]

			final_title = title
			if not final_title:
				final_title = self._get_page_title()
			if not final_title:
				final_title = _("Unknown")

			if immediate_mode:
				active = self.core_functions.get('is_download_active', lambda: False)()
				if not active:
					self.core_functions.get('PlayWave', lambda x: None)('start')
					wx.CallAfter(ui.message, _("Starting download: {format} - {title}").format(format=chosen_format.upper(), title=final_title))
					self.core_functions['convertToMP'](chosen_format, self._get_current_download_path(), is_playlist, url, final_title)
				else:
					success = self.core_functions.get('add_pending_download', lambda *a: False)(url, final_title, chosen_format, is_playlist)
					if success:
						wx.CallAfter(ui.message, _("Added to download queue: {format} - {title}").format(format=chosen_format.upper(), title=final_title))
					else:
						wx.CallAfter(ui.message, _("Already in download queue"))
			else:
				success = self.core_functions.get('add_pending_download', lambda *a: False)(url, final_title, chosen_format, is_playlist)
				if success:
					wx.CallAfter(ui.message, _("Added to download list: {format} - {title}").format(format=chosen_format.upper(), title=final_title))
				else:
					wx.CallAfter(ui.message, _("Already in download list"))

		except Exception as e:
			self.core_functions['log'](f"Error in tap action: {e}")
		finally:
			self._tap_count = 0

	@script(description=_("Download or queue video (single tap MP3, double tap MP4, triple tap WAV)"), gesture="kb:NVDA+y")
	def script_downloadMP3OrMP4OrWAV(self, gesture):
		current_time = time.time()
		if current_time - self._last_tap_time > 0.6:
			self._tap_count = 0
			if self._tap_timer and self._tap_timer.IsRunning():
				self._tap_timer.Stop()
		self._tap_count += 1
		self._last_tap_time = current_time
		if self._tap_timer and self._tap_timer.IsRunning():
			self._tap_timer.Stop()
		self._tap_timer = wx.CallLater(500, self._execute_tap_action)

	@script(description=_("Open context menu (single tap), open download folder (double tap), open search dialog (triple tap)"), gesture="kb:control+shift+y")
	def script_contextMenuOrOpenFolder(self, gesture):
		current_time = time.time()
		if current_time - self._last_tap_time > 0.6:
			self._tap_count = 0
			if self._tap_timer and self._tap_timer.IsRunning():
				self._tap_timer.Stop()
		self._tap_count += 1
		self._last_tap_time = current_time
		if self._tap_timer and self._tap_timer.IsRunning():
			self._tap_timer.Stop()
		self._tap_timer = wx.CallLater(500, self._execute_context_action)

	def _execute_context_action(self):
		try:
			if self._tap_count == 1:
				self._openContextMenu()
			elif self._tap_count == 2:
				path = self._get_current_download_path()
				if os.path.isdir(path):
					try:
						os.startfile(path)
					except Exception:
						ui.message(_("Error opening folder"))
				else:
					ui.message(_("Invalid download folder"))
			elif self._tap_count >= 3:
				self._open_search_dialog(None)
		except Exception as e:
			self.core_functions['log'](f"Error in context action: {e}")
		finally:
			self._tap_count = 0

	@script(description=_("Download immediately"), gesture="kb:NVDA+control+y")
	def script_toggleImmediateDownload(self, gesture):
		current_mode = config.conf[sectionName]["ImmediateDownload"]
		new_mode = not current_mode
		config.conf[sectionName]["ImmediateDownload"] = new_mode
		if new_mode:
			ui.message(_("Immediate download mode enabled"))
		else:
			ui.message(_("Immediate download mode disabled"))

	def _open_channel_by_url(self, url):
		if not url:
			ui.message(_("Invalid channel URL"))
			return
		def show_dialog():
			try:
				gui.mainFrame.prePopup()
				dlg = ChannelPlaylistDialog(gui.mainFrame, url, self)
				self.channel_dialog = dlg
				dlg.ShowModal()
				self.channel_dialog = None
				gui.mainFrame.postPopup()
			except Exception as e:
				self.core_functions['log'](f"Error opening channel dialog: {e}")
				ui.message(_("Error opening channel dialog"))
		wx.CallAfter(show_dialog)

	def _create_short_youtube_url(self, full_url):
		try:
			parsed = urllib.parse.urlparse(full_url)
			params = urllib.parse.parse_qs(parsed.query)
			video_id = params.get('v', [None])[0]
			if not video_id:
				if "youtu.be" in full_url:
					path = parsed.path.lstrip('/')
					if path and '/' not in path:
						video_id = path
			if not video_id:
				return None
			short_url = f"https://youtu.be/{video_id}"
			parts = []
			if 'list' in params:
				parts.append(f"list={params['list'][0]}")
			if parts:
				short_url += "?" + "&".join(parts)
			return short_url
		except Exception as e:
			self.core_functions['log'](f"Error creating short URL: {e}")
			return None

	def _open_download_list_dialog(self, menuInstance):
		if menuInstance:
			menuInstance.Close()
		try:
			from .download_list import DownloadListDialog
			def show_dialog():
				try:
					gui.mainFrame.prePopup()
					dlg = DownloadListDialog(gui.mainFrame, self.core_functions)
					self.download_list_dialog = dlg
					dlg.ShowModal()
					self.download_list_dialog = None
					gui.mainFrame.postPopup()
				except Exception as e:
					ui.message(_("Error opening download list dialog: {str}").format(str=str(e)))
					self.core_functions['log'](f"Error in download list dialog: {e}")
			wx.CallAfter(show_dialog)
		except ImportError as e:
			self.core_functions['log'](f"Error importing download_list: {e}")
			ui.message(_("Error: Download list module not available"))

	def _buildMenuItemsForFrame(self):
		url_for_copy, title_for_copy, is_link = self._get_url_for_download()
		is_on_video_page = self._is_on_youtube_video_page()

		menu_items = []

		if url_for_copy and is_youtube_url(url_for_copy):
			menu_items.append((_("Copy video Shorten URL"), lambda: self._copy_specific_short_url(url_for_copy)))

		menu_items.append((_("Download list manager"), lambda: self._open_download_list_dialog(None)))

		failed_downloads = self.core_functions.get('load_failed_downloads', lambda: [])()
		if failed_downloads:
			menu_items.append((_("Download fail manager"), lambda: self._open_download_fail_dialog(None)))
		else:
			menu_items.append((_("Download fail manager (no failed)"), lambda: self._open_download_fail_dialog(None)))

		menu_items.append((_("Favorite channel"), lambda: self._open_channel_playlist_dialog(None)))

		if is_on_video_page:
			menu_items.append((_("Snapshot"), lambda: self._capture_snapshot()))
			menu_items.append((_("Trim setting"), lambda: self._open_trim_dialog()))

		menu_items.append((_("Search Youtube"), lambda: self._open_search_dialog(None)))

		menu_items.append((_("Absolute YouTube setting"), lambda: self._open_youtube_settings(None)))

		return menu_items

	def _openContextMenu(self):
		def showMenu():
			try:
				frame = wx.Frame(gui.mainFrame, -1, "", pos=(0,0), size=(0,0))
				frame.Show()
				frame.Raise()
				menu = wx.Menu()
				for label, callback in self._buildMenuItemsForFrame():
					menu_item = menu.Append(wx.ID_ANY, label)
					menu.Bind(wx.EVT_MENU, lambda evt, cb=callback: core.callLater(0, cb), menu_item)
				frame.PopupMenu(menu)
				menu.Destroy()
				frame.Destroy()
			except Exception as e:
				self.core_functions['log'](f"Error in context menu: {e}")
				ui.message(_("Error displaying context menu"))
		wx.CallAfter(showMenu)

	def _copy_specific_short_url(self, url):
		if not url:
			ui.message(_("No YouTube URL found"))
			return
		if not is_youtube_url(url):
			ui.message(_("Not a YouTube URL"))
			return
		short_url = self._create_short_youtube_url(url)
		if short_url:
			api.copyToClip(short_url)
			ui.message(_("Short URL copied to clipboard"))
		else:
			ui.message(_("Could not create shortened URL"))

	def _open_download_fail_dialog(self, menuInstance):
		if menuInstance:
			menuInstance.Close()
		failed_downloads = self.core_functions.get('load_failed_downloads', lambda: [])()
		if not failed_downloads:
			ui.message(_("No failed downloads"))
			return
		try:
			if not self.DownloadFailDialog:
				ui.message(_("Error: DownloadFail module not available"))
				return
			def show_dialog():
				try:
					gui.mainFrame.prePopup()
					dlg = self.DownloadFailDialog(gui.mainFrame)
					dlg.ShowModal()
					dlg.Destroy()
					gui.mainFrame.postPopup()
				except Exception as e:
					ui.message(_("Error opening download fail dialog: {str}").format(str=str(e)))
					self.core_functions['log'](f"Error in download fail dialog: {e}")
			wx.CallAfter(show_dialog)
		except Exception as e:
			ui.message(_("Error opening download fail dialog: {str}").format(str=str(e)))
			self.core_functions['log'](f"Error opening download fail dialog: {e}")

	def _open_channel_playlist_dialog(self, menuInstance):
		if menuInstance:
			menuInstance.Close()
		doc_url = self.core_functions.get('getCurrentDocumentURL', lambda: None)()
		link_url = getLinkURL()
		if doc_url and is_channel_or_playlist_url(doc_url):
			url = doc_url.split('?')[0]
			self._show_channel_dialog(url)
		elif link_url and is_youtube_video_url(link_url):
			self._show_channel_dialog(None)
		else:
			self._show_channel_dialog(None)

	def _capture_snapshot(self):
		url = self.core_functions.get('getCurrentDocumentURL', lambda: None)()
		if not url or not is_youtube_video_url(url):
			ui.message(_("You must be on a YouTube page to use this feature"))
			return
		try:
			from .Snapshot import capture_snapshot
			path = self._get_current_download_path()
			capture_snapshot(url, path)
		except ImportError as e:
			self.core_functions['log'](f"Error importing Snapshot: {e}")
			ui.message(_("Error: Snapshot module not available"))

	def _open_trim_dialog(self):
		url = self.core_functions.get('getCurrentDocumentURL', lambda: None)()
		if not url or not is_youtube_video_url(url):
			ui.message(_("You must be on a YouTube page to use this feature"))
			return
		self.core_functions['log']("Attempting to open Trim dialog")
		if not self.TrimDialog:
			ui.message(_("Error: Trim module not available"))
			self.core_functions['log']("TrimDialog not initialized")
			return
		def show_dialog():
			try:
				gui.mainFrame.prePopup()
				dlg = self.TrimDialog(gui.mainFrame, url)
				dlg.ShowModal()
				dlg.Destroy()
				gui.mainFrame.postPopup()
			except Exception as e:
				ui.message(_("Error opening trim dialog: {str}").format(str=str(e)))
				self.core_functions['log'](f"Error in trim dialog: {e}")
		wx.CallAfter(show_dialog)

	def _open_search_dialog(self, menuInstance):
		if menuInstance:
			menuInstance.Close()
		try:
			from .search import SearchDialog
			def show_dialog():
				try:
					gui.mainFrame.prePopup()
					dlg = SearchDialog(gui.mainFrame, self)
					self.search_dialog = dlg
					dlg.ShowModal()
					self.search_dialog = None
					dlg.Destroy()
					gui.mainFrame.postPopup()
				except Exception as e:
					ui.message(_("Error opening search dialog: {str}").format(str=str(e)))
					self.core_functions['log'](f"Error in search dialog: {e}")
			wx.CallAfter(show_dialog)
		except ImportError as e:
			self.core_functions['log'](f"Error importing search module: {e}")
			ui.message(_("Error: Search module not available"))

	def _open_youtube_settings(self, menuInstance):
		if menuInstance:
			menuInstance.Close()
		try:
			from .Youtube_settings import AudioYoutubeDownloadPanel
			self.core_functions['log']("Opening settings dialog for Absolute YouTube")
			wx.CallAfter(gui.mainFrame.popupSettingsDialog, NVDASettingsDialog, AudioYoutubeDownloadPanel)
		except ImportError as e:
			ui.message(_("Error importing settings panel: {str}").format(str=str(e)))
			self.core_functions['log'](f"Error importing AudioYoutubeDownloadPanel: {e}")
		except Exception as e:
			ui.message(_("Error opening settings dialog: {str}").format(str=str(e)))
			self.core_functions['log'](f"Error opening settings: {e}")

	def _get_channel_url_from_video(self, video_url):
		try:
			cmd = [YouTubeEXE, "--print", "channel_url", "--no-playlist", video_url]
			process = subprocess.run(
				cmd,
				capture_output=True,
				text=True,
				timeout=30,
				creationflags=subprocess.CREATE_NO_WINDOW
			)
			if process.returncode == 0:
				channel_url = process.stdout.strip()
				if channel_url:
					return channel_url
		except Exception as e:
			self.core_functions['log'](f"Error extracting channel URL from video: {e}")
		return None

	def _open_channel_from_video(self, video_url):
		def worker():
			channel_url = self._get_channel_url_from_video(video_url)
			wx.CallAfter(self._show_channel_dialog, channel_url)
		threading.Thread(target=worker, daemon=True).start()
		ui.message(_("Fetching channel information..."))

	def _show_channel_dialog(self, url=None):
		def show_dialog():
			try:
				gui.mainFrame.prePopup()
				dlg = ChannelPlaylistDialog(gui.mainFrame, url, self)
				self.channel_dialog = dlg
				dlg.ShowModal()
				self.channel_dialog = None
				gui.mainFrame.postPopup()
			except Exception as e:
				self.core_functions['log'](f"Error in channel/playlist dialog: {e}")
				ui.message(_("Error opening channel/playlist list: {str}").format(str=str(e)))
				if self.channel_dialog:
					self.channel_dialog = None
		wx.CallAfter(show_dialog)

	@script(description=_("Toggle playlist mode"), gesture="kb:NVDA+shift+y")
	def script_togglePlaylistMode(self, gesture):
		current_mode = config.conf[sectionName]["PlaylistMode"]
		if 'setINI' in self.core_functions:
			self.core_functions['setINI']("PlaylistMode", not current_mode)
		ui.message(_("Playlist mode enabled") if not current_mode else _("Playlist mode disabled"))

	@script(description=_("Cycle MP3 quality settings"), gesture="kb:alt+windows+y")
	def script_cycleMP3Quality(self, gesture):
		mp3_quality_cycle = [128, 192, 256, 320]
		current_quality = config.conf[sectionName]["MP3Quality"]
		try:
			current_index = mp3_quality_cycle.index(current_quality)
			new_index = (current_index + 1) % len(mp3_quality_cycle)
		except ValueError:
			new_index = 3
		new_quality = mp3_quality_cycle[new_index]
		if 'setINI' in self.core_functions:
			self.core_functions['setINI']("MP3Quality", new_quality)
		ui.message(_("{quality} kbps").format(quality=new_quality))