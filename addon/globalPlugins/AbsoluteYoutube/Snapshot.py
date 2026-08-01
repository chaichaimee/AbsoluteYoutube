# Snapshot.py

import os
import re
import glob
import subprocess
import threading
import ui
import wx
import shutil
import addonHandler
from .Download_core import YouTubeEXE, log, PlayWave, clean_youtube_url

addonHandler.initTranslation()


def _find_next_snapshot_number(save_path):
	try:
		existing_files = glob.glob(os.path.join(save_path, "Snapshot *.jpg"))
		numbers = []
		for file_path in existing_files:
			match = re.search(r"Snapshot (\d+)\.jpg$", os.path.basename(file_path))
			if match:
				numbers.append(int(match.group(1)))
		if not numbers:
			return 1
		next_number = max(numbers) + 1
		return next_number
	except Exception as e:
		log(f"Error finding next snapshot number: {e}")
		return 1


def capture_snapshot(video_url, download_path):
	if not os.path.exists(download_path):
		try:
			os.makedirs(download_path, exist_ok=True)
		except Exception as e:
			log(f"Error creating directory: {e}")
			wx.CallAfter(ui.message, _("Error creating download folder"))
			return

	# Clean URL to remove playlist parameters and normalize
	cleaned_url = clean_youtube_url(video_url, is_playlist=False)
	log(f"Cleaned URL for snapshot: {cleaned_url}")

	next_number = _find_next_snapshot_number(download_path)
	output_filename = f"Snapshot {next_number}"

	temp_dir = os.path.join(download_path, "temp_snapshot_dir")
	os.makedirs(temp_dir, exist_ok=True)
	temp_output_path = os.path.join(temp_dir, f"{output_filename}.%(ext)s")

	final_output_path = os.path.join(download_path, f"{output_filename}.jpg")
	if os.path.exists(final_output_path):
		wx.CallAfter(ui.message, _("Snapshot file already exists"))
		return

	PlayWave("snapshot", force=True)
	wx.CallAfter(ui.message, _("Capturing full-size snapshot..."))

	def snapshot_worker():
		success = False
		try:
			wx.CallAfter(ui.message, _("Downloading thumbnail..."))
			cmd = [
				YouTubeEXE,
				cleaned_url,
				"--write-thumbnail",
				"--skip-download",
				"--no-playlist",
				"--no-check-certificate",
				"--convert-thumbnails", "jpg",
				"-o", temp_output_path
			]
			log(f"Snapshot command: {cmd}")

			process = subprocess.run(
				cmd,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				text=True,
				timeout=60,
				creationflags=subprocess.CREATE_NO_WINDOW
			)

			if process.returncode != 0:
				log(f"Snapshot capture failed (returncode {process.returncode}): {process.stderr}")
				wx.CallAfter(ui.message, _("Error: Failed to capture snapshot."))
				PlayWave("error")
				return

			wx.CallAfter(ui.message, _("Processing snapshot..."))

			# Find downloaded thumbnail file (may be .jpg, .webp, .png)
			downloaded_files = glob.glob(os.path.join(temp_dir, f"{output_filename}*"))
			if not downloaded_files:
				downloaded_files = glob.glob(os.path.join(temp_dir, "Snapshot*"))
			log(f"Found files in temp dir: {downloaded_files}")

			if not downloaded_files:
				log("No thumbnail file found after download")
				wx.CallAfter(ui.message, _("Error: No snapshot file created."))
				PlayWave("error")
				return

			# Prefer .jpg files
			jpg_files = [f for f in downloaded_files if f.lower().endswith('.jpg')]
			if jpg_files:
				downloaded_file = jpg_files[0]
			else:
				downloaded_file = downloaded_files[0]
				# If not jpg, rename to .jpg (yt-dlp should have converted, but safe)
				if not downloaded_file.lower().endswith('.jpg'):
					new_name = downloaded_file.rsplit('.', 1)[0] + '.jpg'
					shutil.move(downloaded_file, new_name)
					downloaded_file = new_name

			shutil.move(downloaded_file, final_output_path)
			success = True
			log(f"Snapshot saved to {final_output_path}")

		except Exception as e:
			log(f"Unexpected error during snapshot capture: {e}")
			wx.CallAfter(ui.message, _("An unexpected error occurred."))
			PlayWave("error")
		finally:
			if os.path.exists(temp_dir):
				shutil.rmtree(temp_dir)

			if success:
				wx.CallAfter(ui.message, _("Full-size snapshot complete"))
				PlayWave("complete", force=True)
			else:
				PlayWave("error")

	threading.Thread(target=snapshot_worker, daemon=True).start()

