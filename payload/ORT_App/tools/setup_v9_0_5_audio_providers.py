from __future__ import annotations

"""ORT v9.0.5 R3 provider-setup entry point.

The implementation also replaces ``setup_v9_0_4_audio_providers.py`` so older
recovery shortcuts cannot fall back to the obsolete Hugging Face dry-run path.
"""

from setup_v9_0_4_audio_providers import main


if __name__ == "__main__":
    raise SystemExit(main())
