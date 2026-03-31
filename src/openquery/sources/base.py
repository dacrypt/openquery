"""Base source abstraction.

Every data source (SIMIT, RUNT, NHTSA, etc.) implements BaseSource.
Sources are self-describing via SourceMeta.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    """Types of identifiers that can be used to query sources."""

    CEDULA = "cedula"
    NIT = "nit"
    PASSPORT = "pasaporte"
    PLATE = "placa"
    VIN = "vin"
    SSN = "ssn"
    CUSTOM = "custom"


class QueryInput(BaseModel):
    """Input for a source query."""

    document_type: DocumentType
    document_number: str
    extra: dict[str, Any] = Field(default_factory=dict)
    audit: bool = False  # When True, capture screenshots + network log + PDF evidence


class SourceMeta(BaseModel):
    """Metadata describing a data source."""

    name: str  # e.g., "co.simit"
    display_name: str  # e.g., "SIMIT — Multas de Tránsito"
    description: str
    country: str  # ISO 3166-1 alpha-2 (e.g., "CO", "US")
    url: str  # Source website URL
    supported_inputs: list[DocumentType]
    requires_captcha: bool = False
    requires_browser: bool = True
    rate_limit_rpm: int = 10


class BaseSource(ABC):
    """Abstract base class for all data sources."""

    @abstractmethod
    def meta(self) -> SourceMeta:
        """Return metadata about this source."""

    @abstractmethod
    def query(self, input: QueryInput) -> BaseModel:
        """Execute a query against this source.

        Args:
            input: Query parameters (document type and number).

        Returns:
            Pydantic model with the query results.

        Raises:
            SourceError: If the query fails.
        """

    def supports(self, doc_type: DocumentType) -> bool:
        """Check if this source supports a given document type."""
        return doc_type in self.meta().supported_inputs
