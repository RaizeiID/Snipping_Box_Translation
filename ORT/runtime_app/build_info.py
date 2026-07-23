from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


VERSION = (8, 9, 9)
VERSION_SUFFIX = ""
APP_VERSION = ".".join(str(part) for part in VERSION) + VERSION_SUFFIX
APP_VERSION_TAG = f"v{APP_VERSION}"
APP_NAME = "ORT Translation"
APP_DISPLAY_NAME = f"{APP_NAME} {APP_VERSION_TAG}"
RELEASE_NAME = "R2 F2 Long-Turn Context and Japanese Accuracy Fix"
RELEASE_CHANNEL = "v8-9-9-r2-f2-long-turn-japanese-context"
BASE_RELEASE_CHANNEL = "v8-9-9-r2-gpu-runtime-normal-realtime"
COMPAT_RELEASE_CHANNELS = (
    "v8-9-9-r2-f1-hybrid-subtitle-continuity",
    "v8-9-9-r2-gpu-runtime-normal-realtime",
)
BUILD_DATE = "2026-07-24"
STATUS_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class BuildInfo:
    name: str = APP_NAME
    version: str = APP_VERSION
    version_tag: str = APP_VERSION_TAG
    display_name: str = APP_DISPLAY_NAME
    release_name: str = RELEASE_NAME
    release_channel: str = RELEASE_CHANNEL
    build_date: str = BUILD_DATE
    status_schema_version: int = STATUS_SCHEMA_VERSION

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version_tag,
            "version_number": self.version,
            "display_name": self.display_name,
            "release_name": self.release_name,
            "release_channel": self.release_channel,
            "build_date": self.build_date,
            "status_schema_version": self.status_schema_version,
        }


BUILD_INFO = BuildInfo()


def version_payload(**extra: Any) -> Dict[str, Any]:
    payload = BUILD_INFO.as_dict()
    payload.update(extra)
    return payload
