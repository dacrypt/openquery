"""Brazil FIPE data model — vehicle reference prices."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BrFipeResult(BaseModel):
    """Brazil FIPE vehicle price lookup result.

    Source: https://brasilapi.com.br/api/fipe/preco/v1/{codigoFipe}
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    codigo_fipe: str = ""
    marca: str = ""
    modelo: str = ""
    ano: str = ""
    combustivel: str = ""
    valor: str = ""
    mes_referencia: str = ""
    tipo_veiculo: int = 0
    audit: Any | None = Field(default=None, exclude=True)
