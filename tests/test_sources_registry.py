"""Tests for the source registry — register, get_source, list_sources."""

from __future__ import annotations

import pytest

from openquery.sources import get_source, list_sources, register
from openquery.sources.base import BaseSource


class TestRegister:
    def test_register_valid_source(self):
        """register() decorator adds a source to the registry."""
        # All 13 sources should be registered by now
        sources = list_sources()
        names = [s.meta().name for s in sources]
        assert "co.simit" in names
        assert "co.runt" in names
        assert "co.pico_y_placa" in names

    def test_register_rejects_non_basesource(self):
        with pytest.raises(TypeError, match="must be a subclass"):

            @register
            class NotASource:  # type: ignore[type-var]
                pass


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
    def test_returns_all_13(self):
        sources = list_sources()
        assert len(sources) >= 13

    def test_returns_instances(self):
        sources = list_sources()
        for src in sources:
            assert isinstance(src, BaseSource)
            assert src.meta().name
            assert src.meta().country == "CO"

    def test_all_sources_have_supported_inputs(self):
        for src in list_sources():
            assert len(src.meta().supported_inputs) >= 1

    def test_no_duplicate_names(self):
        names = [s.meta().name for s in list_sources()]
        assert len(names) == len(set(names))


class TestEnsureLoaded:
    def test_all_expected_sources_loaded(self):
        expected = [
            "co.simit", "co.runt", "co.procuraduria", "co.policia",
            "co.adres", "co.pico_y_placa", "co.peajes", "co.combustible",
            "co.estaciones_ev", "co.siniestralidad", "co.vehiculos",
            "co.fasecolda", "co.recalls",
        ]
        sources = list_sources()
        names = [s.meta().name for s in sources]
        for name in expected:
            assert name in names, f"Missing source: {name}"
