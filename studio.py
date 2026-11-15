"""Safe document/project generation helpers for DUCMANH AI.
Generated files are stored in a temporary workspace; never execute generated code.
"""
from __future__ import annotations
import io, os, re, zipfile
from pathlib import Path
from datetime import datetime

MAX_TEXT = 120_000
ALLOWED = {"html", "txt", "md", "pdf", "docx", "pptx", "xlsx", "zip"}

def _safe_name(name: str, ext: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", Path(name or "ducmanh-ai").stem).strip("-")[:60] or "ducmanh-ai"
    return f"{stem}.{ext}"

def generate_file(kind: str, name: str, content: str) -> tuple[str, bytes, str]:
    kind = (kind or "").lower().lstrip(".")
    if kind not in ALLOWED:
        raise ValueError("Định dạng chưa hỗ trợ: " + kind)
    content = (content or "")[:MAX_TEXT]
    filename = _safe_name(name, kind)
    if kind in ("html", "txt", "md"):
        if kind == "html" and "<html" not in content.lower():
            content = "<!doctype html><html lang='vi'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>DUCMANH AI</title><body>" + content + "</body></html>"
        data = content.encode("utf-8")
        mime = {"html":"text/html","txt":"text/plain","md":"text/markdown"}[kind]
    elif kind == "docx":
        from docx import Document
        doc = Document()
        for line in content.splitlines():
            if line.startswith("# "): doc.add_heading(line[2:], 1)
            elif line.startswith("## "): doc.add_heading(line[3:], 2)
            elif line.strip(): doc.add_paragraph(line)
        buf=io.BytesIO(); doc.save(buf); data=buf.getvalue(); mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif kind == "pdf":
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        # Register an available Unicode font so Vietnamese text is preserved.
        candidates=["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf","/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
        font=next((p for p in candidates if os.path.exists(p)),None)
        buf=io.BytesIO(); styles=getSampleStyleSheet()
        if font:
            pdfmetrics.registerFont(TTFont("DucUnicode",font)); styles["Normal"].fontName="DucUnicode"
            styles["Title"].fontName="DucUnicode"; styles["Heading2"].fontName="DucUnicode"
        story=[]
        for line in content.splitlines():
            safe=(line or " ").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            style=styles["Title"] if line.startswith("# ") else styles["Heading2"] if line.startswith("## ") else styles["Normal"]
            story.append(Paragraph(safe.lstrip("# "),style)); story.append(Spacer(1,6))
        SimpleDocTemplate(buf,pagesize=A4).build(story); data=buf.getvalue(); mime="application/pdf"
    elif kind == "pptx":
        from pptx import Presentation
        prs=Presentation()
        chunks=re.split(r"(?m)^#\s+",content)
        for idx,chunk in enumerate(chunks):
            lines=[x.strip() for x in chunk.splitlines() if x.strip()]
            if not lines: continue
            slide=prs.slides.add_slide(prs.slide_layouts[1 if len(prs.slide_layouts)>1 else 0])
            slide.shapes.title.text=lines[0][:180]
            if len(slide.placeholders)>1:
                slide.placeholders[1].text="\n".join(lines[1:])[:3000]
        if not prs.slides:
            slide=prs.slides.add_slide(prs.slide_layouts[0]); slide.shapes.title.text="DUCMANH AI"; slide.placeholders[1].text=content[:3000]
        buf=io.BytesIO(); prs.save(buf); data=buf.getvalue(); mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    elif kind == "xlsx":
        from openpyxl import Workbook
        wb=Workbook(); ws=wb.active; ws.title="DUCMANH AI"
        for row in content.splitlines():
            ws.append(row.split("\t") if "\t" in row else [row])
        buf=io.BytesIO(); wb.save(buf); data=buf.getvalue(); mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as z: z.writestr(_safe_name(name,"txt"),content)
        data=buf.getvalue(); mime="application/zip"
    return filename,data,mime
