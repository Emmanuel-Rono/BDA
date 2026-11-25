"""Create clean text PDFs from the demo text files (no OCR or external assets)."""
from pathlib import Path
from reportlab.pdfgen import canvas

root = Path(__file__).resolve().parent / 'examples'
for path in root.glob('*invoice.txt'):
    target = path.with_suffix('.pdf')
    pdf = canvas.Canvas(str(target))
    pdf.setTitle('Demo invoice')
    text = pdf.beginText(48, 790)
    text.setFont('Courier', 10)
    for line in path.read_text(encoding='utf-8').splitlines():
        text.textLine(line)
    pdf.drawText(text)
    pdf.save()
for path in root.glob('*packing-slip.txt'):
    pdf = canvas.Canvas(str(path.with_suffix('.pdf')))
    pdf.setTitle('Demo packing slip')
    text = pdf.beginText(48, 790)
    text.setFont('Courier', 10)
    for line in path.read_text(encoding='utf-8').splitlines():
        text.textLine(line)
    pdf.drawText(text)
    pdf.save()
print('Demo text PDFs generated in examples/.')
