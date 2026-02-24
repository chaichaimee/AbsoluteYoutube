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

# Import helper functions from new utils module
from .utils import getLinkURL, getLinkName

addonHandler.initTranslation()

AddOnSummary = _("Absolute YouTube")
AddOnName = "AbsoluteYoutube"

if sys.version_info.major >= 3 and sys.version_info.minor >= 10:
    AddOnPath = os.path.dirname(__file__)
else:
    AddOnPath = os.path.dirname(__file__)

sectionName = AddOnName

log = logging.getLogger("AbsoluteYoutube")


def initConfiguration():
    """Initialize configuration specifications for the addon"""
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
    }
    config.conf.spec[sectionName] = confspec


initConfiguration()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = AddOnSummary

    def __init__(self):
        """Initialize the AbsoluteYoutube plugin"""
        super().__init__()

        # Import core functions from Download_core
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
                YouTubeEXE,
                check_yt_dlp_update,
                add_failed_download,
                get_failed_downloads,
                remove_failed_download,
                clear_failed_downloads,
                load_failed_downloads,
                save_failed_downloads
            )
            self.core_functions = {
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
                'log': core_log,
                'check_yt_dlp_update': check_yt_dlp_update,
                'YouTubeEXE': YouTubeEXE,
                'add_failed_download': add_failed_download,
                'get_failed_downloads': get_failed_downloads,
                'remove_failed_download': remove_failed_download,
                'clear_failed_downloads': clear_failed_downloads,
                'load_failed_downloads': load_failed_downloads,
                'save_failed_downloads': save_failed_downloads
            }
        except ImportError as e:
            ui.message(_("Error importing core functions: {str}").format(str=str(e)))
            self.core_functions = {'log': lambda x: None}
            self.core_functions['log'](f"ImportError in Download_core: {e}")
            raise

        # Initialize folders, resume downloads, and start worker threads
        try:
            self.core_functions['log']("Initializing AbsoluteYoutube plugin")
            self.core_functions['initialize_folders']()
            wx.CallAfter(self.core_functions['resumeInterruptedDownloads'])
            wx.CallAfter(self.core_functions['start_worker_threads'])
            if config.conf[sectionName]["AutoUpdateYtDlp"]:
                wx.CallAfter(self._auto_update_yt_dlp)
            else:
                wx.CallAfter(self._check_for_yt_dlp_update)
        except Exception as e:
            ui.message(_("Error initializing AbsoluteYoutube: {str}").format(str=str(e)))
            self.core_functions['log'](f"Error during initialization: {e}")
            raise

        # Register settings panel
        try:
            from .Youtube_settings import AudioYoutubeDownloadPanel
            if AudioYoutubeDownloadPanel not in NVDASettingsDialog.categoryClasses:
                NVDASettingsDialog.categoryClasses.append(AudioYoutubeDownloadPanel)
        except ImportError as e:
            self.core_functions['log'](f"Error importing AudioYoutubeDownloadPanel: {e}")

        # Initialize trim dialog
        try:
            from .Trim import TrimDialog
            self.TrimDialog = TrimDialog
        except ImportError as e:
            self.core_functions['log'](f"Error importing TrimDialog: {e}")
            self.TrimDialog = None

        # Initialize download fail dialog
        try:
            from .downloadFail import DownloadFailDialog
            self.DownloadFailDialog = DownloadFailDialog
        except ImportError as e:
            self.core_functions['log'](f"Error importing DownloadFailDialog: {e}")
            self.DownloadFailDialog = None

        # Initialize tap detection variables
        self._tap_count = 0
        self._last_tap_time = 0
        self._tap_timer = None

    def terminate(self):
        """Clean up when the plugin is terminated"""
        try:
            from .Youtube_settings import AudioYoutubeDownloadPanel
            if AudioYoutubeDownloadPanel in NVDASettingsDialog.categoryClasses:
                NVDASettingsDialog.categoryClasses.remove(AudioYoutubeDownloadPanel)
        except Exception:
            pass
        try:
            self.core_functions['shutdown_workers']()
        except Exception as e:
            self.core_functions['log'](f"Error during shutdown: {e}")

    def _get_current_download_path(self):
        """Get the current download path from config or default"""
        return config.conf[sectionName]["ResultFolder"] or self.core_functions['DownloadPath']

    def _check_for_yt_dlp_update(self):
        """Check for yt-dlp updates and notify if a new version is available"""
        try:
            current_version, latest_version = self.core_functions['check_yt_dlp_update']()
            if current_version and latest_version and current_version != latest_version:
                ui.message(_("A new version of yt-dlp is available: {latest}. Current: {current}. Please update in settings.").format(
                    latest=latest_version, current=current_version
                ))
        except Exception as e:
            self.core_functions['log'](f"Error checking yt-dlp update: {e}")

    def _auto_update_yt_dlp(self):
        """Automatically update yt-dlp if a new version is available"""
        try:
            current_version, latest_version = self.core_functions['check_yt_dlp_update']()
            if current_version and latest_version and current_version != latest_version:
                self._download_and_replace_yt_dlp()
        except Exception as e:
            self.core_functions['log'](f"Error during auto-update of yt-dlp: {e}")
            ui.message(_("Error during auto-update of yt-dlp: {str}").format(str=str(e)))

    def _download_and_replace_yt_dlp(self):
        """Download and replace yt-dlp.exe with the latest version"""
        try:
            ui.message(_("Updating yt-dlp..."))
            req = urllib.request.Request(
                "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            temp_file = os.path.join(tempfile.gettempdir(), f"yt-dlp_{uuid.uuid4().hex}.exe")
            with urllib.request.urlopen(req) as response, open(temp_file, 'wb') as out_file:
                out_file.write(response.read())
            shutil.move(temp_file, self.core_functions['YouTubeEXE'])
            ui.message(_("yt-dlp updated successfully"))
            self.core_functions['log']("yt-dlp updated successfully")
        except Exception as e:
            ui.message(_("Update failed: {str}").format(str=str(e)))
            self.core_functions['log'](f"Error updating yt-dlp: {e}")

    def _get_url_for_download(self):
        """Get URL for download - from selected link or current page"""
        link_url = getLinkURL()
        if link_url and any(x in link_url.lower() for x in ["youtube.com", "youtu.be"]):
            return link_url, getLinkName(), True
        url = self.core_functions['getCurrentDocumentURL']()
        return url, None, False

    def _execute_tap_action(self):
        """Execute action based on tap count for download formats"""
        try:
            url, title, is_link = self._get_url_for_download()
            if not url:
                wx.CallAfter(ui.message, _("No YouTube URL found"))
                return
            if self._tap_count == 1:
                self.core_functions['PlayWave']('start')
                wx.CallAfter(ui.message, _("Download MP3"))
                self.core_functions['convertToMP']("mp3", self._get_current_download_path(), 
                                                  config.conf[sectionName]["PlaylistMode"], url, title)
            elif self._tap_count == 2:
                self.core_functions['PlayWave']('start')
                wx.CallAfter(ui.message, _("Download MP4"))
                self.core_functions['convertToMP']("mp4", self._get_current_download_path(), 
                                                  config.conf[sectionName]["PlaylistMode"], url, title)
            elif self._tap_count >= 3:
                self.core_functions['PlayWave']('start')
                wx.CallAfter(ui.message, _("Download WAV"))
                self.core_functions['convertToMP']("wav", self._get_current_download_path(), 
                                                  config.conf[sectionName]["PlaylistMode"], url, title)
        except Exception as e:
            self.core_functions['log'](f"Error in tap action: {e}")
        finally:
            self._tap_count = 0

    @script(description=_("Download MP3 (single tap), MP4 (double tap), or WAV (triple tap)"), gesture="kb:NVDA+y")
    def script_downloadMP3OrMP4OrWAV(self, gesture):
        """Handle download based on tap count (MP3, MP4, WAV)"""
        current_time = time.time()
        if current_time - self._last_tap_time > 0.4:
            self._tap_count = 0
            if self._tap_timer and self._tap_timer.IsRunning():
                self._tap_timer.Stop()
        self._tap_count += 1
        self._last_tap_time = current_time
        if self._tap_timer and self._tap_timer.IsRunning():
            self._tap_timer.Stop()
        self._tap_timer = wx.CallLater(300, self._execute_tap_action)

    @script(description=_("Open context menu (single tap) or download folder (double tap)"), gesture="kb:control+shift+y")
    def script_contextMenuOrOpenFolder(self, gesture):
        """Handle single tap: open context menu, double tap: open download folder"""
        current_time = time.time()
        if current_time - self._last_tap_time > 0.4:
            self._tap_count = 0
            if self._tap_timer and self._tap_timer.IsRunning():
                self._tap_timer.Stop()
        self._tap_count += 1
        self._last_tap_time = current_time
        if self._tap_timer and self._tap_timer.IsRunning():
            self._tap_timer.Stop()
        self._tap_timer = wx.CallLater(300, self._execute_context_action)

    def _execute_context_action(self):
        """Execute action based on tap count for context menu / open folder"""
        try:
            if self._tap_count == 1:
                self._openContextMenu()
            elif self._tap_count >= 2:
                path = self._get_current_download_path()
                if os.path.isdir(path):
                    try:
                        os.startfile(path)
                    except Exception:
                        ui.message(_("Error opening folder"))
                else:
                    ui.message(_("Invalid download folder"))
        except Exception as e:
            self.core_functions['log'](f"Error in context action: {e}")
        finally:
            self._tap_count = 0

    def _create_short_youtube_url(self, full_url):
        """Convert full YouTube URL to shortened youtu.be format"""
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

    def _copy_specific_short_url(self, url):
        """Helper to copy a specific URL as shortened YouTube URL."""
        if not url:
            ui.message(_("No YouTube URL found"))
            return
        if not any(x in url.lower() for x in ["youtube.com", "youtu.be"]):
            ui.message(_("Not a YouTube URL"))
            return
        short_url = self._create_short_youtube_url(url)
        if short_url:
            api.copyToClip(short_url)
            ui.message(_("Short URL copied to clipboard"))
        else:
            ui.message(_("Could not create shortened URL"))

    def _openContextMenu(self):
        """Open context menu with AbsoluteYoutube options"""
        # Capture URL at menu build time
        url_for_copy, title_for_copy, is_link = self._get_url_for_download()
        doc_url = self.core_functions['getCurrentDocumentURL']()
        is_youtube_doc = any(x in (doc_url or "").lower() for x in ["youtube.com", "youtu.be"])

        menu_items = []

        # Copy short URL item
        if url_for_copy and any(x in url_for_copy.lower() for x in ["youtube.com", "youtu.be"]):
            menu_items.append((_("Copy video Shorten URL"), lambda: self._copy_specific_short_url(url_for_copy)))

        # YouTube document specific items
        if is_youtube_doc:
            menu_items.append((_("Snapshot"), self._capture_snapshot))
            menu_items.append((_("Trim setting"), self._open_trim_dialog))

        # Always add Absolute YouTube setting
        menu_items.append((_("Absolute YouTube setting"), self._open_youtube_settings))

        # Download fail manager (conditionally enabled)
        failed_downloads = self.core_functions['load_failed_downloads']()
        failed_count = len(failed_downloads)
        menu_items.append((_("Download fail manager"), self._open_download_fail_dialog, failed_count > 0))

        # No sorting to preserve desired order

        menu = wx.Menu()

        for item in menu_items:
            if len(item) == 3:
                label, callback, enabled = item
                menu_item = menu.Append(wx.ID_ANY, label)
                menu_item.Enable(enabled)
            else:
                label, callback = item
                menu_item = menu.Append(wx.ID_ANY, label)

            menu.Bind(wx.EVT_MENU, lambda evt, cb=callback: core.callLater(0, cb), menu_item)

        def show_menu():
            try:
                focus = api.getFocusObject()
                if not focus:
                    ui.message(_("Cannot determine current context"))
                    return
                frame = wx.Frame(gui.mainFrame, -1, "", pos=(0, 0), size=(0, 0))
                try:
                    frame.Show()
                    frame.Raise()
                    frame.PopupMenu(menu)
                finally:
                    try:
                        frame.Destroy()
                    except:
                        pass
            except Exception as e:
                self.core_functions['log'](f"Error displaying context menu: {e}")
                ui.message(_("Error displaying context menu"))

        wx.CallAfter(show_menu)

    @script(description=_("Toggle playlist mode"), gesture="kb:NVDA+shift+y")
    def script_togglePlaylistMode(self, gesture):
        current_mode = config.conf[sectionName]["PlaylistMode"]
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
        self.core_functions['setINI']("MP3Quality", new_quality)
        ui.message(_("{quality} kbps").format(quality=new_quality))

    def _open_trim_dialog(self):
        url = self.core_functions['getCurrentDocumentURL']()
        if not url or ("youtube.com" not in url.lower() and "youtu.be" not in url.lower()):
            ui.message(_("You must be on a YouTube page to use this feature"))
            return
        self.core_functions['log']("Attempting to open Trim dialog")
        if not self.TrimDialog:
            ui.message(_("Error: Trim module not available"))
            self.core_functions['log']("TrimDialog not initialized")
            return
        url = None
        for _ in range(3):
            url = self.core_functions['getCurrentDocumentURL']()
            self.core_functions['log'](f"Retrieved URL: {url}")
            if url:
                break
            time.sleep(0.5)

        def show_dialog():
            try:
                gui.mainFrame.prePopup()
                self.core_functions['log'](f"Opening TrimDialog with URL: {url}")
                dlg = self.TrimDialog(gui.mainFrame, url or "")
                dlg.ShowModal()
                dlg.Destroy()
                gui.mainFrame.postPopup()
            except Exception as e:
                ui.message(_("Error opening trim dialog: {str}").format(str=str(e)))
                self.core_functions['log'](f"Error in trim dialog: {e}")

        wx.CallAfter(show_dialog)

    def _capture_snapshot(self):
        url = self.core_functions['getCurrentDocumentURL']()
        if not url or ("youtube.com" not in url.lower() and "youtu.be" not in url.lower()):
            ui.message(_("You must be on a YouTube page to use this feature"))
            return
        try:
            from .Snapshot import capture_snapshot
            path = self._get_current_download_path()
            capture_snapshot(url, path)
        except ImportError as e:
            self.core_functions['log'](f"Error importing Snapshot: {e}")
            ui.message(_("Error: Snapshot module not available"))

    def _open_youtube_settings(self):
        try:
            from .Youtube_settings import AudioYoutubeDownloadPanel
            wx.CallAfter(gui.mainFrame.popupSettingsDialog, NVDASettingsDialog, AudioYoutubeDownloadPanel)
        except ImportError as e:
            ui.message(_("Error importing settings panel: {str}").format(str=str(e)))
            self.core_functions['log'](f"Error importing AudioYoutubeDownloadPanel: {e}")
        except Exception as e:
            ui.message(_("Error opening settings dialog: {str}").format(str=str(e)))
            self.core_functions['log'](f"Error opening settings: {e}")

    def _open_download_fail_dialog(self):
        try:
            if not self.DownloadFailDialog:
                ui.message(_("Error: DownloadFail module not available"))
                return
            failed_downloads = self.core_functions['load_failed_downloads']()
            if not failed_downloads:
                ui.message(_("No failed downloads"))
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