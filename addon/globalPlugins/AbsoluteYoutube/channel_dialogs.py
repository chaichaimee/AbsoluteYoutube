# channel_dialogs.py

import wx
import ui
import addonHandler
from .Download_core import log, getINI, DownloadPath

addonHandler.initTranslation()


class VirtualVideoList(wx.ListCtrl):
	def __init__(self, parent, video_source_callback, filtered_indices_callback):
		style = wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VIRTUAL
		super().__init__(parent, style=style)
		self.InsertColumn(0, _("Title"), width=550)
		self.InsertColumn(1, _(" "), width=100)
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
			if video.get('is_playlist', False):
				return ''
			return video.get('duration', '')
		return ""


class AddChannelDialog(wx.Dialog):
	def __init__(self, parent, default_name="", default_url=""):
		super().__init__(parent, title=_("Add New Channel"), size=(500, 200))
		self.default_name = default_name
		self.default_url = default_url
		self.name = ""
		self.url = ""

		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		name_sizer = wx.BoxSizer(wx.HORIZONTAL)
		name_label = wx.StaticText(panel, label=_("Channel name:"))
		name_sizer.Add(name_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		self.name_ctrl = wx.TextCtrl(panel, value=default_name)
		name_sizer.Add(self.name_ctrl, 1, wx.ALL | wx.EXPAND, 5)
		sizer.Add(name_sizer, 0, wx.EXPAND)

		url_sizer = wx.BoxSizer(wx.HORIZONTAL)
		url_label = wx.StaticText(panel, label=_("Channel URL:"))
		url_sizer.Add(url_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		clipboard_url = self._get_clipboard_url()
		initial_url = clipboard_url if clipboard_url else default_url
		self.url_ctrl = wx.TextCtrl(panel, value=initial_url)
		url_sizer.Add(self.url_ctrl, 1, wx.ALL | wx.EXPAND, 5)
		sizer.Add(url_sizer, 0, wx.EXPAND)

		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		ok_btn = wx.Button(panel, wx.ID_OK, label=_("&OK"))
		ok_btn.Bind(wx.EVT_BUTTON, self.on_ok)
		cancel_btn = wx.Button(panel, wx.ID_CANCEL, label=_("&Cancel"))
		btn_sizer.Add(ok_btn, 0, wx.ALL, 5)
		btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
		sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER)

		panel.SetSizer(sizer)
		self.CentreOnParent()

	def _get_clipboard_url(self):
		try:
			if wx.TheClipboard.Open():
				data = wx.TextDataObject()
				if wx.TheClipboard.GetData(data):
					text = data.GetText().strip()
					if text:
						return text
		except Exception as e:
			log(f"Error reading clipboard: {e}")
		finally:
			wx.TheClipboard.Close()
		return ""

	def on_ok(self, event):
		self.name = self.name_ctrl.GetValue().strip()
		self.url = self.url_ctrl.GetValue().strip()
		if not self.name:
			ui.message(_("Please enter a channel name."))
			return
		if not self.url:
			ui.message(_("Please enter a channel URL."))
			return
		self.EndModal(wx.ID_OK)


class EditChannelDialog(wx.Dialog):
	def __init__(self, parent, current_name, current_url):
		super().__init__(parent, title=_("Edit Channel"), size=(500, 200))
		self.current_name = current_name
		if current_url is None:
			current_url = ""
		self.current_url = current_url
		self.new_name = ""
		self.new_url = ""

		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		name_sizer = wx.BoxSizer(wx.HORIZONTAL)
		name_label = wx.StaticText(panel, label=_("Channel name:"))
		name_sizer.Add(name_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		self.name_ctrl = wx.TextCtrl(panel, value=current_name)
		name_sizer.Add(self.name_ctrl, 1, wx.EXPAND)
		sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 5)

		url_sizer = wx.BoxSizer(wx.HORIZONTAL)
		url_label = wx.StaticText(panel, label=_("Channel URL:"))
		url_sizer.Add(url_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		self.url_ctrl = wx.TextCtrl(panel, value=current_url)
		url_sizer.Add(self.url_ctrl, 1, wx.EXPAND)
		sizer.Add(url_sizer, 0, wx.EXPAND | wx.ALL, 5)

		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		ok_btn = wx.Button(panel, wx.ID_OK, label=_("&OK"))
		ok_btn.Bind(wx.EVT_BUTTON, self.on_ok)
		cancel_btn = wx.Button(panel, wx.ID_CANCEL, label=_("&Cancel"))
		btn_sizer.Add(ok_btn, 0, wx.ALL, 5)
		btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
		sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

		panel.SetSizer(sizer)
		self.CentreOnParent()

	def on_ok(self, event):
		self.new_name = self.name_ctrl.GetValue().strip()
		self.new_url = self.url_ctrl.GetValue().strip()
		if not self.new_name:
			ui.message(_("Please enter a channel name."))
			return
		if not self.new_url:
			ui.message(_("Please enter a channel URL."))
			return
		self.EndModal(wx.ID_OK)


class DownloadAllFormatDialog(wx.Dialog):
	def __init__(self, parent):
		super().__init__(parent, title=_("Download All Videos"), size=(400, 300))
		self.format = "mp3"
		self.quality = 320

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

		quality_box = wx.StaticBox(panel, label=_("Audio Quality"))
		quality_sizer = wx.StaticBoxSizer(quality_box, wx.VERTICAL)
		choices = ["128 kbps", "192 kbps", "256 kbps", "320 kbps"]
		self.quality_combo = wx.ComboBox(panel, choices=choices, style=wx.CB_READONLY)
		self.quality_combo.SetStringSelection("320 kbps")
		quality_sizer.Add(self.quality_combo, 0, wx.EXPAND | wx.ALL, 5)
		sizer.Add(quality_sizer, 0, wx.EXPAND | wx.ALL, 5)

		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		start_btn = wx.Button(panel, wx.ID_OK, label=_("Start download"))
		start_btn.Bind(wx.EVT_BUTTON, self.on_start)
		cancel_btn = wx.Button(panel, wx.ID_CANCEL, label=_("Cancel"))
		btn_sizer.Add(start_btn, 0, wx.ALL, 5)
		btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
		sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

		panel.SetSizer(sizer)
		self.CentreOnParent()

		self.mp3_radio.Bind(wx.EVT_RADIOBUTTON, self.on_format_change)
		self.mp4_radio.Bind(wx.EVT_RADIOBUTTON, self.on_format_change)
		self.wav_radio.Bind(wx.EVT_RADIOBUTTON, self.on_format_change)
		self.on_format_change(None)

	def on_format_change(self, event):
		self.quality_combo.Enable(self.mp3_radio.GetValue())

	def on_start(self, event):
		if self.mp3_radio.GetValue():
			self.format = "mp3"
		elif self.mp4_radio.GetValue():
			self.format = "mp4"
		else:
			self.format = "wav"
		quality_str = self.quality_combo.GetStringSelection()
		if quality_str:
			self.quality = int(quality_str.split()[0])
		else:
			self.quality = 320
		self.EndModal(wx.ID_OK)