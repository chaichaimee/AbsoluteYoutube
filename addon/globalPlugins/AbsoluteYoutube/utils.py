# utils.py
import re
import glob
import os
import urllib.parse
import api
import controlTypes
import logging

log = logging.getLogger("AbsoluteYoutube")

def _find_next_trim_number(save_path):
	try:
		existing_files = glob.glob(os.path.join(save_path, "Trimmed Clip *.mp3"))
		existing_files.extend(glob.glob(os.path.join(save_path, "Trimmed Clip *.mp4")))
		existing_files.extend(glob.glob(os.path.join(save_path, "Trimmed Clip *.wav")))
		numbers = []
		for file_path in existing_files:
			match = re.search(r"Trimmed Clip (\d+).(mp3|mp4|wav)$", os.path.basename(file_path))
			if match:
				numbers.append(int(match.group(1)))
		return max(numbers) + 1 if numbers else 1
	except Exception:
		return 1

def _format_timedelta(seconds):
	hours = seconds // 3600
	minutes = (seconds % 3600) // 60
	seconds = seconds % 60
	return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

def getLinkURL():
	obj = api.getNavigatorObject()
	if obj and obj.role == controlTypes.Role.LINK:
		url = getattr(obj, 'value', None)
		if url:
			log.debug(f"getLinkURL: {url}")
			url = urllib.parse.unquote(url)
			return url[:-1] if url.endswith("/") else url
	return ""

def getLinkName():
	obj = api.getNavigatorObject()
	if obj and obj.role == controlTypes.Role.LINK:
		return obj.name
	return ""

def is_youtube_url(url):
	if not url:
		return False
	lower_url = url.lower()
	return any(domain in lower_url for domain in ["youtube.com", "youtu.be"])

def is_youtube_video_url(url):
	if not url:
		return False
	lower_url = url.lower()
	return any(x in lower_url for x in ["youtube.com/watch", "youtu.be/", "youtube.com/shorts/"])

def is_channel_or_playlist_url(url):
	if not url:
		return False
	lower_url = url.lower()
	channel_pattern = r'(youtube\.com/(@|channel/|c/|user/))'
	playlist_pattern = r'(youtube\.com/playlist\?.*list=)'
	return bool(re.search(channel_pattern, lower_url) or re.search(playlist_pattern, lower_url))

def _find_link_in_parents(obj):
	current = obj
	for _ in range(10):
		if not current:
			break
		if current.role == controlTypes.Role.LINK:
			url = getattr(current, 'value', None)
			if url and is_youtube_url(url):
				log.debug(f"Found LINK in parent: {url}")
				return url, getattr(current, 'name', None)
		current = current.parent
	return None, None

def _find_link_in_children(obj):
	if not obj:
		return None, None
	for child in obj.children:
		if child.role == controlTypes.Role.LINK:
			url = getattr(child, 'value', None)
			if url and is_youtube_url(url):
				log.debug(f"Found LINK in child: {url}")
				return url, getattr(child, 'name', None)
		sub_url, sub_title = _find_link_in_children(child)
		if sub_url:
			return sub_url, sub_title
	return None, None

def get_url_from_object(obj):
	if not obj:
		return None, None
	
	if obj.role == controlTypes.Role.LINK:
		url = getattr(obj, 'value', None)
		if url and is_youtube_url(url):
			title = getattr(obj, 'name', None)
			log.debug(f"URL from LINK object: {url}")
			return url, title
	
	url = getattr(obj, 'value', None)
	if url and is_youtube_url(url):
		title = getattr(obj, 'name', None)
		log.debug(f"URL from object value: {url}")
		return url, title
	
	try:
		ia2_attrs = getattr(obj, 'IAccessible2Attributes', {})
		if isinstance(ia2_attrs, dict):
			for key in ['href', 'url', 'data-url', 'data-video-url']:
				if key in ia2_attrs and is_youtube_url(ia2_attrs[key]):
					url = ia2_attrs[key]
					title = getattr(obj, 'name', None)
					log.debug(f"URL from IAccessible2 attr {key}: {url}")
					return url, title
	except Exception:
		pass
	
	child_url, child_title = _find_link_in_children(obj)
	if child_url:
		return child_url, child_title
	
	parent_url, parent_title = _find_link_in_parents(obj)
	if parent_url:
		return parent_url, parent_title
	
	return None, None

def get_focused_youtube_link():
	nav_obj = api.getNavigatorObject()
	url, title = get_url_from_object(nav_obj)
	if url:
		log.debug(f"Using navigator object URL via get_url_from_object: {url}")
		return url, title
	
	focused = api.getFocusObject()
	url, title = get_url_from_object(focused)
	if url:
		log.debug(f"Using focused object URL: {url}")
		return url, title
	
	legacy_url = getLinkURL()
	if legacy_url and is_youtube_url(legacy_url):
		legacy_title = getLinkName()
		log.debug(f"Using legacy getLinkURL: {legacy_url}")
		return legacy_url, legacy_title
	
	log.debug("get_focused_youtube_link: No YouTube URL found")
	return None, None

def remove_playlist_params(url):
	if not url or not is_youtube_url(url):
		return url
	try:
		parsed = urllib.parse.urlparse(url)
		query_params = urllib.parse.parse_qs(parsed.query)
		if 'list' in query_params:
			del query_params['list']
		if 'index' in query_params:
			del query_params['index']
		new_query = urllib.parse.urlencode(query_params, doseq=True)
		clean_url = urllib.parse.urlunparse((
			parsed.scheme, parsed.netloc, parsed.path,
			parsed.params, new_query, parsed.fragment
		))
		log.debug(f"Removed playlist params: {url} -> {clean_url}")
		return clean_url
	except Exception as e:
		log.error(f"Error removing playlist params: {e}")
		return url

def extract_video_id_from_url(url):
	if not url:
		return None
	patterns = [
		r'(?:youtube\.com\/watch\?v=)([\w-]+)',
		r'(?:youtu\.be\/)([\w-]+)',
		r'(?:youtube\.com\/shorts\/)([\w-]+)'
	]
	for pattern in patterns:
		match = re.search(pattern, url)
		if match:
			return match.group(1)
	return None