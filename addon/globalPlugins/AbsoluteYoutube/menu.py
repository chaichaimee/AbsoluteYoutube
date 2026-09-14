# menu.py

import wx
import addonHandler
import tones
from logHandler import log

addonHandler.initTranslation()

_instance = None

class AbsoluteYoutubeMenu(wx.Frame):
	def __init__(self, itemsFunc, configPath=None):
		super().__init__(None, title=_("Absolute Youtube"), size=(450, 400),
						 style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)
		self.itemsFunc = itemsFunc
		self.configPath = configPath
		self.currentItems = []

		panel = wx.Panel(self)
		vbox = wx.BoxSizer(wx.VERTICAL)

		self.listBox = wx.ListBox(panel, style=wx.LB_SINGLE)
		vbox.Add(self.listBox, 1, wx.EXPAND | wx.ALL, 10)
		panel.SetSizer(vbox)

		self.timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.onTimeout, self.timer)

		self.refreshList()

		self.listBox.Bind(wx.EVT_LISTBOX_DCLICK, self.onSelect)
		# EVT_CHAR_HOOK must be bound to the owning Frame, not a child
		# control -- binding it to self.listBox let IsDialogMessage swallow
		# Escape/Enter before onKey ever saw them, the same confirmed
		# failure mode already fixed elsewhere in this add-on's dialogs
		# (see downloadFail.py / download_list.py, which both bind it to
		# self).
		self.Bind(wx.EVT_CHAR_HOOK, self.onKey)

		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.Show()
		self.Raise()
		self.RequestUserAttention()
		self.timer.Start(15000)

	def refreshList(self):
		rawItems = self.itemsFunc()
		self.currentItems = rawItems
		self.listBox.Clear()
		for label, _callback in rawItems:
			self.listBox.Append(label)
		if self.listBox.GetCount() > 0:
			self.listBox.SetSelection(0)
		self.listBox.SetFocus()
		self.timer.Start(15000)

	def onSelect(self, event):
		self.timer.Start(15000)
		idx = self.listBox.GetSelection()
		if idx != wx.NOT_FOUND:
			callback = self.currentItems[idx][1]
			if callback is not None:
				callback(self)

	def onKey(self, event):
		self.timer.Start(15000)
		key = event.GetKeyCode()
		if key == wx.WXK_RETURN:
			idx = self.listBox.GetSelection()
			if idx != wx.NOT_FOUND:
				callback = self.currentItems[idx][1]
				if callback is not None:
					callback(self)
		elif key == wx.WXK_ESCAPE:
			self.Close()
		else:
			event.Skip()

	def onTimeout(self, event):
		tones.beep(100, 100)
		self.Close()

	def onClose(self, event):
		global _instance
		_instance = None
		self.Destroy()

def showAbsoluteYoutubeMenu(itemsFunc, configPath=None):
	global _instance
	if _instance:
		_instance.Raise()
		_instance.RequestUserAttention()
		_instance.timer.Start(15000)
	else:
		_instance = AbsoluteYoutubeMenu(itemsFunc, configPath)
