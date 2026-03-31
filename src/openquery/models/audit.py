"""Audit and evidence capture models."""

from __future__ import annotations

import hashlib
from datetime import datetime

from pydantic import BaseModel, Field


class NetworkEntry(BaseModel):
    """A single HTTP request/response pair captured during a query."""

    timestamp: datetime = Field(default_factory=datetime.now)
    method: str = "GET"
    url: str = ""
    request_headers: dict[str, str] = Field(default_factory=dict)
    request_body: str | None = None
    status: int = 0
    response_headers: dict[str, str] = Field(default_factory=dict)
    response_body: str | None = None
    duration_ms: int = 0


class Screenshot(BaseModel):
    """A screenshot captured during a query."""

    label: str = ""  # e.g., "pre_query", "result", "certificate"
    timestamp: datetime = Field(default_factory=datetime.now)
    png_base64: str = ""  # base64-encoded PNG
    width: int = 0
    height: int = 0


class AuditRecord(BaseModel):
    """Complete audit/evidence package for a single query."""

    id: str = ""  # UUID
    queried_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    source: str = ""
    document_type: str = ""
    document_number_masked: str = ""  # "****5678"
    duration_ms: int = 0
    result_hash: str = ""  # SHA-256 of result JSON
    screenshots: list[Screenshot] = Field(default_factory=list)
    network_log: list[NetworkEntry] = Field(default_factory=list)
    console_log: list[str] = Field(default_factory=list)
    page_url: str = ""  # final URL after query
    user_agent: str = ""
    pdf_base64: str = ""  # base64-encoded evidence PDF

    @staticmethod
    def mask_document(doc_number: str) -> str:
        """Mask a document number for privacy, keeping last 4 digits."""
        if len(doc_number) <= 4:
            return "****"
        return "*" * (len(doc_number) - 4) + doc_number[-4:]

    @staticmethod
    def hash_result(result_json: str) -> str:
        """SHA-256 hash of the result JSON for integrity verification."""
        return hashlib.sha256(result_json.encode()).hexdigest()
