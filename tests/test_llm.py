"""Unit tests for LLM-based QA solvers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from openquery.core.llm import (
    AnthropicQA,
    ChainedQA,
    HuggingFaceQA,
    OllamaQA,
    OpenAIQA,
    QAError,
    QASolver,
    _clean_answer,
    build_qa_chain,
)

# -- Test helpers --

class FailingQA(QASolver):
    """Always fails."""

    def answer(self, question: str) -> str:
        raise QAError("test", "always fails")


class FixedQA(QASolver):
    """Always returns a fixed value."""

    def __init__(self, value: str) -> None:
        self._value = value

    def answer(self, question: str) -> str:
        return self._value


# -- Unit tests --

class TestCleanAnswer:
    def test_basic(self):
        assert _clean_answer("Medellin") == "medellin"

    def test_strip_punctuation(self):
        assert _clean_answer("Medellin.") == "medellin"
        assert _clean_answer("Medellin!") == "medellin"
        assert _clean_answer("(Medellin)") == "medellin"

    def test_strip_whitespace(self):
        assert _clean_answer("  medellin  ") == "medellin"

    def test_empty(self):
        assert _clean_answer("") == ""


class TestChainedQA:
    def test_first_solver_wins(self):
        chain = ChainedQA([FixedQA("medellin"), FixedQA("bogota")])
        assert chain.answer("Capital de Antioquia?") == "medellin"

    def test_fallback_on_failure(self):
        chain = ChainedQA([FailingQA(), FixedQA("medellin")])
        assert chain.answer("Capital de Antioquia?") == "medellin"

    def test_all_fail_raises(self):
        chain = ChainedQA([FailingQA(), FailingQA()])
        with pytest.raises(QAError, match="All QA solvers failed"):
            chain.answer("What?")

    def test_error_message_mentions_options(self):
        chain = ChainedQA([FailingQA()])
        with pytest.raises(QAError, match="Ollama|HF_TOKEN|ANTHROPIC_API_KEY|OPENAI_API_KEY"):
            chain.answer("What?")


class TestOllamaQA:
    def test_successful_answer(self):
        solver = OllamaQA()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "Medellin"}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            result = solver.answer("Capital de Antioquia?")
            assert result == "medellin"
            call_args = mock_post.call_args
            assert "localhost:11434" in call_args[0][0]
            body = call_args[1]["json"]
            assert body["model"] == "llama3.2:1b"
            assert "Capital de Antioquia?" in body["prompt"]
            assert body["stream"] is False

    def test_connection_refused(self):
        import httpx

        with patch("httpx.post", side_effect=httpx.ConnectError("Connection refused")):
            solver = OllamaQA()
            with pytest.raises(QAError, match="Cannot connect to Ollama"):
                solver.answer("Question?")

    def test_empty_response(self):
        solver = OllamaQA()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": ""}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(QAError, match="Empty response"):
                solver.answer("Question?")

    def test_custom_model(self):
        solver = OllamaQA(model="phi3:mini")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "answer"}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            solver.answer("Q?")
            body = mock_post.call_args[1]["json"]
            assert body["model"] == "phi3:mini"

    def test_custom_base_url(self):
        solver = OllamaQA(base_url="http://myserver:11434")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "answer"}
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            solver.answer("Q?")
            assert "myserver:11434" in mock_post.call_args[0][0]


class TestHuggingFaceQA:
    def test_missing_token_raises(self):
        import os

        old = os.environ.pop("HF_TOKEN", None)
        try:
            solver = HuggingFaceQA()
            with pytest.raises(QAError, match="HF_TOKEN"):
                solver.answer("Question?")
        finally:
            if old:
                os.environ["HF_TOKEN"] = old

    def test_successful_answer(self):
        import os

        os.environ["HF_TOKEN"] = "test-token"
        try:
            solver = HuggingFaceQA()
            mock_client = MagicMock()
            mock_client.text_generation.return_value = "Medellin"

            with patch("openquery.core.llm.HuggingFaceQA._get_client", return_value=mock_client):
                result = solver.answer("Capital de Antioquia?")
                assert result == "medellin"
        finally:
            os.environ.pop("HF_TOKEN", None)


class TestAnthropicQA:
    def test_missing_key_raises(self):
        import os

        old = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            solver = AnthropicQA()
            with pytest.raises(QAError, match="ANTHROPIC_API_KEY"):
                solver.answer("Question?")
        finally:
            if old:
                os.environ["ANTHROPIC_API_KEY"] = old

    def test_successful_answer(self):
        import os

        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        try:
            solver = AnthropicQA()
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "content": [{"text": "Medellin"}],
            }

            with patch("httpx.post", return_value=mock_resp):
                result = solver.answer("Capital de Antioquia?")
                assert result == "medellin"
        finally:
            os.environ.pop("ANTHROPIC_API_KEY", None)


class TestOpenAIQA:
    def test_missing_key_raises(self):
        import os

        old = os.environ.pop("OPENAI_API_KEY", None)
        try:
            solver = OpenAIQA()
            with pytest.raises(QAError, match="OPENAI_API_KEY"):
                solver.answer("Question?")
        finally:
            if old:
                os.environ["OPENAI_API_KEY"] = old

    def test_successful_answer(self):
        import os

        os.environ["OPENAI_API_KEY"] = "test-key"
        try:
            solver = OpenAIQA()
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "Medellin"}}],
            }

            with patch("httpx.post", return_value=mock_resp):
                result = solver.answer("Capital de Antioquia?")
                assert result == "medellin"
        finally:
            os.environ.pop("OPENAI_API_KEY", None)


class TestBuildQAChain:
    def test_always_includes_ollama(self):
        import os

        # Clear all keys
        old = {}
        for key in ("HF_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
            old[key] = os.environ.pop(key, None)
        try:
            chain = build_qa_chain()
            # Should have at least Ollama
            assert len(chain._solvers) >= 1
            assert isinstance(chain._solvers[0], OllamaQA)
        finally:
            for key, val in old.items():
                if val:
                    os.environ[key] = val

    def test_includes_hf_when_token_set(self):
        import os

        old = {}
        for key in ("HF_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
            old[key] = os.environ.pop(key, None)
        os.environ["HF_TOKEN"] = "test"
        try:
            chain = build_qa_chain()
            types = [type(s).__name__ for s in chain._solvers]
            assert "HuggingFaceQA" in types
        finally:
            os.environ.pop("HF_TOKEN", None)
            for key, val in old.items():
                if val:
                    os.environ[key] = val

    def test_includes_all_when_all_keys_set(self):
        import os

        old = {}
        for key in ("HF_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
            old[key] = os.environ.pop(key, None)
        os.environ["HF_TOKEN"] = "test"
        os.environ["ANTHROPIC_API_KEY"] = "test"
        os.environ["OPENAI_API_KEY"] = "test"
        try:
            chain = build_qa_chain()
            types = [type(s).__name__ for s in chain._solvers]
            assert "OllamaQA" in types
            assert "HuggingFaceQA" in types
            assert "AnthropicQA" in types
            assert "OpenAIQA" in types
        finally:
            for key in ("HF_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
                os.environ.pop(key, None)
            for key, val in old.items():
                if val:
                    os.environ[key] = val
