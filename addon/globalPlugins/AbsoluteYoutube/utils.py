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
	"""Find the next available number for trimmed clip files"""
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
	"""Convert seconds to HH:MM:SS format without days"""
	hours = seconds // 3600
	minutes = (seconds % 3600) // 60
	seconds = seconds % 60
	return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"


def getLinkURL():
	"""Get the URL of the current link using the navigator object."""
	obj = api.getNavigatorObject()
	if obj and obj.role == controlTypes.Role.LINK:
		url = getattr(obj, 'value', None)
		if url:
			log.debug(f"getLinkURL: {url}")
			url = urllib.parse.unquote(url)
			return url[:-1] if url.endswith("/") else url
	return ""


def getLinkName():
	"""Get the name of the current link using the navigator object."""
	obj = api.getNavigatorObject()
	if obj and obj.role == controlTypes.Role.LINK:
		return obj.name
	return ""