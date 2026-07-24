from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


VERSION = (9, 0, 1)
VERSION_SUFFIX = ""
APP_VERSION = ".".join(str(part) for part in VERSION) + VERSION_SUFFIX
APP_VERSION_TAG = f"v{APP_VERSION}"
APP_NAME = "ORT Translation"
APP_DISPLAY_NAME = f"{APP_NAME} {APP_VERSION_TAG}"
RELEASE_NAME = "Audio Lab Preload, Watchdog & Diagnostics"
RELEASE_CHANNEL = "v9-0-1-audio-lab-preload-watchdog"
BASE_RELEASE_CHANNEL = "v9-0-0-open-architecture-clean-layout"
COMPAT_RELEASE_CHANNELS = (
    "v9-0-0-open-architecture-clean-layout",
    "v8-9-9-r2-f2-long-turn-japanese-context",
    "v8-9-9-r2-f1-hybrid-subtitle-continuity",
    "v8-9-9-r2-gpu-runtime-normal-realtime",
)
BUILD_DATE = "2026-07-24"
STATUS_SCHEMA_VERSION = 3
PROJECT_LAYOUT_SCHEMA_VERSION = 9
OPEN_ARCHITECTURE_SCHEMA_VERSION = 1


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
    project_layout_schema_version: int = PROJECT_LAYOUT_SCHEMA_VERSION
    open_architecture_schema_version: int = OPEN_ARCHITECTURE_SCHEMA_VERSION

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version_tag,
            "version_number": self.version,
            "display_name": self.display_name,
            "release_name": self.release_name,
            "release_channel": self.release_channel,
            "base_release_channel": BASE_RELEASE_CHANNEL,
            "compatible_release_channels": list(COMPAT_RELEASE_CHANNELS),
            "build_date": self.build_date,
            "status_schema_version": self.status_schema_version,
            "project_layout_schema_version": self.project_layout_schema_version,
            "open_architecture_schema_version": self.open_architecture_schema_version,
        }


BUILD_INFO = BuildInfo()


def version_payload(**extra: Any) -> Dict[str, Any]:
    payload = BUILD_INFO.as_dict()
    payload.update(extra)
    return payload
