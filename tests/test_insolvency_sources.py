"""Tests for insolvency sources (co.supersociedades, cl.superir)."""

from __future__ import annotations

from openquery.sources.base import DocumentType


class TestSupersociedadesMeta:
    """Test co.supersociedades source metadata."""

    def test_meta_fields(self):
        from openquery.sources.co.supersociedades import SupersociedadesSource

        src = SupersociedadesSource()
        meta = src.meta()
        assert meta.name == "co.supersociedades"
        assert meta.country == "CO"
        assert DocumentType.NIT in meta.supported_inputs
        assert DocumentType.CEDULA in meta.supported_inputs
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True

    def test_supports_nit(self):
        from openquery.sources.co.supersociedades import SupersociedadesSource

        src = SupersociedadesSource()
        assert src.supports(DocumentType.NIT) is True
        assert src.supports(DocumentType.PLATE) is False


class TestSupersociedadesModel:
    """Test SupersociedadesResult model."""

    def test_default_values(self):
        from openquery.models.co.supersociedades import SupersociedadesResult

        result = SupersociedadesResult()
        assert result.documento == ""
        assert result.procesos == []
        assert result.total_procesos == 0
        assert result.tiene_proceso_insolvencia is False

    def test_with_proceedings(self):
        from openquery.models.co.supersociedades import (
            InsolvencyProceeding,
            SupersociedadesResult,
        )

        result = SupersociedadesResult(
            documento="900123456",
            razon_social="EMPRESA TEST SAS",
            nit="900123456-1",
            procesos=[
                InsolvencyProceeding(
                    tipo_proceso="Reorganizacion",
                    estado="En tramite",
                    fecha_admision="2024-01-15",
                )
            ],
            total_procesos=1,
            tiene_proceso_insolvencia=True,
        )
        assert result.total_procesos == 1
        assert result.procesos[0].tipo_proceso == "Reorganizacion"
        data = result.model_dump(mode="json")
        assert "audit" not in data  # excluded


class TestSuperirMeta:
    """Test cl.superir source metadata."""

    def test_meta_fields(self):
        from openquery.sources.cl.superir import SuperirSource

        src = SuperirSource()
        meta = src.meta()
        assert meta.name == "cl.superir"
        assert meta.country == "CL"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is True

    def test_supports_custom(self):
        from openquery.sources.cl.superir import SuperirSource

        src = SuperirSource()
        assert src.supports(DocumentType.CUSTOM) is True
        assert src.supports(DocumentType.CEDULA) is False


class TestSuperirModel:
    """Test SuperirResult model."""

    def test_default_values(self):
        from openquery.models.cl.superir import SuperirResult

        result = SuperirResult()
        assert result.rut == ""
        assert result.procedimientos == []
        assert result.total_procedimientos == 0
        assert result.tiene_procedimiento is False

    def test_with_proceedings(self):
        from openquery.models.cl.superir import BankruptcyProceeding, SuperirResult

        result = SuperirResult(
            rut="12.345.678-9",
            nombre="EMPRESA TEST LTDA",
            procedimientos=[
                BankruptcyProceeding(
                    tipo_procedimiento="Liquidacion",
                    estado="En tramite",
                    tribunal="1er Juzgado Civil",
                )
            ],
            total_procedimientos=1,
            tiene_procedimiento=True,
        )
        assert result.total_procedimientos == 1
        data = result.model_dump(mode="json")
        assert "audit" not in data


class TestSourceRegistration:
    """Test that new sources are registered in the registry."""

    def test_supersociedades_registered(self):
        from openquery.sources import get_source

        src = get_source("co.supersociedades")
        assert src.meta().name == "co.supersociedades"

    def test_superir_registered(self):
        from openquery.sources import get_source

        src = get_source("cl.superir")
        assert src.meta().name == "cl.superir"
