"""
Professional CIM PDF Generator using ReportLab.
Produces a multi-page, investment-bank-quality PDF with:
  - Cover page, table of contents
  - Section headers, subheadings
  - Markdown-like formatting (bold, tables, bullets)
  - Embedded matplotlib charts
  - Page headers/footers with page numbers
"""
import os
import re
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Image, KeepTogether,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics

from chart_generator import generate_chart
from config import settings

# ─── Brand colours ───────────────────────────
NAVY   = colors.HexColor("#0F2B5B")
BLUE   = colors.HexColor("#1D4ED8")
LIGHT_BLUE = colors.HexColor("#DBEAFE")
ACCENT = colors.HexColor("#F59E0B")
GRAY   = colors.HexColor("#64748B")
LIGHT_GRAY = colors.HexColor("#F1F5F9")
WHITE  = colors.white
BLACK  = colors.HexColor("#0F172A")
GREEN  = colors.HexColor("#059669")
RED    = colors.HexColor("#DC2626")

W, H = A4  # 595 x 842 pts

SECTION_LABELS = {
    "executive_summary":  "1. Executive Summary",
    "investment_thesis":  "2. Investment Thesis",
    "market_overview":    "3. Overview of the Market",
    "company_overview":   "4. Overview of the Target Company",
    "products_services":  "5. Products & Services",
    "revenue_profile":    "6. Revenue Profile",
    "employee_profile":   "7. Employee Profile",
    "customer_profile":   "8. Customer Profile",
    "financials":         "9. Financials – Historical & Projections",
    "management_structure": "10. Management Structure",
}

SECTION_ORDER = list(SECTION_LABELS.keys())


# ─────────────────────────────────────────────
# Page template (header/footer)
# ─────────────────────────────────────────────

class CIMPageTemplate:
    def __init__(self, company_name: str = "Confidential"):
        self.company_name = company_name
        self.logo_path = None

    def on_page(self, canvas_obj: canvas.Canvas, doc):
        page = canvas_obj.getPageNumber()
        if page == 1:
            return  # cover page has no header/footer

        canvas_obj.saveState()

        # Header bar
        canvas_obj.setFillColor(NAVY)
        canvas_obj.rect(0, H - 28*mm, W, 12*mm, fill=1, stroke=0)
        canvas_obj.setFillColor(WHITE)
        canvas_obj.setFont("Helvetica-Bold", 9)
        canvas_obj.drawString(20*mm, H - 20*mm, "CONFIDENTIAL INFORMATION MEMORANDUM")
        canvas_obj.setFont("Helvetica", 9)
        canvas_obj.drawRightString(W - 20*mm, H - 20*mm, self.company_name)

        # Footer
        canvas_obj.setFillColor(LIGHT_GRAY)
        canvas_obj.rect(0, 0, W, 14*mm, fill=1, stroke=0)
        canvas_obj.setFillColor(GRAY)
        canvas_obj.setFont("Helvetica", 7.5)
        canvas_obj.drawString(20*mm, 5*mm,
            "STRICTLY CONFIDENTIAL — This document is for the exclusive use of the intended recipient(s) only.")
        canvas_obj.setFont("Helvetica-Bold", 9)
        canvas_obj.drawRightString(W - 20*mm, 5*mm, f"Page {page}")

        canvas_obj.restoreState()


# ─────────────────────────────────────────────
# Style sheet
# ─────────────────────────────────────────────

def _build_styles():
    base = getSampleStyleSheet()

    s = {}
    s["cover_title"] = ParagraphStyle("cover_title", fontName="Helvetica-Bold",
        fontSize=32, textColor=WHITE, alignment=TA_CENTER, leading=40, spaceAfter=8)
    s["cover_subtitle"] = ParagraphStyle("cover_subtitle", fontName="Helvetica",
        fontSize=16, textColor=colors.HexColor("#93C5FD"), alignment=TA_CENTER, leading=22, spaceAfter=6)
    s["cover_meta"] = ParagraphStyle("cover_meta", fontName="Helvetica",
        fontSize=11, textColor=WHITE, alignment=TA_CENTER, leading=16)
    s["cover_conf"] = ParagraphStyle("cover_conf", fontName="Helvetica-BoldOblique",
        fontSize=9, textColor=ACCENT, alignment=TA_CENTER, leading=14)

    s["section_header"] = ParagraphStyle("section_header", fontName="Helvetica-Bold",
        fontSize=18, textColor=NAVY, spaceBefore=18, spaceAfter=10, leading=24,
        borderPad=0, leftIndent=0)
    s["subsection_header"] = ParagraphStyle("subsection_header", fontName="Helvetica-Bold",
        fontSize=13, textColor=BLUE, spaceBefore=12, spaceAfter=6, leading=18)
    s["sub2_header"] = ParagraphStyle("sub2_header", fontName="Helvetica-Bold",
        fontSize=11, textColor=BLACK, spaceBefore=8, spaceAfter=4, leading=16)
    s["body"] = ParagraphStyle("body", fontName="Helvetica",
        fontSize=10, textColor=BLACK, leading=15, spaceAfter=5, alignment=TA_JUSTIFY)
    s["body_bold"] = ParagraphStyle("body_bold", fontName="Helvetica-Bold",
        fontSize=10, textColor=BLACK, leading=15, spaceAfter=5)
    s["bullet"] = ParagraphStyle("bullet", fontName="Helvetica",
        fontSize=10, textColor=BLACK, leading=15, spaceAfter=3,
        leftIndent=16, bulletIndent=4, bulletText="•")
    s["bullet2"] = ParagraphStyle("bullet2", fontName="Helvetica",
        fontSize=9.5, textColor=GRAY, leading=14, spaceAfter=2,
        leftIndent=32, bulletIndent=20, bulletText="–")
    s["caption"] = ParagraphStyle("caption", fontName="Helvetica-Oblique",
        fontSize=8.5, textColor=GRAY, alignment=TA_CENTER, spaceAfter=6)
    s["table_header"] = ParagraphStyle("table_header", fontName="Helvetica-Bold",
        fontSize=9, textColor=WHITE, alignment=TA_CENTER, leading=12)
    s["table_cell"] = ParagraphStyle("table_cell", fontName="Helvetica",
        fontSize=9, textColor=BLACK, leading=12)
    s["toc_entry"] = ParagraphStyle("toc_entry", fontName="Helvetica",
        fontSize=11, textColor=NAVY, leading=20, leftIndent=0)
    s["disclaimer"] = ParagraphStyle("disclaimer", fontName="Helvetica",
        fontSize=7.5, textColor=GRAY, leading=11, alignment=TA_JUSTIFY)
    s["highlight_box"] = ParagraphStyle("highlight_box", fontName="Helvetica",
        fontSize=10, textColor=NAVY, leading=15, backColor=LIGHT_BLUE,
        borderPad=8, leftIndent=8, rightIndent=8, spaceAfter=8)

    return s


# ─────────────────────────────────────────────
# Markdown-to-ReportLab content parser
# ─────────────────────────────────────────────

def _parse_markdown(text: str, styles: dict, output_dir: str, charts_data: list) -> list:
    """Convert markdown-ish text from LLM into ReportLab flowables."""
    flowables = []
    lines = text.split("\n")
    i = 0

    # Pre-generate chart images
    chart_images = {}
    for cd in (charts_data or []):
        img_path = generate_chart(cd, output_dir)
        if img_path:
            chart_images[cd.get("id", "")] = (img_path, cd.get("title", ""))

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty
        if not stripped:
            flowables.append(Spacer(1, 4))
            i += 1
            continue

        # === Section header (##)
        if stripped.startswith("## "):
            txt = stripped[3:].strip()
            flowables.append(Spacer(1, 6))
            flowables.append(Paragraph(_clean(txt), styles["subsection_header"]))
            flowables.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE, spaceAfter=6))
            i += 1
            continue

        # === Sub-subsection (###)
        if stripped.startswith("### "):
            txt = stripped[4:].strip()
            flowables.append(Paragraph(_clean(txt), styles["sub2_header"]))
            i += 1
            continue

        # === Table detection (| col | col |)
        if stripped.startswith("|") and "|" in stripped[1:]:
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            tbl = _build_table(table_lines, styles)
            if tbl:
                flowables.append(tbl)
                flowables.append(Spacer(1, 8))
            continue

        # === Bullet point
        if stripped.startswith("- ") or stripped.startswith("* "):
            txt = stripped[2:].strip()
            flowables.append(Paragraph(_clean(txt), styles["bullet"]))
            i += 1
            continue

        # === Numbered list
        m = re.match(r"^\d+\.\s+(.+)", stripped)
        if m:
            txt = m.group(1).strip()
            flowables.append(Paragraph(_clean(txt), styles["bullet"]))
            i += 1
            continue

        # === Bold line (starts and ends with **)
        if stripped.startswith("**") and stripped.endswith("**") and len(stripped) > 4:
            txt = stripped[2:-2].strip()
            flowables.append(Paragraph(_clean(txt), styles["body_bold"]))
            i += 1
            continue

        # === Regular paragraph
        # Collect continuation lines
        para_lines = [stripped]
        i += 1
        while i < len(lines):
            next_line = lines[i].strip()
            if (not next_line or next_line.startswith("#") or
                next_line.startswith("|") or next_line.startswith("- ") or
                next_line.startswith("* ") or re.match(r"^\d+\.\s+", next_line) or
                next_line.startswith("```")):
                break
            para_lines.append(next_line)
            i += 1

        para_text = " ".join(para_lines)
        if para_text.strip():
            flowables.append(Paragraph(_clean(para_text), styles["body"]))

    # Add charts at the end
    for cid, (img_path, img_title) in chart_images.items():
        flowables.append(Spacer(1, 12))
        max_w = W - 4*cm
        try:
            img = Image(img_path, width=max_w, height=max_w * 0.55)
            img.hAlign = "CENTER"
            flowables.append(img)
        except Exception:
            pass
        if img_title:
            flowables.append(Paragraph(f"Exhibit: {img_title}", styles["caption"]))
        flowables.append(Spacer(1, 8))

    return flowables


def _build_table(lines: list, styles: dict) -> Optional[Table]:
    """Build a styled ReportLab Table from pipe-delimited markdown table lines."""
    rows = []
    for line in lines:
        if re.match(r"^\|[-| :]+\|$", line.replace(" ", "")):
            continue  # separator row
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)

    if not rows:
        return None

    max_cols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < max_cols:
            r.append("")

    col_width = (W - 4*cm) / max(max_cols, 1)
    col_widths = [col_width] * max_cols

    # Build Paragraph cells
    table_data = []
    for ri, row in enumerate(rows):
        p_style = styles["table_header"] if ri == 0 else styles["table_cell"]
        table_data.append([Paragraph(_clean(cell), p_style) for cell in row])

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tbl


def _clean(text: str) -> str:
    """Escape special ReportLab XML chars and convert **bold** / *italic*."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    return text


# ─────────────────────────────────────────────
# PDF Generator
# ─────────────────────────────────────────────

class PDFGenerator:

    def generate(self, sections: Dict[str, dict], output_path: str, session_id: str = "") -> str:
        styles = _build_styles()
        page_tmpl = CIMPageTemplate(company_name="Confidential")
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=3.5*cm, bottomMargin=2.5*cm,
            title="Confidential Information Memorandum",
            author="CIM Generator",
        )

        story = []

        # 1. Cover page
        story.extend(self._cover_page(styles, sections))

        # 2. Disclaimer page
        story.append(PageBreak())
        story.extend(self._disclaimer_page(styles))

        # 3. Table of Contents
        story.append(PageBreak())
        story.extend(self._toc_page(styles, sections))

        # 4. Sections
        ordered_sections = sorted(
            sections.items(),
            key=lambda kv: SECTION_ORDER.index(kv[0]) if kv[0] in SECTION_ORDER else 99
        )
        for section_key, section_data in ordered_sections:
            story.append(PageBreak())
            label = SECTION_LABELS.get(section_key, section_key.replace("_", " ").title())
            content = section_data.get("content", "")
            charts = section_data.get("charts", [])

            # Section heading bar
            story.extend(self._section_heading(label, styles))

            # Body
            flowables = _parse_markdown(content, styles, settings.output_dir, charts)
            story.extend(flowables)

        doc.build(story, onFirstPage=page_tmpl.on_page, onLaterPages=page_tmpl.on_page)
        return output_path

    # ─────────────────────────────────────────────
    # Page builders
    # ─────────────────────────────────────────────

    def _cover_page(self, styles, sections) -> list:
        company_name = self._extract_company_name(sections)
        date_str = datetime.now().strftime("%B %Y")

        items = [Spacer(1, 180)]

        # Blue background effect using a table
        cover_data = [[
            Paragraph("CONFIDENTIAL INFORMATION MEMORANDUM", styles["cover_conf"]),
        ]]
        cover_tbl = Table(cover_data, colWidths=[W - 4*cm])
        cover_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("TOPPADDING", (0, 0), (-1, -1), 30),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 20),
            ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ]))
        items.append(cover_tbl)

        title_data = [[Paragraph(company_name.upper(), styles["cover_title"])]]
        title_tbl = Table(title_data, colWidths=[W - 4*cm])
        title_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 20),
            ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ]))
        items.append(title_tbl)

        sub_data = [[Paragraph("Investment Opportunity Overview", styles["cover_subtitle"])]]
        sub_tbl = Table(sub_data, colWidths=[W - 4*cm])
        sub_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 30),
            ("LEFTPADDING", (0, 0), (-1, -1), 20),
            ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ]))
        items.append(sub_tbl)

        items.append(Spacer(1, 40))
        items.append(Paragraph(date_str, styles["cover_meta"]))
        items.append(Spacer(1, 16))
        items.append(Paragraph("STRICTLY PRIVATE AND CONFIDENTIAL", styles["cover_conf"]))
        return items

    def _disclaimer_page(self, styles) -> list:
        items = [
            Spacer(1, 20),
            Paragraph("IMPORTANT NOTICE & DISCLAIMER", styles["section_header"]),
            HRFlowable(width="100%", thickness=2, color=NAVY, spaceAfter=16),
        ]
        disclaimer_text = (
            "This Confidential Information Memorandum (\"CIM\") has been prepared solely for the purpose of "
            "providing general information to prospective investors and does not constitute an offer to sell "
            "or a solicitation of an offer to buy any securities. This document is strictly confidential and "
            "is being provided to a limited number of prospective investors on a confidential basis."
            "<br/><br/>"
            "The information contained herein has been obtained from sources believed to be reliable, but its "
            "accuracy and completeness cannot be guaranteed. Certain information contained in this document "
            "represents forward-looking statements which involve known and unknown risks, uncertainties, and "
            "other factors that may cause actual results to differ materially from those anticipated."
            "<br/><br/>"
            "This document is confidential and may not be reproduced, redistributed, or passed on, directly "
            "or indirectly, to any other person or published, in whole or in part, for any purpose without "
            "the prior written consent of the Company and its advisors."
            "<br/><br/>"
            "Recipients of this document should not treat its contents as advice relating to legal, taxation, "
            "investment, or any other matters and are recommended to consult their own professional advisors "
            "concerning the acquisition."
            "<br/><br/>"
            "By accepting this document, the recipient agrees to be bound by the foregoing limitations and "
            "agrees to keep the contents strictly confidential. The recipient acknowledges that the contents "
            "of this document are confidential information within the terms of any non-disclosure agreement "
            "executed between the recipient and the Company or its advisors."
        )
        items.append(Paragraph(disclaimer_text, styles["disclaimer"]))
        return items

    def _toc_page(self, styles, sections) -> list:
        items = [
            Spacer(1, 20),
            Paragraph("TABLE OF CONTENTS", styles["section_header"]),
            HRFlowable(width="100%", thickness=2, color=NAVY, spaceAfter=16),
        ]
        ordered = sorted(
            [k for k in sections if k in SECTION_ORDER],
            key=lambda k: SECTION_ORDER.index(k)
        )
        for key in ordered:
            label = SECTION_LABELS.get(key, key)
            toc_row = [[
                Paragraph(label, styles["toc_entry"]),
                Paragraph("• • • • • • • • •", styles["caption"]),
            ]]
            t = Table(toc_row, colWidths=[W - 6*cm, 3*cm])
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            items.append(t)
        return items

    def _section_heading(self, label: str, styles) -> list:
        header_data = [[Paragraph(label, ParagraphStyle(
            "sec_h", fontName="Helvetica-Bold", fontSize=16,
            textColor=WHITE, leading=22, alignment=TA_LEFT
        ))]]
        t = Table(header_data, colWidths=[W - 4*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("TOPPADDING", (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ("LEFTPADDING", (0, 0), (-1, -1), 16),
            ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ]))
        # Accent bar
        accent = Table([[""]], colWidths=[W - 4*cm], rowHeights=[5])
        accent.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT)]))
        return [t, accent, Spacer(1, 14)]

    def _extract_company_name(self, sections: dict) -> str:
        for sec in ("executive_summary", "company_overview"):
            content = sections.get(sec, {}).get("content", "")
            m = re.search(r"Company[:\s]+([A-Za-z0-9\s&,\.]+)", content[:500])
            if m:
                return m.group(1).strip()[:50]
        return "Target Company"
