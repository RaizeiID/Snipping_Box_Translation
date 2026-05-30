# -*- coding: utf-8 -*-
"""Archived build helper for old ORT/Titan v5 packages.

v7 ships as a complete project folder and no longer uses this legacy builder at
runtime. The previous file contained an unfinished code-generation block that
could raise a SyntaxError during project-wide checks. This safe stub is kept so
old references do not crash, while making it clear that v7 should be packaged
from the project folder directly.
"""

from __future__ import annotations


def main() -> int:
    print("build_titan_v5_zip.py is archived in ORT Translation v7.")
    print("Use Start_ORT_Translation.bat for runtime, or zip the ORT_Translation_v7 folder for distribution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
