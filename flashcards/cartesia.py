"""Thin client for Cartesia's text-to-speech API.

We only need the synchronous "bytes" endpoint: send a transcript + language
+ voice, get an MP3 back. Sonic-3 (and Sonic-2 before it) supports Georgian
(`ka`) natively via voices like Levan and Tamara.

The client is intentionally dependency-light – it uses the standard library
so we don't add another package to ship in the container.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


DEFAULT_MODEL_ID = "sonic-3"
DEFAULT_API_VERSION = "2024-11-13"
DEFAULT_OUTPUT_FORMAT = {
    "container": "mp3",
    "sample_rate": 44100,
    "bit_rate": 128000,
}


class CartesiaError(RuntimeError):
    """Raised when the Cartesia API returns a non-2xx response."""


class CartesiaNotConfigured(RuntimeError):
    """Raised when required env vars (API key, voice IDs) are missing."""


@dataclass(frozen=True)
class CartesiaConfig:
    api_key: str
    model_id: str
    api_version: str
    voice_ka: str
    voice_en: str

    @classmethod
    def from_env(cls) -> "CartesiaConfig":
        api_key = os.environ.get("CARTESIA_API_KEY", "").strip()
        voice_ka = os.environ.get("CARTESIA_VOICE_KA", "").strip()
        voice_en = os.environ.get("CARTESIA_VOICE_EN", "").strip()
        if not api_key:
            raise CartesiaNotConfigured("CARTESIA_API_KEY is not set.")
        if not voice_ka or not voice_en:
            raise CartesiaNotConfigured(
                "CARTESIA_VOICE_KA and CARTESIA_VOICE_EN must both be set."
            )
        return cls(
            api_key=api_key,
            model_id=os.environ.get("CARTESIA_MODEL_ID", DEFAULT_MODEL_ID),
            api_version=os.environ.get("CARTESIA_API_VERSION", DEFAULT_API_VERSION),
            voice_ka=voice_ka,
            voice_en=voice_en,
        )


def synthesise(text: str, language: str, *, config: CartesiaConfig, timeout: float = 30.0) -> bytes:
    """Return MP3 bytes for `text` in the given `language` ('ka' or 'en')."""
    if language not in {"ka", "en"}:
        raise ValueError(f"Unsupported language: {language!r}")

    voice_id = config.voice_ka if language == "ka" else config.voice_en

    body = {
        "model_id": config.model_id,
        "transcript": text,
        "voice": {"mode": "id", "id": voice_id},
        "language": language,
        "output_format": DEFAULT_OUTPUT_FORMAT,
    }
    data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        "https://api.cartesia.ai/tts/bytes",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": config.api_key,
            "Cartesia-Version": config.api_version,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise CartesiaError(
            f"Cartesia HTTP {e.code} for {language!r} text {text[:40]!r}: {detail}"
        ) from e
    except urllib.error.URLError as e:
        raise CartesiaError(f"Cartesia connection error: {e.reason}") from e
