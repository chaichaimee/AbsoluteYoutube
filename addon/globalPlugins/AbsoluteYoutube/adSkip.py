# adSkip.py

import functools
import re
import time
import unicodedata

import addonHandler
import api
import browseMode
import controlTypes
import core
import globalVars
import inputCore
import textInfos
import ui
import winUser
from comtypes import COMError
from logHandler import log
from speech.extensions import filter_speechSequence

from .Download_core import getINI

addonHandler.initTranslation()

BROWSER_APP_NAMES = ("chrome", "msedge", "firefox", "brave", "opera", "vivaldi", "thorium")
WATCH_URL_MARKERS = ("youtube.com/watch", "youtube.com/shorts/", "youtube.com/live/")
POLL_INTERVAL_MS = 1000
# A page that has just been opened is watched for this long. Every successful
# click extends the watch, so two ads in a row are both handled.
WATCH_WINDOW_SECONDS = 60
CHAIN_WINDOW_SECONDS = 30
SHORTCUT_WINDOW_SECONDS = 10
POST_CLICK_DELAY_MS = 1200
MIN_CLICK_INTERVAL_SECONDS = 1.2
MAX_CLICKS_PER_RUN = 6
RETRY_DELAY_SCHEDULE_MS = (300, 500, 900, 1500)
# The player sits near the top of the page buffer, so an automatic watch only
# reads the first part of the document on every pass instead of the whole page.
SCAN_PARAGRAPHS_PER_CHUNK = 10
MAX_SCAN_PARAGRAPHS_SILENT = 400
MAX_SCAN_PARAGRAPHS_SHORTCUT = 1500
MAX_COM_ERROR_STREAK = 6
MAX_BUTTON_TEXT_LENGTH = 60
ANCESTOR_CHECK_DEPTH = 6
DEFAULT_SKIP_WORD = "skip"
MAX_EXTRA_WORDS = 20
MAX_WORD_LENGTH = 40
MOUSE_DOWN_DELAY_MS = 50
MOUSE_UP_DELAY_MS = 100
# While a skip run is active, and for a while after a click, every announcement
# the user did not ask for is held back so the ad and the video play silently.
# Speech spoken shortly after a keypress, and the skip confirmation itself, pass.
GESTURE_SPEECH_WINDOW_SECONDS = 2.0
SKIP_FEEDBACK_PASS_SECONDS = 1.5
AD_SPEECH_TAIL_SECONDS = 20
# A YouTube watch page that has just gained focus is silent for this long, even
# for speech right after a keypress, so its window and page titles stay quiet.
PAGE_LOAD_HOLD_SECONDS = 3.0

_WORD_SEPARATORS = re.compile(r"[,;|\r\n]+")
_STALE_BUFFER_MARKERS = ("too big for buffer", "out of range", "is past end of buffer")
_SAFE_ERRORS = (COMError, AttributeError, RuntimeError, NotImplementedError, ValueError, OSError)
_EDITABLE_ROLES = tuple(
	role for role in (
		controlTypes.Role.EDITABLETEXT,
		controlTypes.Role.COMBOBOX,
		getattr(controlTypes.Role, "SEARCHBOX", None),
	) if role is not None
)


def parseSkipWords(text):
	words = []
	seenKeys = {DEFAULT_SKIP_WORD}
	for part in _WORD_SEPARATORS.split(text or ""):
		word = unicodedata.normalize("NFC", part.strip())
		word = word.removeprefix("^").removesuffix("$").strip()
		if not word or len(word) > MAX_WORD_LENGTH:
			continue
		key = word.casefold()
		if key in seenKeys:
			continue
		seenKeys.add(key)
		words.append(word)
		if len(words) >= MAX_EXTRA_WORDS:
			break
	return words


def cleanSkipWords(text):
	return ", ".join(parseSkipWords(text))


@functools.lru_cache(maxsize=8)
def buildSkipWordSet(extraWordsText):
	# Whole-text, case-insensitive comparison: the same result as ^skip$ with
	# the ignore-case flag, without compiling anything from the settings field.
	return frozenset(word.casefold() for word in [DEFAULT_SKIP_WORD] + parseSkipWords(extraWordsText))


def _normalizeText(text):
	if not text:
		return ""
	return unicodedata.normalize("NFC", text.strip())


def _isEditableObject(targetObj):
	try:
		if targetObj.role in _EDITABLE_ROLES:
			return True
		return controlTypes.State.EDITABLE in targetObj.states
	except _SAFE_ERRORS:
		return False


def _isStaleBufferError(error):
	message = str(error)
	return any(marker in message for marker in _STALE_BUFFER_MARKERS)


class _SkipRun:
	def __init__(self, treeInt, url, isInteractive, deadline):
		self.treeInt = treeInt
		self.url = url
		self.isInteractive = isInteractive
		self.deadline = deadline
		self.attempt = 0
		self.clicks = 0
		self.lastClickAt = 0.0
		self.activationFailed = False
		self.skipWords = frozenset()
		self.textInfo = None
		self.scanned = 0
		self.scanLimit = 0
		self.comErrorStreak = 0


class AdSkipper:
	def __init__(self, onContextChange):
		self._onContextChange = onContextChange
		self._active = False
		self._pollTimer = None
		self._chainTimer = None
		self._run = None
		self._watchTreeInt = None
		self._watchUrl = ""
		self._contextActive = False
		self._lastReason = None
		self._hooksRegistered = False
		self._lastGestureAt = 0.0
		self._speechPassUntil = 0.0
		self._holdTailUntil = 0.0
		self._holdTailTreeInt = None
		self._heldCount = 0
		self._pageLoadHoldUntil = 0.0
		self._pageLoadHoldTreeInt = None
		self._pageLoadHoldUrl = ""

	def start(self):
		if getattr(globalVars.appArgs, "secure", False):
			return
		self._active = True
		inputCore.decide_executeGesture.register(self._onDecideExecuteGesture)
		filter_speechSequence.register(self._onFilterSpeechSequence)
		self._hooksRegistered = True
		self._schedulePoll()

	def stop(self):
		self._active = False
		if self._hooksRegistered:
			self._hooksRegistered = False
			inputCore.decide_executeGesture.unregister(self._onDecideExecuteGesture)
			filter_speechSequence.unregister(self._onFilterSpeechSequence)
		self._holdTailUntil = 0.0
		self._holdTailTreeInt = None
		self._pageLoadHoldUntil = 0.0
		self._pageLoadHoldTreeInt = None
		self._cancelRun()
		if self._pollTimer is not None and self._pollTimer.IsRunning():
			self._pollTimer.Stop()
		self._pollTimer = None
		self._watchTreeInt = None
		self._watchUrl = ""
		self._contextActive = False

	def _onDecideExecuteGesture(self, gesture):
		self._lastGestureAt = time.monotonic()
		return True

	def _speechHoldTreeInt(self):
		if self._run is not None:
			return self._run.treeInt
		if time.monotonic() < self._holdTailUntil:
			return self._holdTailTreeInt
		return None

	def noteFocusedDocument(self, focusObj):
		if not self._active or not getINI("AutoSkipAds"):
			return
		treeInt = getattr(focusObj, "treeInterceptor", None)
		if not isinstance(treeInt, browseMode.BrowseModeTreeInterceptor):
			return
		try:
			url = str(getattr(treeInt, "documentConstantIdentifier", "") or "")
		except _SAFE_ERRORS:
			return
		lowerUrl = url.lower()
		if "youtube.com" not in lowerUrl or not any(marker in lowerUrl for marker in WATCH_URL_MARKERS):
			return
		if treeInt is self._pageLoadHoldTreeInt and url == self._pageLoadHoldUrl:
			return
		self._pageLoadHoldTreeInt = treeInt
		self._pageLoadHoldUrl = url
		self._pageLoadHoldUntil = time.monotonic() + PAGE_LOAD_HOLD_SECONDS
		log.debug("adSkip: speech hold started on page load for %s", url[:80])

	def _onFilterSpeechSequence(self, speechSequence):
		now = time.monotonic()
		isPageLoadHold = now < self._pageLoadHoldUntil
		holdTreeInt = self._pageLoadHoldTreeInt if isPageLoadHold else self._speechHoldTreeInt()
		if holdTreeInt is None:
			return speechSequence
		if now <= self._speechPassUntil:
			return speechSequence
		if not isPageLoadHold and now - self._lastGestureAt <= GESTURE_SPEECH_WINDOW_SECONDS:
			return speechSequence
		if not self._isTreeIntFocused(holdTreeInt):
			return speechSequence
		self._heldCount += 1
		return []

	def _allowSpeechBriefly(self):
		self._speechPassUntil = time.monotonic() + SKIP_FEEDBACK_PASS_SECONDS

	def _reportHeldSpeech(self, reason):
		log.debug("adSkip: speech hold ended (%s), held back %d announcement(s)", reason, self._heldCount)
		self._heldCount = 0

	def _note(self, reason):
		# One line per change of state, never per tick.
		if reason != self._lastReason:
			self._lastReason = reason
			log.debug("adSkip: %s", reason)

	def _schedulePoll(self):
		if self._active:
			self._pollTimer = core.callLater(POLL_INTERVAL_MS, self._tick)

	def _later(self, delayMs, callback, *args):
		self._chainTimer = core.callLater(delayMs, callback, *args)

	def _cancelRun(self):
		if self._chainTimer is not None and self._chainTimer.IsRunning():
			self._chainTimer.Stop()
		self._chainTimer = None
		self._run = None

	# ------------------------------------------------------------------
	# Context detection and automatic watch
	# ------------------------------------------------------------------
	def _tick(self):
		if not self._active:
			return
		if self._pageLoadHoldUntil and time.monotonic() >= self._pageLoadHoldUntil:
			self._pageLoadHoldUntil = 0.0
			self._pageLoadHoldTreeInt = None
		if self._holdTailUntil and time.monotonic() >= self._holdTailUntil:
			self._holdTailUntil = 0.0
			self._holdTailTreeInt = None
			self._reportHeldSpeech("quiet period after the last skip ended")
		try:
			self._poll()
		except _SAFE_ERRORS:
			log.debugWarning("adSkip: poll failed", exc_info=True)
			self._cancelRun()
		self._schedulePoll()

	def _poll(self):
		if not getINI("AutoSkipAds"):
			self._note("ad skipping is turned off in the settings")
			self._cancelRun()
			self._publishContext(False)
			return
		treeInt, url = self._resolveContext()
		lowerUrl = url.lower()
		isYouTube = treeInt is not None and "youtube.com" in lowerUrl
		self._publishContext(isYouTube)
		if not isYouTube:
			return
		if not any(marker in lowerUrl for marker in WATCH_URL_MARKERS):
			return
		if treeInt is self._watchTreeInt and url == self._watchUrl:
			return
		self._beginWatch(treeInt, url)

	def _publishContext(self, isActive):
		if isActive == self._contextActive:
			return
		self._contextActive = isActive
		self._onContextChange(isActive)

	def _resolveContext(self):
		focusObj = api.getFocusObject()
		if focusObj is None:
			return None, ""
		appName = getattr(getattr(focusObj, "appModule", None), "appName", "")
		if appName not in BROWSER_APP_NAMES:
			return None, ""
		treeInt = getattr(focusObj, "treeInterceptor", None)
		if treeInt is None or not isinstance(treeInt, browseMode.BrowseModeTreeInterceptor):
			return None, ""
		if not getattr(treeInt, "isReady", False):
			return None, ""
		return treeInt, str(getattr(treeInt, "documentConstantIdentifier", "") or "")

	def _currentTreeInterceptor(self):
		try:
			focusObj = api.getFocusObject()
			return getattr(focusObj, "treeInterceptor", None) if focusObj else None
		except _SAFE_ERRORS:
			return None

	def _isTreeIntFocused(self, treeInt):
		# Identity only: an SPA can replace the treeInterceptor under the same
		# URL, and a TextInfo from the old object is a stale COM reference.
		return self._currentTreeInterceptor() is treeInt

	def _beginWatch(self, treeInt, url):
		self._watchTreeInt = treeInt
		self._watchUrl = url
		self._note("watching for a skip button on " + url[:80])
		run = _SkipRun(treeInt, url, False, time.monotonic() + WATCH_WINDOW_SECONDS)
		self._startRun(run)

	# ------------------------------------------------------------------
	# Keyboard shortcut
	# ------------------------------------------------------------------
	def handleShortcut(self):
		# False means the key must be passed on to the page.
		if not self._active or not getINI("AutoSkipAds"):
			return False
		try:
			treeInt, url = self._resolveContext()
			if treeInt is None or "youtube.com" not in url.lower():
				return False
			if treeInt.passThrough and self._isTypingTargetFocused():
				return False
		except _SAFE_ERRORS:
			log.debugWarning("adSkip: shortcut context check failed", exc_info=True)
			return False
		run = _SkipRun(treeInt, url, True, time.monotonic() + SHORTCUT_WINDOW_SECONDS)
		self._startRun(run)
		return True

	def _isTypingTargetFocused(self):
		try:
			focusObj = api.getFocusObject()
		except _SAFE_ERRORS:
			return True
		if focusObj is None:
			return True
		return _isEditableObject(focusObj)

	# ------------------------------------------------------------------
	# Scan pass
	# ------------------------------------------------------------------
	def _startRun(self, run):
		self._cancelRun()
		self._run = run
		self._beginPass(run)

	def _beginPass(self, run):
		if run is not self._run or not self._active:
			return
		if time.monotonic() >= run.deadline:
			self._finishRun(run)
			return
		if not self._isTreeIntFocused(run.treeInt):
			self._abandonRun(run, "document changed or lost focus")
			return
		try:
			if not getattr(run.treeInt, "isReady", False):
				self._retryLater(run)
				return
			info = run.treeInt.makeTextInfo(textInfos.POSITION_FIRST)
			info.collapse()
			info.expand(textInfos.UNIT_PARAGRAPH)
		except _SAFE_ERRORS as error:
			log.debug("adSkip: could not start a scan pass: %s", error)
			self._retryLater(run)
			return
		run.skipWords = buildSkipWordSet(getINI("AdSkipExtraWords"))
		run.scanLimit = MAX_SCAN_PARAGRAPHS_SHORTCUT if run.isInteractive else MAX_SCAN_PARAGRAPHS_SILENT
		run.textInfo = info
		run.scanned = 0
		run.comErrorStreak = 0
		self._scanChunk(run)

	def _scanChunk(self, run):
		if run is not self._run or not self._active:
			return
		if not self._isTreeIntFocused(run.treeInt):
			self._abandonRun(run, "document changed during a scan")
			return
		info = run.textInfo
		for step in range(SCAN_PARAGRAPHS_PER_CHUNK):
			run.scanned += 1
			try:
				if self._isSkipParagraph(info, run.skipWords):
					self._later(0, self._clickTarget, run, info.copy())
					return
				if run.scanned >= run.scanLimit or info.move(textInfos.UNIT_PARAGRAPH, 1) == 0:
					self._retryLater(run)
					return
				info.expand(textInfos.UNIT_PARAGRAPH)
				run.comErrorStreak = 0
			except _SAFE_ERRORS as error:
				run.comErrorStreak += 1
				if run.comErrorStreak >= MAX_COM_ERROR_STREAK or _isStaleBufferError(error):
					log.debug("adSkip: buffer changed during a scan, starting a new pass: %s", error)
					self._retryLater(run)
					return
				try:
					if info.move(textInfos.UNIT_PARAGRAPH, 1) == 0:
						self._retryLater(run)
						return
					info.expand(textInfos.UNIT_PARAGRAPH)
				except _SAFE_ERRORS:
					self._retryLater(run)
					return
		self._later(0, self._scanChunk, run)

	def _isSkipParagraph(self, info, skipWords):
		text = _normalizeText(info.text)
		if not text or len(text) > MAX_BUTTON_TEXT_LENGTH:
			return False
		if text.casefold() not in skipWords:
			return False
		return self._isSafeTarget(info)

	def _isSafeTarget(self, info):
		# A text field that happens to contain the word must never be clicked.
		try:
			fields = info.getTextWithFields()
			targetObj = info.NVDAObjectAtStart
		except _SAFE_ERRORS:
			return False
		for field in fields:
			if not isinstance(field, textInfos.FieldCommand) or field.command != "controlStart":
				continue
			if field.field.get("role") in _EDITABLE_ROLES:
				return False
			if controlTypes.State.EDITABLE in field.field.get("states", set()):
				return False
		depth = 0
		while targetObj is not None and depth < ANCESTOR_CHECK_DEPTH:
			if _isEditableObject(targetObj):
				return False
			try:
				targetObj = targetObj.parent
			except _SAFE_ERRORS:
				break
			depth += 1
		return True

	def _retryLater(self, run):
		if run is not self._run:
			return
		if time.monotonic() >= run.deadline:
			self._finishRun(run)
			return
		delay = RETRY_DELAY_SCHEDULE_MS[min(run.attempt, len(RETRY_DELAY_SCHEDULE_MS) - 1)]
		run.attempt += 1
		self._later(delay, self._beginPass, run)

	def _finishRun(self, run):
		if run is not self._run:
			return
		self._run = None
		log.debug("adSkip: run finished after %d click(s), interactive=%s", run.clicks, run.isInteractive)
		if run.clicks == 0 or time.monotonic() >= self._holdTailUntil:
			self._reportHeldSpeech("watch finished")
		if run.isInteractive and run.clicks == 0:
			self._allowSpeechBriefly()
			if run.activationFailed:
				ui.message(_("Could not click the skip button."))
			else:
				ui.message(_("No skip button found."))

	def _abandonRun(self, run, reason):
		if run is not self._run:
			return
		self._run = None
		log.debug("adSkip: run abandoned, %s", reason)
		self._reportHeldSpeech("watch abandoned")

	# ------------------------------------------------------------------
	# Click
	# ------------------------------------------------------------------
	def _clickTarget(self, run, targetInfo):
		if run is not self._run or not self._active:
			return
		if not self._isTreeIntFocused(run.treeInt):
			self._abandonRun(run, "document changed before the click")
			return
		now = time.monotonic()
		if now - run.lastClickAt < MIN_CLICK_INTERVAL_SECONDS:
			self._retryLater(run)
			return
		if not self._activate(run.treeInt, targetInfo):
			run.activationFailed = True
			log.debug("adSkip: every click method failed for the skip button")
			self._retryLater(run)
			return
		run.clicks += 1
		run.lastClickAt = now
		run.isInteractive = False
		run.activationFailed = False
		run.attempt = 0
		run.deadline = max(run.deadline, now + CHAIN_WINDOW_SECONDS)
		log.debug("adSkip: skip button activated, click %d", run.clicks)
		self._holdTailUntil = now + AD_SPEECH_TAIL_SECONDS
		self._holdTailTreeInt = run.treeInt
		self._allowSpeechBriefly()
		ui.message(_("Ad skipped"))
		if run.clicks >= MAX_CLICKS_PER_RUN:
			self._finishRun(run)
			return
		# Keep looking: a second ad can follow the first one immediately.
		self._later(POST_CLICK_DELAY_MS, self._beginPass, run)

	def _activate(self, treeInt, targetInfo):
		try:
			focusable = targetInfo.focusableNVDAObjectAtStart
		except _SAFE_ERRORS:
			focusable = None
		if focusable is not None:
			return self._performRobustClick(focusable)
		activatePosition = getattr(treeInt, "activatePosition", None)
		if activatePosition is None:
			return False
		try:
			activatePosition(targetInfo)
		except _SAFE_ERRORS as error:
			log.debug("adSkip: activatePosition failed: %s", error)
			return False
		return True

	def _performRobustClick(self, targetObj):
		try:
			targetObj.doAction()
			return True
		except _SAFE_ERRORS as error:
			log.debug("adSkip: doAction failed: %s", error)
		try:
			left, top, width, height = targetObj.location
		except (TypeError, *_SAFE_ERRORS) as error:
			log.debug("adSkip: no usable location for a mouse click: %s", error)
			return False
		if width <= 0 or height <= 0:
			return False
		try:
			winUser.setCursorPos(left + width // 2, top + height // 2)
		except _SAFE_ERRORS as error:
			log.debug("adSkip: could not move the mouse pointer: %s", error)
			return False
		core.callLater(MOUSE_DOWN_DELAY_MS, winUser.mouse_event, winUser.MOUSEEVENTF_LEFTDOWN, 0, 0, None, None)
		core.callLater(MOUSE_UP_DELAY_MS, winUser.mouse_event, winUser.MOUSEEVENTF_LEFTUP, 0, 0, None, None)
		return True
