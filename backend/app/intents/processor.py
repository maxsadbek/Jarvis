"""Intent Processor — Natural Language Command Router.

Parses user input in Uzbek (primarily), Russian, and English.
Returns a structured intent: {tool, action, params, confidence}.

Languages supported:
- Uzbek (uz): "Chrome och", "Telegramni och", "ovozni 50 foiz qil"
- Russian (ru): "открой YouTube", "найди файл"
- English (en): "open Chrome", "search for file"

Uses pattern matching first (fast), then falls back to LLM for complex queries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


class CommandIntent(str, Enum):
    """High-level intent categories mapped to tools."""
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"
    SWITCH_WINDOW = "switch_window"
    SEARCH_WEB = "search_web"
    OPEN_WEBSITE = "open_website"
    SEARCH_FILES = "search_files"
    CREATE_FILE = "create_file"
    MOVE_FILE = "move_file"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_RESTART = "system_restart"
    SYSTEM_SLEEP = "system_sleep"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    VOLUME_SET = "volume_set"
    PLAY_MEDIA = "play_media"
    PAUSE_MEDIA = "pause_media"
    NEXT_TRACK = "next_track"
    PREV_TRACK = "prev_track"
    TAKE_SCREENSHOT = "take_screenshot"
    LOCK_SCREEN = "lock_screen"
    GET_TIME = "get_time"
    GET_WEATHER = "get_weather"
    CREATE_REMINDER = "create_reminder"
    SAVE_MEMORY = "save_memory"
    RECALL_MEMORY = "recall_memory"
    CODING_MODE = "coding_mode"
    RUN_COMMAND = "run_command"
    CHAT = "chat"  # General conversation
    UNKNOWN = "unknown"


@dataclass
class IntentResult:
    """Result of intent parsing."""
    intent: CommandIntent = CommandIntent.UNKNOWN
    confidence: float = 0.0
    tool_name: str = ""
    action: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    requires_confirmation: bool = False


# ─── Pattern Definitions ─────────────────────────────────────────────────────

# Each pattern group: (regex, intent, tool, action, param_extractor)
# Supports Uzbek (uz), Russian (ru), and English (en)
# Uzbek is PRIMARY language — patterns must be checked first

class IntentPatterns:
    """Pattern-based intent classification — fast, no LLM needed.

    Supports three languages:
    - Uzbek (uz): "Chrome och", "Telegramni och", "ovozni 50% qil"
    - Russian (ru): "открой YouTube", "найди файл"
    - English (en): "open Chrome", "search for file"
    """

    PATTERNS: list[tuple[str, CommandIntent, str, str, callable]] = [
        # ====================================================================
        # UZBEK PATTERNS (checked first — the user speaks Uzbek)
        # ====================================================================

        # ─── Open App (Uzbek) ───
        # Three patterns to handle all suffix formats:
        # ORDER: space-separated FIRST (prevents false matches), then attached, then no suffix
        # 1. Space-separated suffix: "Telegram ni och", "Chrome ni och"  ← FIRST
        # 2. Attached suffix: "Telegramni och", "Spotifyni och"
        # 3. No suffix: "Chrome och", "skype och"
        (r"(\w+)\s+(ni|ни|ны)\s+och\b", CommandIntent.OPEN_APP, "app_control", "open",
         lambda m: {"target": m.group(1).strip()}),
        (r"(\w+?)(?:ni|ни|ны|da|да|dan|дан|ning|нинг)\s+och\b", CommandIntent.OPEN_APP, "app_control", "open",
         lambda m: {"target": m.group(1).strip()}),
        (r"(\w+)\s+och\b", CommandIntent.OPEN_APP, "app_control", "open",
         lambda m: {"target": m.group(1).strip()}),

        # ─── Close App (Uzbek) ───
        # Three patterns matching the open patterns, same ORDER
        (r"(\w+)\s+(ni|ни|ны)\s+yop\b", CommandIntent.CLOSE_APP, "system_ctl", "close_app",
         lambda m: {"target": m.group(1).strip()}),
        (r"(\w+?)(?:ni|ни|ны)\s+yop\b", CommandIntent.CLOSE_APP, "system_ctl", "close_app",
         lambda m: {"target": m.group(1).strip()}),
        (r"(\w+)\s+yop\b", CommandIntent.CLOSE_APP, "system_ctl", "close_app",
         lambda m: {"target": m.group(1).strip()}),

        # ─── System Shutdown / Restart (Uzbek) ───
        # "kompyuterni o'chir", "qayta yukla", "компьютерни o'chir"
        (r"(компьютерни|компьютер|pc|comp|system|тизим|kompyuter|kompyuterni)\s+o['\u02bc]?chir", CommandIntent.SYSTEM_SHUTDOWN, "system_ctl", "shutdown",
         lambda m: {}),
        (r"o['\u02bc]?chir\s+(компьютер|pc|system|kompyuter)", CommandIntent.SYSTEM_SHUTDOWN, "system_ctl", "shutdown",
         lambda m: {}),
        (r"qayta\s+yukla", CommandIntent.SYSTEM_RESTART, "system_ctl", "restart",
         lambda m: {}),

        # ─── Volume Control (Uzbek) ───
        # "ovozni 50 foiz qil", "ovozni oshir", "ovozni kamaytir"
        (r"(ovoz|овоз|овозни|ovozni|sounds?|volume)\s+(\d+)\s*(foiz|%|protsent|процент)", CommandIntent.VOLUME_SET, "system_ctl", "volume",
         lambda m: {"value": int(m.group(2))}),
        (r"(ovoz|овоз|овозни|ovozni|sounds?|volume)\s+(oshir|baland|кўтар|увеличь|raise|up)", CommandIntent.VOLUME_UP, "system_ctl", "volume_up",
         lambda m: {"amount": 10}),
        (r"(ovoz|овоз|овозни|ovozni|sounds?|volume)\s+(kamaytir|pasayt|уменьш|lower|down)", CommandIntent.VOLUME_DOWN, "system_ctl", "volume_down",
         lambda m: {"amount": 10}),

        # ─── Brightness (Uzbek) ───
        # "brightnessni kamaytir", "yorug'likni oshir"
        (r"(brightness|yorug['\u02bc]?lik|ёруглик|яркость)\s+(ni|ни)\s+(oshir|baland|кўтар|увелич)", CommandIntent.VOLUME_UP, "system_ctl", "brightness_up",
         lambda m: {"amount": 10}),
        (r"(brightness|yorug['\u02bc]?lik|ёруглик|яркость)\s+(ni|ни)\s+(kamaytir|pasayt|уменьш)", CommandIntent.VOLUME_DOWN, "system_ctl", "brightness_down",
         lambda m: {"amount": 10}),

        # ─── Search Web (Uzbek) ───
        # "Google'dan qidir", "YouTube'da Eminem qidir", "internetdan qidir"
        (r"(google|youtube|internet|web)\S*\s+(dan|da|дан|да)\s+qidir", CommandIntent.SEARCH_WEB, "web_search", "search",
         lambda m: {"query": m.group(0)}),
        (r"qidir\s+(.+)", CommandIntent.SEARCH_WEB, "web_search", "search",
         lambda m: {"query": m.group(1).strip()}),

        # ─── Open Website (Uzbek) ───
        # "YouTube och", "Google och"
        (r"(youtube|google|github|facebook|instagram|telegram|web|сайт)\s+och", CommandIntent.OPEN_WEBSITE, "app_control", "open_url",
         lambda m: {"url": f"https://www.{m.group(1).lower()}.com" if m.group(1).lower() not in ("telegram",) else f"https://{m.group(1).lower()}.org"}),

        # ─── Find File (Uzbek) ───
        # "fayl top", "papka top", "fayl qidir"
        (r"(fayl|файл|file|papka|папка|folder|hujjat|документ)\s+(top|qidir|изла|найди)", CommandIntent.SEARCH_FILES, "file_ops", "search",
         lambda m: {"pattern": m.group(1)}),

        # ─── Create File/Folder (Uzbek) ───
        # "papka yarat", "fayl yarat", "folder yarat"
        (r"(papka|папка|folder|fayl|файл|file)\s+(yarat|создай|make|create)", CommandIntent.CREATE_FILE, "file_ops", "create",
         lambda m: {"path": m.group(1), "type": "folder" if m.group(1) in ("papka", "папка", "folder") else "file"}),

        # ─── Open Camera (Uzbek) ───
        # "camera och", "kamerani och", "fotoapparatni och"
        (r"(camera|kamera|камера|foto|фото)\s+(ni|ни)?\s*och", CommandIntent.OPEN_APP, "app_control", "open",
         lambda m: {"target": "camera"}),

        # ─── Screenshot (Uzbek) ───
        # "ekran rasmini ol", "skrinshot ol", "ekran suratini ol"
        (r"(ekran|экран|screen)\s+(rasmini|расмини|suratini|snapshot|shot)\s+(ol|ол|take|got)", CommandIntent.TAKE_SCREENSHOT, "system_ctl", "screenshot",
         lambda m: {}),

        # ─── Task Manager (Uzbek) ───
        # "task manager och", "dispetcher och"
        (r"(task manager|taskmanager|диспетчер|dispetcher|вазифалар)\s+och", CommandIntent.OPEN_APP, "app_control", "open",
         lambda m: {"target": "taskmgr"}),

        # ─── Settings (Uzbek) ───
        # "settings och", "sozlamalarni och", "parametrlarni och"
        (r"(settings|sozlamalar|созламалар|parametr|параметр|настройки)\s+(ni|ни|lar)?(ni|ни)?\s*och", CommandIntent.OPEN_APP, "app_control", "open",
         lambda m: {"target": "settings"}),

        # ─── Control Panel (Uzbek) ───
        # "control panel och", "boshqaruv paneli och"
        (r"(control panel|boshqaruv|бошцарув|панель)\s+och", CommandIntent.OPEN_APP, "app_control", "open",
         lambda m: {"target": "control"}),

        # ─── Terminal/CMD (Uzbek) ───
        # "terminal och", "cmd och", "powershell och"
        (r"(terminal|терминал|cmd|command|powershell)\s+och", CommandIntent.OPEN_APP, "app_control", "open",
         lambda m: {"target": m.group(1).strip()}),

        # ─── WiFi (Uzbek) ───
        # "wifi yoq", "bluetooth o'chir"
        (r"(wifi|wi[-\s]?fi|вайфай|bluetooth|блютуз)\s+(yoq|ёк|on|off|o['\u02bc]?chir|включи|выключи)", CommandIntent.OPEN_APP, "system_ctl", "toggle_network",
         lambda m: {"target": m.group(1).strip(), "state": "on" if m.group(2) in ("yoq", "ёк", "on", "включи") else "off"}),

        # ─── Run Python (Uzbek) ───
        # "Pythonni ishga tushir", "python run"
        (r"(python|питон|код)\s+(ni|ни)?\s*(ishga\s+tushir|run|запусти|exec|execute)", CommandIntent.RUN_COMMAND, "command_runner", "run",
         lambda m: {"command": f"python {m.group(1).strip()}.py" if m.group(1).lower() == "python" else m.group(1)}),

        # ─── Open Notepad (Uzbek) ───
        (r"(notepad|блокнот|daftar|дафтар)\s+och", CommandIntent.OPEN_APP, "app_control", "open",
         lambda m: {"target": "notepad"}),

        # ─── Open Calculator (Uzbek) ───
        (r"(calculator|калькулятор|kalkulyator|калькулятор|hisoblagich|хисоблагич)\s+och", CommandIntent.OPEN_APP, "app_control", "open",
         lambda m: {"target": "calc"}),

        # ─── Open Explorer (Uzbek) ───
        (r"(explorer|проводник|eksplorer|эксплорер|fayllar|файллар)\s+och", CommandIntent.OPEN_APP, "app_control", "open",
         lambda m: {"target": "explorer"}),

        # ─── Lock Screen (Uzbek) ───
        # "ekranni qulfla", "qulfla", "blokla"
        (r"(ekran|экран)\s+(ni|ни)?\s*(qulfla|кулфла|blokla|блокла|заблокируй|lock)", CommandIntent.LOCK_SCREEN, "system_ctl", "lock_screen",
         lambda m: {}),

        # ─── Open Developer Mode (Uzbek) ───
        (r"(developer|dev|dasturchi|дастурчи|код|code|coding|программир)\s+(mode|режим|рекзим)?", CommandIntent.CODING_MODE, "developer", "activate",
         lambda m: {}),

        # ─── Specific YouTube Search (Uzbek) ───
        # "YouTube'da Eminem qidir", "YouTube'da qidir"
        (r"(youtube)\S*\s+(da|дан|да|да')\s+(\w[\w\s]+)\s+qidir", CommandIntent.OPEN_WEBSITE, "app_control", "open_url",
         lambda m: {"url": f"https://www.youtube.com/results?search_query={m.group(3).strip().replace(' ', '+')}"}),

        # ─── Music Play (Uzbek) ───
        # "musiqa qo'y", "qo'shiq qo'y", "music play"
        (r"(musiqa|мусица|qo['\u02bc]?shiq|кўшик|song|music|песню|трек)\s+(qo['\u02bc]?y|кўй|play|включи)", CommandIntent.PLAY_MEDIA, "media_control", "play",
         lambda m: {}),

        # ====================================================================
        # RUSSIAN / ENGLISH PATTERNS (existing, with enhancements)
        # ====================================================================

        # ─── Website / URL open (MUST come BEFORE generic 'open app') ───
        (r"(открой|open|go to)\s+(youtube)\b", CommandIntent.OPEN_WEBSITE, "app_control", "open_url",
         lambda m: {"url": "https://youtube.com"}),

        (r"(открой|open|go to)\s+(google)\b", CommandIntent.OPEN_WEBSITE, "app_control", "open_url",
         lambda m: {"url": "https://google.com"}),

        (r"(открой|open|go to)\s+(github|facebook|twitter|instagram|reddit)\b", CommandIntent.OPEN_WEBSITE, "app_control", "open_url",
         lambda m: {"url": f"https://www.{m.group(2).lower()}.com"}),

        (r"(открой|open|go to)\s+(https?://\S+|www\.\S+)", CommandIntent.OPEN_WEBSITE, "app_control", "open_url",
         lambda m: {"url": m.group(2).strip()}),

        (r"(найди|поищи|search|find|look up)\s+(\w[\w\s]*)", CommandIntent.SEARCH_WEB, "web_search", "search",
         lambda m: {"query": m.group(2).strip()}),

        # ─── App Control (MUST come after specific web patterns) ───
        (r"(открой|запусти|open|launch|start)\s+(\w[\w\s]*)", CommandIntent.OPEN_APP, "app_control", "open",
         lambda m: {"target": m.group(2).strip()}),

        (r"(закрой|выключи|close|exit|kill)\s+(\w[\w\s]*)", CommandIntent.CLOSE_APP, "system_ctl", "close_app",
         lambda m: {"target": m.group(2).strip()}),

        (r"(переключи|перейди|switch|focus)\s+(на|to)\s+(\w[\w\s]*)", CommandIntent.SWITCH_WINDOW, "system_ctl", "switch_window",
         lambda m: {"target": m.group(3).strip()}),

        # ─── System Commands ───
        (r"(выключи|shutdown|shut down)\s+(компьютер|пк|computer|pc|system)", CommandIntent.SYSTEM_SHUTDOWN, "system_ctl", "shutdown",
         lambda m: {}),

        (r"(перезагрузи|restart|reboot)", CommandIntent.SYSTEM_RESTART, "system_ctl", "restart",
         lambda m: {}),

        (r"(спящий|сон|sleep|hibernate)", CommandIntent.SYSTEM_SLEEP, "system_ctl", "sleep",
         lambda m: {}),

        # ─── Volume ───
        (r"(громкость|volume)\s+(выше|up|увеличь|увеличить|громче)\s*(\d*)", CommandIntent.VOLUME_UP, "system_ctl", "volume_up",
         lambda m: {"amount": int(m.group(3)) if m.group(3) else 10}),

        (r"(громкость|volume)\s+(ниже|down|уменьши|уменьшить|тише)\s*(\d*)", CommandIntent.VOLUME_DOWN, "system_ctl", "volume_down",
         lambda m: {"amount": int(m.group(3)) if m.group(3) else 10}),

        (r"(громкость|volume)\s+(\d+)", CommandIntent.VOLUME_SET, "system_ctl", "volume",
         lambda m: {"value": int(m.group(2))}),

        # ─── Screen ───
        (r"(блокируй|lock|заблокируй)\s+(экран|screen)", CommandIntent.LOCK_SCREEN, "system_ctl", "lock_screen",
         lambda m: {}),

        (r"(скриншот|screenshot)", CommandIntent.TAKE_SCREENSHOT, "system_ctl", "screenshot",
         lambda m: {}),

        # ─── Music / Media ───
        (r"(включи|play|запусти)\s+(музыку|music|песню|song|трек|track)", CommandIntent.PLAY_MEDIA, "media_control", "play",
         lambda m: {}),

        (r"(пауза|pause|стоп|stop|останови)", CommandIntent.PAUSE_MEDIA, "media_control", "pause",
         lambda m: {}),

        (r"(следующий|next|след)\s*(трек|track|песня|song)", CommandIntent.NEXT_TRACK, "media_control", "next",
         lambda m: {}),

        (r"(предыдущий|previous|prev|пред)\s*(трек|track|песня|song)", CommandIntent.PREV_TRACK, "media_control", "previous",
         lambda m: {}),

        # ─── Files ───
        (r"(создай|create|make)\s+(файл|file|папку|folder|директорию|directory)\s+(\w[\w\s.]*)", CommandIntent.CREATE_FILE, "file_ops", "create",
         lambda m: {"path": m.group(3).strip(), "type": "file" if m.group(2) in ("file", "файл") else "folder"}),

        (r"(найди|find|search|поищи)\s+(файл|file)\s+(\w[\w\s.]*)", CommandIntent.SEARCH_FILES, "file_ops", "search",
         lambda m: {"pattern": m.group(3).strip()}),

        (r"(перемести|move|переименуй|rename)\s+(\w[\w\s.]+)\s+(в|to)\s+(\w[\w\s./\\]+)", CommandIntent.MOVE_FILE, "file_ops", "move",
         lambda m: {"source": m.group(2).strip(), "destination": m.group(4).strip()}),

        # ─── Memory ───
        (r"(запомни|remember|save|eslab|эслаб|yodda|ёдда)\s+(что|that|buni|буни)\s+(.+)", CommandIntent.SAVE_MEMORY, "memory", "save",
         lambda m: {"content": m.group(3).strip()}),

        (r"(напомни|remind|recall|eslat|эслат|what|что я говорил|nima degan)", CommandIntent.RECALL_MEMORY, "memory", "recall",
         lambda m: {"query": m.group(0)}),

        (r"my name is\s+(\w+)", CommandIntent.SAVE_MEMORY, "memory", "save_name",
         lambda m: {"content": f"user_name = {m.group(1).strip()}"}),

        (r"(меня зовут|my name is|mening ismim|менинг исмим)\s+(\w+)", CommandIntent.SAVE_MEMORY, "memory", "save_name",
         lambda m: {"content": f"user_name = {m.group(2).strip()}"}),

        # ─── Developer Mode ───
        (r"(coding mode|dev mode|developer mode|режим разработчика|кодинг|dasturchi|дастурчи)", CommandIntent.CODING_MODE, "developer", "activate",
         lambda m: {}),

        (r"(запусти|run|execute|ishga tushir|ишга тушир)\s+(команду|command|buyruq|буйрук)\s+(.+)", CommandIntent.RUN_COMMAND, "command_runner", "run",
         lambda m: {"command": m.group(3).strip()}),

        # ─── Time / Weather ───
        (r"(сколько времени|который час|time|current time|soat necha|соат неча|vaqt necha|вакт неча)", CommandIntent.GET_TIME, "system", "get_time",
         lambda m: {}),

        (r"(погода|weather|ob-havo|об-хаво|температура|temperature|harorat|харорат)\s+(.+)", CommandIntent.GET_WEATHER, "web_search", "search",
         lambda m: {"query": f"weather in {m.group(2).strip()}"}),

        (r"(погода|weather|ob-havo|об-хаво)", CommandIntent.GET_WEATHER, "web_search", "search",
         lambda m: {"query": "current weather"}),

        # ─── Create Reminder ───
        (r"(напомни|remind me|eslat|эслат)\s+(.+)\s+(завтра|tomorrow|ertaga|эртага|через|in|keyin|кейин)\s+(\d+)\s*(минут|minutes|daqiqa|дакица|часов|hours|soat|соат|дней|days|kun|кун)",
         CommandIntent.CREATE_REMINDER, "system", "create_reminder",
         lambda m: {"text": m.group(2).strip(), "delay": f"{m.group(4)} {m.group(5)}"}),
    ]

    @classmethod
    def match(cls, text: str) -> Optional[IntentResult]:
        """Try to match text against all patterns."""
        text_lower = text.lower().strip()

        for pattern, intent, tool, action, extractor in cls.PATTERNS:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                params = extractor(match)
                requires_confirmation = intent in (
                    CommandIntent.SYSTEM_SHUTDOWN,
                    CommandIntent.SYSTEM_RESTART,
                    CommandIntent.SYSTEM_SLEEP,
                )
                return IntentResult(
                    intent=intent,
                    confidence=0.85,
                    tool_name=tool,
                    action=action,
                    params=params,
                    raw_text=text,
                    requires_confirmation=requires_confirmation,
                )

        return None


class IntentProcessor:
    """Main intent processing pipeline.

    Flow:
    1. Pattern match (fast, 85% confidence)
    2. Keyword analysis (medium, 60% confidence)
    3. LLM fallback (slow, but handles anything)
    """

    def __init__(self, llm_provider=None) -> None:
        self._llm = llm_provider

    async def process(self, text: str) -> IntentResult:
        """Process natural language input and return structured intent.

        Args:
            text: User's natural language input.

        Returns:
            IntentResult with the parsed command.
        """
        if not text or not text.strip():
            return IntentResult(
                intent=CommandIntent.UNKNOWN,
                raw_text=text or "",
            )

        # Stage 1: Pattern match (fast path)
        result = IntentPatterns.match(text)
        if result:
            logger.debug(f"Intent matched via pattern: {result.intent.value} ({result.confidence})")
            return result

        # Stage 2: Keyword analysis (medium path)
        result = self._keyword_analysis(text)
        if result and result.confidence >= 0.6:
            logger.debug(f"Intent matched via keywords: {result.intent.value} ({result.confidence})")
            return result

        # Stage 3: LLM fallback (if available)
        if self._llm and self._llm.is_available:
            result = await self._llm_classify(text)
            if result and result.confidence >= 0.5:
                logger.debug(f"Intent matched via LLM: {result.intent.value} ({result.confidence})")
                return result

        # Default: general chat
        return IntentResult(
            intent=CommandIntent.CHAT,
            confidence=0.5,
            raw_text=text,
        )

    def _keyword_analysis(self, text: str) -> Optional[IntentResult]:
        """Simple keyword-based intent classification as fallback.

        Supports Uzbek (uz), Russian (ru), English (en).
        """
        text_lower = text.lower()

        # ─── Uzbek: open/och keywords ───
        if re.search(r'\boch\b', text_lower):
            return IntentResult(CommandIntent.OPEN_APP, 0.6, "app_control", "open", {"target": text}, text)

        # ─── Uzbek: close/yop keywords ───
        if re.search(r'\byop\b', text_lower):
            return IntentResult(CommandIntent.CLOSE_APP, 0.6, "system_ctl", "close_app", {"target": text}, text)

        # ─── Uzbek: shutdown/o'chir keywords ───
        if re.search(r"o['\u02bc]?chir", text_lower) and any(w in text_lower for w in ["компьютер", "pc", "system", "comp"]):
            return IntentResult(CommandIntent.SYSTEM_SHUTDOWN, 0.7, "system_ctl", "shutdown", {}, text, True)

        # ─── Uzbek: restart/qayta yukla ───
        if "qayta" in text_lower and "yukla" in text_lower:
            return IntentResult(CommandIntent.SYSTEM_RESTART, 0.7, "system_ctl", "restart", {}, text, True)

        # ─── Uzbek: search/qidir keywords ───
        if "qidir" in text_lower:
            return IntentResult(CommandIntent.SEARCH_WEB, 0.6, "web_search", "search", {"query": text}, text)

        # ─── Uzbek: volume/ovoz keywords ───
        if any(w in text_lower for w in ["ovoz", "овоз", "овозни", "ovozni"]):
            if any(w in text_lower for w in ["oshir", "baland", "увелич", "raise", "up"]):
                return IntentResult(CommandIntent.VOLUME_UP, 0.7, "system_ctl", "volume_up", {"amount": 10}, text)
            if any(w in text_lower for w in ["kamaytir", "pasayt", "уменьш", "lower", "down"]):
                return IntentResult(CommandIntent.VOLUME_DOWN, 0.7, "system_ctl", "volume_down", {"amount": 10}, text)

        # ─── Uzbek: create/yarat keywords ───
        if "yarat" in text_lower:
            return IntentResult(CommandIntent.CREATE_FILE, 0.6, "file_ops", "create", {"path": text}, text)

        # ─── Media keywords (multi-language) ───
        if any(w in text_lower for w in ["музык", "music", "песн", "song", "play", "мусица", "musiqa", "кўшик", "qo'shiq"]):
            if any(w in text_lower for w in ["след", "next", "следующ", "keyingi", "кейинги"]):
                return IntentResult(CommandIntent.NEXT_TRACK, 0.7, "media_control", "next", {"query": text}, text)
            if any(w in text_lower for w in ["пред", "prev", "previous", "oldingi", "олдинги"]):
                return IntentResult(CommandIntent.PREV_TRACK, 0.7, "media_control", "previous", {"query": text}, text)
            return IntentResult(CommandIntent.PLAY_MEDIA, 0.7, "media_control", "play", {"query": text}, text)

        # ─── Browser keywords (multi-language) ───
        if any(w in text_lower for w in ["браузер", "browser", "сайт", "site", "поиск", "search", "internet", "интернет"]):
            return IntentResult(CommandIntent.OPEN_WEBSITE, 0.6, "app_control", "open_url", {"url": text}, text)

        # ─── System keywords (multi-language) ───
        if any(w in text_lower for w in ["выключ", "shutdown", "отключ", "o'chir", "ўчир"]):
            return IntentResult(CommandIntent.SYSTEM_SHUTDOWN, 0.7, "system_ctl", "shutdown", {}, text, True)

        # ─── Volume keywords (multi-language) ───
        if any(w in text_lower for w in ["громк", "volume", "тише", "громче", "ovoz", "овоз"]):
            if any(w in text_lower for w in ["выше", "up", "увелич", "громче", "oshir", "baland"]):
                return IntentResult(CommandIntent.VOLUME_UP, 0.7, "system_ctl", "volume_up", {"amount": 10}, text)
            if any(w in text_lower for w in ["ниже", "down", "уменьш", "тише", "kamaytir", "pasayt"]):
                return IntentResult(CommandIntent.VOLUME_DOWN, 0.7, "system_ctl", "volume_down", {"amount": 10}, text)

        # ─── Coding keywords (multi-language) ───
        if any(w in text_lower for w in ["code", "coding", "dev", "код", "программир", "разработк", "dasturchi", "дастурчи"]):
            return IntentResult(CommandIntent.CODING_MODE, 0.7, "developer", "activate", {}, text)

        # ─── Screenshot keywords ───
        if any(w in text_lower for w in ["скрин", "screenshot", "ekran", "rasm", "snapshot"]):
            return IntentResult(CommandIntent.TAKE_SCREENSHOT, 0.6, "system_ctl", "screenshot", {}, text)

        return None

    async def _llm_classify(self, text: str) -> Optional[IntentResult]:
        """Use LLM to classify intent for complex queries."""
        if not self._llm:
            return None

        try:
            from backend.app.models.schemas import Message, MessageRole

            prompt = (
                "You are a command intent classifier. Analyze the user's request and "
                "determine what action they want to perform. Respond with ONLY a JSON object.\n\n"
                "Possible intents: open_app, close_app, search_web, open_website, search_files, "
                "system_shutdown, system_restart, system_sleep, volume_up, volume_down, "
                "play_music, pause_music, save_memory, recall_memory, chat, coding_mode\n\n"
                f"User request: {text}\n\n"
                "JSON response format: {\"intent\": \"...\", \"tool\": \"...\", \"action\": \"...\", \"params\": {...}}"
            )

            response = await self._llm.chat(
                messages=[Message(role=MessageRole.USER, content=prompt)],
                temperature=0.1,
                max_tokens=200,
            )

            import json
            try:
                data = json.loads(response.content)
                intent_str = data.get("intent", "chat")
                try:
                    intent = CommandIntent(intent_str)
                except ValueError:
                    intent = CommandIntent.CHAT

                return IntentResult(
                    intent=intent,
                    confidence=0.75,
                    tool_name=data.get("tool", ""),
                    action=data.get("action", ""),
                    params=data.get("params", {}),
                    raw_text=text,
                )
            except json.JSONDecodeError:
                return None

        except Exception as e:
            logger.warning(f"LLM intent classification failed: {e}")
            return None
