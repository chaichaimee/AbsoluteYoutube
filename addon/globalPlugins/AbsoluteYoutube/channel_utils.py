# channel_utils.py
import os
import re
import json
import urllib.parse
import threading
import addonHandler
import globalVars
from .Download_core import log

addonHandler.initTranslation()

CHANNEL_DATA_DIR = os.path.join(
	globalVars.appArgs.configPath,
	'ChaiChaimee', 'AbsoluteYoutube', 'Channel'
)
PINNED_ORDER_FILE = os.path.join(
	globalVars.appArgs.configPath,
	'ChaiChaimee', 'AbsoluteYoutube', 'pinned_order.json'
)
VIDEO_CACHE_FILE = os.path.join(
	globalVars.appArgs.configPath,
	'ChaiChaimee', 'AbsoluteYoutube', 'video_cache.json'
)

_cache_lock = threading.Lock()
_cache_dirty = False
_cache_debounce_timer = None
_internal_cache = None

def ensure_channel_dir():
	if not os.path.exists(CHANNEL_DATA_DIR):
		os.makedirs(CHANNEL_DATA_DIR, exist_ok=True)
		log(f"Created channel data directory: {CHANNEL_DATA_DIR}")

def sanitize_filename(name):
	invalid_chars = r'[\\/*?:"<>|]'
	name = re.sub(invalid_chars, '_', name)
	name = ''.join(c if ord(c) >= 32 else '_' for c in name)
	name = name.strip(' .')
	if not name:
		name = 'unnamed'
	return name

def get_channel_filepath(channel_identifier):
	filename = sanitize_filename(channel_identifier) + '.json'
	return os.path.join(CHANNEL_DATA_DIR, filename)

def load_channel_videos(filepath):
	if os.path.exists(filepath):
		try:
			with open(filepath, 'r', encoding='utf-8') as f:
				return json.load(f)
		except Exception as e:
			log(f"Error loading {filepath}: {e}")
	return []

def save_channel_videos(filepath, videos, channel_url=None, content_type="videos", playlist_data=None):
	data = {
		'channel_url': channel_url,
		'videos': videos,
		'content_type': content_type
	}
	if playlist_data:
		data['playlist_data'] = playlist_data
	try:
		os.makedirs(os.path.dirname(filepath), exist_ok=True)
		with open(filepath, 'w', encoding='utf-8') as f:
			json.dump(data, f, ensure_ascii=False, indent=2)
		log(f"Saved {len(videos)} videos to {filepath}")
	except Exception as e:
		log(f"Error saving {filepath}: {e}")

def get_all_channel_files():
	ensure_channel_dir()
	files = []
	for f in os.listdir(CHANNEL_DATA_DIR):
		if f.endswith('.json'):
			path = os.path.join(CHANNEL_DATA_DIR, f)
			name = f[:-5]
			files.append((name, path))
	return files

def _get_internal_cache():
	global _internal_cache
	if _internal_cache is None:
		_internal_cache = load_video_cache()
	return _internal_cache

def load_video_cache():
	if os.path.exists(VIDEO_CACHE_FILE):
		try:
			with open(VIDEO_CACHE_FILE, 'r', encoding='utf-8') as f:
				return json.load(f)
		except Exception as e:
			log(f"Error loading video cache: {e}")
	return {}

def _do_save_video_cache():
	global _cache_dirty, _cache_debounce_timer, _internal_cache
	with _cache_lock:
		if not _cache_dirty:
			return
		try:
			os.makedirs(os.path.dirname(VIDEO_CACHE_FILE), exist_ok=True)
			with open(VIDEO_CACHE_FILE, 'w', encoding='utf-8') as f:
				json.dump(_internal_cache if _internal_cache else {}, f, ensure_ascii=False, indent=2)
			_cache_dirty = False
			log("Video cache saved (debounced)")
		except Exception as e:
			log(f"Error saving video cache: {e}")
		_cache_debounce_timer = None

def schedule_video_cache_save(delay=2.0):
	global _cache_debounce_timer
	with _cache_lock:
		if _cache_debounce_timer:
			_cache_debounce_timer.cancel()
		_cache_debounce_timer = threading.Timer(delay, _do_save_video_cache)
		_cache_debounce_timer.daemon = True
		_cache_debounce_timer.start()

def update_video_cache(video_url, video_info):
	global _cache_dirty
	cache = _get_internal_cache()
	cache[video_url] = video_info
	with _cache_lock:
		_cache_dirty = True
	schedule_video_cache_save()

def get_video_from_cache(video_url):
	cache = _get_internal_cache()
	return cache.get(video_url)

def flush_video_cache():
	global _cache_debounce_timer
	with _cache_lock:
		if _cache_debounce_timer:
			_cache_debounce_timer.cancel()
			_cache_debounce_timer = None
		if _cache_dirty:
			_do_save_video_cache()

def merge_videos(old_videos, new_videos):
	cache = _get_internal_cache()
	old_by_url = {v['url']: v for v in old_videos}
	seen_urls = set()
	merged = []

	for new_v in new_videos:
		url = new_v['url']
		cached_info = get_video_from_cache(url)
		if cached_info:
			video = {
				'url': url,
				'title': cached_info.get('title', new_v.get('title', 'Untitled')),
				'duration': cached_info.get('duration', new_v.get('duration', '')),
				'title_finalized': True
			}
			if 'is_playlist' in new_v:
				video['is_playlist'] = new_v['is_playlist']
		else:
			video = new_v.copy()
			update_video_cache(url, {
				'title': video.get('title', ''),
				'duration': video.get('duration', ''),
				'title_finalized': video.get('title_finalized', False)
			})

		if url in old_by_url:
			old_v = old_by_url[url]
			if url not in seen_urls:
				merged.append(old_v)
				seen_urls.add(url)
		else:
			if url not in seen_urls:
				merged.append(video)
				seen_urls.add(url)

	for old_v in old_videos:
		if old_v['url'] not in seen_urls:
			merged.append(old_v)
			seen_urls.add(old_v['url'])

	return merged

def create_short_youtube_url(full_url):
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
	except Exception:
		return None

def load_pinned_order():
	if os.path.exists(PINNED_ORDER_FILE):
		try:
			with open(PINNED_ORDER_FILE, 'r', encoding='utf-8') as f:
				return json.load(f)
		except Exception as e:
			log(f"Error loading pinned order: {e}")
	return []

def save_pinned_order(order_list):
	try:
		os.makedirs(os.path.dirname(PINNED_ORDER_FILE), exist_ok=True)
		with open(PINNED_ORDER_FILE, 'w', encoding='utf-8') as f:
			json.dump(order_list, f, indent=2)
		log(f"Saved pinned order: {order_list}")
	except Exception as e:
		log(f"Error saving pinned order: {e}")

def update_pinned_after_rename(old_id, new_id):
	order = load_pinned_order()
	if old_id in order:
		order[order.index(old_id)] = new_id
		save_pinned_order(order)

def update_pinned_after_delete(channel_id):
	order = load_pinned_order()
	if channel_id in order:
		order.remove(channel_id)
		save_pinned_order(order)

def get_base_channel_url(url):
	if not url:
		return None
	base = url.split('?')[0]
	base = re.sub(r'/(videos|shorts|streams|podcasts|playlists)$', '', base)
	return base