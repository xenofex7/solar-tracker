import json
import os

SUPPORTED = {"de", "en", "fr", "es", "it"}
FALLBACK = "en"

_TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), "translations")
_cache: dict[str, dict] = {}


def _load(lang: str) -> dict:
    if lang not in _cache:
        path = os.path.join(_TRANSLATIONS_DIR, f"{lang}.json")
        with open(path, encoding="utf-8") as f:
            _cache[lang] = json.load(f)
    return _cache[lang]


def get_lang(request) -> str:
    lang = request.cookies.get("lang", "")
    if lang in SUPPORTED:
        return lang
    accept = request.headers.get("Accept-Language", "")
    for part in accept.split(","):
        code = part.strip().split(";")[0].split("-")[0].lower()
        if code in SUPPORTED:
            return code
    return FALLBACK


def get_translations(lang: str) -> dict:
    try:
        return _load(lang)
    except (FileNotFoundError, json.JSONDecodeError):
        return _load(FALLBACK)
