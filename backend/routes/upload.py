"""Upload route — Flask blueprint. Supports multi-file + auto-reconciliation."""
import os
import re
import time
import uuid
import logging
from flask import Blueprint, jsonify, request, g, Response

from store import store
from config import Config
from routes.auth import require_auth
from services.storage_service import validate_pdf_content, save_uploaded_file, delete_upload_file
from services.pdf_parser import parse_gst_pdf, _extract_period_from_filename
from services.analytics_engine import run_analytics
from services.reconciliation import compute_reconciliation

upload_bp = Blueprint("upload", __name__)
logger = logging.getLogger(__name__)

# Vercel serverless payload hard limit is 4.5 MB (4,718,592 bytes)
VERCEL_MAX_PAYLOAD_BYTES = int(4.5 * 1024 * 1024)


def _get_request_id() -> str:
    """Retrieve existing X-Request-ID from request or generate a new correlation ID."""
    req_id = request.headers.get("X-Request-ID")
    if req_id and re.match(r'^[a-zA-Z0-9_\-\.]{4,64}$', req_id.strip()):
        return req_id.strip()
    return f"req_{uuid.uuid4().hex[:12]}"


def _make_response(data: dict, status_code: int, request_id: str) -> Response:
    """Return a JSON response with correlation X-Request-ID header attached."""
    resp = jsonify(data)
    resp.status_code = status_code
    resp.headers["X-Request-ID"] = request_id
    return resp


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal or sensitive path exposure."""
    base = os.path.basename(filename or "unknown.pdf")
    return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', base)


@upload_bp.post("/upload")
@require_auth
def upload_pdf():
    t_start = time.perf_counter()
    request_id = _get_request_id()

    # Stage 1: UPLOAD_RECEIVED
    content_length = request.content_length or 0
    raw_filename = request.files.get("file").filename if "file" in request.files else ""
    sanitized_name = _sanitize_filename(raw_filename)

    logger.info(
        "[req_id=%s] stage=UPLOAD_RECEIVED filename=%s content_length=%s",
        request_id, sanitized_name, content_length
    )

    # ── 1. Validation: Missing file ───────────────────────────────────────────
    if "file" not in request.files:
        logger.warning(
            "[req_id=%s] stage=VALIDATION_FAILED reason='No file provided' status_code=400",
            request_id
        )
        return _make_response({"error": "No file provided", "request_id": request_id}, 400, request_id)

    f = request.files["file"]
    if not f.filename or f.filename.strip() == "":
        logger.warning(
            "[req_id=%s] stage=VALIDATION_FAILED reason='Empty filename' status_code=400",
            request_id
        )
        return _make_response({"error": "No file selected", "request_id": request_id}, 400, request_id)

    # ── 2. Validation: Extension check ───────────────────────────────────────
    if not f.filename.lower().endswith(".pdf"):
        logger.warning(
            "[req_id=%s] stage=VALIDATION_FAILED reason='Invalid extension' filename=%s status_code=400",
            request_id, sanitized_name
        )
        return _make_response({"error": "Only PDF files accepted (.pdf)", "request_id": request_id}, 400, request_id)

    # ── 3. Read content & Size check (413 Payload Too Large) ──────────────────
    try:
        content = f.read()
    except Exception as exc:
        logger.exception("[req_id=%s] stage=READ_FAILED reason='%s'", request_id, exc)
        return _make_response({"error": "Failed to read uploaded file", "request_id": request_id}, 400, request_id)

    file_size_bytes = len(content)
    max_allowed_bytes = VERCEL_MAX_PAYLOAD_BYTES

    if file_size_bytes > max_allowed_bytes:
        logger.warning(
            "[req_id=%s] stage=VALIDATION_FAILED reason='Payload too large' size_bytes=%d max_bytes=%d status_code=413",
            request_id, file_size_bytes, max_allowed_bytes
        )
        return _make_response(
            {
                "error": f"File size ({file_size_bytes / (1024*1024):.2f} MB) exceeds maximum allowed limit ({max_allowed_bytes / (1024*1024):.1f} MB)",
                "code": "PAYLOAD_TOO_LARGE",
                "request_id": request_id
            },
            413,
            request_id
        )

    # ── 4. Validation: Magic Header Verification ─────────────────────────────
    if not validate_pdf_content(content):
        logger.warning(
            "[req_id=%s] stage=VALIDATION_FAILED reason='Invalid PDF magic header' size_bytes=%d status_code=400",
            request_id, file_size_bytes
        )
        return _make_response(
            {"error": "Invalid PDF format: file signature verification failed", "request_id": request_id},
            400,
            request_id
        )

    logger.info(
        "[req_id=%s] stage=VALIDATION_PASSED filename=%s size_bytes=%d",
        request_id, sanitized_name, file_size_bytes
    )

    # ── 5. File Persistence ──────────────────────────────────────────────────
    try:
        file_id, save_path = save_uploaded_file(content, f.filename)
    except Exception as exc:
        logger.exception("[req_id=%s] stage=FILE_SAVE_FAILED reason='%s'", request_id, exc)
        return _make_response({"error": "Failed to store uploaded file", "request_id": request_id}, 500, request_id)

    user_id = getattr(g, "current_user", {}).get("id", "default_user")
    logger.info("[req_id=%s] stage=FILE_SAVED file_id=%s", request_id, file_id)

    # ── 6. PDF Parsing (Phase 4 Robustness) ──────────────────────────────────
    logger.info("[req_id=%s] stage=PARSING_STARTED file_id=%s", request_id, file_id)
    t_parse_start = time.perf_counter()

    try:
        extracted = parse_gst_pdf(save_path)
    except Exception as exc:
        parse_duration_ms = round((time.perf_counter() - t_parse_start) * 1000, 2)
        delete_upload_file(file_id)
        logger.exception(
            "[req_id=%s] stage=PARSING_FAILED duration_ms=%.2f error='%s' status_code=500",
            request_id, parse_duration_ms, exc
        )
        return _make_response(
            {"error": "An unexpected error occurred while parsing the PDF", "request_id": request_id},
            500,
            request_id
        )

    parse_duration_ms = round((time.perf_counter() - t_parse_start) * 1000, 2)
    gst_type = extracted.get("form_type", "UNKNOWN")
    period = extracted.get("period", "")
    page_count = extracted.get("_page_count", 0)
    parse_ok = extracted.get("_parse_success", False)
    warnings = extracted.get("_parse_warnings", [])
    is_corrupt = extracted.get("_corrupt", False)

    logger.info(
        "[req_id=%s] stage=PARSING_COMPLETED file_id=%s form_type=%s page_count=%d duration_ms=%.2f parse_success=%s",
        request_id, file_id, gst_type, page_count, parse_duration_ms, parse_ok
    )

    # ── 7. Handle Corrupted PDF Container (400 Bad Request) ──────────────────
    if is_corrupt:
        delete_upload_file(file_id)
        logger.warning(
            "[req_id=%s] stage=PARSING_FAILED reason='Corrupted PDF structure' status_code=400",
            request_id
        )
        return _make_response(
            {
                "error": "Corrupted PDF file: unable to read document structure",
                "request_id": request_id,
                "parse_warnings": warnings
            },
            400,
            request_id
        )

    # ── 8. Handle Unsupported / Unparsable GST Structure (422 Unprocessable) ─
    if gst_type == "UNKNOWN" or not parse_ok:
        delete_upload_file(file_id)
        logger.warning(
            "[req_id=%s] stage=PARSING_UNPROCESSABLE form_type=%s warnings=%s status_code=422",
            request_id, gst_type, warnings
        )
        error_msg = (
            "Unsupported PDF format: document is not a recognized GST return (GSTR-1, GSTR-3B, GSTR-9, GSTR-9C)"
            if gst_type == "UNKNOWN"
            else "Unprocessable GST structure: failed to extract required GST filing sections"
        )
        return _make_response(
            {
                "error": error_msg,
                "form_type": gst_type,
                "request_id": request_id,
                "parse_warnings": warnings
            },
            422,
            request_id
        )

    # ── 9. Period Refinement from Filename if FY-only ─────────────────────────
    if not period or re.match(r'^\d{4}-\d{2,4}$', period.strip()):
        name_period = _extract_period_from_filename(f.filename)
        if name_period:
            period = name_period
            extracted['period'] = period

    # ── 10. Database Persistence ─────────────────────────────────────────────
    try:
        store.add_file(file_id, f.filename, gst_type, period, user_id=user_id)
        store.set_extracted_data(file_id, extracted)
        logger.info("[req_id=%s] stage=DATABASE_SAVED file_id=%s form_type=%s period=%s", request_id, file_id, gst_type, period)
    except Exception as exc:
        delete_upload_file(file_id)
        logger.exception("[req_id=%s] stage=DATABASE_FAILED error='%s'", request_id, exc)
        return _make_response({"error": "Failed to save parsed GST data", "request_id": request_id}, 500, request_id)

    # ── 11. Analytics Engine ──────────────────────────────────────────────────
    t_analytics_start = time.perf_counter()
    try:
        analytics = run_analytics(extracted)
        analytics_duration_ms = round((time.perf_counter() - t_analytics_start) * 1000, 2)
        logger.info("[req_id=%s] stage=ANALYTICS_COMPLETED file_id=%s duration_ms=%.2f", request_id, file_id, analytics_duration_ms)
    except Exception as exc:
        logger.exception("[req_id=%s] stage=ANALYTICS_FAILED error='%s'", request_id, exc)
        analytics = {"error": "Analytics computation encountered an issue", "kpis": [], "ratios": [], "insights": []}

    store.set_analytics(file_id, analytics)
    store.mark_file_ready(file_id)

    # ── 12. Auto-Reconciliation ───────────────────────────────────────────────
    reconciliation = None
    reconciliation_triggered = False

    if gst_type in ("GSTR-1", "GSTR-3B") and period and period != "Period not found":
        try:
            counterpart_id = store.find_counterpart(file_id)
            if counterpart_id:
                counterpart_data = store.get_extracted_data(counterpart_id)
                if gst_type == "GSTR-1":
                    gstr1_data, gstr3b_data = extracted, counterpart_data
                else:
                    gstr1_data, gstr3b_data = counterpart_data, extracted

                reconciliation = compute_reconciliation(gstr1_data, gstr3b_data)
                store.set_reconciliation(period, reconciliation)
                reconciliation_triggered = True
                logger.info("[req_id=%s] stage=RECONCILIATION_COMPLETED period=%s", request_id, period)
        except Exception as exc:
            logger.exception("[req_id=%s] stage=RECONCILIATION_FAILED error='%s'", request_id, exc)

    # ── 13. Response Ready ────────────────────────────────────────────────────
    total_duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
    logger.info("[req_id=%s] stage=RESPONSE_READY status_code=200 total_duration_ms=%.2f", request_id, total_duration_ms)

    return _make_response(
        {
            "file_id": file_id,
            "filename": f.filename,
            "gst_type": gst_type,
            "period": period,
            "parse_success": parse_ok,
            "parse_warnings": warnings,
            "extracted_data": {k: v for k, v in extracted.items() if not k.startswith("_")},
            "analytics": analytics,
            "reconciliation": reconciliation,
            "reconciliation_triggered": reconciliation_triggered,
            "request_id": request_id,
            "message": f"Successfully parsed {gst_type} for {period}",
        },
        200,
        request_id
    )
