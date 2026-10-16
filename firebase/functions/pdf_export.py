"""產生「已簽署完成」的合約 PDF。

內容：封面 → 合約條款 → 上傳文件文字（或附件說明）→ 簽署頁（各方姓名、時間、手寫簽名）
→ 稽核紀錄（合約編號、文件 SHA-256、PDF 產生時間）。
若上傳的是 PDF，原始 PDF 頁面會完整附在最後。字型內嵌（繁／簡／英皆可顯示）。
"""
from __future__ import annotations

import hashlib
import io
import os
from datetime import datetime, timedelta, timezone

from fpdf import FPDF

FONT = os.path.join(os.path.dirname(__file__), "fonts", "DroidSansFallbackFull.ttf")  # 中文
LATIN = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")  # 英數
TW = timezone(timedelta(hours=8))
COVER_COLORS = {
    "classic-navy": ((15, 31, 61), (244, 246, 251)),
    "business-gold": ((22, 19, 13), (233, 210, 154)),
    "minimal-white": ((255, 255, 255), (23, 32, 51)),
    "tech-blue": ((30, 58, 138), (232, 240, 255)),
    "jade-green": ((227, 238, 228), (31, 61, 43)),
    "crimson-seal": ((251, 247, 241), (43, 29, 20)),
}
ACTION_TEXT = {"sign": "已簽署 Signed", "decline": "拒絕 Declined", "request_changes": "退回修改 Changes requested"}


def _fmt(value) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(TW).strftime("%Y-%m-%d %H:%M:%S (UTC+8)")
    return str(value or "")


class _Doc(FPDF):
    def __init__(self, contract_id: str):
        super().__init__(format="A4")
        self.contract_id = contract_id
        self.add_font("latin", "", LATIN)
        self.add_font("cjk", "", FONT)
        self.set_fallback_fonts(["cjk"])
        self.set_auto_page_break(True, margin=18)
        self.set_margins(18, 18, 18)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-12)
        self.set_font("latin", size=8)
        self.set_text_color(120, 130, 150)
        self.cell(0, 6, f"{self.contract_id}  |  第 {self.page_no()} 頁 Page {self.page_no()}", align="C")


def build_signed_pdf(contract_id: str, contract: dict, signatures: list[dict], original_pdf: bytes | None = None) -> bytes:
    """signatures: [{role, name, email, at, image(bytes|None)}]，依簽署順序。"""
    pdf = _Doc(contract_id)
    bg, fg = COVER_COLORS.get(contract.get("coverId", "classic-navy"), COVER_COLORS["classic-navy"])

    # ---- 封面
    pdf.add_page()
    pdf.set_fill_color(*bg)
    pdf.rect(0, 0, 210, 297, "F")
    if contract.get("coverId") == "crimson-seal":
        pdf.set_fill_color(180, 35, 24)
        pdf.rect(0, 0, 7, 297, "F")
    if contract.get("coverId") == "business-gold":
        pdf.set_fill_color(184, 145, 58)
        pdf.rect(0, 0, 210, 14, "F")
    pdf.set_text_color(*fg)
    pdf.set_font("latin", size=10)
    pdf.set_xy(22, 34)
    pdf.cell(0, 8, "GLOBAL CONTRACT MANAGEMENT")
    pdf.set_xy(22, 120)
    pdf.set_font("latin", size=11)
    pdf.cell(0, 8, "CONTRACT  ·  已簽署完成 FULLY SIGNED")
    pdf.set_xy(22, 132)
    pdf.set_font("latin", size=26)
    pdf.multi_cell(166, 13, contract.get("title", ""), new_x="LMARGIN", new_y="NEXT", align="L")
    if contract.get("summary"):
        pdf.set_x(22)
        pdf.set_font("latin", size=11)
        pdf.multi_cell(166, 7, contract["summary"], new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.ln(6)
    for p in contract.get("parties", []):
        pdf.set_x(22)
        pdf.set_font("latin", size=11)
        pdf.cell(0, 7, f"{p.get('role', '')}：{p.get('company') or p.get('email', '')}", new_x="LMARGIN", new_y="NEXT", align="L")
        extra = "　".join(x for x in [f"統編 {p['taxId']}" if p.get("taxId") else "", f"代表人 {p['representative']}" if p.get("representative") else ""] if x)
        if extra:
            pdf.set_x(28)
            pdf.set_font("latin", size=9)
            pdf.cell(0, 5, extra, new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.set_xy(22, 262)
    pdf.set_font("latin", size=9)
    pdf.cell(0, 6, f"合約編號 Contract ID：{contract_id}", new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.set_x(22)
    pdf.cell(0, 6, f"建立 Created：{_fmt(contract.get('createdAt'))}")

    # ---- 條款與文件文字
    pdf.add_page()
    pdf.set_text_color(23, 32, 51)
    pdf.set_font("latin", size=16)
    pdf.cell(0, 10, "立約當事人 Parties", new_x="LMARGIN", new_y="NEXT", align="L")
    for p in contract.get("parties", []):
        pdf.set_font("latin", size=11)
        pdf.cell(0, 7, f"{p.get('role', '')}　{p.get('company') or '（個人 Individual）'}", new_x="LMARGIN", new_y="NEXT", align="L")
        pdf.set_font("latin", size=9)
        pdf.set_text_color(90, 100, 120)
        for label, key in (("統一編號 Tax ID", "taxId"), ("地址 Address", "address"), ("代表人 Representative", "representative"), ("Email", "email")):
            if p.get(key):
                pdf.multi_cell(0, 5, f"    {label}：{p[key]}", new_x="LMARGIN", new_y="NEXT", align="L")
        pdf.set_text_color(23, 32, 51)
        pdf.ln(1)
    pdf.ln(3)
    pdf.set_font("latin", size=16)
    pdf.cell(0, 10, "合約條款 Terms", new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.set_font("latin", size=11)
    pdf.multi_cell(0, 7, contract.get("body") or "（本合約條款以附件文件為準 See attached document）", new_x="LMARGIN", new_y="NEXT", align="L")
    doc = contract.get("document") or {}
    if doc:
        pdf.ln(4)
        pdf.set_font("latin", size=13)
        pdf.cell(0, 9, "附件文件 Attached document", new_x="LMARGIN", new_y="NEXT", align="L")
        pdf.set_font("latin", size=9)
        pdf.set_text_color(90, 100, 120)
        pdf.multi_cell(0, 6, f"{doc.get('name', '')}｜{doc.get('size', 0)} bytes｜SHA-256 {doc.get('sha256', '')}", new_x="LMARGIN", new_y="NEXT", align="L")
        pdf.set_text_color(23, 32, 51)
        if original_pdf:
            pdf.set_font("latin", size=10)
            pdf.multi_cell(0, 6, "原始 PDF 文件完整附於本檔最後。The original PDF is appended at the end.", new_x="LMARGIN", new_y="NEXT", align="L")
        elif contract.get("documentText"):
            pdf.set_font("latin", size=10)
            pdf.multi_cell(0, 6, contract["documentText"], new_x="LMARGIN", new_y="NEXT", align="L")

    # ---- 簽署頁
    pdf.add_page()
    pdf.set_font("latin", size=16)
    pdf.cell(0, 10, "簽署頁 Signatures", new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.ln(2)
    for s in signatures:
        if pdf.get_y() > 230:
            pdf.add_page()
        top = pdf.get_y()
        pdf.set_draw_color(205, 214, 228)
        pdf.rect(18, top, 174, 46)
        pdf.set_xy(22, top + 4)
        pdf.set_font("latin", size=12)
        pdf.cell(80, 7, f"{s.get('role', '')}　{s.get('name', '')}", new_x="LMARGIN", new_y="NEXT", align="L")
        pdf.set_font("latin", size=9)
        pdf.set_text_color(90, 100, 120)
        party = next((p for p in contract.get("parties", []) if p.get("email") == s.get("email") or p.get("role") == s.get("role")), {})
        comp = party.get("company", "")
        ids = "｜".join(x for x in [f"統編 {party['taxId']}" if party.get("taxId") else "", f"代表人 {party['representative']}" if party.get("representative") else ""] if x)
        for line in (comp, ids, s.get("email", ""), f"簽署時間 Signed at：{_fmt(s.get('at'))}", ACTION_TEXT.get(s.get("action", "sign"), "")):
            if not line:
                continue
            pdf.set_x(22)
            pdf.cell(80, 6, line, new_x="LMARGIN", new_y="NEXT", align="L")
        pdf.set_text_color(23, 32, 51)
        if s.get("image"):
            pdf.image(io.BytesIO(s["image"]), x=112, y=top + 4, w=76, h=36, keep_aspect_ratio=True)
        pdf.set_y(top + 50)

    # ---- 稽核紀錄
    pdf.ln(4)
    pdf.set_font("latin", size=13)
    pdf.cell(0, 9, "稽核紀錄 Audit trail", new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.set_font("latin", size=9)
    pdf.set_text_color(90, 100, 120)
    audit = [
        f"合約編號 Contract ID：{contract_id}",
        f"簽署方數 Parties：{len(contract.get('parties', []))}　已簽 Signed：{len(signatures)}",
        "簽署方式：一次性專屬連結（使用後立即失效）＋姓名＋電子簽署同意＋手寫簽名",
        f"PDF 產生時間 Generated：{_fmt(datetime.now(timezone.utc))}",
    ]
    if doc.get("sha256"):
        audit.append(f"附件 SHA-256：{doc['sha256']}")
    for line in audit:
        pdf.multi_cell(0, 6, line, new_x="LMARGIN", new_y="NEXT", align="L")

    body = bytes(pdf.output())
    if not original_pdf:
        return body
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    for src in (body, original_pdf):
        for page in PdfReader(io.BytesIO(src)).pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
