"""
Report generation + download. Powers the Reports page PDF/Excel buttons.
"""
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.services.report_service import generate_pdf_report
import io

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{report_type}/pdf")
async def download_report_pdf(report_type: str, business_id: str):
    pdf_bytes = generate_pdf_report(report_type, business_id)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={report_type}_report.pdf"},
    )
