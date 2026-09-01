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

from .Download_core import YouTubeEXE, log, PlayStartBeep, getAddonConfigBaseDir, _kill_process_tree

def _safeWidgetCall(func, *args, **kwargs):
	# A background thread's wx.CallAfter callback can still be pending
	# after the settings dialog (and its widgets) has already been
	# destroyed, e.g. the user pressed OK before an export/update finished.
	# Touching a destroyed wx widget then raises "wrapped C/C++ object of
	# type X has been deleted" as an unhandled exception in NVDA's log.
	# Swallowing just that failure here makes a late callback a no-op
	# instead of a crash.
	try:
		func(*args, **kwargs)
	except RuntimeError:
		pass

AddOnSummary = _("Absolute YouTube")
AddOnName = "AbsoluteYoutube"
sectionName = AddOnName


def getINI(key):
	return config.conf[sectionName][key]


def setINI(key, value):
	config.conf[sectionName][key] = value


def _isProcessRunning(processName):
	# A quick tasklist filter is simpler and more robust here than
	# duplicating a CreateToolhelp32Snapshot walk for a single yes/no
	# check that only runs once per button press.
	try:
		result = subprocess.run(
			["tasklist", "/FI", f"IMAGENAME eq {processName}", "/NH"],
			stdout=subprocess.PIPE,
			stderr=subprocess.DEVNULL,
			creationflags=subprocess.CREATE_NO_WINDOW,
			timeout=5
		)
		output = result.stdout.decode(errors="ignore")
		return processName.lower() in output.lower()
	except Exception as e:
		log(f"Error checking if {processName} is running: {e}")
		return False


class AudioYoutubeDownloadPanel(SettingsPanel):
	title = AddOnSummary

	def makeSettings(self, settingsSizer):
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

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

		# --- Download behavior -------------------------------------------------
		behaviorSizer = wx.StaticBoxSizer(wx.VERTICAL, self, label=_("Download Behavior"))
		behaviorBox = behaviorSizer.GetStaticBox()
		behaviorHelper = guiHelper.BoxSizerHelper(self, sizer=behaviorSizer)

		self.immediateChk = behaviorHelper.addItem(
			wx.CheckBox(behaviorBox, label=_("Start download immediately (NVDA+Y)"))
		)
		self.immediateChk.SetValue(getINI("ImmediateDownload"))

		self.playlistModeChk = behaviorHelper.addItem(
			wx.CheckBox(behaviorBox, label=_("Enable &playlist mode by default"))
		)
		self.playlistModeChk.SetValue(getINI("PlaylistMode"))

		self.skipExistingChk = behaviorHelper.addItem(
			wx.CheckBox(behaviorBox, label=_("Skip existing files"))
		)
		self.skipExistingChk.SetValue(getINI("SkipExisting"))

		self.resumeOnRestartChk = behaviorHelper.addItem(
			wx.CheckBox(behaviorBox, label=_("Resume interrupted downloads on restart"))
		)
		self.resumeOnRestartChk.SetValue(getINI("ResumeOnRestart"))

		self.loggingChk = behaviorHelper.addItem(
			wx.CheckBox(behaviorBox, label=_("Enable &logging"))
		)
		self.loggingChk.SetValue(getINI("Logging"))

		qualityLabel = _("MP3 &quality (kbps):")
		self.qualityChoice = behaviorHelper.addLabeledControl(
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

		maxDownloadsLabel = _("&Max concurrent downloads (1-4):")
		self.maxDownloadsSpin = behaviorHelper.addLabeledControl(
			maxDownloadsLabel,
			wx.SpinCtrl,
			min=1, max=4
		)
		self.maxDownloadsSpin.SetValue(getINI("MaxConcurrentDownloads"))

		helper.addItem(behaviorSizer)

		# --- Speed & connections ------------------------------------------------
		# Grouped together deliberately: multi-part/aria2c connections and
		# throttle rate both control how fast (or deliberately how slow) a
		# download runs, so they belong in one place rather than split
		# across unrelated sections.
		speedSizer = wx.StaticBoxSizer(wx.VERTICAL, self, label=_("Speed && Connections"))
		speedBox = speedSizer.GetStaticBox()
		speedHelper = guiHelper.BoxSizerHelper(self, sizer=speedSizer)

		self.multipartChk = speedHelper.addItem(
			wx.CheckBox(speedBox, label=_("Use download section"))
		)
		self.multipartChk.SetValue(getINI("UseMultiPart"))

		connectionsLabel = _("&Number of connections:")
		self.connectionsChoice = speedHelper.addLabeledControl(
			connectionsLabel,
			wx.Choice,
			choices=[str(i) for i in range(1, 17)]
		)
		try:
			self.connectionsChoice.SetSelection(
				getINI("MultiPartConnections") - 1
			)
		except Exception:
			self.connectionsChoice.SetSelection(15)

		# A plain SpinCtrl only steps by 1 per arrow press, and 10000
		# individual KB/s steps is a lot to dig through one at a time --
		# on_throttle_rate_changed below turns each arrow press into a
		# 5 KB/s jump instead, and also snaps any directly-typed value to
		# the nearest multiple of 5.
		self.throttleRateSpin = speedHelper.addLabeledControl(
			_("&Throttle rate (KB/s, 0=unlimited, step of 5):"),
			wx.SpinCtrl,
			min=0, max=10000
		)
		self.throttleRateSpin.SetValue(getINI("ThrottleRate"))
		self._lastThrottleValue = self.throttleRateSpin.GetValue()

		self.throttleMaxHelpLabel = wx.StaticText(
			speedBox,
			label=_(
				"At the maximum (10,000 KB/s = 10 MB/s), this limit essentially never "
				"binds -- YouTube's own per-connection serving speed and most home "
				"connections stay well under that, so the maximum behaves almost "
				"identically to leaving it at 0 (unlimited)."
			)
		)
		self.throttleMaxHelpLabel.Wrap(400)
		speedHelper.addItem(self.throttleMaxHelpLabel)

		self.sleepRequestsSpin = speedHelper.addLabeledControl(
			_("&Sleep between requests (seconds):"),
			wx.SpinCtrl,
			min=0, max=60
		)
		self.sleepRequestsSpin.SetValue(getINI("SleepBetweenRequests"))

		self.retryCountSpin = speedHelper.addLabeledControl(
			_("&Retry count:"),
			wx.SpinCtrl,
			min=1, max=20
		)
		self.retryCountSpin.SetValue(getINI("RetryCount"))

		self.fragmentRetriesSpin = speedHelper.addLabeledControl(
			_("Fragment &retries:"),
			wx.SpinCtrl,
			min=1, max=50
		)
		self.fragmentRetriesSpin.SetValue(getINI("FragmentRetries"))

		self.skipUnavailableChk = speedHelper.addItem(
			wx.CheckBox(speedBox, label=_("Skip &unavailable fragments"))
		)
		self.skipUnavailableChk.SetValue(getINI("SkipUnavailableFragments"))

		helper.addItem(speedSizer)

		# --- Sound & status announcements ---------------------------------------
		soundSizer = wx.StaticBoxSizer(wx.VERTICAL, self, label=_("Sound && Status Announcements"))
		soundBox = soundSizer.GetStaticBox()
		soundHelper = guiHelper.BoxSizerHelper(self, sizer=soundSizer)

		self.beepChk = soundHelper.addItem(
			wx.CheckBox(soundBox, label=_("&Beep while converting"))
		)
		self.beepChk.SetValue(getINI("BeepWhileConverting"))

		# Built manually (rather than via addLabeledControl) so both the
		# label and the control can be hidden together -- the volume
		# setting is meaningless with the beep off, and this control was
		# specifically asked to be hidden in that case, not just greyed
		# out.
		beepVolumeSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.beepVolumeLabel = wx.StaticText(soundBox, label=_("Beep &volume (%):"))
		self.beepVolumeSpin = wx.SpinCtrl(soundBox, min=0, max=100)
		self.beepVolumeSpin.SetValue(getINI("ConvertingBeepVolume"))
		self._lastBeepVolumeValue = self.beepVolumeSpin.GetValue()
		beepVolumeSizer.Add(self.beepVolumeLabel, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=guiHelper.SPACE_BETWEEN_ASSOCIATED_CONTROL_HORIZONTAL)
		beepVolumeSizer.Add(self.beepVolumeSpin)
		soundHelper.addItem(beepVolumeSizer)
		self.beepVolumeLabel.Show(self.beepChk.GetValue())
		self.beepVolumeSpin.Show(self.beepChk.GetValue())

		# Time-based heartbeat: beeps on this fixed interval for as long as
		# a download/conversion is running, independent of byte/percentage
		# progress tracking (which can be unreliable or unavailable for
		# some formats/sources). This is what actually keeps the beep
		# audible from start to finish rather than only at bucket changes.
		beepIntervalSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.beepIntervalLabel = wx.StaticText(soundBox, label=_("Beep e&very (seconds):"))
		self.beepIntervalSpin = wx.SpinCtrl(soundBox, min=1, max=120)
		self.beepIntervalSpin.SetValue(getINI("ProgressBeepIntervalSeconds"))
		beepIntervalSizer.Add(self.beepIntervalLabel, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=guiHelper.SPACE_BETWEEN_ASSOCIATED_CONTROL_HORIZONTAL)
		beepIntervalSizer.Add(self.beepIntervalSpin)
		soundHelper.addItem(beepIntervalSizer)
		self.beepIntervalLabel.Show(self.beepChk.GetValue())
		self.beepIntervalSpin.Show(self.beepChk.GetValue())

		self.sayCompleteChk = soundHelper.addItem(
			wx.CheckBox(soundBox, label=_("&Say download complete"))
		)
		self.sayCompleteChk.SetValue(getINI("SayDownloadComplete"))

		self.announceProgressChk = soundHelper.addItem(
			wx.CheckBox(soundBox, label=_("&Announce download progress"))
		)
		self.announceProgressChk.SetValue(getINI("AnnounceDownloadProgress"))

		helper.addItem(soundSizer)

		antiBlockSizer = wx.StaticBoxSizer(wx.VERTICAL, self, label=_("Anti-blocking settings"))
		antiBlockBox = antiBlockSizer.GetStaticBox()
		antiBlockHelper = guiHelper.BoxSizerHelper(self, sizer=antiBlockSizer)

		self.useCookiesChk = antiBlockHelper.addItem(
			wx.CheckBox(antiBlockBox, label=_("Use &cookies (recommended to avoid block)"))
		)
		self.useCookiesChk.SetValue(getINI("UseCookies"))

		cookiesSizer = wx.BoxSizer(wx.HORIZONTAL)
		cookiesLabel = wx.StaticText(antiBlockBox, label=_("Cookies &file:"))
		cookiesSizer.Add(cookiesLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		self.cookiesFilePicker = wx.FilePickerCtrl(
			antiBlockBox,
			style=wx.FLP_USE_TEXTCTRL | wx.FLP_OPEN | wx.FLP_FILE_MUST_EXIST
		)
		cookiesSizer.Add(self.cookiesFilePicker, 1, wx.EXPAND)

		self.cookiesHelpBtn = wx.Button(antiBlockBox, label=_("How to get cookies?"))
		cookiesSizer.Add(self.cookiesHelpBtn, 0, wx.LEFT, 5)
		antiBlockHelper.addItem(cookiesSizer)

		cookies_file = getINI("CookiesFile")
		if cookies_file and os.path.exists(cookies_file):
			self.cookiesFilePicker.SetPath(cookies_file)

		self.cookiesHelpBtn.Bind(wx.EVT_BUTTON, self.on_cookies_help)

		self._autoCookiesBrowserValues = ["chrome", "edge", "firefox", "brave", "opera"]
		autoCookiesBrowserLabels = [
			_("Google Chrome"), _("Microsoft Edge"), _("Mozilla Firefox"), _("Brave"), _("Opera")
		]
		self.autoCookiesBrowserChoice = antiBlockHelper.addLabeledControl(
			_("&Browser for automatic cookies (used when cookies file is off):"),
			wx.Choice,
			choices=autoCookiesBrowserLabels
		)
		storedAutoCookiesBrowser = getINI("AutoCookiesBrowser") or "chrome"
		try:
			self.autoCookiesBrowserChoice.SetSelection(self._autoCookiesBrowserValues.index(storedAutoCookiesBrowser))
		except ValueError:
			self.autoCookiesBrowserChoice.SetSelection(0)

		self.exportCookiesBtn = wx.Button(antiBlockBox, label=_("Export YouTube Cookies (Anti-Block)"))
		antiBlockHelper.addItem(self.exportCookiesBtn)
		self.exportCookiesBtn.Bind(wx.EVT_BUTTON, self.on_export_cookies)

		self.customUserAgentChk = antiBlockHelper.addItem(
			wx.CheckBox(antiBlockBox, label=_("Use &custom user agent"))
		)
		self.customUserAgentChk.SetValue(getINI("UseCustomUserAgent"))

		self.userAgentText = antiBlockHelper.addLabeledControl(
			_("User &agent:"),
			wx.TextCtrl
		)
		self.userAgentText.SetValue(getINI("CustomUserAgent") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

		self.useProxyChk = antiBlockHelper.addItem(
			wx.CheckBox(antiBlockBox, label=_("Use &proxy"))
		)
		self.useProxyChk.SetValue(getINI("UseProxy"))

		self.proxyText = antiBlockHelper.addLabeledControl(
			_("Proxy &URL:"),
			wx.TextCtrl
		)
		self.proxyText.SetValue(getINI("ProxyURL") or "")

		self.geoBypassChk = antiBlockHelper.addItem(
			wx.CheckBox(antiBlockBox, label=_("&Geo bypass"))
		)
		self.geoBypassChk.SetValue(getINI("GeoBypass"))

		self.geoBypassCountryText = antiBlockHelper.addLabeledControl(
			_("Geo bypass &country:"),
			wx.TextCtrl
		)
		self.geoBypassCountryText.SetValue(getINI("GeoBypassCountry") or "US")

		self.forceIpv4Chk = antiBlockHelper.addItem(
			wx.CheckBox(antiBlockBox, label=_("Force I&Pv4"))
		)
		self.forceIpv4Chk.SetValue(getINI("ForceIpv4"))

		self.forceIpv6Chk = antiBlockHelper.addItem(
			wx.CheckBox(antiBlockBox, label=_("Force I&Pv6"))
		)
		self.forceIpv6Chk.SetValue(getINI("ForceIpv6"))

		self.markWatchedChk = antiBlockHelper.addItem(
			wx.CheckBox(antiBlockBox, label=_("&Mark as watched"))
		)
		self.markWatchedChk.SetValue(getINI("MarkWatched"))

		self.resetSafeBtn = wx.Button(antiBlockBox, label=_("Reset to &safe settings (recommended if blocked)"))
		antiBlockHelper.addItem(self.resetSafeBtn)
		self.resetSafeBtn.Bind(wx.EVT_BUTTON, self.on_reset_safe_settings)

		helper.addItem(antiBlockSizer)

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

		self.useCookiesChk.Bind(wx.EVT_CHECKBOX, self.on_use_cookies_changed)
		self.customUserAgentChk.Bind(wx.EVT_CHECKBOX, self.on_custom_user_agent_changed)
		self.useProxyChk.Bind(wx.EVT_CHECKBOX, self.on_use_proxy_changed)
		self.multipartChk.Bind(wx.EVT_CHECKBOX, self.on_multipart_changed)
		self.beepChk.Bind(wx.EVT_CHECKBOX, self.on_beep_changed)
		self.throttleRateSpin.Bind(wx.EVT_SPINCTRL, self.on_throttle_rate_changed)
		self.beepVolumeSpin.Bind(wx.EVT_SPINCTRL, self.on_beep_volume_changed)

		self.on_use_cookies_changed(None)
		self.on_custom_user_agent_changed(None)
		self.on_use_proxy_changed(None)
		self.on_multipart_changed(None)

	def on_cookies_help(self, event):
		help_text = _(
			"How to get YouTube cookies:\n\n"
			"Option 1 (automatic): Use the 'Export YouTube Cookies (Anti-Block)' "
			"button below. Close your browser first, then press it and pick your "
			"browser from the list.\n\n"
			"Option 2 (manual):\n"
			"1. Install 'Get cookies.txt' extension in Chrome or Firefox\n"
			"2. Login to YouTube in your browser\n"
			"3. Click the extension icon and export cookies\n"
			"4. Save as cookies.txt and select it here\n\n"
			"Using cookies helps avoid blocks because YouTube sees you as a logged-in user."
		)
		wx.MessageBox(help_text, _("How to get cookies"), wx.OK | wx.ICON_INFORMATION)

	def on_export_cookies(self, event):
		browserLabels = [
			_("Google Chrome"), _("Microsoft Edge"), _("Mozilla Firefox"), _("Brave"), _("Opera")
		]
		browserValues = ["chrome", "edge", "firefox", "brave", "opera"]
		browserProcessNames = {
			"chrome": "chrome.exe",
			"edge": "msedge.exe",
			"firefox": "firefox.exe",
			"brave": "brave.exe",
			"opera": "opera.exe",
		}

		defaultIndex = self.autoCookiesBrowserChoice.GetSelection()
		if defaultIndex == wx.NOT_FOUND:
			defaultIndex = 0

		dialog = wx.SingleChoiceDialog(
			self,
			_(
				"Select the browser you are currently logged into YouTube with.\n"
				"Close that browser first if possible -- yt-dlp usually cannot read "
				"its cookie database while the browser is still running."
			),
			_("Export YouTube Cookies"),
			browserLabels
		)
		dialog.SetSelection(defaultIndex)
		if dialog.ShowModal() != wx.ID_OK:
			dialog.Destroy()
			return
		selectedBrowser = browserValues[dialog.GetSelection()]
		dialog.Destroy()

		if not os.path.exists(YouTubeEXE):
			ui.message(_("yt-dlp.exe missing"))
			return

		processName = browserProcessNames.get(selectedBrowser)
		if processName and _isProcessRunning(processName):
			proceed = wx.MessageBox(
				_(
					"{browser} appears to still be running. The cookie database is "
					"usually locked while the browser is open, so the export will "
					"likely fail with a database error.\n\n"
					"Close {browser} completely, then click OK to continue anyway "
					"or Cancel to stop and close it first."
				).format(browser=selectedBrowser),
				_("Browser still running"),
				wx.OK | wx.CANCEL | wx.ICON_WARNING
			)
			if proceed != wx.OK:
				return

		self.exportCookiesBtn.Enable(False)
		ui.message(_("Exporting cookies from {browser}...").format(browser=selectedBrowser))

		def export_thread():
			# stderr is captured to a temp file rather than subprocess.PIPE,
			# and process.wait() is used instead of subprocess.run(...,
			# timeout=X)/communicate(). communicate() hangs on Windows past
			# its own timeout if yt-dlp's browser-cookie step spawns a
			# grandchild that inherits the pipe's write handle and outlives
			# yt-dlp itself -- the reader thread never sees EOF. This is
			# what left export attempts stuck indefinitely (visible as a
			# thread still blocked in communicate() minutes later in the
			# NVDA freeze dump) instead of failing or succeeding promptly.
			stderrLogPath = None
			stderrLogFile = None
			process = None
			try:
				wx.CallAfter(PlayStartBeep)
				addonConfigDir = os.path.join(getAddonConfigBaseDir(), 'ChaiChaimee', 'AbsoluteYoutube')
				os.makedirs(addonConfigDir, exist_ok=True)
				cookiesPath = os.path.join(addonConfigDir, 'cookies.txt')
				command = [
					YouTubeEXE,
					"--cookies-from-browser", selectedBrowser,
					"--cookies", cookiesPath,
					"--skip-download",
					"https://www.youtube.com"
				]
				try:
					stderrFd, stderrLogPath = tempfile.mkstemp(prefix="ytdlp_cookies_stderr_", suffix=".log")
					stderrLogFile = os.fdopen(stderrFd, "wb")
				except Exception:
					stderrLogPath = None
					stderrLogFile = None
				process = subprocess.Popen(
					command,
					stdout=subprocess.DEVNULL,
					stderr=(stderrLogFile if stderrLogFile else subprocess.DEVNULL),
					stdin=subprocess.DEVNULL,
					creationflags=subprocess.CREATE_NO_WINDOW
				)
				if stderrLogFile:
					stderrLogFile.close()
				# 60s was too tight for some browser profiles (Firefox in
				# particular can take noticeably longer to read/decrypt its
				# cookie store) and was timing out before the process had
				# actually finished, now that we correctly bound the wait
				# instead of hanging forever on it.
				process.wait(timeout=120)
				errorText = ""
				if stderrLogPath:
					try:
						with open(stderrLogPath, "rb") as f:
							errorText = f.read().decode(errors="ignore").strip()
					except Exception:
						errorText = ""
				if process.returncode == 0 and os.path.exists(cookiesPath):
					wx.CallAfter(_safeWidgetCall, self._on_cookies_exported, cookiesPath)
				else:
					lowerErrorText = errorText.lower()
					# yt-dlp cannot copy a browser's cookie database while that
					# browser still holds the file open (see yt-dlp issue #7271),
					# which is by far the most common failure here -- surfacing
					# that cause directly saves a confusing round trip through
					# the raw yt-dlp error text.
					if "cookie database" in lowerErrorText:
						friendlyMessage = _(
							"Could not read the {browser} cookie database. Close {browser} "
							"completely and try exporting again."
						).format(browser=selectedBrowser)
					# A separate failure: newer Chrome-based browsers encrypt
					# cookies with App-Bound Encryption, which older yt-dlp
					# builds cannot decrypt via DPAPI (see yt-dlp issue
					# #10927). Closing the browser does not help here -- an
					# updated yt-dlp build or the manual export method is
					# needed instead, so this needs its own message rather
					# than falling into the generic "close the browser" one.
					elif "dpapi" in lowerErrorText:
						# Only Chromium-based browsers (chrome/edge/brave/opera) use
						# DPAPI/App-Bound Encryption for their cookie store -- Firefox
						# does not, so it is a genuine working alternative here rather
						# than a generic suggestion, and worth surfacing directly since
						# updating yt-dlp does not always resolve this in time.
						if selectedBrowser != "firefox":
							friendlyMessage = _(
								"Could not decrypt {browser}'s cookies (DPAPI decryption failed). "
								"This usually means yt-dlp needs updating to support this browser's "
								"newer cookie encryption. Try 'Update yt-dlp now' below, then export "
								"again, or export from Firefox instead, which does not use this "
								"encryption. If it still fails, use the manual cookies.txt method."
							).format(browser=selectedBrowser)
						else:
							friendlyMessage = _(
								"Could not decrypt {browser}'s cookies (DPAPI decryption failed). "
								"This usually means yt-dlp needs updating. Try 'Update yt-dlp now' "
								"below, then export again. If it still fails, use the manual "
								"cookies.txt method instead."
							).format(browser=selectedBrowser)
					else:
						lastLine = errorText.splitlines()[-1] if errorText else _("unknown error")
						friendlyMessage = _("Cookie export failed: {str}").format(str=lastLine)
					wx.CallAfter(ui.message, friendlyMessage)
					log(f"Cookie export failed for browser {selectedBrowser}: {errorText}")
			except subprocess.TimeoutExpired:
				if process:
					_kill_process_tree(process.pid)
					try:
						process.wait(timeout=5)
					except Exception:
						pass
				wx.CallAfter(ui.message, _("Cookie export timed out"))
				log(f"Cookie export timed out for browser {selectedBrowser}")
			except Exception as e:
				if process:
					_kill_process_tree(process.pid)
					try:
						process.wait(timeout=5)
					except Exception:
						pass
				wx.CallAfter(ui.message, _("Cookie export failed: {str}").format(str=str(e)))
				log(f"Error exporting cookies from {selectedBrowser}: {e}")
			finally:
				if stderrLogPath:
					try:
						os.remove(stderrLogPath)
					except Exception:
						pass
				wx.CallAfter(_safeWidgetCall, self.exportCookiesBtn.Enable, True)

		threading.Thread(target=export_thread, daemon=True).start()

	def _on_cookies_exported(self, cookiesPath):
		# Persist immediately rather than waiting for the panel's onSave --
		# a successful export should not be silently lost if this settings
		# dialog gets dismissed some other way (Escape, closing NVDA, etc.)
		# after the export, which was leaving CookiesFile/UseCookies unset
		# in config even though the file itself existed on disk.
		setINI("UseCookies", True)
		setINI("CookiesFile", cookiesPath)
		self.useCookiesChk.SetValue(True)
		self.cookiesFilePicker.SetPath(cookiesPath)
		self.on_use_cookies_changed(None)
		ui.message(_("Cookies exported successfully to {path}. Anti-blocking is now active.").format(path=cookiesPath))
		log(f"Cookies exported successfully to {cookiesPath}")

	def on_reset_safe_settings(self, event):
		safe_settings = {
			"MaxConcurrentDownloads": 1,
			"UseMultiPart": False,
			"MultiPartConnections": 1,
			"ThrottleRate": 100,
			"SleepBetweenRequests": 10,
			"RetryCount": 3,
			"FragmentRetries": 10,
		}
		self.maxDownloadsSpin.SetValue(safe_settings["MaxConcurrentDownloads"])
		self.multipartChk.SetValue(safe_settings["UseMultiPart"])
		self.connectionsChoice.SetSelection(safe_settings["MultiPartConnections"] - 1)
		self.throttleRateSpin.SetValue(safe_settings["ThrottleRate"])
		self.sleepRequestsSpin.SetValue(safe_settings["SleepBetweenRequests"])
		self.retryCountSpin.SetValue(safe_settings["RetryCount"])
		self.fragmentRetriesSpin.SetValue(safe_settings["FragmentRetries"])
		ui.message(_("Reset to safe settings. Remember to use cookies for best results."))

	def on_use_cookies_changed(self, event):
		enable = self.useCookiesChk.GetValue()
		self.cookiesFilePicker.Enable(enable)
		self.cookiesHelpBtn.Enable(enable)

	def on_custom_user_agent_changed(self, event):
		self.userAgentText.Enable(self.customUserAgentChk.GetValue())

	def on_use_proxy_changed(self, event):
		self.proxyText.Enable(self.useProxyChk.GetValue())

	def on_multipart_changed(self, event):
		self.connectionsChoice.Enable(self.multipartChk.GetValue())

	def on_beep_changed(self, event):
		show = self.beepChk.GetValue()
		self.beepVolumeLabel.Show(show)
		self.beepVolumeSpin.Show(show)
		self.beepIntervalLabel.Show(show)
		self.beepIntervalSpin.Show(show)
		self.Layout()

	def _snap_spin_to_step(self, spinCtrl, lastValueAttr, step, minValue, maxValue):
		value = spinCtrl.GetValue()
		previous = getattr(self, lastValueAttr, minValue)
		delta = value - previous
		# EVT_SPINCTRL fires identically for an arrow-button click and for
		# directly typing a new value into the edit field, with no clean
		# way to tell them apart from the event alone. Previously every
		# change was forced to move by exactly one step away from the old
		# value regardless of what was actually typed -- so typing "10"
		# when the previous value was 40 silently became 35 (one step
		# down from 40), never 10. Treating any change within one step of
		# the previous value as an arrow nudge (and snapping it cleanly to
		# the next step boundary) while treating a larger jump as a
		# direct edit -- and respecting exactly what was typed, clamped to
		# range -- fixes that without losing the clean-multiples-of-step
		# behavior arrow clicks are for.
		if abs(delta) <= step:
			if delta > 0:
				newValue = min(maxValue, previous + step)
			elif delta < 0:
				newValue = max(minValue, previous - step)
			else:
				newValue = value
			newValue = round(newValue / step) * step
		else:
			newValue = max(minValue, min(maxValue, value))
		spinCtrl.SetValue(newValue)
		setattr(self, lastValueAttr, newValue)

	def on_throttle_rate_changed(self, event):
		self._snap_spin_to_step(self.throttleRateSpin, "_lastThrottleValue", 5, 0, 10000)

	def on_beep_volume_changed(self, event):
		self._snap_spin_to_step(self.beepVolumeSpin, "_lastBeepVolumeValue", 5, 0, 100)

	def on_update_yt_dlp(self, event):
		def update_thread():
			try:
				wx.CallAfter(_safeWidgetCall, self.updateStatusLabel.SetLabel, _("Update status: Updating..."))
				ui.message(_("Updating yt-dlp..."))
				req = urllib.request.Request(
					"https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
					headers={'User-Agent': 'Mozilla/5.0'}
				)
				temp_file = os.path.join(tempfile.gettempdir(), f"yt-dlp_{uuid.uuid4().hex}.exe")
				with urllib.request.urlopen(req) as response, open(temp_file, 'wb') as out_file:
					out_file.write(response.read())
				shutil.move(temp_file, YouTubeEXE)
				wx.CallAfter(_safeWidgetCall, self.updateStatusLabel.SetLabel, _("Update status: Update successful"))
				ui.message(_("yt-dlp updated successfully"))
				log("yt-dlp updated successfully")
			except Exception as e:
				wx.CallAfter(_safeWidgetCall, self.updateStatusLabel.SetLabel, _("Update status: Update failed: {str}").format(str=str(e)))
				ui.message(_("Update failed: {str}").format(str=str(e)))
				log(f"Error updating yt-dlp: {e}")
		threading.Thread(target=update_thread, daemon=True).start()

	def onSave(self):
		# Guard clause: validate/create the destination folder first and
		# bail out early on failure, but do not let a folder problem stop
		# every other setting on this panel from being saved -- that was
		# the previous bug, where an unresolvable folder silently discarded
		# the whole form instead of just the folder field.
		folder = self.folderPathCtrl.GetValue().strip()
		if folder.endswith("\\"):
			folder = folder[:-1]
		if not folder:
			AppData = os.environ["APPDATA"]
			folder = os.path.join(AppData, "AbsoluteYoutube")
		if not os.path.isdir(folder):
			try:
				os.makedirs(folder, exist_ok=True)
			except Exception:
				ui.message(_("Failed to create the specified folder. Please select a valid folder."))
				return

		setINI("ResultFolder", folder)
		setINI("ImmediateDownload", self.immediateChk.GetValue())
		setINI("BeepWhileConverting", self.beepChk.GetValue())
		setINI("ConvertingBeepVolume", self.beepVolumeSpin.GetValue())
		setINI("ProgressBeepIntervalSeconds", self.beepIntervalSpin.GetValue())
		setINI("SayDownloadComplete", self.sayCompleteChk.GetValue())
		setINI("MP3Quality", int(self.qualityChoice.GetStringSelection()))
		setINI("PlaylistMode", self.playlistModeChk.GetValue())
		setINI("SkipExisting", self.skipExistingChk.GetValue())
		setINI("ResumeOnRestart", self.resumeOnRestartChk.GetValue())
		setINI("Logging", self.loggingChk.GetValue())
		setINI("UseMultiPart", self.multipartChk.GetValue())
		setINI("MultiPartConnections", int(self.connectionsChoice.GetStringSelection()))
		setINI("AnnounceDownloadProgress", self.announceProgressChk.GetValue())
		setINI("AutoUpdateYtDlp", self.autoUpdateChk.GetValue())
		setINI("MaxConcurrentDownloads", self.maxDownloadsSpin.GetValue())

		setINI("UseCookies", self.useCookiesChk.GetValue())
		setINI("CookiesFile", self.cookiesFilePicker.GetPath())
		autoCookiesIndex = self.autoCookiesBrowserChoice.GetSelection()
		if autoCookiesIndex != wx.NOT_FOUND:
			setINI("AutoCookiesBrowser", self._autoCookiesBrowserValues[autoCookiesIndex])
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

