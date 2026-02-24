# Youtube_settings.py

import wx
import gui
import config
from gui.settingsDialogs import SettingsPanel
from gui import guiHelper
import os
import subprocess
import threading
import ui
import tempfile
import uuid
import urllib.request
import shutil
import addonHandler

addonHandler.initTranslation()

from .Download_core import YouTubeEXE, log

AddOnSummary = _("Absolute YouTube")
AddOnName = "AbsoluteYoutube"
sectionName = AddOnName


def getINI(key):
    """Get configuration value by key"""
    return config.conf[sectionName][key]


def setINI(key, value):
    """Set configuration value for a key"""
    config.conf[sectionName][key] = value


class AudioYoutubeDownloadPanel(SettingsPanel):
    title = AddOnSummary

    def makeSettings(self, settingsSizer):
        """Create the settings panel UI"""
        helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

        # Destination folder selection
        folderSizer = wx.StaticBoxSizer(wx.VERTICAL, self, label=_("Destination folder"))
        folderBox = folderSizer.GetStaticBox()
        folderHelper = guiHelper.BoxSizerHelper(self, sizer=folderSizer)
        browseText = _("&Browse...")
        dirDialogTitle = _("Select a directory")
        pathHelper = guiHelper.PathSelectionHelper(folderBox, browseText, dirDialogTitle)
        pathCtrl = folderHelper.addItem(pathHelper)
        self.folderPathCtrl = pathCtrl.pathControl

        current_result_folder = getINI("ResultFolder")
        if not current_result_folder:
            AppData = os.environ["APPDATA"]
            self.folderPathCtrl.SetValue(os.path.join(AppData, "AbsoluteYoutube"))
        else:
            self.folderPathCtrl.SetValue(current_result_folder)
        helper.addItem(folderSizer)

        # Beep while converting
        self.beepChk = helper.addItem(
            wx.CheckBox(self, label=_("&Beep while converting"))
        )
        self.beepChk.SetValue(getINI("BeepWhileConverting"))

        # Announce download completion
        self.sayCompleteChk = helper.addItem(
            wx.CheckBox(self, label=_("&Say download complete"))
        )
        self.sayCompleteChk.SetValue(getINI("SayDownloadComplete"))

        # MP3 quality selection
        qualityLabel = _("MP3 &quality (kbps):")
        self.qualityChoice = helper.addLabeledControl(
            qualityLabel,
            wx.Choice,
            choices=["320", "256", "192", "128"]
        )
        try:
            self.qualityChoice.SetSelection(
                ["320", "256", "192", "128"].index(str(getINI("MP3Quality")))
            )
        except ValueError:
            self.qualityChoice.SetSelection(0)

        # Use multi-part download
        self.multipartChk = helper.addItem(
            wx.CheckBox(self, label=_("Use download section"))
        )
        self.multipartChk.SetValue(getINI("UseMultiPart"))

        # Number of connections for multi-part download
        connectionsLabel = _("&Number of connections:")
        self.connectionsChoice = helper.addLabeledControl(
            connectionsLabel,
            wx.Choice,
            choices=[str(i) for i in range(1, 17)]
        )
        try:
            self.connectionsChoice.SetSelection(
                getINI("MultiPartConnections") - 1
            )
        except Exception:
            self.connectionsChoice.SetSelection(7)

        # Playlist mode
        self.playlistModeChk = helper.addItem(
            wx.CheckBox(self, label=_("Enable &playlist mode by default"))
        )
        self.playlistModeChk.SetValue(getINI("PlaylistMode"))

        # Skip existing files
        self.skipExistingChk = helper.addItem(
            wx.CheckBox(self, label=_("Skip existing files"))
        )
        self.skipExistingChk.SetValue(getINI("SkipExisting"))

        # Resume downloads on restart
        self.resumeOnRestartChk = helper.addItem(
            wx.CheckBox(self, label=_("Resume interrupted downloads on restart"))
        )
        self.resumeOnRestartChk.SetValue(getINI("ResumeOnRestart"))

        # Enable logging
        self.loggingChk = helper.addItem(
            wx.CheckBox(self, label=_("Enable &logging"))
        )
        self.loggingChk.SetValue(getINI("Logging"))

        # Max concurrent downloads
        maxDownloadsLabel = _("&Max concurrent downloads (1-4):")
        self.maxDownloadsSpin = helper.addLabeledControl(
            maxDownloadsLabel,
            wx.SpinCtrl,
            min=1, max=4
        )
        self.maxDownloadsSpin.SetValue(getINI("MaxConcurrentDownloads"))

        # --- Anti-Blocking Settings ---
        antiBlockSizer = wx.StaticBoxSizer(wx.VERTICAL, self, label=_("Anti-blocking settings"))
        antiBlockBox = antiBlockSizer.GetStaticBox()
        antiBlockHelper = guiHelper.BoxSizerHelper(self, sizer=antiBlockSizer)

        # Use cookies
        self.useCookiesChk = antiBlockHelper.addItem(
            wx.CheckBox(antiBlockBox, label=_("Use &cookies (recommended to avoid block)"))
        )
        self.useCookiesChk.SetValue(getINI("UseCookies"))

        # Cookies file picker
        cookiesSizer = wx.BoxSizer(wx.HORIZONTAL)
        cookiesLabel = wx.StaticText(antiBlockBox, label=_("Cookies &file:"))
        cookiesSizer.Add(cookiesLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.cookiesFilePicker = wx.FilePickerCtrl(
            antiBlockBox,
            style=wx.FLP_USE_TEXTCTRL | wx.FLP_OPEN | wx.FLP_FILE_MUST_EXIST
        )
        cookiesSizer.Add(self.cookiesFilePicker, 1, wx.EXPAND)

        # Help button for cookies
        self.cookiesHelpBtn = wx.Button(antiBlockBox, label=_("How to get cookies?"))
        cookiesSizer.Add(self.cookiesHelpBtn, 0, wx.LEFT, 5)
        antiBlockHelper.addItem(cookiesSizer)

        # Set initial cookies file path
        cookies_file = getINI("CookiesFile")
        if cookies_file and os.path.exists(cookies_file):
            self.cookiesFilePicker.SetPath(cookies_file)

        # Bind cookies help button
        self.cookiesHelpBtn.Bind(wx.EVT_BUTTON, self.on_cookies_help)

        # Custom user agent
        self.customUserAgentChk = antiBlockHelper.addItem(
            wx.CheckBox(antiBlockBox, label=_("Use &custom user agent"))
        )
        self.customUserAgentChk.SetValue(getINI("UseCustomUserAgent"))

        self.userAgentText = antiBlockHelper.addLabeledControl(
            _("User &agent:"),
            wx.TextCtrl
        )
        self.userAgentText.SetValue(getINI("CustomUserAgent") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # Throttle rate
        self.throttleRateSpin = antiBlockHelper.addLabeledControl(
            _("&Throttle rate (KB/s, 0=unlimited):"),
            wx.SpinCtrl,
            min=0, max=10000
        )
        self.throttleRateSpin.SetValue(getINI("ThrottleRate"))

        # Sleep between requests
        self.sleepRequestsSpin = antiBlockHelper.addLabeledControl(
            _("&Sleep between requests (seconds):"),
            wx.SpinCtrl,
            min=0, max=60
        )
        self.sleepRequestsSpin.SetValue(getINI("SleepBetweenRequests"))

        # Retry count
        self.retryCountSpin = antiBlockHelper.addLabeledControl(
            _("&Retry count:"),
            wx.SpinCtrl,
            min=1, max=20
        )
        self.retryCountSpin.SetValue(getINI("RetryCount"))

        # Fragment retries
        self.fragmentRetriesSpin = antiBlockHelper.addLabeledControl(
            _("Fragment &retries:"),
            wx.SpinCtrl,
            min=1, max=50
        )
        self.fragmentRetriesSpin.SetValue(getINI("FragmentRetries"))

        # Skip unavailable fragments
        self.skipUnavailableChk = antiBlockHelper.addItem(
            wx.CheckBox(antiBlockBox, label=_("Skip &unavailable fragments"))
        )
        self.skipUnavailableChk.SetValue(getINI("SkipUnavailableFragments"))

        # Use proxy
        self.useProxyChk = antiBlockHelper.addItem(
            wx.CheckBox(antiBlockBox, label=_("Use &proxy"))
        )
        self.useProxyChk.SetValue(getINI("UseProxy"))

        self.proxyText = antiBlockHelper.addLabeledControl(
            _("Proxy &URL:"),
            wx.TextCtrl
        )
        self.proxyText.SetValue(getINI("ProxyURL") or "")

        # Geo bypass
        self.geoBypassChk = antiBlockHelper.addItem(
            wx.CheckBox(antiBlockBox, label=_("&Geo bypass"))
        )
        self.geoBypassChk.SetValue(getINI("GeoBypass"))

        self.geoBypassCountryText = antiBlockHelper.addLabeledControl(
            _("Geo bypass &country:"),
            wx.TextCtrl
        )
        self.geoBypassCountryText.SetValue(getINI("GeoBypassCountry") or "US")

        # Force IPv4/IPv6
        self.forceIpv4Chk = antiBlockHelper.addItem(
            wx.CheckBox(antiBlockBox, label=_("Force I&Pv4"))
        )
        self.forceIpv4Chk.SetValue(getINI("ForceIpv4"))

        self.forceIpv6Chk = antiBlockHelper.addItem(
            wx.CheckBox(antiBlockBox, label=_("Force I&Pv6"))
        )
        self.forceIpv6Chk.SetValue(getINI("ForceIpv6"))

        # Mark as watched
        self.markWatchedChk = antiBlockHelper.addItem(
            wx.CheckBox(antiBlockBox, label=_("&Mark as watched"))
        )
        self.markWatchedChk.SetValue(getINI("MarkWatched"))

        # Reset to safe settings button
        self.resetSafeBtn = wx.Button(antiBlockBox, label=_("Reset to &safe settings (recommended if blocked)"))
        antiBlockHelper.addItem(self.resetSafeBtn)
        self.resetSafeBtn.Bind(wx.EVT_BUTTON, self.on_reset_safe_settings)

        helper.addItem(antiBlockSizer)

        # yt-dlp update section
        updateSizer = wx.StaticBoxSizer(wx.VERTICAL, self, label=_("yt-dlp Update"))
        updateBox = updateSizer.GetStaticBox()
        updateHelper = guiHelper.BoxSizerHelper(self, sizer=updateSizer)

        self.autoUpdateChk = updateHelper.addItem(
            wx.CheckBox(updateBox, label=_("Auto-update yt-dlp on startup"))
        )
        self.autoUpdateChk.SetValue(getINI("AutoUpdateYtDlp"))

        updateBtnSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.updateBtn = wx.Button(updateBox, label=_("Update yt-dlp now"))
        self.updateBtn.Bind(wx.EVT_BUTTON, self.on_update_yt_dlp)
        updateBtnSizer.Add(self.updateBtn, 0, wx.ALL, 5)

        self.updateStatusLabel = wx.StaticText(updateBox, label=_("Update status: Idle"))
        updateBtnSizer.Add(self.updateStatusLabel, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        updateHelper.addItem(updateBtnSizer)
        helper.addItem(updateSizer)

        # Bind events for enabling/disabling controls
        self.useCookiesChk.Bind(wx.EVT_CHECKBOX, self.on_use_cookies_changed)
        self.customUserAgentChk.Bind(wx.EVT_CHECKBOX, self.on_custom_user_agent_changed)
        self.useProxyChk.Bind(wx.EVT_CHECKBOX, self.on_use_proxy_changed)
        self.multipartChk.Bind(wx.EVT_CHECKBOX, self.on_multipart_changed)

        # Set initial states
        self.on_use_cookies_changed(None)
        self.on_custom_user_agent_changed(None)
        self.on_use_proxy_changed(None)
        self.on_multipart_changed(None)

    def on_cookies_help(self, event):
        """Show help dialog for getting cookies"""
        help_text = _(
            "How to get YouTube cookies:\n\n"
            "1. Install 'Get cookies.txt' extension in Chrome or Firefox\n"
            "2. Login to YouTube in your browser\n"
            "3. Click the extension icon and export cookies\n"
            "4. Save as cookies.txt and select it here\n\n"
            "Using cookies helps avoid blocks because YouTube sees you as a logged-in user."
        )
        wx.MessageBox(help_text, _("How to get cookies"), wx.OK | wx.ICON_INFORMATION)

    def on_reset_safe_settings(self, event):
        """Reset to safe settings to avoid blocks"""
        safe_settings = {
            "MaxConcurrentDownloads": 1,
            "UseMultiPart": False,
            "MultiPartConnections": 1,
            "ThrottleRate": 100,
            "SleepBetweenRequests": 10,
            "RetryCount": 3,
            "FragmentRetries": 10,
        }

        # Apply safe settings
        self.maxDownloadsSpin.SetValue(safe_settings["MaxConcurrentDownloads"])
        self.multipartChk.SetValue(safe_settings["UseMultiPart"])
        self.connectionsChoice.SetSelection(safe_settings["MultiPartConnections"] - 1)
        self.throttleRateSpin.SetValue(safe_settings["ThrottleRate"])
        self.sleepRequestsSpin.SetValue(safe_settings["SleepBetweenRequests"])
        self.retryCountSpin.SetValue(safe_settings["RetryCount"])
        self.fragmentRetriesSpin.SetValue(safe_settings["FragmentRetries"])

        ui.message(_("Reset to safe settings. Remember to use cookies for best results."))

    def on_use_cookies_changed(self, event):
        """Enable/disable cookies file picker"""
        enable = self.useCookiesChk.GetValue()
        self.cookiesFilePicker.Enable(enable)
        self.cookiesHelpBtn.Enable(enable)

    def on_custom_user_agent_changed(self, event):
        """Enable/disable custom user agent text field"""
        self.userAgentText.Enable(self.customUserAgentChk.GetValue())

    def on_use_proxy_changed(self, event):
        """Enable/disable proxy URL text field"""
        self.proxyText.Enable(self.useProxyChk.GetValue())

    def on_multipart_changed(self, event):
        """Enable/disable connections choice"""
        self.connectionsChoice.Enable(self.multipartChk.GetValue())

    def on_update_yt_dlp(self, event):
        """Handle manual yt-dlp update"""
        def update_thread():
            try:
                wx.CallAfter(self.updateStatusLabel.SetLabel, _("Update status: Updating..."))
                ui.message(_("Updating yt-dlp..."))
                req = urllib.request.Request(
                    "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                temp_file = os.path.join(tempfile.gettempdir(), f"yt-dlp_{uuid.uuid4().hex}.exe")
                with urllib.request.urlopen(req) as response, open(temp_file, 'wb') as out_file:
                    out_file.write(response.read())

                shutil.move(temp_file, YouTubeEXE)
                wx.CallAfter(self.updateStatusLabel.SetLabel, _("Update status: Update successful"))
                ui.message(_("yt-dlp updated successfully"))
                log("yt-dlp updated successfully")
            except Exception as e:
                wx.CallAfter(self.updateStatusLabel.SetLabel, _("Update status: Update failed: {str}").format(str=str(e)))
                ui.message(_("Update failed: {str}").format(str=str(e)))
                log(f"Error updating yt-dlp: {e}")

        threading.Thread(target=update_thread, daemon=True).start()

    def onSave(self):
        """Save settings to configuration"""
        folder = self.folderPathCtrl.GetValue().strip()
        if folder.endswith("\\"):
            folder = folder[:-1]
        if folder:
            if not os.path.isdir(folder):
                try:
                    os.makedirs(folder, exist_ok=True)
                except Exception:
                    ui.message(_("Failed to create the specified folder. Please select a valid folder."))
                    return
            setINI("ResultFolder", folder)
            setINI("BeepWhileConverting", self.beepChk.GetValue())
            setINI("SayDownloadComplete", self.sayCompleteChk.GetValue())
            setINI("MP3Quality", int(self.qualityChoice.GetStringSelection()))
            setINI("PlaylistMode", self.playlistModeChk.GetValue())
            setINI("SkipExisting", self.skipExistingChk.GetValue())
            setINI("ResumeOnRestart", self.resumeOnRestartChk.GetValue())
            setINI("Logging", self.loggingChk.GetValue())
            setINI("UseMultiPart", self.multipartChk.GetValue())
            setINI("MultiPartConnections", int(self.connectionsChoice.GetStringSelection()))
            setINI("AutoUpdateYtDlp", self.autoUpdateChk.GetValue())
            setINI("MaxConcurrentDownloads", self.maxDownloadsSpin.GetValue())

            # Anti-blocking settings
            setINI("UseCookies", self.useCookiesChk.GetValue())
            setINI("CookiesFile", self.cookiesFilePicker.GetPath())
            setINI("UseCustomUserAgent", self.customUserAgentChk.GetValue())
            setINI("CustomUserAgent", self.userAgentText.GetValue())
            setINI("ThrottleRate", self.throttleRateSpin.GetValue())
            setINI("SleepBetweenRequests", self.sleepRequestsSpin.GetValue())
            setINI("RetryCount", self.retryCountSpin.GetValue())
            setINI("FragmentRetries", self.fragmentRetriesSpin.GetValue())
            setINI("SkipUnavailableFragments", self.skipUnavailableChk.GetValue())
            setINI("UseProxy", self.useProxyChk.GetValue())
            setINI("ProxyURL", self.proxyText.GetValue())
            setINI("GeoBypass", self.geoBypassChk.GetValue())
            setINI("GeoBypassCountry", self.geoBypassCountryText.GetValue())
            setINI("ForceIpv4", self.forceIpv4Chk.GetValue())
            setINI("ForceIpv6", self.forceIpv6Chk.GetValue())
            setINI("MarkWatched", self.markWatchedChk.GetValue())