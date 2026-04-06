"""Audit evidence collector — captures screenshots, network traffic, and generates PDF reports.

Hooks into a Playwright page to automatically capture:
- All network requests/responses
- Console log messages
- Screenshots at labeled moments
- Generates an HTML evidence report converted to PDF via Playwright
"""

from __future__ import annotations

import base64
import logging
import time
import uuid
from datetime import datetime
from typing import Any

from openquery.models.audit import AuditRecord, NetworkEntry, Screenshot

logger = logging.getLogger(__name__)


class AuditCollector:
    """Collects audit evidence from a Playwright page session."""

    def __init__(self, source: str, document_type: str, document_number: str) -> None:
        self._id = str(uuid.uuid4())
        self._source = source
        self._document_type = document_type
        self._document_number = document_number
        self._start_time = time.monotonic()
        self._started_at = datetime.now()
        self._screenshots: list[Screenshot] = []
        self._network_log: list[NetworkEntry] = []
        self._console_log: list[str] = []
        self._pending_requests: dict[str, dict] = {}  # url -> request info
        self._page_url = ""
        self._user_agent = ""

    def attach(self, page: Any) -> None:
        """Attach event listeners to a Playwright page."""
        # Capture user agent
        self._user_agent = page.evaluate("() => navigator.userAgent")

        # Network request listener
        page.on("request", self._on_request)
        page.on("response", self._on_response)

        # Console log listener
        page.on("console", self._on_console)

        logger.info("Audit collector attached to page (id=%s)", self._id)

    def _on_request(self, request: Any) -> None:
        """Capture outgoing request."""
        url = request.url
        self._pending_requests[url] = {
            "timestamp": datetime.now(),
            "method": request.method,
            "url": url,
            "request_headers": dict(request.headers),
            "request_body": request.post_data,
            "start_time": time.monotonic(),
        }

    def _on_response(self, response: Any) -> None:
        """Capture incoming response and pair with its request."""
        url = response.url
        req_info = self._pending_requests.pop(url, None)

        # Skip data URIs and blob URLs
        if url.startswith(("data:", "blob:")):
            return

        timestamp = req_info["timestamp"] if req_info else datetime.now()
        method = req_info["method"] if req_info else "GET"
        req_headers = req_info.get("request_headers", {}) if req_info else {}
        req_body = req_info.get("request_body") if req_info else None
        start = req_info.get("start_time", time.monotonic()) if req_info else time.monotonic()

        # Get response headers
        resp_headers = {}
        try:
            resp_headers = dict(response.headers)
        except Exception:
            pass

        # Get response body (truncate large responses)
        resp_body = None
        content_type = resp_headers.get("content-type", "")
        if any(t in content_type for t in ["json", "html", "text", "xml"]):
            try:
                body = response.text()
                resp_body = body[:10_000] if len(body) > 10_000 else body
            except Exception:
                pass

        duration = int((time.monotonic() - start) * 1000)

        self._network_log.append(
            NetworkEntry(
                timestamp=timestamp,
                method=method,
                url=url,
                request_headers=req_headers,
                request_body=req_body,
                status=response.status,
                response_headers=resp_headers,
                response_body=resp_body,
                duration_ms=duration,
            )
        )

    def _on_console(self, msg: Any) -> None:
        """Capture console messages."""
        try:
            self._console_log.append(f"[{msg.type}] {msg.text}")
        except Exception:
            pass

    def screenshot(self, page: Any, label: str) -> None:
        """Capture a full-page screenshot."""
        try:
            png_bytes = page.screenshot(full_page=True)
            png_b64 = base64.b64encode(png_bytes).decode()
            viewport = page.viewport_size or {}
            self._screenshots.append(
                Screenshot(
                    label=label,
                    timestamp=datetime.now(),
                    png_base64=png_b64,
                    width=viewport.get("width", 0),
                    height=viewport.get("height", 0),
                )
            )
            self._page_url = page.url
            logger.info("Screenshot captured: %s (%d bytes)", label, len(png_bytes))
        except Exception as e:
            logger.warning("Failed to capture screenshot '%s': %s", label, e)

    def build_record(self, result_json: str = "") -> AuditRecord:
        """Build the final audit record."""
        elapsed = int((time.monotonic() - self._start_time) * 1000)
        return AuditRecord(
            id=self._id,
            queried_at=self._started_at,
            completed_at=datetime.now(),
            source=self._source,
            document_type=self._document_type,
            document_number_masked=AuditRecord.mask_document(self._document_number),
            duration_ms=elapsed,
            result_hash=AuditRecord.hash_result(result_json) if result_json else "",
            screenshots=self._screenshots,
            network_log=self._network_log,
            console_log=self._console_log,
            page_url=self._page_url,
            user_agent=self._user_agent,
        )

    def generate_pdf(self, page: Any, result_json: str = "") -> AuditRecord:
        """Generate a PDF evidence report and return the complete audit record.

        Uses Playwright to render an HTML report and convert it to PDF.
        The page parameter should be a Playwright page (can reuse the query page
        or create a new one).
        """
        record = self.build_record(result_json)

        try:
            html = self._render_html(record, result_json)
            page.set_content(html, wait_until="networkidle")
            pdf_bytes = page.pdf(
                format="A4",
                margin={"top": "20mm", "bottom": "20mm", "left": "15mm", "right": "15mm"},
                print_background=True,
            )
            record.pdf_base64 = base64.b64encode(pdf_bytes).decode()
            logger.info("Evidence PDF generated (%d bytes)", len(pdf_bytes))
        except Exception as e:
            logger.warning("Failed to generate PDF: %s", e)

        return record

    def _render_html(self, record: AuditRecord, result_json: str) -> str:
        """Render the audit record as an HTML evidence report."""
        import json

        screenshots_html = ""
        for ss in record.screenshots:
            screenshots_html += f"""
            <div class="screenshot">
                <h3>{ss.label} — {ss.timestamp.strftime("%Y-%m-%d %H:%M:%S")}</h3>
                <img src="data:image/png;base64,{ss.png_base64}"
                     style="max-width:100%; border:1px solid #ccc;" />
            </div>
            """

        # Format result JSON
        result_formatted = ""
        if result_json:
            try:
                result_formatted = json.dumps(json.loads(result_json), indent=2, ensure_ascii=False)
            except Exception:
                result_formatted = result_json

        # Network log table rows
        network_rows = ""
        for entry in record.network_log[:50]:  # Limit to 50 entries in PDF
            status_class = "ok" if 200 <= entry.status < 400 else "error"
            network_rows += f"""
            <tr>
                <td>{entry.timestamp.strftime("%H:%M:%S.%f")[:-3]}</td>
                <td>{entry.method}</td>
                <td class="url-cell">{_truncate(entry.url, 80)}</td>
                <td class="{status_class}">{entry.status}</td>
                <td>{entry.duration_ms}ms</td>
            </tr>
            """

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Evidence Report — {record.source}</title>
<style>
    body {{ font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 11px;
           color: #333; line-height: 1.5; }}
    h1 {{ color: #1a1a2e; border-bottom: 2px solid #16213e; padding-bottom: 8px; }}
    h2 {{ color: #16213e; margin-top: 24px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
    .header {{ background: #f8f9fa; padding: 16px; border-radius: 8px; margin-bottom: 20px; }}
    .header table {{ width: 100%; border-collapse: collapse; }}
    .header td {{ padding: 4px 12px; }}
    .header td:first-child {{ font-weight: bold; width: 180px; color: #555; }}
    .hash {{ font-family: monospace; font-size: 10px; word-break: break-all; color: #666; }}
    pre {{ background: #f4f4f4; padding: 12px; border-radius: 4px; overflow-x: auto;
           font-size: 10px; border: 1px solid #ddd; }}
    table.network {{ width: 100%; border-collapse: collapse; font-size: 10px; }}
    table.network th {{ background: #16213e; color: white; padding: 6px 8px; text-align: left; }}
    table.network td {{ padding: 4px 8px; border-bottom: 1px solid #eee; }}
    table.network tr:nth-child(even) {{ background: #f9f9f9; }}
    .url-cell {{ word-break: break-all; max-width: 300px; }}
    .ok {{ color: #27ae60; font-weight: bold; }}
    .error {{ color: #e74c3c; font-weight: bold; }}
    .screenshot img {{ border-radius: 4px; margin: 8px 0; }}
    .footer {{ margin-top: 30px; padding-top: 12px; border-top: 1px solid #ddd;
               font-size: 9px; color: #999; text-align: center; }}
    .integrity {{ background: #eaf6ea; padding: 12px; border-radius: 4px;
                  border: 1px solid #c3e6c3; margin: 16px 0; }}
</style>
</head>
<body>

<h1>Evidence Report</h1>

<div class="header">
<table>
    <tr><td>Report ID</td><td><code>{record.id}</code></td></tr>
    <tr><td>Source</td><td>{record.source}</td></tr>
    <tr><td>Document Type</td><td>{record.document_type}</td></tr>
    <tr><td>Document Number</td><td>{record.document_number_masked}</td></tr>
    <tr><td>Query Started</td><td>{record.queried_at.strftime("%Y-%m-%d %H:%M:%S UTC")}</td></tr>
    <tr><td>Query Completed</td><td>{
            record.completed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if record.completed_at else "N/A"
        }</td></tr>
    <tr><td>Duration</td><td>{record.duration_ms} ms</td></tr>
    <tr><td>Final URL</td><td class="url-cell">{record.page_url}</td></tr>
    <tr><td>User Agent</td><td style="font-size:9px">{record.user_agent}</td></tr>
</table>
</div>

<div class="integrity">
    <strong>Integrity Verification</strong><br>
    Result SHA-256: <span class="hash">{record.result_hash}</span>
</div>

<h2>Query Result</h2>
<pre>{result_formatted}</pre>

<h2>Screenshots ({len(record.screenshots)})</h2>
{screenshots_html if screenshots_html else "<p>No screenshots captured.</p>"}

<h2>Network Log ({len(record.network_log)} requests)</h2>
<table class="network">
    <thead>
        <tr><th>Time</th><th>Method</th><th>URL</th><th>Status</th><th>Duration</th></tr>
    </thead>
    <tbody>
        {network_rows or '<tr><td colspan="5">No network activity.</td></tr>'}
    </tbody>
</table>

<div class="footer">
    Generated by OpenQuery Audit &mdash; {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}<br>
    This document serves as evidence of a data query performed against a public government source.
</div>

</body>
</html>"""


def _truncate(s: str, max_len: int) -> str:
    """Truncate a string, adding ellipsis if needed."""
    return s if len(s) <= max_len else s[: max_len - 3] + "..."
