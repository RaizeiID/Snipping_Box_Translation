from __future__ import annotations

from .base import ProviderHealth


class ORTNativeAdapter:
    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id

    def health(self) -> ProviderHealth:
        return ProviderHealth(True, "READY", "Provider ORT Native tersedia.", {"provider_id": self.provider_id})
