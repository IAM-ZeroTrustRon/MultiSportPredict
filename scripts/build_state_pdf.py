#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_state_pdf.py - Renders STATE.md to a print-ready PDF, letter size.

Not part of the prediction pipeline. Run manually after STATE.md changes:
    venv/Scripts/python.exe scripts/build_state_pdf.py
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

import markdown
from xhtml2pdf import pisa

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "STATE.md"
OUT = ROOT / "STATE.pdf"

CSS = """
@page {
    size: letter;
    margin: 1in 0.85in 0.9in 0.85in;
    @frame footer_frame {
        -pdf-frame-content: footer_content;
        bottom: 0.4in; height: 0.4in; left: 0.85in; right: 0.85in;
    }
}
body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 9.5pt;
    line-height: 1.45;
    color: #1a1a1a;
}
h1 {
    font-size: 18pt;
    margin: 0 0 4pt 0;
    color: #111;
    border-bottom: 2pt solid #333;
    padding-bottom: 6pt;
}
h2 {
    font-size: 13pt;
    margin: 18pt 0 6pt 0;
    color: #111;
    border-bottom: 0.75pt solid #999;
    padding-bottom: 3pt;
    -pdf-keep-with-next: true;
}
h3 {
    font-size: 10.5pt;
    margin: 10pt 0 4pt 0;
    color: #222;
    -pdf-keep-with-next: true;
}
p { margin: 4pt 0; text-align: left; }
strong { color: #000; }
em { color: #333; }
ul, ol { margin: 4pt 0 8pt 0; padding-left: 16pt; }
li { margin: 2pt 0; }
code {
    font-family: Courier, monospace;
    font-size: 8.5pt;
    background-color: #f0f0f0;
    padding: 1pt 2pt;
}
pre {
    font-family: Courier, monospace;
    font-size: 8pt;
    background-color: #f5f5f5;
    padding: 6pt;
    border: 0.5pt solid #ccc;
}
hr {
    border: none;
    border-top: 0.5pt solid #bbb;
    margin: 12pt 0;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 6pt 0 10pt 0;
    font-size: 8pt;
}
th, td {
    border: 0.5pt solid #999;
    padding: 4pt 5pt;
    text-align: left;
    vertical-align: top;
}
th {
    background-color: #e8e8e8;
    font-weight: bold;
}
.meta {
    font-size: 8.5pt;
    color: #555;
    margin-bottom: 14pt;
}
#footer_content {
    font-size: 7.5pt;
    color: #888;
    text-align: center;
    border-top: 0.5pt solid #ccc;
    padding-top: 4pt;
}
"""

FOOTER_HTML = (
    '<div id="footer_content">MultiSportPredict &mdash; STATE.md, rendered '
    f'{_dt.date.today().isoformat()} &mdash; page <pdf:pagenumber/> of <pdf:pagecount/></div>'
)


def build() -> None:
    md_text = SRC.read_text(encoding="utf-8")
    body_html = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    full_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body>
{FOOTER_HTML}
{body_html}
</body></html>"""

    with open(OUT, "wb") as f:
        result = pisa.CreatePDF(full_html, dest=f)

    if result.err:
        raise SystemExit(f"PDF generation failed with {result.err} error(s)")
    print(f"Wrote {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
