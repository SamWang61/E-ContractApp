"""合約文件：驗證、儲存到 Firebase Storage、擷取文字供翻譯與簽署頁顯示。"""
from __future__ import annotations

import base64
import io
import re

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_TEXT = 60000
ALLOWED = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}
EXT_TYPES = {v: k for k, v in ALLOWED.items()} | {".jpeg": "image/jpeg"}


def safe_name(name: str) -> str:
    name = (name or "document").replace("\\", "/").split("/")[-1].strip()
    name = re.sub(r"[^\w.\-\u3400-\u9fff ]+", "_", name)[:120]
    return name or "document"


def decode_upload(file_name: str, content_type: str, data_base64: str) -> tuple[str, str, bytes]:
    name = safe_name(file_name)
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype not in ALLOWED:
        ctype = EXT_TYPES.get(ext, "")
    if ctype not in ALLOWED:
        raise ValueError("unsupported_file_type")
    if "," in data_base64 and data_base64.strip().startswith("data:"):
        data_base64 = data_base64.split(",", 1)[1]
    try:
        data = base64.b64decode(data_base64, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("invalid_file_data") from exc
    if not data:
        raise ValueError("empty_file")
    if len(data) > MAX_BYTES:
        raise ValueError("file_too_large")
    return name, ctype, data


def extract_text(ctype: str, data: bytes) -> str:
    text = ""
    try:
        if ctype == "application/pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:60])
        elif ctype.endswith("wordprocessingml.document"):
            from docx import Document
            doc = Document(io.BytesIO(data))
            text = "\n".join(p.text for p in doc.paragraphs)
        elif ctype == "text/plain":
            for enc in ("utf-8-sig", "utf-8", "big5", "gb18030"):
                try:
                    text = data.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
    except Exception:  # noqa: BLE001 - 擷取失敗不影響上傳，只是沒有可翻譯文字
        text = ""
    text = re.sub(r"[ \t]+\n", "\n", text).strip()
    return text[:MAX_TEXT]


def decode_signature(data_url: str) -> bytes | None:
    """手寫簽名 PNG（data URL），上限 300 KB。"""
    if not data_url:
        return None
    if not data_url.startswith("data:image/png;base64,"):
        raise ValueError("invalid_signature_image")
    raw = base64.b64decode(data_url.split(",", 1)[1])
    if len(raw) > 300 * 1024:
        raise ValueError("signature_image_too_large")
    return raw
