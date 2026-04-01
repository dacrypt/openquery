"""Tests for sources.base — DocumentType, QueryInput, SourceMeta, BaseSource."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta


class TestDocumentType:
    def test_all_values(self):
        assert DocumentType.CEDULA == "cedula"
        assert DocumentType.NIT == "nit"
        assert DocumentType.PASSPORT == "pasaporte"
        assert DocumentType.PLATE == "placa"
        assert DocumentType.VIN == "vin"
        assert DocumentType.SSN == "ssn"
        assert DocumentType.CUSTOM == "custom"

    def test_is_string(self):
        assert isinstance(DocumentType.CEDULA, str)

    def test_from_string(self):
        assert DocumentType("cedula") == DocumentType.CEDULA
        assert DocumentType("placa") == DocumentType.PLATE

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            DocumentType("invalid_type")


class TestQueryInput:
    def test_basic_creation(self):
        qi = QueryInput(document_type=DocumentType.CEDULA, document_number="123456")
        assert qi.document_type == DocumentType.CEDULA
        assert qi.document_number == "123456"
        assert qi.extra == {}
        assert qi.audit is False

    def test_with_extra(self):
        qi = QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number="",
            extra={"ciudad": "Bogota", "limit": 100},
        )
        assert qi.extra["ciudad"] == "Bogota"
        assert qi.extra["limit"] == 100

    def test_audit_flag(self):
        qi = QueryInput(
            document_type=DocumentType.PLATE,
            document_number="ABC123",
            audit=True,
        )
        assert qi.audit is True

    def test_json_roundtrip(self):
        qi = QueryInput(
            document_type=DocumentType.VIN,
            document_number="5YJ3E1EA1PF000001",
            extra={"test": True},
        )
        data = qi.model_dump()
        qi2 = QueryInput(**data)
        assert qi2.document_type == qi.document_type
        assert qi2.document_number == qi.document_number
        assert qi2.extra == qi.extra


class TestSourceMeta:
    def test_required_fields(self):
        meta = SourceMeta(
            name="co.test",
            display_name="Test Source",
            description="A test source",
            country="CO",
            url="https://example.com",
            supported_inputs=[DocumentType.CEDULA],
        )
        assert meta.name == "co.test"
        assert meta.country == "CO"
        assert meta.requires_captcha is False
        assert meta.requires_browser is True
        assert meta.rate_limit_rpm == 10

    def test_custom_options(self):
        meta = SourceMeta(
            name="co.api",
            display_name="API Source",
            description="No browser needed",
            country="CO",
            url="https://api.example.com",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=60,
        )
        assert meta.requires_browser is False
        assert meta.rate_limit_rpm == 60

    def test_multiple_supported_inputs(self):
        meta = SourceMeta(
            name="co.multi",
            display_name="Multi",
            description="Supports multiple inputs",
            country="CO",
            url="https://example.com",
            supported_inputs=[DocumentType.CEDULA, DocumentType.PLATE, DocumentType.VIN],
        )
        assert len(meta.supported_inputs) == 3


class TestBaseSource:
    def test_supports_method(self):
        class TestSource(BaseSource):
            def meta(self) -> SourceMeta:
                return SourceMeta(
                    name="test",
                    display_name="Test",
                    description="Test",
                    country="CO",
                    url="https://test.com",
                    supported_inputs=[DocumentType.CEDULA, DocumentType.PLATE],
                )

            def query(self, input: QueryInput) -> BaseModel:
                return BaseModel()

        src = TestSource()
        assert src.supports(DocumentType.CEDULA) is True
        assert src.supports(DocumentType.PLATE) is True
        assert src.supports(DocumentType.VIN) is False
        assert src.supports(DocumentType.CUSTOM) is False

    def test_abstract_not_instantiable(self):
        with pytest.raises(TypeError):
            BaseSource()  # type: ignore[abstract]
