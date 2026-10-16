"""合約翻譯：繁體中文（zh-TW）、簡體中文（zh-CN）、英文（en）。

- 繁 ↔ 簡：OpenCC 對照轉換（不需外部服務、免費、結果穩定）。
- 中 ↔ 英：Google Cloud Translation API v2，使用 Cloud Functions 預設服務帳號
  （需在 GCP 啟用「Cloud Translation API」）。
"""
from __future__ import annotations

import os
import re
from typing import Iterable

import requests

SUPPORTED = ("zh-TW", "zh-CN", "en")
_CJK = re.compile(r"[\u3400-\u9fff]")
_converters: dict[str, object] = {}
CHUNK = 4500  # Cloud Translation 單次請求建議上限


def _opencc(config: str):
    if config not in _converters:
        from opencc import OpenCC  # opencc-python-reimplemented
        _converters[config] = OpenCC(config)
    return _converters[config]


def is_chinese(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if _CJK.match(c)) / len(letters) >= 0.3


def _chunks(text: str) -> Iterable[str]:
    buf = ""
    for line in text.splitlines(keepends=True):
        while len(line) > CHUNK:
            if buf:
                yield buf
                buf = ""
            yield line[:CHUNK]
            line = line[CHUNK:]
        if len(buf) + len(line) > CHUNK:
            yield buf
            buf = ""
        buf += line
    if buf:
        yield buf


def _access_token() -> str:
    import google.auth
    from google.auth.transport.requests import Request

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-translation"])
    creds.refresh(Request())
    return creds.token


def cloud_translate(text: str, target: str) -> str:
    """呼叫 Cloud Translation v2；target 為 en / zh-TW / zh-CN。"""
    if not text.strip():
        return text
    if os.getenv("TRANSLATE_FAKE") == "1":  # 僅供本機模擬器測試
        return f"[{target}] {text}"
    token = _access_token()
    out = []
    for part in _chunks(text):
        res = requests.post(
            "https://translation.googleapis.com/language/translate/v2",
            headers={"Authorization": f"Bearer {token}"},
            json={"q": part, "target": target, "format": "text"},
            timeout=30,
        )
        if res.status_code == 403:
            raise ValueError("translation_api_not_enabled")
        if res.status_code >= 400:
            raise ValueError(f"translation_failed_{res.status_code}")
        out.append(res.json()["data"]["translations"][0]["translatedText"])
    return "".join(out)


def translate_text(text: str, target: str) -> str:
    if target not in SUPPORTED:
        raise ValueError("unsupported_language")
    text = text or ""
    if not text.strip():
        return text
    if is_chinese(text):
        if target == "zh-TW":
            return _opencc("s2twp").convert(text)
        if target == "zh-CN":
            return _opencc("tw2sp").convert(text)
        return cloud_translate(text, "en")
    # 原文為英文（或其他語言）
    if target == "en":
        return text
    zh = cloud_translate(text, "zh-TW")
    return zh if target == "zh-TW" else _opencc("tw2sp").convert(zh)


def translate_fields(fields: dict[str, str], target: str) -> dict[str, str]:
    return {k: translate_text(v or "", target) for k, v in fields.items()}
