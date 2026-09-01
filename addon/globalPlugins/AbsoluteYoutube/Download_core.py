# Download_core.py

import wx
import os
import json
import time
import urllib.parse
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
import core
import re
import uuid
import tones
import shutil
import tempfile
import psutil
import sys
import urllib.request
import zipfile
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

def getAddonConfigBaseDir():
	try:
		import globalVars
		if globalVars.appArgs.secure:
			return os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'nvda')
		return config.getUserDefaultConfigPath()
	except Exception:
		return os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'nvda')

def getStateFilePath():
	base = getAddonConfigBaseDir()
	new_dir = os.path.join(base, 'ChaiChaimee', 'AbsoluteYoutube')
	return os.path.join(new_dir, 'AbsoluteYoutube.json')

StateFilePath = getStateFilePath()
FAILED_DOWNLOADS_FILE = os.path.join(os.path.dirname(StateFilePath), 'AbsoluteYoutubeFail.json')
Aria2cDir = os.path.join(os.path.dirname(StateFilePath), 'bin')
Aria2cEXE = os.path.join(Aria2cDir, 'aria2c.exe')
Aria2cReleaseAPI = "https://api.github.com/repos/aria2/aria2/releases/latest"

def _migrate_old_json_files():
	try:
		old_base = getAddonConfigBaseDir()
		old_state = os.path.join(old_base, 'AbsoluteYoutube.json')
		old_fail = os.path.join(old_base, 'AbsoluteYoutubeFail.json')
		new_dir = os.path.dirname(StateFilePath)
		if not os.path.exists(new_dir):
			os.makedirs(new_dir, exist_ok=True)
		if os.path.exists(old_state):
			try:
				shutil.move(old_state, StateFilePath)
				log(f"Migrated old state file to {StateFilePath}")
			except Exception as e:
				log(f"Failed to migrate old state file: {e}")
		if os.path.exists(old_fail):
			try:
				shutil.move(old_fail, FAILED_DOWNLOADS_FILE)
				log(f"Migrated old fail file to {FAILED_DOWNLOADS_FILE}")
			except Exception as e:
				log(f"Failed to migrate old fail file: {e}")
	except Exception as e:
		log(f"Error during migration of old JSON files: {e}")

def _safe_write_json(path, data):
	# Atomic write: write to a temp file, fsync it, keep a .bak copy of the
	# previous good file, then atomically replace the real path with
	# os.replace() (atomic on both Windows and POSIX). Without this, a
	# crash or forced NVDA termination exactly mid-write leaves a
	# truncated/corrupted file, and the next load silently returns an
	# empty list -- losing every pending/queued/failed download with no
	# warning. This pattern is already proven working elsewhere in this
	# project (another add-on's settings/playlist persistence).
	tmpPath = path + ".tmp"
	bakPath = path + ".bak"
	try:
		folder = os.path.dirname(path)
		if folder and not os.path.exists(folder):
			os.makedirs(folder, exist_ok=True)
		with open(tmpPath, 'w', encoding='utf-8') as f:
			json.dump(data, f, ensure_ascii=False, indent=4)
			f.flush()
			try:
				os.fsync(f.fileno())
			except Exception:
				pass
		if os.path.exists(path):
			try:
				os.replace(path, bakPath)
			except Exception:
				pass
		os.replace(tmpPath, path)
		return True
	except Exception as e:
		log(f"Error writing JSON ({path}): {e}")
		try:
			if os.path.exists(tmpPath):
				os.remove(tmpPath)
		except Exception:
			pass
		return False

def load_failed_downloads():
	try:
		if os.path.exists(FAILED_DOWNLOADS_FILE):
			with open(FAILED_DOWNLOADS_FILE, 'r', encoding='utf-8') as f:
				return json.load(f)
	except Exception as e:
		log(f"Error loading failed downloads: {e}")
	return []

def save_failed_downloads(failed_list):
	_safe_write_json(FAILED_DOWNLOADS_FILE, failed_list)

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

def get_yt_dlp_versions():
	# Blocking network + subprocess work, deliberately not wrapped in its
	# own thread here -- callers that are already on the main thread must
	# use check_yt_dlp_update() below instead of calling this directly,
	# while callers already running on a background thread (see __init__.py)
	# can call this synchronously without spawning a redundant thread.
	if not os.path.exists(YouTubeEXE):
		return None, None
	try:
		current_version = subprocess.check_output(
			[YouTubeEXE, "--version"],
			stderr=subprocess.STDOUT,
			creationflags=subprocess.CREATE_NO_WINDOW
		).decode().strip()
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

def _download_aria2c_worker(statusCallback=None):
	# Runs entirely on a background thread. This is called on every add-on
	# load, but os.path.exists(Aria2cEXE) makes it a no-op after the first
	# successful run -- Aria2cDir lives under the add-on's own config
	# directory, which an NVDA add-on install/update/uninstall never
	# touches, so the file downloaded here survives future add-on updates
	# without needing to be re-fetched or separately migrated.
	if os.path.exists(Aria2cEXE):
		return
	maxRetries = 3
	backoffSeconds = 2
	tmpZipPath = os.path.join(Aria2cDir, "aria2c_download.tmp")
	for attempt in range(1, maxRetries + 1):
		try:
			releaseReq = urllib.request.Request(
				Aria2cReleaseAPI,
				headers={'User-Agent': 'Mozilla/5.0'}
			)
			with urllib.request.urlopen(releaseReq, timeout=15) as response:
				releaseData = json.loads(response.read().decode())
			assetUrl = None
			for asset in releaseData.get('assets', []):
				assetName = asset.get('name', '').lower()
				if assetName.endswith('.zip') and 'win-64bit' in assetName:
					assetUrl = asset.get('browser_download_url')
					break
			if not assetUrl:
				log("Error: no matching win-64bit aria2c release asset found")
				return
			zipReq = urllib.request.Request(assetUrl, headers={'User-Agent': 'Mozilla/5.0'})
			with urllib.request.urlopen(zipReq, timeout=60) as response, open(tmpZipPath, 'wb') as f:
				shutil.copyfileobj(response, f)
			with zipfile.ZipFile(tmpZipPath, 'r') as archive:
				exeEntryName = next((n for n in archive.namelist() if n.lower().endswith("aria2c.exe")), None)
				if not exeEntryName:
					log("Error: aria2c.exe not found inside downloaded release archive")
					return
				extractedBytes = archive.read(exeEntryName)
			# A real aria2c.exe build is several hundred KB; anything far
			# smaller almost certainly means a truncated download or an
			# HTML error page saved as if it were the archive.
			if len(extractedBytes) < 200000:
				log(f"Error: extracted aria2c.exe looked too small ({len(extractedBytes)} bytes), discarding")
				return
			tmpExePath = Aria2cEXE + ".tmp"
			with open(tmpExePath, 'wb') as f:
				f.write(extractedBytes)
			os.replace(tmpExePath, Aria2cEXE)
			log(f"aria2c.exe downloaded successfully to {Aria2cEXE}")
			if statusCallback:
				wx.CallAfter(statusCallback, True)
			return
		except Exception as e:
			log(f"Error downloading aria2c.exe (attempt {attempt}/{maxRetries}): {e}")
			if attempt < maxRetries:
				time.sleep(backoffSeconds)
				backoffSeconds *= 2
		finally:
			try:
				if os.path.exists(tmpZipPath):
					os.remove(tmpZipPath)
			except Exception:
				pass
	log("aria2c.exe download failed after all retries; multi-part downloading will stay unavailable until the next add-on load.")
	if statusCallback:
		wx.CallAfter(statusCallback, False)

def ensure_aria2c_available(statusCallback=None):
	# Safe to call unconditionally: does nothing but a fast os.path.exists()
	# check when aria2c.exe is already present, and otherwise hands the
	# actual network fetch off to a background thread so this never blocks
	# NVDA's startup (Section 5.1/5.7).
	if os.path.exists(Aria2cEXE):
		if statusCallback:
			wx.CallAfter(statusCallback, True)
		return
	threading.Thread(target=_download_aria2c_worker, args=(statusCallback,), daemon=True).start()

def check_yt_dlp_update(callback=None):
	# Main-thread-safe entry point: always hands the blocking work in
	# get_yt_dlp_versions() off to a background thread and reports back
	# through wx.CallAfter, so this is safe to call directly from UI code.
	def _worker():
		current_version, latest_version = get_yt_dlp_versions()
		if callback:
			wx.CallAfter(callback, current_version, latest_version)
	threading.Thread(target=_worker, daemon=True).start()

def _fractionToGain(fraction):
	# Human loudness perception is much closer to logarithmic than linear:
	# a straight linear multiplier barely changes perceived loudness
	# across the top half of the range and barely attenuates anything in
	# the bottom half either -- 5% linear amplitude still sounded "like
	# 20%" to a real listener, which is why "Beep volume" had so little
	# audible effect even when it was confirmed to be the exact number
	# reaching tones.beep(). Squaring the fraction is a standard, simple
	# approximation of a perceptual/audio-taper curve, matching the same
	# fix already proven in soundAlign's own tone renderer (its
	# fraction_to_gain()). This makes AbsoluteYoutube's own slider behave
	# correctly on its own -- e.g. without soundAlign installed, where
	# tones.beep() uses this add-on's left/right values directly. When
	# soundAlign IS installed and active, its own hook on tones.beep()
	# substitutes its own "Beep volume" setting for ADDON_BEEP-category
	# sounds regardless of what's passed in here -- that's soundAlign's
	# own intentional, centralized design for giving every add-on's beeps
	# a consistent volume, and is outside this add-on's control either
	# way. This curve is what's actually heard whenever soundAlign isn't
	# in the picture.
	fraction = max(0.0, min(1.0, fraction))
	return fraction * fraction

def _playConfiguredTone(frequency, length):
	# tones.beep(), dispatched via wx.CallAfter with a direct-call
	# fallback and a 150ms length -- the proven-reliable structure for
	# repeated background-thread-driven beeps.
	#
	# Going through tones.beep() (rather than this add-on generating and
	# feeding its own raw PCM) means AbsoluteYoutube's beeps get the same
	# soundAlign panning/enhancement treatment any other add-on's beeps
	# do when soundAlign is installed -- e.g. simpleCopy's speech-history
	# beep -- with no separate pan control needed here. soundAlign's own
	# "Beep volume" setting takes over from this add-on's own slider in
	# that case (see _fractionToGain above); without soundAlign, this
	# add-on's own slider and gain curve are what's actually heard.
	beepEnabled = getINI("BeepWhileConverting")
	if not beepEnabled:
		log(f"Beep skipped ({frequency}Hz): BeepWhileConverting is off")
		return
	try:
		volumePercent = max(0, min(100, getINI("ConvertingBeepVolume")))
	except Exception:
		volumePercent = 50
	if volumePercent <= 0:
		log(f"Beep skipped ({frequency}Hz): configured volume is 0")
		return
	volume = int(round(_fractionToGain(volumePercent / 100.0) * 100))
	volume = max(1, min(100, volume))

	def _beep():
		try:
			log(f"Beep attempting ({frequency}Hz, {length}ms, configured={volumePercent}%, gain-adjusted volume={volume})")
			tones.beep(frequency, length, left=volume, right=volume)
			log(f"Beep succeeded ({frequency}Hz)")
		except Exception as e:
			log(f"Error playing tone ({frequency}Hz): {e}")

	try:
		wx.CallAfter(_beep)
	except Exception as e:
		log(f"wx.CallAfter failed for tone ({frequency}Hz), falling back to direct call: {e}")
		_beep()

def PlayStartBeep():
	_playConfiguredTone(200, 150)

def PlayProgressBeep(frequency=600):
	_playConfiguredTone(frequency, 150)

def PlayCompleteBeep():
	_playConfiguredTone(800, 150)

def PlayFailBeep():
	_playConfiguredTone(120, 150)

def _kill_process_tree(pid):
	# process.terminate()/kill() only signal the immediate yt-dlp.exe
	# process; if yt-dlp (or the browser cookie-copy step) spawned a
	# grandchild (ffmpeg, etc.) that grandchild keeps running and, on
	# Windows, can keep inherited stderr file/pipe handles open, which is
	# what was leaving communicate() blocked indefinitely even after the
	# nominal process we launched had already exited. taskkill /T kills the
	# whole tree so nothing is left running or holding handles open.
	try:
		subprocess.run(
			["taskkill", "/F", "/T", "/PID", str(pid)],
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
			stdin=subprocess.DEVNULL,
			creationflags=subprocess.CREATE_NO_WINDOW,
			timeout=10
		)
	except Exception:
		pass

def PlayTrimCompleteBeep():
	_playConfiguredTone(800, 150)

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
	if not os.path.exists(Aria2cDir):
		os.makedirs(Aria2cDir, exist_ok=True)
	_migrate_old_json_files()
	if not os.path.exists(StateFilePath):
		saveState([])
	if getINI("UseMultiPart"):
		ensure_aria2c_available()
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
	_safe_write_json(StateFilePath, queue_list)

def loadState():
	try:
		if os.path.exists(StateFilePath):
			with open(StateFilePath, 'r', encoding='utf-8') as f:
				return json.load(f)
	except Exception as e:
		log(f"Error loading state: {e}")
	return []

def clearState():
	_safe_write_json(StateFilePath, [])

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
			core.callLater(0, ui.message, _("Cannot create folder"))
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
	return False

def promptResumeDownloads(downloads_list):
	count = len(downloads_list)
	msg = _("Found {count} interrupted downloads\nResume all?").format(count=count)
	return gui.messageBox(msg, _("Resume downloads"), wx.YES_NO) == wx.YES

def _cleanup_temp_files(save_path, title, file_format, check_count=2):
	def _worker():
		if not title or not save_path:
			return
		sanitized_title = validFilename(title)
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
						except Exception:
							pass
	threading.Thread(target=_worker, daemon=True).start()

def get_video_duration(url):
	try:
		cmd = [YouTubeEXE, "--get-duration", "--no-playlist", "--quiet", url]
		result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW, timeout=60)
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
		return None
	except Exception:
		return None

def repairIncompleteFiles(path):
	def _worker():
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
						continue
					matches = re.findall(r"^(.*?)(?:-\w+)?(?:\.\w+)?$", original_file)
					if matches:
						potential_final_base = matches[0]
						if os.path.exists(os.path.join(path, f"{potential_final_base}.mp4")) or os.path.exists(os.path.join(path, f"{potential_final_base}.mp3")) or os.path.exists(os.path.join(path, f"{potential_final_base}.wav")):
							continue
					if os.path.getsize(temp_file) > 0:
						os.remove(temp_file)
						repaired_count += 1
				except Exception:
					pass
	threading.Thread(target=_worker, daemon=True).start()

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
		repairIncompleteFiles(path)
	core.callLater(0, ui.message, _("Checking interrupted downloads..."))
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
	except Exception:
		pass

def remove_failed_download(url, title):
	try:
		failed_list = load_failed_downloads()
		new_list = [item for item in failed_list if not (item.get('url') == url and item.get('title') == title)]
		if len(new_list) < len(failed_list):
			save_failed_downloads(new_list)
			return True
		return False
	except Exception:
		return False

def clear_failed_downloads():
	try:
		save_failed_downloads([])
		return True
	except Exception:
		return False

def get_pending_file_path():
	base = getAddonConfigBaseDir()
	new_dir = os.path.join(base, 'ChaiChaimee', 'AbsoluteYoutube')
	return os.path.join(new_dir, 'pending_downloads.json')

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
	_safe_write_json(pending_file, pending_list)

def add_pending_download(url, title, format_type, is_playlist=False):
	with _pending_lock:
		pending_list = load_pending_downloads()
		for item in pending_list:
			if item.get('url') == url and item.get('format') == format_type:
				return False
		new_item = {
			'url': url,
			'title': title,
			'format': format_type,
			'is_playlist': is_playlist,
			'status': 'waiting',
			'added_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		}
		pending_list.append(new_item)
		save_pending_downloads(pending_list)
		return True

def mark_pending_download_downloading(url, format_type):
	with _pending_lock:
		pending_list = load_pending_downloads()
		changed = False
		for item in pending_list:
			if item.get('url') == url and item.get('format') == format_type:
				item['status'] = 'downloading'
				changed = True
		if changed:
			save_pending_downloads(pending_list)
		return changed

def remove_pending_download_by_url(url, format_type):
	with _pending_lock:
		pending_list = load_pending_downloads()
		new_list = [item for item in pending_list if not (item.get('url') == url and item.get('format') == format_type)]
		if len(new_list) != len(pending_list):
			save_pending_downloads(new_list)
			return True
		return False

def remove_pending_download_by_index(idx):
	with _pending_lock:
		pending_list = load_pending_downloads()
		if 0 <= idx < len(pending_list):
			pending_list.pop(idx)
			save_pending_downloads(pending_list)
			return True
		return False

def clear_pending_downloads():
	with _pending_lock:
		save_pending_downloads([])

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
	core.callLater(0, ui.message, _("Starting next download from queue: {title}").format(title=next_item['title']))
	convertToMP(next_item['format'], getINI("ResultFolder") or DownloadPath, next_item['is_playlist'], next_item['url'], next_item['title'])
	return True

_bandwidth_cache = {"kbps": None, "timestamp": 0}
_BANDWIDTH_CACHE_TTL = 600

_DOWNLOADER_ERROR_MARKERS = (
	"aria2c", "general protocol error", "connection refused",
	"could not resolve host", "network is unreachable",
	"timeout was reached", "max download tries",
	"unable to connect", "connection reset", "connection aborted",
	"http error 429", "http error 500", "http error 502", "http error 503",
	"remote end closed connection", "eof occurred in violation of protocol",
	"read timed out", "temporary failure in name resolution",
)

def estimate_optimal_connections(user_setting):
	now = time.time()
	if _bandwidth_cache["kbps"] is None or (now - _bandwidth_cache["timestamp"]) > _BANDWIDTH_CACHE_TTL:
		try:
			probe_bytes = 250_000
			probe_url = f"https://speed.cloudflare.com/__down?bytes={probe_bytes}"
			probe_request = urllib.request.Request(
				probe_url,
				headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AbsoluteYoutube-BandwidthProbe"}
			)
			probe_start = time.time()
			bytes_read = 0
			with urllib.request.urlopen(probe_request, timeout=5) as resp:
				deadline = probe_start + 5
				while bytes_read < probe_bytes and time.time() < deadline:
					chunk = resp.read(16_384)
					if not chunk:
						break
					bytes_read += len(chunk)
			probe_elapsed = max(time.time() - probe_start, 0.001)
			if bytes_read <= 0:
				raise ValueError("Bandwidth probe received no data")
			_bandwidth_cache["kbps"] = (bytes_read / 1024) / probe_elapsed
			_bandwidth_cache["timestamp"] = now
		except Exception as e:
			log(f"Bandwidth probe failed, keeping configured connection count: {e}")
			return user_setting
	kbps = _bandwidth_cache["kbps"]
	if kbps is None:
		return user_setting
	if kbps < 300:
		suggested = 2
	elif kbps < 800:
		suggested = 4
	elif kbps < 2000:
		suggested = 8
	else:
		suggested = 16
	return min(user_setting, suggested)

def _adjust_multipart_connections(cmd, new_connections):
	try:
		if "--external-downloader-args" in cmd:
			idx = cmd.index("--external-downloader-args")
			downloader_prefix, _, args_str = cmd[idx + 1].partition(":")
			args_str = re.sub(r"-x\d+", f"-x{new_connections}", args_str)
			args_str = re.sub(r"-j\d+", f"-j{new_connections}", args_str)
			args_str = re.sub(r"-s\d+", f"-s{new_connections}", args_str)
			cmd[idx + 1] = f"{downloader_prefix}:{args_str}"
		elif "--concurrent-fragments" in cmd:
			idx = cmd.index("--concurrent-fragments")
			cmd[idx + 1] = str(new_connections)
	except Exception:
		pass
	return cmd

def _fallback_to_native_downloader(cmd, connections):
	new_cmd = list(cmd)
	try:
		idx = new_cmd.index("--external-downloader")
		del new_cmd[idx:idx + 2]
	except ValueError:
		pass
	try:
		idx = new_cmd.index("--external-downloader-args")
		del new_cmd[idx:idx + 2]
	except ValueError:
		pass
	new_cmd.extend(["--concurrent-fragments", str(max(1, connections))])
	return new_cmd

def _looks_like_downloader_error(stderr_text):
	lowered = (stderr_text or "").lower()
	return any(marker in lowered for marker in _DOWNLOADER_ERROR_MARKERS)

def _poll_download_progress(save_path, total_bytes, process, stop_event, needs_extraction, announce_enabled):
	# Beeping was removed from this function -- see _progress_beep_heartbeat
	# below. Byte-percentage buckets depend on save_path scanning and a
	# total_bytes estimate that can be wrong or unavailable for some
	# formats/sources, so a beep tied to bucket changes could go quiet for
	# long stretches (or the whole download) even while everything was
	# working normally. A plain time-based heartbeat has no such
	# dependency: it beeps on a fixed interval from the moment the process
	# starts until it exits, independent of whether percentage tracking
	# itself is working.
	ANNOUNCE_MIN_INTERVAL = 2.0
	CONVERTING_REPEAT_INTERVAL = 10.0
	start_time = time.time()
	last_announce_time = time.time()
	last_bucket = 0
	last_mb = -1
	in_postprocess = False
	last_converting_announce = 0.0
	while not stop_event.is_set() and process.poll() is None:
		try:
			now = time.time()
			if in_postprocess:
				if now - last_converting_announce >= CONVERTING_REPEAT_INTERVAL:
					last_converting_announce = now
					if announce_enabled:
						core.callLater(0, ui.message, _("Converting"))
				stop_event.wait(2)
				continue
			current_bytes = 0
			for entry in os.scandir(save_path):
				if entry.is_file() and entry.stat().st_mtime >= start_time - 5:
					current_bytes += entry.stat().st_size
			if current_bytes > 0:
				if total_bytes:
					percent = min(100, (current_bytes / total_bytes) * 100)
					bucket = int(percent // 10) * 10
					if bucket != last_bucket and (now - last_announce_time) >= ANNOUNCE_MIN_INTERVAL:
						last_bucket = bucket
						last_announce_time = now
						if announce_enabled:
							core.callLater(0, ui.message, _("{percent}%").format(percent=bucket))
					if needs_extraction and percent >= 95 \
							and (now - last_announce_time) >= ANNOUNCE_MIN_INTERVAL:
						in_postprocess = True
						last_announce_time = now
						last_converting_announce = now
						if announce_enabled:
							core.callLater(0, ui.message, _("Converting"))
				else:
					mb = int(current_bytes / (1024 * 1024))
					mb_bucket = (mb // 5) * 5
					if mb_bucket != last_mb and mb_bucket > 0 and (now - last_announce_time) >= ANNOUNCE_MIN_INTERVAL:
						last_mb = mb_bucket
						last_announce_time = now
						if announce_enabled:
							core.callLater(0, ui.message, _("{mb} MB downloaded").format(mb=mb_bucket))
		except Exception:
			pass
		stop_event.wait(2)

def _progress_beep_heartbeat(stop_event, process):
	# Plain time-based beep, independent of _poll_download_progress: beeps
	# on a fixed interval (config-controlled) from the moment the process
	# starts until it exits or stop_event is set, so it stays audible
	# for the whole download/convert regardless of whether byte/percentage
	# tracking is working for this particular file.
	try:
		interval = getINI("ProgressBeepIntervalSeconds")
		if interval < 1:
			interval = 1
	except Exception:
		interval = 10
	log(f"Progress beep heartbeat started, interval={interval}s")
	tickCount = 0
	# 5-step frequency cycle (was a 2-value alternation) -- close enough
	# together to still read as the same "tick" sound, just with a bit
	# more variety.
	TICK_FREQUENCIES = (600, 630, 660, 630, 600)
	# Polled in short slices rather than one long stop_event.wait(interval)
	# so a tick that's about to fire can be skipped if the process finished
	# during this same window -- otherwise the last tick and the complete
	# beep could land well under a second apart and read as a double-beep.
	POLL_GRANULARITY = 0.5
	elapsed = 0.0
	while not stop_event.is_set() and process.poll() is None:
		if stop_event.wait(POLL_GRANULARITY):
			break
		if process.poll() is not None:
			break
		elapsed += POLL_GRANULARITY
		if elapsed + 1e-6 < interval:
			continue
		elapsed = 0.0
		if stop_event.is_set() or process.poll() is not None:
			break
		tickCount += 1
		tickFrequency = TICK_FREQUENCIES[(tickCount - 1) % len(TICK_FREQUENCIES)]
		log(f"Progress beep heartbeat tick #{tickCount}")
		PlayProgressBeep(tickFrequency)
	log(f"Progress beep heartbeat ended after {tickCount} tick(s)")

def get_estimated_filesize(url, file_format):
	try:
		cmd = [YouTubeEXE, "--no-playlist", "--quiet"]
		if file_format in ("mp3", "wav"):
			cmd += ["-f", "bestaudio/best"]
		else:
			cmd += ["-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b"]
		cmd += ["--print", "filesize,filesize_approx", url]
		result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
								creationflags=subprocess.CREATE_NO_WINDOW, timeout=60)
		if result.returncode == 0:
			for line in result.stdout.strip().splitlines():
				line = line.strip()
				if line and line.upper() != "NA":
					try:
						return int(float(line))
					except ValueError:
						continue
		return None
	except Exception:
		return None

def run_download(item):
	download_id = item["id"]
	cmd = item["cmd"]
	save_path = item["path"]
	url = item["url"]
	title = item["title"]
	file_format = item["format"]
	is_trimming = item.get("trimming", False)
	is_multipart_download = item.get("is_multipart", False)
	requested_connections = item.get("requested_connections")

	with _global_active_lock:
		global _global_active_downloads
		_global_active_downloads += 1
		concurrent_downloads = _global_active_downloads

	if is_multipart_download and requested_connections:
		bandwidth_capped = estimate_optimal_connections(requested_connections)
		if concurrent_downloads > 1:
			effective_connections = max(2, bandwidth_capped // concurrent_downloads)
		else:
			effective_connections = bandwidth_capped
		if effective_connections != requested_connections:
			cmd = _adjust_multipart_connections(cmd, effective_connections)
			item["cmd"] = cmd

	updateDownloadStatusInQueue(download_id, "running")
	PlayStartBeep()
	process = None
	try:
		DEFAULT_TIMEOUT = 10800
		# get_video_duration() is a separate, synchronous subprocess/network
		# round-trip (up to several seconds) that was previously run before
		# launching the actual download -- that's what was delaying the
		# heartbeat's first tick well past the start beep, since nothing
		# past it (including Popen() and starting the heartbeat thread)
		# could begin until it returned. It only ever matters for videos
		# over ~55 minutes anyway (DEFAULT_TIMEOUT already covers 3 hours
		# via the max() below), so it's fetched in parallel on its own
		# thread instead; timeoutHolder is read fresh at the point
		# process.wait() actually needs it, whatever value is in it by then.
		timeoutHolder = [DEFAULT_TIMEOUT]
		def _fetchDurationForTimeout():
			try:
				duration_seconds = get_video_duration(url)
				if duration_seconds:
					timeoutHolder[0] = max(DEFAULT_TIMEOUT, int(duration_seconds * 3) + 900)
			except Exception:
				pass
		threading.Thread(target=_fetchDurationForTimeout, daemon=True).start()
		si = subprocess.STARTUPINFO()
		si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
		si.wShowWindow = subprocess.SW_HIDE
		# stderr is captured to a real temp file instead of subprocess.PIPE.
		# communicate() on Windows hangs indefinitely past its own timeout
		# if yt-dlp spawns a grandchild (ffmpeg, etc.) that inherits the
		# pipe's write handle and outlives yt-dlp itself -- the reader
		# thread never sees EOF, so .join() inside communicate() blocks
		# forever regardless of the timeout= value passed in. A file
		# doesn't have that problem: process.wait() bounds correctly on
		# the process handle itself, and we just read the file afterward.
		stderrLogPath = None
		stderrLogFile = None
		try:
			stderrFd, stderrLogPath = tempfile.mkstemp(prefix="ytdlp_stderr_", suffix=".log")
			stderrLogFile = os.fdopen(stderrFd, "wb")
		except Exception:
			stderrLogPath = None
			stderrLogFile = None
		process = subprocess.Popen(
			cmd,
			stdout=subprocess.DEVNULL,
			stderr=(stderrLogFile if stderrLogFile else subprocess.DEVNULL),
			stdin=subprocess.DEVNULL,
			cwd=save_path,
			startupinfo=si,
			creationflags=subprocess.CREATE_NO_WINDOW
		)
		if stderrLogFile:
			stderrLogFile.close()
		progress_stop_event = None
		if not is_trimming:
			announce_enabled = getINI("AnnounceDownloadProgress")
			if announce_enabled:
				core.callLater(0, ui.message, _("0%"))
			progress_stop_event = threading.Event()
			# Heartbeat is started before the (potentially several-second)
			# filesize estimate below, and before _poll_download_progress,
			# so its interval timer starts counting from right when the
			# subprocess actually begins -- as close as possible to the
			# moment the start beep played -- rather than only after
			# get_estimated_filesize() happens to finish.
			heartbeat_thread = threading.Thread(
				target=_progress_beep_heartbeat,
				args=(progress_stop_event, process),
				daemon=True
			)
			heartbeat_thread.start()
			estimated_total_bytes = get_estimated_filesize(url, file_format)
			progress_thread = threading.Thread(
				target=_poll_download_progress,
				args=(save_path, estimated_total_bytes, process, progress_stop_event,
					  file_format in ("mp3", "wav"), announce_enabled),
				daemon=True
			)
			progress_thread.start()

		def monitor_process():
			try:
				process.wait(timeout=timeoutHolder[0])
				return_code = process.returncode
				stderr_text = ""
				if stderrLogPath:
					try:
						with open(stderrLogPath, "rb") as f:
							stderr_text = f.read().decode('utf-8', errors='replace').strip()
					except Exception:
						stderr_text = ""
				if return_code == 0:
					if is_trimming:
						PlayTrimCompleteBeep()
					else:
						PlayCompleteBeep()
					if getINI("SayDownloadComplete"):
						core.callLater(0, ui.message, _("Download complete"))
					updateDownloadStatusInQueue(download_id, "completed")
					remove_failed_download(url, title)
				else:
					retry_count = item.get("_multipart_retry_count", 0)
					is_retryable_error = _looks_like_downloader_error(stderr_text)
					aria2c_itself_failed = "aria2c" in stderr_text.lower()
					if is_multipart_download and retry_count < 2 and is_retryable_error:
						if aria2c_itself_failed and retry_count >= 1:
							fallback_connections = max(1, item.get("requested_connections") or 4)
							item["cmd"] = _fallback_to_native_downloader(item["cmd"], fallback_connections)
							item["is_multipart"] = False
						else:
							original_connections = item.get("requested_connections") or 4
							reduced_connections = max(1, original_connections // 2)
							item["requested_connections"] = reduced_connections
							item["is_multipart"] = True
						item["_multipart_retry_count"] = retry_count + 1
						time.sleep(2)
						updateDownloadStatusInQueue(download_id, "queued")
						_download_queue.put(item)
					elif (not is_multipart_download) and retry_count < 2 and is_retryable_error:
						item["_multipart_retry_count"] = retry_count + 1
						time.sleep(3)
						updateDownloadStatusInQueue(download_id, "queued")
						_download_queue.put(item)
					else:
						PlayFailBeep()
						premiere_match = re.search(r'Premieres? in ([^\n\r]+)', stderr_text)
						live_match = re.search(r'This live event will begin in ([^\n\r]+)', stderr_text)
						is_forbidden = "http error 403" in stderr_text.lower()
						if premiere_match:
							core.callLater(0, ui.message, _("This video hasn't premiered yet. It starts in {time}.").format(time=premiere_match.group(1).strip()))
						elif live_match:
							core.callLater(0, ui.message, _("This livestream hasn't started yet. It starts in {time}.").format(time=live_match.group(1).strip()))
						elif is_forbidden:
							core.callLater(0, ui.message, _("Download failed: YouTube blocked this request. Try exporting cookies from your browser in the Anti-blocking settings."))
						else:
							core.callLater(0, ui.message, _("Download failed"))
						updateDownloadStatusInQueue(download_id, "failed")
						duration = get_video_duration(url)
						add_failed_download(url, title, file_format, duration)
			except subprocess.TimeoutExpired:
				if process:
					_kill_process_tree(process.pid)
					try:
						process.wait(timeout=5)
					except Exception:
						pass
				PlayFailBeep()
				core.callLater(0, ui.message, _("Download failed due to timeout"))
				updateDownloadStatusInQueue(download_id, "failed")
				duration = get_video_duration(url)
				add_failed_download(url, title, file_format, duration)
			except Exception:
				if process:
					_kill_process_tree(process.pid)
					try:
						process.wait(timeout=5)
					except Exception:
						pass
				PlayFailBeep()
				core.callLater(0, ui.message, _("Download failed due to an error"))
				updateDownloadStatusInQueue(download_id, "failed")
			finally:
				if stderrLogPath:
					try:
						os.remove(stderrLogPath)
					except Exception:
						pass
				if progress_stop_event:
					progress_stop_event.set()
				if not is_trimming:
					_cleanup_temp_files(save_path, title, file_format)
				removeCompletedOrFailedDownloadsFromQueue()
				remove_pending_download_by_url(url, file_format)
				with _global_active_lock:
					global _global_active_downloads
					_global_active_downloads -= 1
				core.callLater(0, start_next_pending)
		# Run synchronously on this worker thread rather than handing off to a
		# new detached thread. worker_loop() already dedicates one thread per
		# _num_workers slot and blocks on _download_queue.get() between items,
		# so calling monitor_process() directly here is what makes
		# MaxConcurrentDownloads actually throttle concurrency. Spawning a
		# separate thread let worker_loop immediately grab the next queued
		# item (including fast-retried failures) while the previous
		# download's process was still running, so downloads and retries
		# piled up in parallel regardless of the configured limit -- this is
		# what was driving the CPU/RAM spikes with a large failed-download
		# backlog even though only 1 worker was configured.
		monitor_process()
	except Exception:
		if process:
			process.terminate()
		PlayFailBeep()
		core.callLater(0, ui.message, _("Download failed to start"))
		updateDownloadStatusInQueue(download_id, "failed")
		remove_pending_download_by_url(url, file_format)
		with _global_active_lock:
			_global_active_downloads -= 1

def convertToMP(mpFormat, savePath, isPlaylist=False, url=None, title=None):
	if not createFolder(savePath):
		return
	if os.path.isdir(savePath):
		repairIncompleteFiles(savePath)
	current_url = url or getCurrentDocumentURL()
	link_url = getLinkURL()
	if not current_url:
		current_url = link_url
	if not current_url:
		core.callLater(0, ui.message, _("URL not found"))
		return
	is_youtube_url_flag = any(y in current_url.lower() for y in [".youtube.", "youtu.be", "youtube.com"])
	if is_youtube_url_flag:
		current_url = clean_youtube_url(current_url, isPlaylist)
		video_title = title if title else getWebSiteTitle()
		sanitized_title = validFilename(video_title)
		if not isPlaylist:
			if checkFileExists(savePath, sanitized_title, mpFormat):
				if mpFormat in ["mp3", "wav"] and os.path.exists(os.path.join(savePath, f"{sanitized_title}.mp4")):
					pass
				else:
					core.callLater(0, ui.message, _("File exists"))
					return
		if not isPlaylist:
			try:
				parsed = urllib.parse.urlparse(current_url)
				query_params = urllib.parse.parse_qs(parsed.query)
				if 'list' in query_params: del query_params['list']
				if 'index' in query_params: del query_params['index']
				new_query = urllib.parse.urlencode(query_params, doseq=True)
				current_url = urllib.parse.urlunparse((
					parsed.scheme, parsed.netloc, parsed.path,
					parsed.params, new_query, parsed.fragment
				))
			except Exception:
				core.callLater(0, ui.message, _("Error processing URL"))
				return
		if not os.path.exists(YouTubeEXE):
			core.callLater(0, ui.message, _("yt-dlp.exe missing"))
			return
		# Start beep now lives solely in run_download() -- see the comment
		# there. It fires once, uniformly, for every item pulled off the
		# queue regardless of whether it got there from here, from a
		# resumed-after-restart download, or from an internal retry, none
		# of which go through this function again. Beeping here too was
		# firing twice in quick succession for the common case (this
		# function queues the item, then worker_loop picks it up and
		# beeps again within milliseconds).
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
			autoCookiesBrowser = getINI("AutoCookiesBrowser") or "chrome"
			base_cmd.extend(["--cookies-from-browser", autoCookiesBrowser])
		if getINI("UseCookies") and getINI("CookiesFile"):
			cookies_file = getINI("CookiesFile")
			if os.path.exists(cookies_file):
				base_cmd.extend(["--cookies", cookies_file])
		if getINI("UseCustomUserAgent") and getINI("CustomUserAgent"):
			base_cmd.extend(["--user-agent", getINI("CustomUserAgent")])
		if getINI("UseProxy") and getINI("ProxyURL"):
			base_cmd.extend(["--proxy", getINI("ProxyURL")])
		if getINI("GeoBypass"):
			base_cmd.append("--geo-bypass")
			if getINI("GeoBypassCountry"):
				base_cmd.extend(["--geo-bypass-country", getINI("GeoBypassCountry")])
			if getINI("GeoBypassIP"):
				base_cmd.extend(["--geo-bypass-ip", getINI("GeoBypassIP")])
		if getINI("ForceIpv4"): base_cmd.append("--force-ipv4")
		if getINI("ForceIpv6"): base_cmd.append("--force-ipv6")
		if getINI("ThrottleRate") > 0:
			base_cmd.extend(["--limit-rate", f"{getINI('ThrottleRate')}K"])
		if getINI("SleepBetweenRequests") > 0:
			base_cmd.extend(["--sleep-interval", str(getINI("SleepBetweenRequests"))])
		if getINI("UseSponsorBlock"):
			base_cmd.extend(["--sponsorblock-api", "https://sponsor.ajay.app", "--sponsorblock-mark", getINI("SponsorBlockCategories")])
		if getINI("AbortOnError"): base_cmd.append("--abort-on-error")
		if getINI("SkipUnavailableFragments"): base_cmd.append("--skip-unavailable-fragments")
		if getINI("MarkWatched"): base_cmd.append("--mark-watched")
		safe_connections = min(connections, 16)
		if mpFormat == "mp3":
			cmd = base_cmd + [
				"-x", "--audio-format", "mp3",
				"--audio-quality", str(getINI("MP3Quality")),
				"--ffmpeg-location", ConverterEXE,
				"-o", output_template, current_url
			]
			if use_multipart:
				aria2_args = f"-x{safe_connections} -j{safe_connections} -s{safe_connections} -k1M --disk-cache=32M --file-allocation=none --allow-overwrite=true --max-tries=3 --retry-wait=5 --quiet --console-log-level=error"
				cmd.extend(["--external-downloader", Aria2cEXE, "--external-downloader-args", f"aria2c:{aria2_args}"])
		elif mpFormat == "wav":
			cmd = base_cmd + [
				"-x", "--audio-format", "wav",
				"--audio-quality", "0",
				"--ffmpeg-location", ConverterEXE,
				"-o", output_template, current_url
			]
			if use_multipart:
				aria2_args = f"-x{safe_connections} -j{safe_connections} -s{safe_connections} -k1M --disk-cache=32M --file-allocation=none --allow-overwrite=true --max-tries=3 --retry-wait=5 --quiet --console-log-level=error"
				cmd.extend(["--external-downloader", Aria2cEXE, "--external-downloader-args", f"aria2c:{aria2_args}"])
		else:
			cmd = base_cmd + [
				"-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
				"--remux-video", "mp4",
				"--ffmpeg-location", ConverterEXE,
				"-o", output_template, current_url
			]
			if use_multipart:
				aria2_args = f"-x{safe_connections} -j{safe_connections} -s{safe_connections} -k1M --disk-cache=32M --file-allocation=none --allow-overwrite=true --max-tries=3 --retry-wait=5 --quiet --console-log-level=error"
				cmd.extend(["--external-downloader", Aria2cEXE, "--external-downloader-args", f"aria2c:{aria2_args}"])
			else:
				cmd.extend(["--concurrent-fragments", str(safe_connections)])
		download_obj = {
			"url": current_url, "title": sanitized_title, "format": mpFormat,
			"path": savePath, "cmd": cmd, "is_playlist": isPlaylist,
			"is_multipart": use_multipart, "requested_connections": safe_connections
		}
		addDownloadToQueue(download_obj)
		_download_queue.put(download_obj)
	else:
		ext = getMultimediaURLExtension().lstrip(".")
		if ext and isValidMultimediaExtension(ext):
			if not os.path.exists(ConverterEXE):
				core.callLater(0, ui.message, _("Error: ffmpeg.exe not found."))
				return
			multimediaLinkURL = getLinkURL()
			linkName = getLinkName()
			if checkFileExists(savePath, linkName, mpFormat):
				core.callLater(0, ui.message, _("File already exists. Skipping download."))
				return
			if not multimediaLinkURL:
				core.callLater(0, ui.message, _("No valid multimedia link found."))
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
			core.callLater(0, ui.message, _("Adding link as {format} to download queue").format(format=mpFormat.upper()))
			# Same reasoning as the other convertToMP() call site above --
			# run_download() beeps once when worker_loop actually picks
			# this item up, so beeping here too would double up.
			download_obj = {
				"url": multimediaLinkURL, "title": linkName, "format": mpFormat,
				"path": savePath, "cmd": cmd, "is_playlist": False
			}
			addDownloadToQueue(download_obj)
			_download_queue.put(download_obj)
		else:
			core.callLater(0, ui.message, _("Not a YouTube video or valid multimedia link"))

def setSpeed(sp):
	speech.setSpeechOption("rate", sp)
	speech.speak(" ")



