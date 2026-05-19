# download_list.py
import wx
import gui
import json
import os
import ui
import addonHandler
import traceback

addonHandler.initTranslation()

class DownloadListDialog(wx.Dialog):
	def __init__(self, parent, core_functions):
		super().__init__(parent, title=_("Download List Manager - Absolute YouTube"), size=(600, 400))
		self.parent = parent
		self.core_functions = core_functions

		required_keys = ['getINI', 'DownloadPath', 'log', 'get_pending_file_path',
						 'add_pending_download', 'start_next_pending', 'is_download_active',
						 'get_pending_downloads', 'remove_pending_download_by_index', 'clear_pending_downloads']
		missing_keys = [k for k in required_keys if k not in self.core_functions]
		if missing_keys:
			self.log_error(f"Missing core functions: {missing_keys}")
			wx.MessageBox(_("Add-on internal error: missing components. Please restart NVDA."),
						  _("Error"), wx.OK | wx.ICON_ERROR)

		self.pending_downloads = self.load_pending()
		self.init_ui()
		self.update_list()
		self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)

	def on_char_hook(self, event):
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			self.EndModal(wx.ID_CANCEL)
			return
		if event.GetKeyCode() == wx.WXK_DELETE:
			self.on_delete_selected(None)
			return
		event.Skip()

	def load_pending(self):
		try:
			return self.core_functions['get_pending_downloads']()
		except Exception:
			pending_file = self.core_functions['get_pending_file_path']()
			if os.path.exists(pending_file):
				try:
					with open(pending_file, 'r', encoding='utf-8') as f:
						return json.load(f)
				except Exception as e:
					self.log_error(f"load_pending error: {e}")
					return []
			return []

	def save_pending(self):
		pass

	def log_error(self, msg):
		try:
			self.core_functions['log'](f"DownloadListDialog: {msg}")
		except Exception:
			pass

	def init_ui(self):
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT)
		self.list_ctrl.InsertColumn(0, _("Video Title"), width=300)
		self.list_ctrl.InsertColumn(1, _("Format"), width=60)
		self.list_ctrl.InsertColumn(2, _("Added Time"), width=150)
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

		mainSizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

		self.list_ctrl.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
		self.SetSizer(mainSizer)
		self.CentreOnScreen()

	def update_list(self):
		self.list_ctrl.DeleteAllItems()
		self.pending_downloads = self.load_pending()
		for i, item in enumerate(self.pending_downloads):
			idx = self.list_ctrl.InsertItem(i, item.get('title', _('Unknown')))
			self.list_ctrl.SetItem(idx, 1, item.get('format', 'mp3').upper())
			self.list_ctrl.SetItem(idx, 2, item.get('added_time', ''))
		for col in range(3):
			self.list_ctrl.SetColumnWidth(col, wx.LIST_AUTOSIZE)

	def on_context_menu(self, event):
		if not self.pending_downloads:
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
			download_item = menu.Append(wx.ID_ANY, _("Download"))
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
		if 0 <= idx < len(self.pending_downloads):
			try:
				self.core_functions['remove_pending_download_by_index'](idx)
			except Exception:
				self.pending_downloads = self.load_pending()
				if 0 <= idx < len(self.pending_downloads):
					del self.pending_downloads[idx]
					pending_file = self.core_functions['get_pending_file_path']()
					os.makedirs(os.path.dirname(pending_file), exist_ok=True)
					with open(pending_file, 'w', encoding='utf-8') as f:
						json.dump(self.pending_downloads, f, ensure_ascii=False, indent=4)
			self.update_list()
			ui.message(_("Item deleted"))

	def download_item(self, idx):
		if 0 <= idx < len(self.pending_downloads):
			item = self.pending_downloads[idx]
			success = self.core_functions['add_pending_download'](item['url'], item['title'], item['format'])
			if success:
				self.delete_item(idx)
				if not self.core_functions['is_download_active']():
					self.core_functions['start_next_pending']()
				ui.message(_("Added to download queue: {title}").format(title=item['title']))
			else:
				ui.message(_("Already in download queue"))
				if not self.core_functions['is_download_active']():
					self.core_functions['start_next_pending']()

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
			self.delete_item(idx)
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
		for idx in selected_indices:
			if 0 <= idx < len(self.pending_downloads):
				item = self.pending_downloads[idx]
				success = self.core_functions['add_pending_download'](item['url'], item['title'], item['format'])
				if success:
					added_any = True
		if added_any:
			for idx in sorted(selected_indices, reverse=True):
				self.delete_item(idx)
			if not self.core_functions['is_download_active']():
				self.core_functions['start_next_pending']()
			ui.message(_("Selected items added to download queue"))
		else:
			ui.message(_("No new items added (already in queue)"))
			if not self.core_functions['is_download_active']():
				self.core_functions['start_next_pending']()

	def on_download_all(self, event):
		if not self.pending_downloads:
			ui.message(_("No pending downloads"))
			return
		added_any = False
		for item in self.pending_downloads[:]:
			success = self.core_functions['add_pending_download'](item['url'], item['title'], item['format'])
			if success:
				added_any = True
		if added_any:
			self.on_clear_all(None)
			if not self.core_functions['is_download_active']():
				self.core_functions['start_next_pending']()
			ui.message(_("All items added to download queue"))
		else:
			ui.message(_("No items added (all already in queue)"))
			if not self.core_functions['is_download_active']():
				self.core_functions['start_next_pending']()

	def on_clear_all(self, event):
		if not self.pending_downloads:
			ui.message(_("No pending downloads to clear"))
			return
		try:
			self.core_functions['clear_pending_downloads']()
		except Exception:
			pending_file = self.core_functions['get_pending_file_path']()
			if os.path.exists(pending_file):
				with open(pending_file, 'w', encoding='utf-8') as f:
					json.dump([], f)
		self.update_list()
		ui.message(_("All pending downloads cleared"))