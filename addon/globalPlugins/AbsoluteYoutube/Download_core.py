# Download_core.py
# Copyright (C) 2026 Chai Chaimee
# Licensed under GNU General Public License. See COPYING.txt for details.

import wx
import os
import json
import time
import urllib
import threading
import subprocess
import datetime
import glob
import winsound
import api
import controlTypes
import speech
import ui
import config
import addonHandler
from scriptHandler import script
import gui
import re
import uuid
import tones
import shutil
import tempfile
import psutil
import sys
import urllib.request
from queue import Queue

addonHandler.initTranslation()

AddOnSummary = _("Absolute YouTube")
AddOnName = "AbsoluteYoutube"

if sys.version_info.major >= 3 and sys.version_info.minor >= 10:
	AddOnPath = os.path.dirname(__file__)
else:
	AddOnPath = os.path.dirname(__file__)

ToolsPath = os.path.join(AddOnPath, "lib")
SoundPath = os.path.join(AddOnPath, "sounds")
AppData = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming')
DownloadPath = None
sectionName = AddOnName

_download_queue = Queue()
_heartbeat_thread = None
_heartbeat_active = False

Aria2cEXE = os.path.join(ToolsPath, "aria2c.exe")
YouTubeEXE = os.path.join(ToolsPath, "yt-dlp.exe")
ConverterEXE = os.path.join(ToolsPath, "ffmpeg.exe")
ConverterPath = ToolsPath

_global_state_lock = threading.Lock()
_global_active_downloads = 0
_global_active_lock = threading.Lock()
_num_workers = 1

_pending_lock = threading.Lock()


def clean_youtube_url(url, is_playlist=False):
	if not url or ("youtube.com" not in url and "youtu.be" not in url):
		return url
	import urllib.parse
	parsed = urllib.parse.urlparse(url)
	query_params = urllib.parse.parse_qs(parsed.query)
	unwanted = ['start_radio', 'pp', 'feature', 'index', 'playnext', 'sp', 'si', 'src_vid', 'rv']
	for param in unwanted:
		if param in query_params:
			del query_params[param]
	if not is_playlist and 'list' in query_params:
		del query_params['list']
	if 'v' not in query_params and "youtu.be" in url:
		video_id = parsed.path.lstrip('/')
		if video_id and '/' not in video_id:
			query_params['v'] = [video_id]
			new_netloc = "www.youtube.com"
			new_path = "/watch"
			parsed = parsed._replace(netloc=new_netloc, path=new_path)
	new_query = urllib.parse.urlencode(query_params, doseq=True)
	clean_url = urllib.parse.urlunparse((
		parsed.scheme, parsed.netloc, parsed.path,
		parsed.params, new_query, parsed.fragment
	))
	return clean_url


def getStateFilePath():
	try:
		import globalVars
		if globalVars.appArgs.secure:
			base = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'nvda')
		else:
			base = globalVars.appArgs.configPath or os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'nvda')
		new_dir = os.path.join(base, 'ChaiChaimee', 'AbsoluteYoutube')
		return os.path.join(new_dir, 'AbsoluteYoutube.json')
	except Exception:
		base = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'nvda')
		return os.path.join(base, 'ChaiChaimee', 'AbsoluteYoutube', 'AbsoluteYoutube.json')


StateFilePath = getStateFilePath()
FAILED_DOWNLOADS_FILE = os.path.join(os.path.dirname(StateFilePath), 'AbsoluteYoutubeFail.json')


def _migrate_old_json_files():
	try:
		import globalVars
		if globalVars.appArgs.secure:
			old_base = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'nvda')
		else:
			old_base = globalVars.appArgs.configPath or os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'nvda')

		old_state = os.path.join(old_base, 'AbsoluteYoutube.json')
		old_fail = os.path.join(old_base, 'AbsoluteYoutubeFail.json')

		new_dir = os.path.dirname(StateFilePath)
		if not os.path.exists(new_dir):
			os.makedirs(new_dir, exist_ok=True)

		moved_any = False

		if os.path.exists(old_state):
			try:
				shutil.move(old_state, StateFilePath)
				log(f"Migrated old state file from {old_state} to {StateFilePath}")
				moved_any = True
			except Exception as e:
				log(f"Failed to migrate old state file {old_state}: {e}")

		if os.path.exists(old_fail):
			try:
				shutil.move(old_fail, FAILED_DOWNLOADS_FILE)
				log(f"Migrated old fail file from {old_fail} to {FAILED_DOWNLOADS_FILE}")
				moved_any = True
			except Exception as e:
				log(f"Failed to migrate old fail file {old_fail}: {e}")

		if moved_any:
			log("Migration of old JSON files completed.")
	except Exception as e:
		log(f"Error during migration of old JSON files: {e}")


def load_failed_downloads():
	try:
		if os.path.exists(FAILED_DOWNLOADS_FILE):
			with open(FAILED_DOWNLOADS_FILE, 'r', encoding='utf-8') as f:
				return json.load(f)
	except Exception as e:
		log(f"Error loading failed downloads: {e}")
	return []


def save_failed_downloads(failed_list):
	try:
		os.makedirs(os.path.dirname(FAILED_DOWNLOADS_FILE), exist_ok=True)
		with open(FAILED_DOWNLOADS_FILE, 'w', encoding='utf-8') as f:
			json.dump(failed_list, f, ensure_ascii=False, indent=4)
	except Exception as e:
		log(f"Error saving failed downloads: {e}")


def getINI(key):
	return config.conf[sectionName][key]


def setINI(key, value):
	config.conf[sectionName][key] = value


def PlayWave(filename, force=False):
	try:
		path = os.path.join(SoundPath, filename + ".wav")
		if os.path.exists(path) and (force or getINI("BeepWhileConverting")):
			winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
	except Exception as e:
		log(f"Error playing sound: {e}")


def check_yt_dlp_update():
	try:
		if not os.path.exists(YouTubeEXE):
			return None, None
		current_version = subprocess.check_output([YouTubeEXE, "--version"],
												stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW).decode().strip()
		req = urllib.request.Request(
			"https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest",
			headers={'User-Agent': 'Mozilla/5.0'}
		)
		with urllib.request.urlopen(req, timeout=10) as response:
			data = json.loads(response.read().decode())
			latest_version = data['tag_name']
		return current_version, latest_version
	except Exception as e:
		log(f"Error checking yt-dlp update: {e}")
		return None, None


def _heartbeat_loop():
	global _heartbeat_active
	while _heartbeat_active:
		PlayWave("heart")
		time.sleep(4)
	winsound.PlaySound(None, winsound.SND_PURGE)


def startHeartbeat():
	global _heartbeat_thread, _heartbeat_active
	if not _heartbeat_active:
		_heartbeat_active = True
		_heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
		_heartbeat_thread.start()


def stopHeartbeat():
	global _heartbeat_thread, _heartbeat_active
	_heartbeat_active = False
	if _heartbeat_thread and _heartbeat_thread.is_alive():
		try:
			_heartbeat_thread.join()
		except Exception:
			pass


def initialize_folders():
	global DownloadPath, _num_workers
	folder = getINI("ResultFolder") or os.path.join(AppData, "AbsoluteYoutube")
	setINI("ResultFolder", folder)
	DownloadPath = folder
	if not os.path.exists(DownloadPath):
		os.makedirs(DownloadPath, exist_ok=True)
	if not os.path.exists(ToolsPath):
		os.makedirs(ToolsPath, exist_ok=True)
	if not os.path.exists(SoundPath):
		os.makedirs(SoundPath, exist_ok=True)

	json_dir = os.path.dirname(StateFilePath)
	if not os.path.exists(json_dir):
		os.makedirs(json_dir, exist_ok=True)
	_migrate_old_json_files()

	if not os.path.exists(StateFilePath):
		saveState([])

	try:
		_num_workers = getINI("MaxConcurrentDownloads")
		if _num_workers < 1:
			_num_workers = 1
		elif _num_workers > 4:
			_num_workers = 4
	except Exception:
		_num_workers = 1

	log("Initialized folders")


def saveState(queue_list):
	try:
		os.makedirs(os.path.dirname(StateFilePath), exist_ok=True)
		with open(StateFilePath, 'w', encoding='utf-8') as f:
			json.dump(queue_list, f, ensure_ascii=False, indent=4)
	except Exception as e:
		log(f"Error saving state: {e}")


def loadState():
	try:
		if os.path.exists(StateFilePath):
			with open(StateFilePath, 'r', encoding='utf-8') as f:
				return json.load(f)
	except Exception as e:
		log(f"Error loading state: {e}")
	return []


def clearState():
	try:
		if os.path.exists(StateFilePath):
			with open(StateFilePath, 'w', encoding='utf-8') as f:
				json.dump([], f)
	except Exception as e:
		log(f"Error clearing state: {e}")


def addDownloadToQueue(download_obj):
	with _global_state_lock:
		queue = loadState()
		download_obj["id"] = str(uuid.uuid4())
		download_obj["start_time"] = datetime.datetime.now().isoformat()
		download_obj["status"] = "queued"
		queue.append(download_obj)
		saveState(queue)
		log(f"Added download to queue: ID {download_obj['id']}")
		return download_obj["id"]


def updateDownloadStatusInQueue(download_id, status):
	with _global_state_lock:
		queue = loadState()
		updated = False
		for item in queue:
			if item.get("id") == download_id:
				item["status"] = status
				if status in ["completed", "failed", "cancelled"]:
					item["end_time"] = datetime.datetime.now().isoformat()
				updated = True
				break
		if updated:
			saveState(queue)
	log(f"Updated download status: ID {download_id} to {status}")


def removeCompletedOrFailedDownloadsFromQueue():
	with _global_state_lock:
		queue = loadState()
		new_queue = [item for item in queue if item.get("status") not in ["completed", "failed", "cancelled"]]
		if len(new_queue) < len(queue):
			saveState(new_queue)
			log(f"Removed {len(queue) - len(new_queue)} completed/failed downloads from queue")


def makePrintable(s):
	return "".join(c if c.isprintable() else " " for c in str(s))


def validFilename(s):
	return "".join(c if c not in ["/", "\\", ":", "*", "<", ">", "?", "\"", "|", "\n", "\r", "\t"] else "_" for c in s)


def log(s):
	try:
		api.log.info(f"AbsoluteYoutube: {makePrintable(s)}")
		if getINI("Logging"):
			path = getINI("ResultFolder") or DownloadPath
			os.makedirs(path, exist_ok=True)
			with open(os.path.join(path, "log.txt"), "a", encoding="utf-8") as f:
				f.write(f"{datetime.datetime.now()} - {makePrintable(s)}\n")
	except Exception as e:
		api.log.error(f"AbsoluteYoutube: Error writing log: {e}")


def createFolder(folder):
	if not os.path.isdir(folder):
		try:
			os.makedirs(folder, exist_ok=True)
			log(f"Created folder: {folder}")
			return True
		except Exception as e:
			ui.message(_("Cannot create folder"))
			log(f"Failed to create folder: {e}")
			return False
	return True


def getCurrentAppName():
	try:
		return api.getForegroundObject().appModule.appName
	except Exception:
		return "Unknown"


def isBrowser():
	obj = api.getFocusObject()
	return obj.treeInterceptor is not None


def getCurrentDocumentURL():
	try:
		obj = api.getFocusObject()
		if hasattr(obj, 'treeInterceptor') and obj.treeInterceptor:
			try:
				url = obj.treeInterceptor.documentConstantIdentifier
				if url:
					return urllib.parse.unquote(url)
			except Exception:
				pass
	except Exception as e:
		log(f"Error getting URL: {e}")
	return None


def getLinkURL():
	obj = api.getNavigatorObject()
	if obj.role == controlTypes.Role.LINK:
		url = obj.value
		if url:
			url = urllib.parse.unquote(url)
			return url[:-1] if url.endswith("/") else url
	return ""


def getLinkName():
	obj = api.getNavigatorObject()
	if obj.role == controlTypes.Role.LINK:
		return obj.name
	return ""


def getMultimediaURLExtension():
	url = getLinkURL()
	return url[url.rfind("."):].lower() if "." in url else ""


def isValidMultimediaExtension(ext):
	return ext.replace(".", "") in {
		"aac", "avi", "flac", "mkv", "m3u8", "m4a", "m4s", "m4v",
		"mpg", "mov", "mp2", "mp3", "mp4", "mpeg", "mpegts", "ogg",
		"ogv", "oga", "ts", "vob", "wav", "webm", "wmv", "f4v",
		"flv", "swf", "avchd", "3gp"
	}


def getWebSiteTitle():
	try:
		title = api.getForegroundObject().name
		unwanted_suffixes = [" - YouTube", "| YouTube", " - Google Chrome", " - Brave", " - Microsoft Edge"]
		for suffix in unwanted_suffixes:
			title = title.replace(suffix, "")
		return title
	except Exception:
		return "Unknown_Title"


def checkFileExists(savePath, title, extension, is_trimming=False):
	if not getINI("SkipExisting"):
		return False

	sanitized_title = validFilename(title)
	filename = os.path.join(savePath, f"{sanitized_title}.{extension}")

	if is_trimming:
		return False

	if os.path.exists(filename):
		log(f"File '{filename}' already exists.")
		return True

	temp_patterns = [
		f"{sanitized_title}.part",
		f"{sanitized_title}.ytdl",
		f"{sanitized_title}.temp",
		f"{sanitized_title}.download",
		f"{sanitized_title}.f*.tmp",
		f"{sanitized_title}.f*.webm",
		f"{sanitized_title}.f*.m4a",
		f"{sanitized_title}.f*.mp4",
		f"{sanitized_title}.part.aria2",
		f"{sanitized_title}.aria2"
	]

	for pattern in temp_patterns:
		full_pattern = os.path.join(savePath, pattern)
		if glob.glob(full_pattern):
			log(f"Found temp file matching pattern {full_pattern}, not skipping.")
			return False

	return False


def promptResumeDownloads(downloads_list):
	count = len(downloads_list)
	msg = _("Found {count} interrupted downloads\nResume all?").format(count=count)
	return gui.messageBox(msg, _("Resume downloads"), wx.YES_NO) == wx.YES


def _cleanup_temp_files(save_path, title, file_format, check_count=2):
	if not title or not save_path:
		log(f"Temp cleanup skipped: title or path missing (title: {title}, path: {save_path})")
		return
	sanitized_title = validFilename(title)
	base_filename = os.path.join(save_path, sanitized_title)

	temp_patterns = [
		f"{sanitized_title}.part",
		f"{sanitized_title}.ytdl",
		f"{sanitized_title}.temp",
		f"{sanitized_title}.download",
		f"{sanitized_title}.f*.tmp",
		f"{sanitized_title}.f*.webm",
		f"{sanitized_title}.f*.m4a",
		f"{sanitized_title}.f*.mp4",
		f"{sanitized_title}.part.aria2",
		f"{sanitized_title}.aria2"
	]

	if file_format == "mp3":
		temp_patterns.append(f"{sanitized_title}.mp4")

	final_file = os.path.join(save_path, f"{sanitized_title}.{file_format}")

	for _ in range(check_count):
		for pattern in temp_patterns:
			for temp_file in glob.glob(os.path.join(save_path, pattern)):
				if temp_file == final_file:
					continue
				if ('f' in os.path.basename(temp_file).split('.')[0] or
					temp_file.endswith(('.part', '.ytdl', '.temp', '.download', '.aria2', '.part.aria2', '.mp4'))):
					try:
						os.remove(temp_file)
						log(f"Removed temp file: {temp_file}")
					except Exception as e:
						log(f"Error removing temp file {temp_file}: {e}")


def get_video_duration(url):
	try:
		cmd = [YouTubeEXE, "--get-duration", "--no-playlist", "--quiet", url]
		result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
		if result.returncode == 0:
			duration_str = result.stdout.strip()
			if duration_str:
				parts = duration_str.split(':')
				if len(parts) == 3:
					h, m, s = map(int, parts)
					return h * 3600 + m * 60 + s
				elif len(parts) == 2:
					m, s = map(int, parts)
					return m * 60 + s
				elif len(parts) == 1:
					return int(parts[0])
				else:
					return None
		return None
	except Exception as e:
		log(f"Error getting video duration: {e}")
	return None


def get_file_duration(file_path):
	try:
		cmd = [ConverterEXE, "-i", file_path, "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"]
		result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
		if result.returncode == 0:
			duration_str = result.stdout.strip()
			if duration_str:
				return float(duration_str)
		return None
	except Exception as e:
		log(f"Error getting file duration: {e}")
	return None


def repairIncompleteFiles(path):
	repaired_count = 0
	patterns = [
		"*.part", "*.ytdl", "*.temp", "*.download", "*.f*.tmp",
		"*.f*.webm", "*.f*.m4a", "*.f*.mp4", "*.part.aria2", "*.aria2"
	]

	for pattern in patterns:
		full_pattern = os.path.join(path, pattern)
		for temp_file in glob.glob(full_pattern):
			try:
				base_name, _ = os.path.splitext(temp_file)
				if base_name.endswith('.part') or base_name.endswith('.aria2'):
					base_name, _ = os.path.splitext(base_name)

				original_file = os.path.splitext(base_name)[0]

				if os.path.exists(original_file + '.mp4') or os.path.exists(original_file + '.mp3') or os.path.exists(original_file + '.wav'):
					log(f"Skipping repair for {temp_file}: corresponding file already exists.")
					continue

				matches = re.findall(r"^(.*?)(?:-\w+)?(?:\.\w+)?$", original_file)
				if matches:
					potential_final_base = matches[0]
					target_mp4 = os.path.join(path, f"{potential_final_base}.mp4")
					target_mp3 = os.path.join(path, f"{potential_final_base}.mp3")
					target_wav = os.path.join(path, f"{potential_final_base}.wav")

					if os.path.exists(target_mp4) or os.path.exists(target_mp3) or os.path.exists(target_wav):
						log(f"Skipping repair for {temp_file}: corresponding final file exists.")
						continue

				if os.path.getsize(temp_file) > 0:
					os.remove(temp_file)
					repaired_count += 1
					log(f"Cleaned up incomplete file: {temp_file}")
			except Exception as e:
				log(f"Error repairing file {temp_file}: {str(e)}")
	return repaired_count


def resumeInterruptedDownloads():
	if not getINI("ResumeOnRestart"):
		return
	if not os.path.exists(StateFilePath):
		saveState([])
	with _global_state_lock:
		queue = loadState()
	downloads_to_resume = [item for item in queue if item.get("status") in ["running", "queued"]]
	if not downloads_to_resume:
		return
	path = getINI("ResultFolder") or DownloadPath
	if os.path.isdir(path):
		repaired = repairIncompleteFiles(path)
		log(f"Auto-repaired {repaired} files before resuming downloads")
	ui.message(_("Checking interrupted downloads..."))
	for item in downloads_to_resume:
		if YouTubeEXE in item["cmd"][0] and "--continue" not in item["cmd"]:
			item["cmd"].insert(1, "--continue")
		updateDownloadStatusInQueue(item.get("id"), "queued")
		if item.get("format") in ["mp3", "wav"]:
			_cleanup_temp_files(item.get("path", ""), item.get("title", ""), item.get("format", ""))
	if not promptResumeDownloads(downloads_to_resume):
		for item in downloads_to_resume:
			updateDownloadStatusInQueue(item.get("id"), "cancelled")
		clearState()
		return
	for item in downloads_to_resume:
		updateDownloadStatusInQueue(item.get("id"), "queued")
		if item.get("format") in ["mp3", "wav"]:
			_cleanup_temp_files(item.get("path", ""), item.get("title", ""), item.get("format", ""))
		_download_queue.put(item)


def start_worker_threads():
	global _num_workers
	try:
		_num_workers = getINI("MaxConcurrentDownloads")
		if _num_workers < 1:
			_num_workers = 1
		elif _num_workers > 4:
			_num_workers = 4
	except Exception:
		_num_workers = 1

	for _ in range(_num_workers):
		t = threading.Thread(target=worker_loop, daemon=True)
		t.start()
	log(f"Started {_num_workers} worker threads")


def shutdown_workers():
	global _num_workers
	for _ in range(_num_workers):
		_download_queue.put(None)


def worker_loop():
	while True:
		item = _download_queue.get()
		if item is None:
			break
		run_download(item)
		_download_queue.task_done()


def _process_next_download():
	pass


def get_failed_downloads():
	return load_failed_downloads()


def add_failed_download(url, title, format_type, duration=None):
	try:
		failed_list = load_failed_downloads()

		for item in failed_list:
			if item.get('url') == url and item.get('title') == title:
				return

		failed_item = {
			'url': url,
			'title': title,
			'format': format_type,
			'duration': duration or _("Unknown"),
			'timestamp': datetime.datetime.now().isoformat()
		}

		failed_list.append(failed_item)
		save_failed_downloads(failed_list)
		log(f"Added failed download: {title}")
	except Exception as e:
		log(f"Error adding failed download: {e}")


def remove_failed_download(url, title):
	try:
		failed_list = load_failed_downloads()
		new_list = [item for item in failed_list if not (item.get('url') == url and item.get('title') == title)]

		if len(new_list) < len(failed_list):
			save_failed_downloads(new_list)
			log(f"Removed failed download: {title}")
			return True
		return False
	except Exception as e:
		log(f"Error removing failed download: {e}")
		return False


def clear_failed_downloads():
	try:
		save_failed_downloads([])
		log("Cleared all failed downloads")
		return True
	except Exception as e:
		log(f"Error clearing failed downloads: {e}")
		return False


def get_pending_file_path():
	try:
		import globalVars
		if globalVars.appArgs.secure:
			base = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'nvda')
		else:
			base = globalVars.appArgs.configPath or os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'nvda')
		new_dir = os.path.join(base, 'ChaiChaimee', 'AbsoluteYoutube')
		return os.path.join(new_dir, 'pending_downloads.json')
	except Exception:
		base = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'nvda')
		return os.path.join(base, 'ChaiChaimee', 'AbsoluteYoutube', 'pending_downloads.json')


def load_pending_downloads():
	pending_file = get_pending_file_path()
	if os.path.exists(pending_file):
		try:
			with open(pending_file, 'r', encoding='utf-8') as f:
				return json.load(f)
		except Exception:
			return []
	return []


def save_pending_downloads(pending_list):
	pending_file = get_pending_file_path()
	os.makedirs(os.path.dirname(pending_file), exist_ok=True)
	with open(pending_file, 'w', encoding='utf-8') as f:
		json.dump(pending_list, f, ensure_ascii=False, indent=4)


def add_pending_download(url, title, format_type):
	with _pending_lock:
		pending_list = load_pending_downloads()
		for item in pending_list:
			if item.get('url') == url and item.get('format') == format_type:
				log(f"Pending download already exists: {title}")
				return False
		new_item = {
			'url': url,
			'title': title,
			'format': format_type,
			'added_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		}
		pending_list.append(new_item)
		save_pending_downloads(pending_list)
		log(f"Added to pending queue: {title}")
		return True


def remove_pending_download_by_index(idx):
	with _pending_lock:
		pending_list = load_pending_downloads()
		if 0 <= idx < len(pending_list):
			removed = pending_list.pop(idx)
			save_pending_downloads(pending_list)
			log(f"Removed from pending queue: {removed.get('title')}")
			return True
		return False


def clear_pending_downloads():
	with _pending_lock:
		save_pending_downloads([])
		log("Cleared all pending downloads")


def get_pending_downloads():
	return load_pending_downloads()


def is_download_active():
	return _global_active_downloads > 0


def start_next_pending():
	with _pending_lock:
		pending_list = load_pending_downloads()
		if not pending_list:
			return False
		next_item = pending_list.pop(0)
		save_pending_downloads(pending_list)
	wx.CallAfter(ui.message, _("Starting next download from queue: {title}").format(title=next_item['title']))
	convertToMP(next_item['format'], getINI("ResultFolder") or DownloadPath, False, next_item['url'], next_item['title'])
	return True


def run_download(item):
	download_id = item["id"]
	cmd = item["cmd"]
	save_path = item["path"]
	url = item["url"]
	title = item["title"]
	file_format = item["format"]
	is_playlist = item.get("is_playlist", False)
	is_trimming = item.get("trimming", False)

	with _global_active_lock:
		global _global_active_downloads
		_global_active_downloads += 1
		if _global_active_downloads == 1:
			wx.CallAfter(startHeartbeat)

	updateDownloadStatusInQueue(download_id, "running")
	log(f"Starting download for ID: {download_id}")
	log(f"Command: {cmd}")

	process = None
	try:
		si = subprocess.STARTUPINFO()
		si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
		si.wShowWindow = subprocess.SW_HIDE

		process = subprocess.Popen(
			cmd,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			stdin=subprocess.DEVNULL,
			cwd=save_path,
			startupinfo=si,
			creationflags=subprocess.CREATE_NO_WINDOW
		)
		log(f"Process started with PID: {process.pid}")

		def monitor_process():
			timeout = 1800
			try:
				process.communicate(timeout=timeout)
				return_code = process.returncode
				if return_code == 0:
					log(f"Download for ID {download_id} completed successfully.")
					if is_trimming:
						PlayWave('complete', force=True)
					else:
						if getINI("BeepWhileConverting"):
							PlayWave('complete')
					if getINI("SayDownloadComplete"):
						wx.CallAfter(ui.message, _("Download complete"))
					updateDownloadStatusInQueue(download_id, "completed")
					remove_failed_download(url, title)
				else:
					log(f"Download for ID {download_id} failed with return code {return_code}.")
					PlayWave('failed')
					wx.CallAfter(ui.message, _("Download failed"))
					updateDownloadStatusInQueue(download_id, "failed")
					duration = get_video_duration(url)
					add_failed_download(url, title, file_format, duration)
			except subprocess.TimeoutExpired:
				log(f"Download for ID {download_id} timed out after {timeout} seconds.")
				if process:
					process.terminate()
					try:
						process.wait(timeout=5)
					except subprocess.TimeoutExpired:
						process.kill()
				PlayWave('failed')
				wx.CallAfter(ui.message, _("Download failed due to timeout"))
				updateDownloadStatusInQueue(download_id, "failed")
				duration = get_video_duration(url)
				add_failed_download(url, title, file_format, duration)
			except Exception as e:
				log(f"Error during download execution for ID {download_id}: {e}")
				if process:
					process.terminate()
					try:
						process.wait(timeout=5)
					except subprocess.TimeoutExpired:
						process.kill()
				PlayWave('failed')
				wx.CallAfter(ui.message, _("Download failed due to an error"))
				updateDownloadStatusInQueue(download_id, "failed")
				duration = get_video_duration(url)
				add_failed_download(url, title, file_format, duration)
			finally:
				if not is_trimming:
					_cleanup_temp_files(save_path, title, file_format)
				removeCompletedOrFailedDownloadsFromQueue()
				with _global_active_lock:
					global _global_active_downloads
					_global_active_downloads -= 1
					if _global_active_downloads == 0:
						wx.CallAfter(stopHeartbeat)
				log(f"Download for ID {download_id} finished.")
				wx.CallAfter(start_next_pending)

		monitor_thread = threading.Thread(target=monitor_process, daemon=True)
		monitor_thread.start()

	except Exception as e:
		log(f"Failed to start download process: {e}")
		if process:
			process.terminate()
		PlayWave('failed')
		wx.CallAfter(ui.message, _("Download failed to start"))
		updateDownloadStatusInQueue(download_id, "failed")
		duration = get_video_duration(url)
		add_failed_download(url, title, file_format, duration)
		with _global_active_lock:
			_global_active_downloads -= 1
			if _global_active_downloads == 0:
				wx.CallAfter(stopHeartbeat)


def convertToMP(mpFormat, savePath, isPlaylist=False, url=None, title=None):
	if not createFolder(savePath):
		ui.message(_("Cannot create folder"))
		return
	if os.path.isdir(savePath):
		repaired = repairIncompleteFiles(savePath)
		log(f"Auto-repaired {repaired} files before new download")
	
	current_url = url or getCurrentDocumentURL()
	link_url = getLinkURL()
	
	if not current_url:
		current_url = link_url
	
	if not current_url:
		ui.message(_("URL not found"))
		return
	
	is_youtube_url_flag = any(y in current_url.lower() for y in [".youtube.", "youtu.be", "youtube.com"])
	
	if is_youtube_url_flag:
		current_url = clean_youtube_url(current_url, isPlaylist)
		
		if title:
			video_title = title
		else:
			video_title = getWebSiteTitle()
		
		sanitized_title = validFilename(video_title)

		if not isPlaylist:
			if checkFileExists(savePath, sanitized_title, mpFormat):
				if mpFormat in ["mp3", "wav"] and os.path.exists(os.path.join(savePath, f"{sanitized_title}.mp4")):
					log(f"MP4 exists for {sanitized_title}, allowing {mpFormat.upper()} download")
				else:
					ui.message(_("File exists"))
					return

		if not isPlaylist:
			try:
				parsed = urllib.parse.urlparse(current_url)
				query_params = urllib.parse.parse_qs(parsed.query)
				if 'list' in query_params:
					del query_params['list']
				if 'index' in query_params:
					del query_params['index']
				new_query = urllib.parse.urlencode(query_params, doseq=True)
				current_url = urllib.parse.urlunparse((
					parsed.scheme, parsed.netloc, parsed.path,
					parsed.params, new_query, parsed.fragment
				))
				log("Removed playlist parameters from URL for single video download")
			except Exception as e:
				log(f"Error parsing URL: {e}")
				ui.message(_("Error processing URL"))
				return

		if not os.path.exists(YouTubeEXE):
			ui.message(_("yt-dlp.exe missing"))
			return
		PlayWave("start")

		output_template = os.path.join(savePath, "%(playlist)s/%(title)s.%(ext)s") if isPlaylist else os.path.join(savePath, "%(title)s.%(ext)s")

		use_multipart = getINI("UseMultiPart") and os.path.exists(Aria2cEXE)
		connections = getINI("MultiPartConnections")

		base_cmd = [
			YouTubeEXE, "--yes-playlist" if isPlaylist else "--no-playlist",
			"--ignore-errors", "--no-warnings", "--quiet", "--no-check-certificate",
			"--fragment-retries", str(getINI("FragmentRetries")),
			"--retries", str(getINI("RetryCount"))
		]

		use_auto_cookies = not getINI("UseCookies")
		if use_auto_cookies:
			base_cmd.extend(["--cookies-from-browser", "chrome"])
			log("Attempting to use cookies from Chrome browser automatically")

		if getINI("UseCookies") and getINI("CookiesFile"):
			cookies_file = getINI("CookiesFile")
			if os.path.exists(cookies_file):
				base_cmd.extend(["--cookies", cookies_file])
				log("Using cookies file for authentication")

		if getINI("UseCustomUserAgent") and getINI("CustomUserAgent"):
			user_agent = getINI("CustomUserAgent")
			base_cmd.extend(["--user-agent", user_agent])
			log(f"Using custom user agent: {user_agent}")

		if getINI("UseProxy") and getINI("ProxyURL"):
			proxy_url = getINI("ProxyURL")
			base_cmd.extend(["--proxy", proxy_url])
			log(f"Using proxy: {proxy_url}")

		if getINI("GeoBypass"):
			base_cmd.append("--geo-bypass")
			if getINI("GeoBypassCountry"):
				base_cmd.extend(["--geo-bypass-country", getINI("GeoBypassCountry")])
			if getINI("GeoBypassIP"):
				base_cmd.extend(["--geo-bypass-ip", getINI("GeoBypassIP")])

		if getINI("ForceIpv4"):
			base_cmd.append("--force-ipv4")
		if getINI("ForceIpv6"):
			base_cmd.append("--force-ipv6")

		if getINI("ThrottleRate") > 0:
			throttle_rate = getINI("ThrottleRate")
			base_cmd.extend(["--limit-rate", f"{throttle_rate}K"])

		if getINI("SleepBetweenRequests") > 0:
			sleep_time = getINI("SleepBetweenRequests")
			base_cmd.extend(["--sleep-interval", str(sleep_time)])

		if getINI("UseSponsorBlock"):
			sponsor_categories = getINI("SponsorBlockCategories")
			base_cmd.extend(["--sponsorblock-api", "https://sponsor.ajay.app", "--sponsorblock-mark", sponsor_categories])

		if getINI("AbortOnError"):
			base_cmd.append("--abort-on-error")

		if getINI("SkipUnavailableFragments"):
			base_cmd.append("--skip-unavailable-fragments")

		if getINI("MarkWatched"):
			base_cmd.append("--mark-watched")

		if mpFormat == "mp3":
			cmd = base_cmd + [
				"-x", "--audio-format", "mp3",
				"--audio-quality", str(getINI("MP3Quality")),
				"--ffmpeg-location", ConverterEXE,
				"-o", output_template, current_url
			]
			if use_multipart:
				safe_connections = min(connections, 4)
				aria2_args = f"-x{safe_connections} -j{safe_connections} -s{safe_connections} -k1M --file-allocation=none --allow-overwrite=true --max-tries=3 --retry-wait=5 --quiet --console-log-level=error"
				cmd.extend(["--external-downloader", Aria2cEXE,
							"--external-downloader-args", f"aria2c:{aria2_args}"])
		elif mpFormat == "wav":
			cmd = base_cmd + [
				"-x", "--audio-format", "wav",
				"--audio-quality", "0",
				"--ffmpeg-location", ConverterEXE,
				"-o", output_template, current_url
			]
			if use_multipart:
				safe_connections = min(connections, 4)
				aria2_args = f"-x{safe_connections} -j{safe_connections} -s{safe_connections} -k1M --file-allocation=none --allow-overwrite=true --max-tries=3 --retry-wait=5 --quiet --console-log-level=error"
				cmd.extend(["--external-downloader", Aria2cEXE,
							"--external-downloader-args", f"aria2c:{aria2_args}"])
		else:
			cmd = base_cmd + [
				"-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
				"--remux-video", "mp4",
				"--ffmpeg-location", ConverterEXE,
				"-o", output_template, current_url
			]
			if use_multipart:
				safe_connections = min(connections, 4)
				aria2_args = f"-x{safe_connections} -j{safe_connections} -s{safe_connections} -k1M --file-allocation=none --allow-overwrite=true --max-tries=3 --retry-wait=5 --quiet --console-log-level=error"
				cmd.extend(["--external-downloader", Aria2cEXE,
							"--external-downloader-args", f"aria2c:{aria2_args}"])
			else:
				safe_connections = min(connections, 4)
				cmd.extend(["--concurrent-fragments", str(safe_connections)])

		download_obj = {
			"url": current_url, "title": sanitized_title, "format": mpFormat,
			"path": savePath, "cmd": cmd, "is_playlist": isPlaylist
		}
		download_id = addDownloadToQueue(download_obj)
		_download_queue.put(download_obj)
	else:
		ext = getMultimediaURLExtension()
		ext = ext.lstrip(".")
		if ext and isValidMultimediaExtension(ext):
			if not os.path.exists(ConverterEXE):
				ui.message(_("Error: ffmpeg.exe not found."))
				return
			multimediaLinkURL = getLinkURL()
			linkName = getLinkName()
			if checkFileExists(savePath, linkName, mpFormat):
				ui.message(_("File already exists. Skipping download."))
				return
			if not multimediaLinkURL:
				ui.message(_("No valid multimedia link found."))
				return
			multimediaLinkName = os.path.join(savePath, validFilename(linkName) + "." + mpFormat)
			if mpFormat == "mp3":
				cmd = [
					ConverterEXE, "-i", multimediaLinkURL,
					"-c:a", "libmp3lame", "-b:a", f"{getINI('MP3Quality')}k",
					"-map", "0:a", "-y", "-loglevel", "quiet", multimediaLinkName
				]
			elif mpFormat == "wav":
				cmd = [
					ConverterEXE, "-i", multimediaLinkURL,
					"-c:a", "pcm_s16le",
					"-map", "0:a", "-y", "-loglevel", "quiet", multimediaLinkName
				]
			else:
				cmd = [
					ConverterEXE, "-i", multimediaLinkURL,
					"-c:v", "libx265", "-preset", "fast", "-crf", "23",
					"-c:a", "copy", "-map", "0:v?", "-map", "0:a?",
					"-y", "-loglevel", "quiet", multimediaLinkName
				]
			ui.message(_("Adding link as {format} to download queue").format(format=mpFormat.upper()))
			PlayWave("start")
			download_obj = {
				"url": multimediaLinkURL, "title": linkName, "format": mpFormat,
				"path": savePath, "cmd": cmd, "is_playlist": False
			}
			download_id = addDownloadToQueue(download_obj)
			_download_queue.put(download_obj)
		else:
			ui.message(_("Not a YouTube video or valid multimedia link"))


def setSpeed(sp):
	speech.setSpeechOption("rate", sp)
	speech.speak(" ")