"""Unit tests for Procuraduria source."""

from __future__ import annotations

import pytest

from openquery.models.co.procuraduria import ProcuraduriaResult
from openquery.sources.co.procuraduria import ProcuraduriaSource


class TestProcuraduriaResult:
    def test_default_no_records(self):
        r = ProcuraduriaResult(cedula="12345678")
        assert r.tiene_antecedentes is False
        assert r.mensaje == ""

    def test_round_trip_json(self):
        r = ProcuraduriaResult(
            cedula="12345678",
            tiene_antecedentes=False,
            mensaje="No registra antecedentes vigentes",
        )
        restored = ProcuraduriaResult.model_validate_json(r.model_dump_json())
        assert restored.cedula == "12345678"
        assert restored.tiene_antecedentes is False


class TestCaptchaSolver:
    def test_multiply(self):
        assert ProcuraduriaSource._solve_captcha("¿ Cuanto es 3 X 3 ?") == "9"

    def test_multiply_lowercase(self):
        assert ProcuraduriaSource._solve_captcha("¿ Cuanto es 7 x 8 ?") == "56"

    def test_multiply_asterisk(self):
        assert ProcuraduriaSource._solve_captcha("¿ Cuanto es 5 * 4 ?") == "20"

    def test_addition(self):
        assert ProcuraduriaSource._solve_captcha("¿ Cuanto es 5 + 3 ?") == "8"

    def test_subtraction(self):
        assert ProcuraduriaSource._solve_captcha("¿ Cuanto es 9 - 2 ?") == "7"

    def test_name_based_captcha(self):
        result = ProcuraduriaSource._solve_captcha(
            "¿Escriba las dos primeras letras del primer nombre?",
            nombre="DAVID",
        )
        assert result == "DA"

    def test_name_based_with_full_name(self):
        result = ProcuraduriaSource._solve_captcha(
            "¿Escriba las dos primeras letras del primer nombre?",
            nombre="MARIA FERNANDA",
        )
        assert result == "MA"

    def test_invalid_without_llm_raises(self):
        """Without LLM API keys, unsolvable captcha should raise."""
        import os

        from openquery.exceptions import SourceError

        # Temporarily clear API keys
        old_anthropic = os.environ.pop("ANTHROPIC_API_KEY", None)
        old_openai = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with pytest.raises(SourceError, match="Cannot solve"):
                ProcuraduriaSource._solve_captcha("What is the meaning of life?")
        finally:
            if old_anthropic:
                os.environ["ANTHROPIC_API_KEY"] = old_anthropic
            if old_openai:
                os.environ["OPENAI_API_KEY"] = old_openai


class TestProcuraduriaSourceMeta:
    def test_meta(self):
        source = ProcuraduriaSource()
        meta = source.meta()
        assert meta.name == "co.procuraduria"
        assert meta.country == "CO"
        assert meta.requires_captcha is True
