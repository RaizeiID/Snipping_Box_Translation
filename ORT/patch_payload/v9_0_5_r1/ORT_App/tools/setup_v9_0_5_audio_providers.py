from __future__ import annotations

"""ORT v9.0.5 provider-setup entry point.

The implementation remains in ``setup_v9_0_4_audio_providers`` so existing
v9.0.4 launchers and recovery shortcuts keep working after an in-place update.
Both entry points execute the same v9.0.5 resilient setup engine.
"""

from setup_v9_0_4_audio_providers import main


if __name__ == "__main__":
    raise SystemExit(main())
