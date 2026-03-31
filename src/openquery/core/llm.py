"""LLM-based question answering for knowledge captchas.

Provides multiple backends with automatic fallback:
- OllamaQA: Local inference via Ollama HTTP API (free, no API key needed)
- HuggingFaceQA: HuggingFace Inference API (free tier, needs HF_TOKEN)
- AnthropicQA: Anthropic API (paid, needs ANTHROPIC_API_KEY)
- OpenAIQA: OpenAI API (paid, needs OPENAI_API_KEY)
- ChainedQA: Try backends in order, first success wins
"""

from __future__ import annotations

import logging
import os
import re
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Answer this question in one or two words only, no punctuation, no explanation. "
    "If it says 'sin tilde' omit accents. Question: {question}"
)


def _clean_answer(text: str) -> str:
    """Normalize an LLM answer: lowercase, strip punctuation."""
    text = text.strip().lower()
    text = re.sub(r"[.!?,;:\"'()]", "", text)
    return text.strip()


class QASolver(ABC):
    """Abstract question-answering solver for knowledge-based captchas."""

    @abstractmethod
    def answer(self, question: str) -> str:
        """Answer a knowledge question.

        Args:
            question: The captcha question text.

        Returns:
            Short text answer (1-2 words).

        Raises:
            QAError: If answering fails.
        """


class QAError(Exception):
    """Raised when a QA solver cannot answer a question."""

    def __init__(self, solver: str, detail: str) -> None:
        self.solver = solver
        self.detail = detail
        super().__init__(f"[{solver}] {detail}")


class OllamaQA(QASolver):
    """Answer questions using a local Ollama instance.

    Requires Ollama running locally. Install: https://ollama.com
    Then pull a model: ollama pull llama3.2:1b

    Zero Python dependencies beyond httpx (already a core dep).
    """

    def __init__(
        self,
        model: str = "llama3.2:1b",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self._model = model
        self._base_url = base_url

    def answer(self, question: str) -> str:
        import httpx

        prompt = SYSTEM_PROMPT.format(question=question)

        try:
            resp = httpx.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=httpx.Timeout(connect=2.0, read=15.0, write=5.0, pool=5.0),
            )
            resp.raise_for_status()
            data = resp.json()
            answer = _clean_answer(data.get("response", ""))
            if not answer:
                raise QAError("ollama", "Empty response from Ollama")
            logger.info("Ollama (%s) answered: '%s'", self._model, answer)
            return answer
        except httpx.ConnectError:
            raise QAError(
                "ollama",
                f"Cannot connect to Ollama at {self._base_url}. "
                "Is Ollama running? Install: https://ollama.com",
            )
        except httpx.HTTPStatusError as e:
            msg = f"Ollama HTTP {e.response.status_code}: {e.response.text[:200]}"
            raise QAError("ollama", msg)
        except QAError:
            raise
        except Exception as e:
            raise QAError("ollama", f"Ollama failed: {e}") from e


class HuggingFaceQA(QASolver):
    """Answer questions using HuggingFace Inference API (free tier).

    Requires HF_TOKEN environment variable.
    Uses text-generation models hosted on HuggingFace.
    """

    def __init__(self, model: str = "meta-llama/Llama-3.2-1B-Instruct") -> None:
        self._model = model
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        token = os.environ.get("HF_TOKEN", "")
        if not token:
            raise QAError("hf_qa", "HF_TOKEN env var required for HuggingFace Inference API")

        try:
            from huggingface_hub import InferenceClient
        except ImportError as e:
            raise QAError(
                "hf_qa",
                "huggingface_hub is required. Install: pip install 'openquery[huggingface]'",
            ) from e

        self._client = InferenceClient(token=token)
        return self._client

    def answer(self, question: str) -> str:
        client = self._get_client()
        prompt = SYSTEM_PROMPT.format(question=question)

        try:
            response = client.text_generation(
                prompt,
                model=self._model,
                max_new_tokens=20,
            )
            answer = _clean_answer(str(response))
            if not answer:
                raise QAError("hf_qa", "Empty response from HuggingFace")
            logger.info("HuggingFace QA answered: '%s'", answer)
            return answer
        except QAError:
            raise
        except Exception as e:
            raise QAError("hf_qa", f"HuggingFace QA failed: {e}") from e


class AnthropicQA(QASolver):
    """Answer questions using the Anthropic API.

    Requires ANTHROPIC_API_KEY environment variable.
    Uses claude-haiku for fast, cheap responses.
    """

    def answer(self, question: str) -> str:
        import httpx

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise QAError("anthropic", "ANTHROPIC_API_KEY env var not set")

        prompt = SYSTEM_PROMPT.format(question=question)

        try:
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 20,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=10.0,
            )
            data = resp.json()
            answer = _clean_answer(data["content"][0]["text"])
            if not answer:
                raise QAError("anthropic", "Empty response from Anthropic")
            logger.info("Anthropic answered: '%s'", answer)
            return answer
        except QAError:
            raise
        except Exception as e:
            raise QAError("anthropic", f"Anthropic API failed: {e}") from e


class OpenAIQA(QASolver):
    """Answer questions using the OpenAI API.

    Requires OPENAI_API_KEY environment variable.
    Uses gpt-4o-mini for fast, cheap responses.
    """

    def answer(self, question: str) -> str:
        import httpx

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise QAError("openai", "OPENAI_API_KEY env var not set")

        prompt = SYSTEM_PROMPT.format(question=question)

        try:
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": 20,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=10.0,
            )
            data = resp.json()
            answer = _clean_answer(data["choices"][0]["message"]["content"])
            if not answer:
                raise QAError("openai", "Empty response from OpenAI")
            logger.info("OpenAI answered: '%s'", answer)
            return answer
        except QAError:
            raise
        except Exception as e:
            raise QAError("openai", f"OpenAI API failed: {e}") from e


class ChainedQA(QASolver):
    """Try multiple QA backends in order. First success wins."""

    def __init__(self, solvers: list[QASolver]) -> None:
        self._solvers = solvers

    def answer(self, question: str) -> str:
        last_error: Exception | None = None
        for solver in self._solvers:
            try:
                return solver.answer(question)
            except (QAError, Exception) as e:
                logger.warning("QA solver %s failed: %s", type(solver).__name__, e)
                last_error = e

        raise QAError(
            "chained",
            f"All QA solvers failed. Last: {last_error}. "
            "Options: run Ollama locally, set HF_TOKEN, ANTHROPIC_API_KEY, or OPENAI_API_KEY.",
        )


def build_qa_chain() -> ChainedQA:
    """Build a QA solver chain based on available backends.

    Order: Ollama (free/local) → HuggingFace (free/cloud) → Anthropic (paid) → OpenAI (paid)
    """
    solvers: list[QASolver] = []

    # Free: Ollama (local, always try — fail-fast 2s timeout if not running)
    solvers.append(OllamaQA())

    # Free: HuggingFace Inference API
    if os.environ.get("HF_TOKEN"):
        solvers.append(HuggingFaceQA())

    # Paid: Anthropic
    if os.environ.get("ANTHROPIC_API_KEY"):
        solvers.append(AnthropicQA())

    # Paid: OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        solvers.append(OpenAIQA())

    return ChainedQA(solvers)
