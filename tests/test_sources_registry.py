"""Tests for the source registry — register, get_source, list_sources."""

from __future__ import annotations

import pytest

from openquery import sources as source_registry
from openquery.sources import get_registry_diagnostics, get_source, list_sources, register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta


class TestRegister:
    def test_register_valid_source(self):
        """register() decorator adds a source to the registry."""
        sources = list_sources()
        names = [s.meta().name for s in sources]
        assert "co.simit" in names
        assert "co.runt" in names
        assert "co.pico_y_placa" in names
        assert "mx.repuve" in names
        assert "uy.sucive" in names

    def test_register_rejects_non_basesource(self):
        with pytest.raises(TypeError, match="must be a subclass"):

            @register
            class NotASource:  # type: ignore[type-var]
                pass

    def test_duplicate_source_name_fails_fast(self):
        original_registry = source_registry._REGISTRY
        source_registry._REGISTRY = {}

        @register
        class FirstDuplicate(BaseSource):
            def meta(self) -> SourceMeta:
                return SourceMeta(
                    name="test.duplicate",
                    display_name="First Duplicate",
                    description="Test source",
                    country="US",
                    url="https://example.com/first",
                    supported_inputs=[DocumentType.CUSTOM],
                    requires_browser=False,
                )

            def query(self, input: QueryInput):  # pragma: no cover - never executed
                raise NotImplementedError

        try:
            with pytest.raises(ValueError, match="Duplicate source name 'test.duplicate'"):

                @register
                class SecondDuplicate(BaseSource):
                    def meta(self) -> SourceMeta:
                        return SourceMeta(
                            name="test.duplicate",
                            display_name="Second Duplicate",
                            description="Test source",
                            country="US",
                            url="https://example.com/second",
                            supported_inputs=[DocumentType.CUSTOM],
                            requires_browser=False,
                        )

                    def query(self, input: QueryInput):  # pragma: no cover - never executed
                        raise NotImplementedError
        finally:
            source_registry._REGISTRY = original_registry


class TestGetSource:
    def test_get_existing_source(self):
        src = get_source("co.pico_y_placa")
        assert src.meta().name == "co.pico_y_placa"

    def test_get_unknown_source(self):
        with pytest.raises(KeyError, match="Unknown source"):
            get_source("xx.nonexistent")

    def test_get_source_with_kwargs(self):
        src = get_source("co.vehiculos", timeout=5.0)
        assert src._timeout == 5.0

    def test_error_lists_available_sources(self):
        with pytest.raises(KeyError, match="co.simit"):
            get_source("xx.nope")


class TestListSources:
    def test_returns_many_sources(self):
        sources = list_sources()
        assert len(sources) >= 100

    def test_returns_instances(self):
        sources = list_sources()
        for src in sources:
            assert isinstance(src, BaseSource)
            assert src.meta().name
            assert src.meta().country in {
                "AR",
                "BO",
                "BR",
                "CL",
                "CO",
                "CR",
                "DO",
                "EC",
                "GT",
                "HN",
                "INTL",
                "MX",
                "PA",
                "PE",
                "PY",
                "SV",
                "US",
                "UY",
            }

    def test_all_sources_have_supported_inputs(self):
        for src in list_sources():
            assert len(src.meta().supported_inputs) >= 1

    def test_no_duplicate_names(self):
        names = [s.meta().name for s in list_sources()]
        assert len(names) == len(set(names))


class TestEnsureLoaded:
    def test_all_expected_sources_loaded(self):
        expected = [
            "co.simit",
            "co.runt",
            "mx.repuve",
            "br.cnpj",
            "pe.sunat_ruc",
            "us.nhtsa_vin",
            "uy.sucive",
        ]
        names = [s.meta().name for s in list_sources()]
        for name in expected:
            assert name in names, f"Missing source: {name}"

    def test_registry_diagnostics_shape(self):
        diagnostics = get_registry_diagnostics()

        assert diagnostics["loaded"] is True
        assert diagnostics["registered_count"] >= 100
        assert diagnostics["loaded_modules"]
        assert isinstance(diagnostics["import_failures"], dict)
