"""
Convierte INFORME.md (con sus capturas) en INFORME.pdf usando Chrome headless.
Uso:  python generar_pdf.py
"""
import subprocess
from pathlib import Path

import markdown

BASE = Path(__file__).resolve().parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1a1a1a; }
h1 { font-size: 19pt; color: #0b3d2e; border-bottom: 3px solid #00684a; padding-bottom: 6px; }
h2 { font-size: 14pt; color: #00684a; margin-top: 26px; border-bottom: 1px solid #ccc; padding-bottom: 3px; page-break-after: avoid; }
h3 { font-size: 11.5pt; color: #0b3d2e; page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 14px; font-size: 9pt; page-break-inside: avoid; }
th { background: #e8f3ee; text-align: left; }
th, td { border: 1px solid #c8d3cd; padding: 4px 6px; vertical-align: top; }
code { font-family: Menlo, monospace; font-size: 8.8pt; background: #f2f4f3; padding: 1px 3px; border-radius: 3px; }
pre { background: #f2f4f3; padding: 8px 10px; border-radius: 4px; overflow-x: hidden; white-space: pre-wrap; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
p:has(> img) { text-align: center; margin: 14px 0 2px; page-break-inside: avoid; page-break-after: avoid; }
img { display: block; margin: 0 auto; max-width: 100%; max-height: 560px; border: 1px solid #bbb; border-radius: 4px; }
p:has(> img) > em { display: block; text-align: center; font-size: 8.8pt; color: #555; margin: 4px 0 14px; }
hr { border: none; border-top: 1px solid #ddd; margin: 18px 0; }
"""


def main():
    md = (BASE / "INFORME.md").read_text(encoding="utf-8")
    cuerpo = markdown.markdown(md, extensions=["tables", "fenced_code"])
    html = f'<!doctype html><html lang="es"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{cuerpo}</body></html>'
    html_path = BASE / "INFORME.html"
    html_path.write_text(html, encoding="utf-8")
    pdf_path = BASE / "INFORME.pdf"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", html_path.as_uri()], check=True, capture_output=True)
    html_path.unlink()
    print(f"PDF generado: {pdf_path}")


if __name__ == "__main__":
    main()
