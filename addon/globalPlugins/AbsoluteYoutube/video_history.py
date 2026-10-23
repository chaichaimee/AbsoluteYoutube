# video_history.py

import os
import threading
import wx
import ui
import addonHandler
from .Download_core import (
	getINI,
	DownloadPath,
	log,
	convertToMP,
	load_video_history,
	remove_video_history_entries,
	toggle_video_history_pin,
	clear_video_history,
)

addonHandler.initTranslation()


def orderForDisplay(entries):
	pinned = [e for e in entries if e.get("pinned")]
	others = [e for e in entries if not e.get("pinned")]
	return pinned + others


class VideoHistoryDialog(wx.Dialog):
	def __init__(self, parent):
		super().__init__(parent, title=_("Video History Report - Absolute YouTube"), size=(760, 450))
		self.entries = []
		self.initUI()
		self.refreshList()
		self.Bind(wx.EVT_CHAR_HOOK, self.onCharHook)

	def initUI(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		self.listCtrl = wx.ListCtrl(self, style=wx.LC_REPORT)
		self.listCtrl.InsertColumn(0, _("Video Title"), width=340)
		self.listCtrl.InsertColumn(1, _("Format"), width=70)
		self.listCtrl.InsertColumn(2, _("Date"), width=140)
		self.listCtrl.InsertColumn(3, _("Pinned"), width=70)
		self.listCtrl.InsertColumn(4, _("URL"), width=260)
		mainSizer.Add(self.listCtrl, 1, wx.EXPAND | wx.ALL, 5)

		buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
		for label, handler in (
			(_("&Download"), self.onDownload),
			(_("&Open URL"), self.onOpenUrl),
			(_("&Pin or unpin"), self.onTogglePin),
			(_("&Remove"), self.onRemove),
			(_("Clear &all"), self.onClearAll),
		):
			button = wx.Button(self, label=label)
			button.Bind(wx.EVT_BUTTON, handler)
			buttonSizer.Add(button, 0, wx.ALL, 5)
		closeButton = wx.Button(self, wx.ID_CANCEL, label=_("C&lose"))
		closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CANCEL))
		buttonSizer.Add(closeButton, 0, wx.ALL, 5)
		mainSizer.Add(buttonSizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

		self.listCtrl.Bind(wx.EVT_CONTEXT_MENU, self.onContextMenu)
		self.SetSizer(mainSizer)
		self.CentreOnScreen()

	def onCharHook(self, event):
		keyCode = event.GetKeyCode()
		if keyCode == wx.WXK_ESCAPE:
			self.EndModal(wx.ID_CANCEL)
			return
		if keyCode == wx.WXK_DELETE and wx.Window.FindFocus() == self.listCtrl:
			self.onRemove(None)
			return
		event.Skip()

	def refreshList(self, focusIndex=0):
		self.entries = orderForDisplay(load_video_history())
		self.listCtrl.DeleteAllItems()
		for pos, entry in enumerate(self.entries):
			row = self.listCtrl.InsertItem(pos, str(entry.get("title") or _("Unknown")))
			self.listCtrl.SetItem(row, 1, str(entry.get("format", "mp3")).upper())
			self.listCtrl.SetItem(row, 2, str(entry.get("added_time", "")))
			self.listCtrl.SetItem(row, 3, _("Pinned") if entry.get("pinned") else "")
			self.listCtrl.SetItem(row, 4, str(entry.get("url", "")))
		count = self.listCtrl.GetItemCount()
		if count:
			target = max(0, min(focusIndex, count - 1))
			self.listCtrl.Select(target)
			self.listCtrl.Focus(target)

	def selectedIndices(self):
		indices = []
		index = self.listCtrl.GetFirstSelected()
		while index != -1:
			indices.append(index)
			index = self.listCtrl.GetNextSelected(index)
		if not indices:
			focused = self.listCtrl.GetFocusedItem()
			if focused != -1:
				indices.append(focused)
		return indices

	def selectedEntries(self):
		return [self.entries[i] for i in self.selectedIndices() if 0 <= i < len(self.entries)]

	def get_selected_download_info(self):
		chosen = self.selectedEntries()
		if not chosen:
			return None
		entry = chosen[0]
		return entry.get("url"), entry.get("title") or None, bool(entry.get("is_playlist"))

	def onContextMenu(self, event):
		chosen = self.selectedEntries()
		if not chosen:
			return
		menu = wx.Menu()
		for label, handler in (
			(_("Download"), self.onDownload),
			(_("Open URL"), self.onOpenUrl),
			(_("Remove"), self.onRemove),
			(_("Unpin") if chosen[0].get("pinned") else _("Pin"), self.onTogglePin),
		):
			item = menu.Append(wx.ID_ANY, label)
			self.Bind(wx.EVT_MENU, handler, item)
		menu.AppendSeparator()
		clearItem = menu.Append(wx.ID_ANY, _("Clear all"))
		self.Bind(wx.EVT_MENU, self.onClearAll, clearItem)
		self.PopupMenu(menu)
		menu.Destroy()

	def onDownload(self, event):
		chosen = self.selectedEntries()
		if not chosen:
			ui.message(_("No items selected"))
			return
		savePath = getINI("ResultFolder") or DownloadPath
		for entry in chosen:
			# convertToMP touches the disk (folder checks, existing-file
			# scan), so it runs off the main thread like the other callers.
			threading.Thread(
				target=convertToMP,
				args=(entry.get("format", "mp3"), savePath, bool(entry.get("is_playlist")), entry.get("url"), entry.get("title") or None),
				daemon=True,
			).start()
		ui.message(_("Download requested for {count} item(s)").format(count=len(chosen)))

	def onOpenUrl(self, event):
		chosen = self.selectedEntries()
		if not chosen:
			ui.message(_("No items selected"))
			return
		url = str(chosen[0].get("url", ""))
		if not url.lower().startswith(("http://", "https://")):
			ui.message(_("This item has no web address"))
			return
		try:
			os.startfile(url)
		except OSError as e:
			log(f"Video history: could not open URL: {e}")
			ui.message(_("Could not open the URL"))

	def onTogglePin(self, event):
		chosen = self.selectedEntries()
		if not chosen:
			ui.message(_("No items selected"))
			return
		changed = toggle_video_history_pin([e.get("url") for e in chosen])
		self.refreshList()
		if len(changed) == 1:
			ui.message(_("Pinned") if changed[0][1] else _("Unpinned"))
		else:
			ui.message(_("Pin state changed for {count} items").format(count=len(changed)))

	def onRemove(self, event):
		indices = self.selectedIndices()
		chosen = self.selectedEntries()
		if not chosen:
			ui.message(_("No items selected"))
			return
		remove_video_history_entries([e.get("url") for e in chosen])
		self.refreshList(min(indices) if indices else 0)
		ui.message(_("Item removed") if len(chosen) == 1 else _("Selected items removed"))

	def onClearAll(self, event):
		if not self.entries:
			ui.message(_("No history to clear"))
			return
		answer = wx.MessageBox(
			_("Remove all items from the video history?"),
			_("Clear all"),
			wx.YES_NO | wx.ICON_QUESTION | wx.NO_DEFAULT,
			self,
		)
		if answer != wx.YES:
			return
		clear_video_history()
		self.refreshList()
		ui.message(_("Video history cleared"))
