# subtitleWatcher.py

import re
import time

import addonHandler
import api
import braille
import controlTypes
import globalVars
import speech
import wx
from comtypes import COMError
from logHandler import log
from NVDAObjects import InvalidNVDAObject
from speech.commands import RateCommand

from .Download_core import getINI

addonHandler.initTranslation()

BROWSER_APP_NAMES = ("chrome", "msedge", "firefox", "brave")
POLL_INTERVAL_MS = 300
SEARCH_INTERVAL_MS = 50
IDLE_INTERVAL_MS = 2000
SEARCH_BUDGET_PER_TICK = 80
MAX_SEARCH_VISITS = 4000
MAX_CAPTION_NODES = 40
SEARCH_BACKOFF_SECONDS = 10
SEGMENT_LENGTH = 160
MAX_TOTAL_LENGTH = 1500
MAX_BRAILLE_LENGTH = 300
SPEED_FREE_LENGTH = 120
SPEED_STEP_LENGTH = 400.0
MAX_SPEED = 1.6
_MUSIC_SYMBOLS = str.maketrans("", "", "\u266a\u266b\u2669\u266c")
_BLOCK_OPENERS = ("{", "[", "(", "\uff5b", "\uff3b", "\uff08", "\u3010", "\u3014")
_BLOCK_CLOSERS = ("}", "]", ")", "\uff5d", "\uff3d", "\uff09", "\u3011", "\u3015")
MIN_CHAR_OVERLAP = 3
MIN_INNER_OVERLAP = 6
SETTLE_PROGRESSIVE_SECONDS = 1.8
SETTLE_DISCRETE_SECONDS = 0.5
PROGRESSIVE_INTERVAL_SECONDS = 1.2
DUPLICATE_FRACTION = 0.85
GRAM_LENGTH = 5
MIN_FUZZY_LENGTH = 12
MAX_FUZZY_REFERENCE = 600
MAX_HOLD_SECONDS = 2.0
MIN_CAPACITY_LENGTH = 30
MAX_PENDING_LENGTH = 100
MAX_FAILED_READS = 6
VANISH_TICKS = 4
MIN_OVERDUE_FRAGMENT = 8
MAX_TAIL_LENGTH = 600
_BRACKETED_RE = re.compile(
	r"\{[^{}]*\}|\[[^\[\]]*\]|\([^()]*\)"
	r"|\uff5b[^\uff5b\uff5d]*\uff5d|\uff3b[^\uff3b\uff3d]*\uff3d|\uff08[^\uff08\uff09]*\uff09"
	r"|\u3010[^\u3010\u3011]*\u3011|\u3014[^\u3014\u3015]*\u3015"
)
_WHITESPACE_RE = re.compile(r"\s+")
_UNSPACED_SCRIPTS = "\u0e00-\u0e7f\u0e80-\u0eff\u1000-\u109f\u1780-\u17ff\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff"
_UNSPACED_GAP_RE = re.compile("([%s])\\s+(?=[%s])" % (_UNSPACED_SCRIPTS, _UNSPACED_SCRIPTS))
WATCH_URL_MARKERS = ("youtube.com/watch", "youtube.com/shorts/")
CAPTION_CONTAINER_ID = "ytp-caption-window-container"
CAPTION_LINE_CLASS = "caption-visual-line"
_READ_ERRORS = (COMError, InvalidNVDAObject, AttributeError, RuntimeError, NotImplementedError, ValueError)


def normalizeForCompare(text):
	return _WHITESPACE_RE.sub("", text)


def _textAfterNormalizedIndex(text, normalizedIndex):
	counted = 0
	for position, character in enumerate(text):
		if counted >= normalizedIndex:
			return text[position:].strip()
		if not character.isspace():
			counted += 1
	return ""


def newSubtitleText(spokenText, currentText):
	"""Returns the part of currentText that was not spoken yet.

	Spacing is ignored, because YouTube may show the same Thai sentence first
	as separate words and later as one string.
	"""
	spoken = normalizeForCompare(spokenText)
	current = normalizeForCompare(currentText)
	if not current or current in spoken:
		return ""
	for overlap in range(min(len(spoken), len(current)), MIN_CHAR_OVERLAP - 1, -1):
		if spoken.endswith(current[:overlap]):
			return _textAfterNormalizedIndex(currentText, overlap)
	for overlap in range(min(len(spoken), len(current)), MIN_INNER_OVERLAP - 1, -1):
		position = current.find(spoken[-overlap:])
		if position != -1:
			return _textAfterNormalizedIndex(currentText, position + overlap)
	return currentText.strip()


def isMostlySpoken(candidate, spokenText):
	"""True when candidate repeats what was already spoken, even if YouTube
	reworded or reordered a few words in the meantime.

	Only runs of GRAM_LENGTH characters that really occur in the spoken text
	count as a match. Scattered single characters must not, because a short
	new sentence is always a loose subsequence of a long spoken text.
	"""
	wanted = normalizeForCompare(candidate)
	spoken = normalizeForCompare(spokenText)[-MAX_FUZZY_REFERENCE:]
	if len(wanted) < MIN_FUZZY_LENGTH or len(spoken) < GRAM_LENGTH:
		return False
	grams = {spoken[position:position + GRAM_LENGTH] for position in range(len(spoken) - GRAM_LENGTH + 1)}
	covered = [False] * len(wanted)
	for position in range(len(wanted) - GRAM_LENGTH + 1):
		if wanted[position:position + GRAM_LENGTH] in grams:
			for index in range(position, position + GRAM_LENGTH):
				covered[index] = True
	return sum(covered) / len(wanted) >= DUPLICATE_FRACTION


def cleanSubtitleText(text):
	previous = None
	while previous != text:
		previous = text
		text = _BRACKETED_RE.sub(" ", text)
	# A block that has not been closed yet is held back until it is complete.
	openings = [position for position in (text.find(opener) for opener in _BLOCK_OPENERS) if position != -1]
	if openings:
		text = text[:min(openings)]
	for closer in _BLOCK_CLOSERS:
		text = text.replace(closer, " ")
	text = " ".join(text.translate(_MUSIC_SYMBOLS).split())
	text = text.lstrip(" .,;:!?-")
	if not any(character.isalnum() for character in text):
		return ""
	return text


def joinUnspacedScripts(text):
	return _UNSPACED_GAP_RE.sub(r"\1", text)


def splitForSpeech(text, maxLength):
	pieces = []
	remaining = text.strip()
	while len(remaining) > maxLength:
		cut = maxLength
		for separator in (". ", "! ", "? ", "; ", ", ", " "):
			position = remaining.rfind(separator, 0, maxLength)
			if position >= maxLength // 3:
				cut = position + 1
				break
		pieces.append(remaining[:cut].strip())
		remaining = remaining[cut:].strip()
	if remaining:
		pieces.append(remaining)
	return pieces


def speedFactor(textLength):
	if textLength <= SPEED_FREE_LENGTH:
		return 1.0
	return min(MAX_SPEED, 1.0 + (textLength - SPEED_FREE_LENGTH) / SPEED_STEP_LENGTH)


class SubtitleWatcher:
	def __init__(self):
		self._active = False
		self._timer = None
		self._resetState()

	def _resetState(self):
		self._treeInterceptor = None
		self._container = None
		self._searchStack = []
		self._visits = 0
		self._backoffUntil = 0.0
		self._lastText = ""
		self._spokenTail = ""
		self._changedAt = 0.0
		self._changeIntervals = []
		self._pendingSince = 0.0
		self._failedReads = 0
		self._capacity = 0
		self._emptyReads = 0
		self._lastUrl = ""

	def _note(self, reason):
		# One line per change of state, never per tick, so a debug log stays small.
		if reason != getattr(self, "_lastReason", None):
			self._lastReason = reason
			log.debug("subtitleWatcher: " + reason)

	def start(self):
		if getattr(globalVars.appArgs, "secure", False):
			return
		self._active = True
		self._schedule(IDLE_INTERVAL_MS)

	def stop(self):
		self._active = False
		if self._timer is not None and self._timer.IsRunning():
			self._timer.Stop()
		self._timer = None
		self._resetState()

	def _schedule(self, delayMs):
		if self._active:
			self._timer = wx.CallLater(delayMs, self._tick)

	def _tick(self):
		if not self._active:
			return
		delay = IDLE_INTERVAL_MS
		try:
			delay = self._poll()
		except _READ_ERRORS:
			log.debugWarning("subtitleWatcher: poll failed", exc_info=True)
			self._resetState()
		self._schedule(delay)

	def _poll(self):
		if not getINI("AutoReadSubtitles"):
			self._note("automatic subtitle reading is turned off in the settings")
			self._resetState()
			return IDLE_INTERVAL_MS
		focus = api.getFocusObject()
		appName = getattr(getattr(focus, "appModule", None), "appName", "")
		if not focus or appName not in BROWSER_APP_NAMES:
			self._note("focus is not in a supported browser (app: %s)" % appName)
			self._resetState()
			return IDLE_INTERVAL_MS
		treeInterceptor = focus.treeInterceptor
		if treeInterceptor is None or not treeInterceptor.isReady:
			self._note("the page document is not ready")
			self._resetState()
			return IDLE_INTERVAL_MS
		if treeInterceptor is not self._treeInterceptor:
			self._resetState()
			self._treeInterceptor = treeInterceptor
		if self._container is None:
			return self._findContainer(treeInterceptor)
		rawText = self._readCaptions()
		if rawText is not None:
			self._handleCaptionText(rawText)
		return POLL_INTERVAL_MS

	def _handleCaptionText(self, rawText):
		text = cleanSubtitleText(rawText)
		if not text:
			# YouTube rebuilds the caption nodes while it updates them, so a read
			# can come back empty for a moment. Only a caption that stays gone
			# counts as finished; resetting earlier makes the sentence repeat.
			self._emptyReads += 1
			if self._emptyReads < VANISH_TICKS:
				return
			self._speakUnspoken(self._lastText)
			self._lastText = ""
			self._spokenTail = ""
			self._changeIntervals = []
			self._pendingSince = 0.0
			self._capacity = 0
			self._emptyReads = 0
			return
		self._emptyReads = 0
		now = time.time()
		if text != self._lastText:
			if self._changedAt:
				self._changeIntervals = (self._changeIntervals + [now - self._changedAt])[-3:]
			self._lastText = text
			self._changedAt = now
		fresh = newSubtitleText(self._spokenTail, text)
		if not fresh:
			self._pendingSince = 0.0
			return
		if not self._pendingSince:
			self._pendingSince = now
		isSettled = now - self._changedAt >= self._settleSeconds()
		# Never hold back for long: captions that keep changing would otherwise
		# stay silent until the speaker pauses, and the oldest words would roll
		# out of the visible window before they were spoken.
		freshLength = len(normalizeForCompare(fresh))
		self._capacity = max(self._capacity, len(normalizeForCompare(text)))
		isOverdue = freshLength >= MIN_OVERDUE_FRAGMENT and (
			now - self._pendingSince >= MAX_HOLD_SECONDS
			or freshLength >= MAX_PENDING_LENGTH
			or (self._capacity >= MIN_CAPACITY_LENGTH and freshLength * 2 >= self._capacity)
		)
		if isSettled or isOverdue:
			self._pendingSince = 0.0
			self._speakUnspoken(text)

	def _settleSeconds(self):
		# Captions that grow word by word are revised again shortly after, so
		# they are read only once the text has stopped changing for a while.
		isProgressive = len(self._changeIntervals) >= 2 and (
			sum(self._changeIntervals) / len(self._changeIntervals) < PROGRESSIVE_INTERVAL_SECONDS
		)
		return SETTLE_PROGRESSIVE_SECONDS if isProgressive else SETTLE_DISCRETE_SECONDS

	def _speakUnspoken(self, text):
		fresh = newSubtitleText(self._spokenTail, text)
		if not fresh:
			return
		repeated = isMostlySpoken(fresh, self._spokenTail)
		self._markSpoken(fresh)
		if not repeated:
			self._speak(fresh)

	def _markSpoken(self, text):
		self._spokenTail = (self._spokenTail + normalizeForCompare(text))[-MAX_TAIL_LENGTH:]

	def _findContainer(self, treeInterceptor):
		now = time.time()
		url = str(getattr(treeInterceptor, "documentConstantIdentifier", "") or "")
		if url != self._lastUrl:
			# A different page was opened: start looking at once instead of
			# waiting out a pause that belonged to the previous page.
			self._lastUrl = url
			self._backoffUntil = 0.0
			self._searchStack = []
			self._visits = 0
		if now < self._backoffUntil:
			return IDLE_INTERVAL_MS
		if not self._searchStack and self._visits == 0:
			if not any(marker in url for marker in WATCH_URL_MARKERS):
				self._note("not a YouTube video page (%s)" % url[:80])
				self._backoffUntil = now + SEARCH_BACKOFF_SECONDS
				return IDLE_INTERVAL_MS
			self._note("looking for the caption container")
			self._searchStack.append(treeInterceptor.rootNVDAObject)
		if self._searchStep():
			self._note("caption container found after %d nodes" % self._visits)
			self._lastText = ""
			self._spokenTail = ""
			return POLL_INTERVAL_MS
		if not self._searchStack or self._visits >= MAX_SEARCH_VISITS:
			self._note("caption container not found after %d nodes, trying again in %d s" % (self._visits, SEARCH_BACKOFF_SECONDS))
			self._searchStack = []
			self._visits = 0
			self._backoffUntil = now + SEARCH_BACKOFF_SECONDS
			return IDLE_INTERVAL_MS
		return SEARCH_INTERVAL_MS

	def _searchStep(self):
		stepVisits = 0
		while self._searchStack and stepVisits < SEARCH_BUDGET_PER_TICK:
			node = self._searchStack.pop()
			stepVisits += 1
			self._visits += 1
			try:
				attributes = node.IA2Attributes or {}
				if attributes.get("id") == CAPTION_CONTAINER_ID:
					self._container = node
					self._searchStack = []
					return True
				child = node.firstChild
				sibling = node.next
			except _READ_ERRORS:
				continue
			if sibling is not None:
				self._searchStack.append(sibling)
			if child is not None:
				self._searchStack.append(child)
		return False

	def _readCaptions(self):
		lines = [[]]
		budget = [MAX_CAPTION_NODES]
		try:
			self._collectText(self._container, lines, budget)
		except _READ_ERRORS:
			# YouTube rebuilds the caption nodes whenever the text changes, so a
			# read can land on stale nodes. Skip that tick instead of treating it
			# as "no caption" and only start over after repeated failures.
			self._failedReads += 1
			if self._failedReads >= MAX_FAILED_READS:
				self._resetState()
			return None
		self._failedReads = 0
		return "\n".join(" ".join(words) for words in lines if words)

	def _collectText(self, node, lines, budget):
		if budget[0] <= 0:
			return
		budget[0] -= 1
		attributes = node.IA2Attributes or {}
		if CAPTION_LINE_CLASS in str(attributes.get("class", "")):
			lines.append([])
		children = node.children
		if not children:
			text = (node.name or "").strip()
			if text:
				lines[-1].append(text)
			return
		for child in children:
			self._collectText(child, lines, budget)

	def _speak(self, text):
		spoken = cleanSubtitleText(text)
		if not spoken:
			return
		if len(spoken) > MAX_TOTAL_LENGTH:
			# Translators: Appended to a subtitle that was cut short before being spoken.
			spoken = spoken[:MAX_TOTAL_LENGTH].rstrip() + _("...truncated")
		sequence = [joinUnspacedScripts(piece) for piece in splitForSpeech(spoken, SEGMENT_LENGTH)]
		factor = speedFactor(len(joinUnspacedScripts(spoken)))
		if factor > 1.0:
			sequence = [RateCommand(multiplier=factor)] + sequence + [RateCommand(multiplier=1)]
		speech.speak(sequence)
		if braille.handler:
			joined = joinUnspacedScripts(spoken)
			brailleText = joined if len(joined) <= MAX_BRAILLE_LENGTH else joined[:MAX_BRAILLE_LENGTH].rstrip() + _("...truncated")
			braille.handler.message(brailleText)
