"""Unit tests for the audit/evidence capture system."""

from __future__ import annotations

import base64
import hashlib
from unittest.mock import MagicMock

from openquery.core.audit import AuditCollector
from openquery.models.audit import AuditRecord, NetworkEntry, Screenshot


class TestAuditRecord:
    def test_mask_document_long(self):
        assert AuditRecord.mask_document("12345678") == "****5678"

    def test_mask_document_short(self):
        assert AuditRecord.mask_document("123") == "****"

    def test_mask_document_exact_four(self):
        assert AuditRecord.mask_document("1234") == "****"

    def test_mask_document_five(self):
        assert AuditRecord.mask_document("12345") == "*2345"

    def test_hash_result(self):
        data = '{"cedula": "12345678"}'
        expected = hashlib.sha256(data.encode()).hexdigest()
        assert AuditRecord.hash_result(data) == expected

    def test_default_values(self):
        record = AuditRecord()
        assert record.id == ""
        assert record.screenshots == []
        assert record.network_log == []
        assert record.console_log == []
        assert record.pdf_base64 == ""

    def test_round_trip_json(self):
        record = AuditRecord(
            id="test-uuid",
            source="co.simit",
            document_type="cedula",
            document_number_masked="****5678",
            duration_ms=1234,
            result_hash="abc123",
        )
        restored = AuditRecord.model_validate_json(record.model_dump_json())
        assert restored.id == "test-uuid"
        assert restored.source == "co.simit"
        assert restored.duration_ms == 1234


class TestNetworkEntry:
    def test_default_values(self):
        entry = NetworkEntry()
        assert entry.method == "GET"
        assert entry.status == 0
        assert entry.url == ""

    def test_with_values(self):
        entry = NetworkEntry(
            method="POST",
            url="https://example.com/api",
            status=200,
            duration_ms=150,
            request_body='{"key": "value"}',
            response_body='{"result": "ok"}',
        )
        assert entry.method == "POST"
        assert entry.status == 200


class TestScreenshot:
    def test_default_values(self):
        ss = Screenshot()
        assert ss.label == ""
        assert ss.png_base64 == ""

    def test_with_values(self):
        ss = Screenshot(
            label="result",
            png_base64="iVBORw0KGgo=",
            width=1280,
            height=720,
        )
        assert ss.label == "result"
        assert ss.width == 1280


class TestAuditCollector:
    def test_init(self):
        collector = AuditCollector("co.simit", "cedula", "12345678")
        assert collector._source == "co.simit"
        assert collector._document_type == "cedula"
        assert collector._document_number == "12345678"
        assert len(collector._id) == 36  # UUID format

    def test_attach(self):
        collector = AuditCollector("co.simit", "cedula", "12345678")
        page = MagicMock()
        page.evaluate.return_value = "Mozilla/5.0"
        collector.attach(page)
        assert collector._user_agent == "Mozilla/5.0"
        assert page.on.call_count == 3  # request, response, console

    def test_screenshot(self):
        collector = AuditCollector("co.simit", "cedula", "12345678")
        page = MagicMock()
        # Return a minimal PNG (1x1 transparent pixel)
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        page.screenshot.return_value = png_bytes
        page.url = "https://example.com"
        page.viewport_size = {"width": 1280, "height": 720}

        collector.screenshot(page, "test_label")

        assert len(collector._screenshots) == 1
        assert collector._screenshots[0].label == "test_label"
        assert collector._screenshots[0].width == 1280
        assert len(collector._screenshots[0].png_base64) > 0

    def test_build_record(self):
        collector = AuditCollector("co.simit", "cedula", "12345678")
        result_json = '{"cedula": "12345678", "paz_y_salvo": true}'
        record = collector.build_record(result_json)

        assert record.source == "co.simit"
        assert record.document_number_masked == "****5678"
        assert record.result_hash == hashlib.sha256(result_json.encode()).hexdigest()
        assert record.duration_ms >= 0

    def test_build_record_no_result(self):
        collector = AuditCollector("co.runt", "vin", "ABC123")
        record = collector.build_record()
        assert record.result_hash == ""

    def test_on_request(self):
        collector = AuditCollector("co.simit", "cedula", "12345678")
        request = MagicMock()
        request.url = "https://example.com/api"
        request.method = "POST"
        request.headers = {"content-type": "application/json"}
        request.post_data = '{"key": "value"}'

        collector._on_request(request)
        assert "https://example.com/api" in collector._pending_requests

    def test_on_response(self):
        collector = AuditCollector("co.simit", "cedula", "12345678")

        # Simulate request first
        request = MagicMock()
        request.url = "https://example.com/api"
        request.method = "POST"
        request.headers = {"content-type": "application/json"}
        request.post_data = None
        collector._on_request(request)

        # Then response
        response = MagicMock()
        response.url = "https://example.com/api"
        response.status = 200
        response.headers = {"content-type": "application/json"}
        response.text.return_value = '{"ok": true}'

        collector._on_response(response)
        assert len(collector._network_log) == 1
        assert collector._network_log[0].status == 200
        assert collector._network_log[0].method == "POST"

    def test_on_console(self):
        collector = AuditCollector("co.simit", "cedula", "12345678")
        msg = MagicMock()
        msg.type = "log"
        msg.text = "Hello world"

        collector._on_console(msg)
        assert len(collector._console_log) == 1
        assert "[log] Hello world" in collector._console_log[0]

    def test_skip_data_urls(self):
        collector = AuditCollector("co.simit", "cedula", "12345678")
        response = MagicMock()
        response.url = "data:image/png;base64,abc"
        response.status = 200

        collector._on_response(response)
        assert len(collector._network_log) == 0

    def test_generate_pdf(self):
        collector = AuditCollector("co.simit", "cedula", "12345678")
        page = MagicMock()
        page.pdf.return_value = b"%PDF-1.4 fake pdf content"

        result_json = '{"cedula": "12345678"}'
        record = collector.generate_pdf(page, result_json)

        assert record.pdf_base64 != ""
        assert record.source == "co.simit"
        page.set_content.assert_called_once()
        page.pdf.assert_called_once()

    def test_render_html_contains_key_elements(self):
        collector = AuditCollector("co.simit", "cedula", "12345678")
        record = collector.build_record('{"test": true}')
        html = collector._render_html(record, '{"test": true}')

        assert "Evidence Report" in html
        assert "co.simit" in html
        assert "****5678" in html
        assert "SHA-256" in html
        assert "Network Log" in html


class TestAuditInQueryInput:
    def test_audit_default_false(self):
        from openquery.sources.base import DocumentType, QueryInput
        qi = QueryInput(document_type=DocumentType.CEDULA, document_number="12345678")
        assert qi.audit is False

    def test_audit_true(self):
        from openquery.sources.base import DocumentType, QueryInput
        qi = QueryInput(
            document_type=DocumentType.CEDULA,
            document_number="12345678",
            audit=True,
        )
        assert qi.audit is True


class TestAuditFieldInModels:
    def test_simit_audit_excluded_from_dump(self):
        from openquery.models.co.simit import SimitResult
        result = SimitResult(cedula="12345678")
        data = result.model_dump()
        assert "audit" not in data

    def test_procuraduria_audit_excluded_from_dump(self):
        from openquery.models.co.procuraduria import ProcuraduriaResult
        result = ProcuraduriaResult(cedula="12345678")
        data = result.model_dump()
        assert "audit" not in data

    def test_policia_audit_excluded_from_dump(self):
        from openquery.models.co.policia import PoliciaResult
        result = PoliciaResult(cedula="12345678")
        data = result.model_dump()
        assert "audit" not in data

    def test_adres_audit_excluded_from_dump(self):
        from openquery.models.co.adres import AdresResult
        result = AdresResult(cedula="12345678")
        data = result.model_dump()
        assert "audit" not in data

    def test_runt_audit_excluded_from_dump(self):
        from openquery.models.co.runt import RuntResult
        result = RuntResult()
        data = result.model_dump()
        assert "audit" not in data

    def test_audit_field_assignable(self):
        from openquery.models.co.simit import SimitResult
        record = AuditRecord(id="test", source="co.simit")
        result = SimitResult(cedula="12345678")
        result.audit = record
        assert result.audit.id == "test"
        # But excluded from serialization
        assert "audit" not in result.model_dump()
