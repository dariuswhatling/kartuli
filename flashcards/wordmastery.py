"""Parse Georgian common-word data from WordMastery's bundled JS or JSON."""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
BUNDLED_JSON = DATA_DIR / "wordmastery_georgian.json"
MAIN_JS_URL = (
    "https://wordmastery.org/wp-content/themes/wordmastery-2/js/main.js"
)

# Keys in WordMastery's JS object → display chapter names.
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("verbs", "Verbs"),
    ("nouns", "Nouns"),
    ("adjectives", "Adjectives"),
    ("adverbs", "Adverbs"),
    ("pronouns", "Pronouns"),
    ("prepositions", "Prepositions"),
    ("conjunctions", "Conjunctions"),
    ("others", "Phrases"),
)

_ENTRY_RE = re.compile(
    r'\{\s*word:\s*"((?:[^"\\]|\\.)*)",\s*translation:\s*"((?:[^"\\]|\\.)*)",\s*pronunciation:\s*"((?:[^"\\]|\\.)*)"\s*\}'
)


def clean_romanised(raw: str) -> str:
    """Strip edge slashes, dashes, hyphens, and whitespace from romanisation."""
    s = (raw or "").strip()
    if len(s) >= 2 and s[0] == "/" and s[-1] == "/":
        s = s[1:-1].strip()
    return s.strip(" \t\n\r/-–—\\")


def clean_text(raw: str) -> str:
    return (raw or "").strip()


def _decode_js_string(value: str) -> str:
    try:
        return bytes(value, "utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return value


def _extract_category_array(block: str, key: str) -> str:
    match = re.search(rf"{key}:\s*\[", block)
    if not match:
        raise ValueError(f"Category {key!r} not found in Georgian block")
    depth = 1
    pos = match.end()
    while pos < len(block) and depth:
        ch = block[pos]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        pos += 1
    return block[match.start() : pos]


def parse_georgian_from_js(js_text: str) -> dict[str, dict]:
    """Return {slug: {name, words: [{georgian, english, romanised}, ...]}}."""
    marker = "'Georgian': {\n      verbs:"
    start = js_text.find(marker)
    if start < 0:
        raise ValueError("Georgian vocabulary block not found in main.js")
    end = js_text.find("\n    'German':", start)
    if end < 0:
        raise ValueError("End of Georgian vocabulary block not found")
    block = js_text[start:end]

    result: dict[str, dict] = {}
    for slug, name in CATEGORIES:
        arr_text = _extract_category_array(block, slug)
        words: list[dict[str, str]] = []
        for georgian, english, pronunciation in _ENTRY_RE.findall(arr_text):
            geo = clean_text(_decode_js_string(georgian))
            eng = clean_text(_decode_js_string(english))
            rom = clean_romanised(_decode_js_string(pronunciation))
            if not geo or not eng:
                continue
            words.append(
                {"georgian": geo, "english": eng, "romanised": rom}
            )
        result[slug] = {"name": name, "words": words}
    return result


def download_main_js() -> str:
    req = urllib.request.Request(
        MAIN_JS_URL,
        headers={"User-Agent": "Kartuli/1.0 (vocabulary import)"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode("utf-8", errors="replace")


def load_vocabulary(*, prefer_bundled: bool = True) -> dict[str, dict]:
    """Load vocabulary from bundled JSON, or download and parse main.js."""
    if prefer_bundled and BUNDLED_JSON.is_file():
        return json.loads(BUNDLED_JSON.read_text(encoding="utf-8"))

    js_text = download_main_js()
    data = parse_georgian_from_js(js_text)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BUNDLED_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return data
