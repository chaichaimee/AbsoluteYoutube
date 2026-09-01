# channel_utils.py

import os
import re
import json
import urllib.parse
import threading
import addonHandler
from .Download_core import log, getAddonConfigBaseDir

addonHandler.initTranslation()

_addonConfigBaseDir = getAddonConfigBaseDir()

CHANNEL_DATA_DIR = os.path.join(
	_addonConfigBaseDir,
	'ChaiChaimee', 'AbsoluteYoutube', 'Channel'
)
PINNED_ORDER_FILE = os.path.join(
	_addonConfigBaseDir,
	'ChaiChaimee', 'AbsoluteYoutube', 'pinned_order.json'
)
VIDEO_CACHE_FILE = os.path.join(
	_addonConfigBaseDir,
	'ChaiChaimee', 'AbsoluteYoutube', 'video_cache.json'
)

_cache_lock = threading.RLock()
_cache_dirty = False
_cache_debounce_timer = None
_internal_cache = None
MAX_CACHE_SIZE_BYTES = 3 * 1024 * 1024
CACHE_TARGET_SIZE_BYTES = 2 * 1024 * 1024

def _atomic_write_json(filepath, data):
	# Writing straight to the target file means a crash or forced process
	# kill mid-write leaves a truncated/corrupt json file that fails to load
	# next time. Write to a temp file first and os.replace() into place --
	# that rename is atomic on both Windows and POSIX, so the target file is
	# always either the complete old version or the complete new one.
	os.makedirs(os.path.dirname(filepath), exist_ok=True)
	tmp_path = filepath + f'.{os.getpid()}.tmp'
	with open(tmp_path, 'w', encoding='utf-8') as f:
		json.dump(data, f, ensure_ascii=False, indent=2)
	os.replace(tmp_path, filepath)

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

CONTENT_TYPES = ("videos", "shorts", "streams", "podcasts", "playlists")

def get_channel_filepath(channel_identifier, content_type="videos"):
	base_filename = sanitize_filename(channel_identifier)
	if content_type and content_type != "videos":
		base_filename += f"__{content_type}"
	return os.path.join(CHANNEL_DATA_DIR, base_filename + '.json')

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
		_atomic_write_json(filepath, data)
		log(f"Saved {len(videos)} videos to {filepath}")
	except Exception as e:
		log(f"Error saving {filepath}: {e}")

def get_all_channel_files():
	# Each channel can now have a separate file per content type
	# (name.json for videos, name__shorts.json, name__playlists.json, etc.)
	# so they stop clobbering each other. The channel picker should still
	# show one entry per channel though, so group by base name here and
	# prefer the "videos" file as the representative path for that entry.
	ensure_channel_dir()
	suffix_pattern = re.compile(r'^(.*)__(' + '|'.join(t for t in CONTENT_TYPES if t != "videos") + r')$')
	grouped = {}
	for f in os.listdir(CHANNEL_DATA_DIR):
		if not f.endswith('.json'):
			continue
		name = f[:-5]
		match = suffix_pattern.match(name)
		base_name = match.group(1) if match else name
		is_videos_file = match is None
		path = os.path.join(CHANNEL_DATA_DIR, f)
		if base_name not in grouped or is_videos_file:
			grouped[base_name] = path
	return list(grouped.items())

def _get_internal_cache():
	global _internal_cache
	if _internal_cache is None:
		_internal_cache = load_video_cache()
	return _internal_cache

def load_video_cache():
	if os.path.exists(VIDEO_CACHE_FILE):
		try:
			with open(VIDEO_CACHE_FILE, 'r', encoding='utf-8') as f:
				cache_data = json.load(f)
				if not isinstance(cache_data, dict):
					log("Cache file corrupted, resetting.")
					return {}
				return cache_data
		except Exception as e:
			log(f"Error loading video cache: {e}")
	return {}

def _enforce_cache_size_limit():
	global _internal_cache, _cache_dirty
	if _internal_cache is None:
		_internal_cache = {}
		return

	current_size = 0
	try:
		current_size = os.path.getsize(VIDEO_CACHE_FILE)
	except OSError:
		pass

	if current_size > MAX_CACHE_SIZE_BYTES and _internal_cache:
		log(f"Cache size {current_size} bytes exceeds limit {MAX_CACHE_SIZE_BYTES}. Trimming...")
		# Keep the most-recently-accessed entries (proper LRU eviction) and
		# stop once we hit the target size. Each entry's size is computed once
		# and added to a running total -- O(N) overall. The previous version
		# re-serialized the entire (growing) new_cache dict to JSON on every
		# single item to check its size, which is O(N^2) and was freezing
		# NVDA for tens of seconds once the cache grew large.
		sorted_items = sorted(
			_internal_cache.items(),
			key=lambda x: x[1].get('last_accessed', 0),
			reverse=True
		)
		new_cache = {}
		running_size = 2  # account for the surrounding {}
		for url, info in sorted_items:
			try:
				entry_size = len(json.dumps({url: info}, ensure_ascii=False).encode('utf-8'))
			except Exception:
				entry_size = 0
			if running_size + entry_size > CACHE_TARGET_SIZE_BYTES:
				break
			new_cache[url] = info
			running_size += entry_size

		_internal_cache = new_cache
		_cache_dirty = True
		log(f"Trimmed cache to {len(_internal_cache)} items.")
		schedule_video_cache_save(delay=0.5)

def _do_save_video_cache():
	global _cache_dirty, _cache_debounce_timer, _internal_cache
	with _cache_lock:
		if not _cache_dirty:
			return
		try:
			_enforce_cache_size_limit()
			_atomic_write_json(VIDEO_CACHE_FILE, _internal_cache if _internal_cache else {})
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
	if video_url not in cache:
		cache[video_url] = {}

	current_info = cache[video_url]
	current_info.update(video_info)
	current_info['last_accessed'] = __import__('time').time()
	cache[video_url] = current_info

	with _cache_lock:
		_cache_dirty = True
	schedule_video_cache_save()

def get_video_from_cache(video_url):
	cache = _get_internal_cache()
	entry = cache.get(video_url)
	if entry:
		entry['last_accessed'] = __import__('time').time()
		return entry
	return None

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
		_atomic_write_json(PINNED_ORDER_FILE, order_list)
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



