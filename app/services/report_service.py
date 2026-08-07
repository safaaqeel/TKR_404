"""
Downloadable PDF report generation. Pulls from analytics_service,
competitor_service, and ml/ modules, assembles a PDF via reportlab.
Powers: Reports page 'PDF' export buttons.
"""
from typing import Dict


def generate_pdf_report(report_type: str, business_id: str) -> bytes:
    """
    report_type: one of 'monthly', 'quarterly', 'risk', 'growth'
    Returns raw PDF bytes; the calling route sets the appropriate
    Content-Disposition header for download.

    Should run inside a BackgroundTasks job (see app/core/background.py)
    for anything beyond a trivial single-page report, then notify the
    frontend via polling or a websocket when ready.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    import io

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 800, f"Smart Automation AI - {report_type.title()} Report")

    # TODO: pull real sections from analytics_service / ml predictions
    c.setFont("Helvetica", 10)
    c.drawString(50, 770, "Business health, financial risk, and recommendations sections go here.")

    c.save()
    buffer.seek(0)
    return buffer.read()
