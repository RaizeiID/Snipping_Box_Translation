from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderHealth:
    ready: bool
    state: str
    message: str
    detail: dict[str, Any]


class ProviderAdapter(Protocol):
    provider_id: str

    def health(self) -> ProviderHealth:
        ...
