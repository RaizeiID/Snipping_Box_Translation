# build_titan_v5_zip.py
# -*- coding: utf-8 -*-
"""
Build ZIP final TITAN V5 remap dari zip project yang ada.

Cara pakai (Windows):
  1) Letakkan file ini di folder yang sama dengan: AI Translation v2 (5).zip
  2) Jalankan:
       python build_titan_v5_zip.py
  3) Hasil:
       AI_Translation_TITAN_V5_FINAL.zip
"""

from __future__ import annotations

import os
import re
import shutil
import zipfile
import textwrap
from pathlib import Path


IN_ZIP_DEFAULT = "AI Translation v2 (5).zip"
OUT_ZIP_DEFAULT = "AI_Translation_TITAN_V5_FINAL.zip"


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def write_text(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8")


def safe_rename(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if dst.exists():
        dst.unlink()
    src.rename(dst)


def make_wrapper(filename: str, model_key: str, target_file: str, desc: str, env: dict) -> str:
    env_lines = []
    for k, v in env.items():
        if v is None:
            env_lines.append(f'    os.environ.setdefault("{k}", "")')
        else:
            env_lines.append(f'    os.environ.setdefault("{k}", "{v}")')
    env_block = "\n".join(env_lines) if env_lines else "    pass"

    return f"""# -*- coding: utf-8 -*-
\"\"\"{filename}

{desc.strip()}
\"\"\"

from __future__ import annotations

import os
import sys
import runpy
from pathlib import Path


def _force_utf8() -> None:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


def main() -> int:
    _force_utf8()
    base_dir = Path(__file__).resolve().parent

    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ["TITAN_MODEL_KEY"] = "{model_key}"

{env_block}

    target = base_dir / "{target_file}"
    if not target.exists():
        print(f"[WRAPPER][ERROR] Base script tidak ditemukan: {{target.name}}")
        raise SystemExit(2)

    if str(base_dir) not in sys.path:
        sys.path.insert(0, str(base_dir))

    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def patch_titanmainv2_idn(tm2_path: Path) -> None:
    """
    Patch TitanMainV2.py:
    - Tambah helper _idn_postprocess + _glossary_html
    - Terapkan postprocess ke BOX translate & CAS translate
    - Tambah label [UNIK] biru kalau cache MISS & TITAN_UNIQUE_LABEL=1
    """
    s = read_text(tm2_path)

    if "_idn_postprocess" in s and "_glossary_html" in s:
        return

    marker = "\n# ==============================================================================\n# TEXT CLEAN / WRAP"
    mpos = s.find(marker)
    if mpos == -1:
        print("[WARN] Tidak menemukan marker TEXT CLEAN / WRAP untuk insert helper IDN.")
        return

    helper = textwrap.dedent("""
    # ==============================================================================
    # IDN (Naturalization + Glossary)  [ACTIVE ONLY IF TITAN_IDN_MODE=1]
    # ==============================================================================
    def _idn_enabled() -> bool:
        v = (os.environ.get("TITAN_IDN_MODE") or "").strip().lower()
        return v in ("1","true","yes","y","on")

    def _idn_level() -> str:
        return (os.environ.get("TITAN_IDN_LEVEL") or "MAX").strip().upper()

    def _idn_postprocess(src_text: str, translated_text: str, kind: str = "DIALOG") -> str:
        if not translated_text:
            return translated_text
        if not _idn_enabled():
            return translated_text

        out = translated_text

        # Protect unique terms so naturalizer doesn't destroy lore terms
        try:
            from TitanIDN_Shared import protect_terms, restore_terms, _load_unique_terms
            terms = _load_unique_terms()
            protected, mapping = protect_terms(out, terms)
        except Exception:
            protected, mapping = out, {}

        # Naturalize + war-context
        try:
            from TitanIndonesianLocalizer import localize_id_with_context, localize_id
            try:
                out_nat = localize_id_with_context(src_text, protected, kind=kind, level=_idn_level())
            except Exception:
                out_nat = localize_id(protected, kind=kind, level=_idn_level())
        except Exception:
            out_nat = protected

        # Restore protected terms
        try:
            from TitanIDN_Shared import restore_terms
            out_nat = restore_terms(out_nat, mapping)
        except Exception:
            pass

        return (out_nat or "").strip()

    def _glossary_html(escaped_html: str) -> str:
        if not escaped_html:
            return escaped_html
        if not _idn_enabled():
            return escaped_html
        try:
            from TitanLoreGlossary import annotate_html_escaped
            return annotate_html_escaped(escaped_html, enable_terms=True)
        except Exception:
            return escaped_html
    """).rstrip() + "\n\n"

    s = s[:mpos] + helper + s[mpos:]

    # BOX pipeline patch: apply _idn_postprocess after preserve_tail_punct
    s = s.replace(
        "            out = offline_translate_ram(dialog)\n            out = _preserve_tail_punct(dialog, out)\n            dt = int((time.time() - t0) * 1000)\n",
        "            out = offline_translate_ram(dialog)\n            out = _preserve_tail_punct(dialog, out)\n            out = _idn_postprocess(dialog, out, kind=kind)\n            dt = int((time.time() - t0) * 1000)\n",
    )

    # CAS patch
    s = s.replace(
        "                trans = offline_translate_ram(src)\n                trans = _preserve_tail_punct(src, trans).strip()\n",
        "                trans = offline_translate_ram(src)\n                trans = _preserve_tail_punct(src, trans).strip()\n                trans = _idn_postprocess(src, trans, kind='CAS')\n",
    )

    # HTML output patch: glossary + UNIK label
    s = s.replace(
        "            safe_out = _html_escape(out)\n",
        "            safe_out = _html_escape(out)\n"
        "            safe_out = _glossary_html(safe_out)\n"
        "            if (not cache_hit) and (os.environ.get('TITAN_UNIQUE_LABEL','0').strip().lower() in ('1','true','yes','on')):\n"
        "                safe_out = f\"<span style='color:#0066FF; font-weight:900;'>[UNIK]</span> \" + safe_out\n",
    )

    write_text(tm2_path, s)


def main() -> int:
    cwd = Path.cwd()
    in_zip = cwd / IN_ZIP_DEFAULT
    out_zip = cwd / OUT_ZIP_DEFAULT

    if not in_zip.exists():
        print(f"[ERROR] Input zip tidak ditemukan: {in_zip}")
        return 2

    work = cwd / "_build_titan_v5_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    # Extract
    with zipfile.ZipFile(in_zip, "r") as z:
        z.extractall(work)

    # -----------------------------
    # Remap versi (sesuai permintaan)
    # -----------------------------
    safe_rename(work / "TitanMainV4.py", work / "TitanMainV3_OnlineOnly_Legacy.py")
    safe_rename(work / "TitanMainV4_IDN.py", work / "TitanMainV3_OnlineOnly_Legacy_IDN.py")
    safe_rename(work / "TitanMainV4Lite_IDN.py", work / "TitanMainFAST_IDN_Legacy.py")

    safe_rename(work / "TitanMainV3.py", work / "TitanMainV4.py")
    safe_rename(work / "TitanMainV3Lite.py", work / "TitanMainV4Lite.py")

    safe_rename(work / "TitanMainV3_IDN.py", work / "TitanMainV4_IDN.py")
    safe_rename(work / "TitanMainV3Lite_IDN.py", work / "TitanMainV4Lite_IDN.py")

    for suf in ["OptionA_FRAMED", "OptionB_FRAMED", "OptionC_FRAMED"]:
        safe_rename(work / f"TitanMainV3_{suf}.py", work / f"TitanMainV4_{suf}.py")
        safe_rename(work / f"TitanMainV3Lite_{suf}.py", work / f"TitanMainV4Lite_{suf}.py")

    # -----------------------------
    # Perbaiki TitanIDN_PatchSuite (env-only, aman)
    # -----------------------------
    (work / "TitanIDN_PatchSuite.py").write_text(textwrap.dedent("""\
    # -*- coding: utf-8 -*-
    \"\"\"TitanIDN_PatchSuite.py

    Version : 1.1.0
    Updated : 2026-01-07

    Patch suite untuk semua *_IDN:

    - Memaksa stdout/stderr UTF-8 (Windows friendly).
    - Menyalakan flag IDN via env:
        TITAN_IDN_MODE=1
        TITAN_IDN_PROFILE=<profile>
        TITAN_IDN_LEVEL=FAST/BALANCED/MAX  (default MAX)
        TITAN_IDN_GAME=GFL2_EXILIUM (opsional)

    Catatan:
    - Implementasi naturalisasi + glossary dilakukan langsung di TitanMainV2
      (hanya aktif jika TITAN_IDN_MODE=1).
    \"\"\"

    from __future__ import annotations

    import os
    import sys

    _INSTALLED = False

    def _force_utf8_stdout() -> None:
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    def install_idn_patch(profile: str = "IDN_MAX") -> None:
        global _INSTALLED
        if _INSTALLED:
            return

        _force_utf8_stdout()

        os.environ.setdefault("TITAN_IDN_MODE", "1")
        os.environ.setdefault("TITAN_IDN_PROFILE", profile)
        os.environ.setdefault("TITAN_IDN_LEVEL", os.environ.get("TITAN_IDN_LEVEL") or "MAX")

        _INSTALLED = True
    """), encoding="utf-8")

    # -----------------------------
    # Update TitanIndonesianLocalizer (war-context aware)
    # -----------------------------
    loc_path = work / "TitanIndonesianLocalizer.py"
    if loc_path.exists():
        s = read_text(loc_path)
        if "def localize_id_with_context" not in s:
            s += "\n\n" + textwrap.dedent(r"""
            # -----------------------------------------------------------------------------
            # Context-aware (war / tactical) disambiguation
            # -----------------------------------------------------------------------------
            _WAR_HINTS = {
                "fire", "open fire", "hold fire", "covering fire", "fire at", "return fire",
                "shoot", "shot", "shots", "gun", "rifle", "pistol", "ammo", "bullet",
                "grenade", "smoke", "smoke grenade", "deploy smoke", "suppression",
                "enemy", "hostile", "target", "aim", "range", "weapon",
            }

            def localize_id_with_context(src_text: str, translated_text: str, kind: str = "DIALOG", level: Optional[str] = None) -> str:
                """
                Naturalize hasil terjemahan ke Bahasa Indonesia, tapi menjaga konteks game perang/taktikal.
                Contoh:
                - 'fire!' sering berarti 'tembak!' (bukan 'api!') jika konteks menembak.
                - 'smoke' dalam konteks taktis -> 'asap' / 'granat asap' (bukan 'merokok').

                Catatan:
                - Tidak menebak akronim dunia nyata (itu urusan glossary).
                """
                out = localize_id(translated_text, kind=kind, level=level)

                src = (src_text or "").lower()
                combo = (src_text or "") + " " + (translated_text or "")
                combo_l = combo.lower()

                def has_any(hints) -> bool:
                    return any(h in combo_l for h in hints)

                # Disambiguate "fire" => "tembak" in tactical context
                if "fire" in src or "open fire" in src or "hold fire" in src:
                    if has_any(_WAR_HINTS) or any(k in src for k in ("fire at", "return fire", "open fire", "hold fire")):
                        out = re.sub(r"\bapi\b", "tembak", out, flags=re.I)
                        out = re.sub(r"\bnyalakan api\b", "tembak", out, flags=re.I)

                # Disambiguate smoke in tactical context
                if "smoke" in src:
                    if "grenade" in src or "deploy" in src or "cover" in src or "screen" in src or "smoke grenade" in combo_l:
                        out = re.sub(r"\bmerokok\b", "asap", out, flags=re.I)

                return out
            """).strip() + "\n"
            write_text(loc_path, s)

    # -----------------------------
    # Overwrite TitanLoreGlossary sesuai request:
    # - Akronim biru langit
    # - Kepanjangan hanya dari titan_glossary_custom.json (bukan dunia nyata)
    # -----------------------------
    (work / "TitanLoreGlossary.py").write_text(textwrap.dedent("""\
    # -*- coding: utf-8 -*-
    \"\"\"TitanLoreGlossary.py

    Version : 2.0.0 (2026-01-07)

    Tujuan:
    - Menandai istilah khas (lore) dan singkatan/akronim agar pembaca paham konteks.
    - Sesuai permintaan:
      1) Akronim/singkatan: warna biru muda / biru langit.
         - Jika kepanjangan diketahui (dari file game), tampilkan: AKRONIM (Kepanjangan)
         - Jika tidak diketahui, tampilkan: AKRONIM (tanpa menebak dari dunia nyata)
      2) Kepanjangan harus berasal dari game melalui titan_glossary_custom.json.

    File custom (editable):
      titan_glossary_custom.json
      {
        "acronyms": { "OGAS": null, "URNC": "..." },
        "terms": { "Doll": "..." }
      }
    \"\"\"

    from __future__ import annotations

    import json
    import re
    from pathlib import Path
    from typing import Dict, Optional, Tuple

    ACRONYM_SKY_HEX = "#66CCFF"     # biru langit

    _ACR_RE = re.compile(r"\\b[A-Z][A-Z0-9]{1,9}\\b")

    TERMS_DEFAULT: Dict[str, str] = {
        "Doll": "Unit tempur / android",
        "Dolls": "Unit tempur / android",
    }

    # Tidak ada akronim global: mencegah tebak dunia nyata.
    ACRONYMS_DEFAULT: Dict[str, Optional[str]] = {}

    _CUSTOM_PATH = Path(__file__).with_name("titan_glossary_custom.json")


    def _load_custom() -> Tuple[Dict[str, Optional[str]], Dict[str, str]]:
        if not _CUSTOM_PATH.exists():
            return {}, {}
        try:
            data = json.loads(_CUSTOM_PATH.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {}, {}
            acr_raw = data.get("acronyms", {}) or {}
            terms_raw = data.get("terms", {}) or {}

            acr: Dict[str, Optional[str]] = {}
            if isinstance(acr_raw, dict):
                for k, v in acr_raw.items():
                    kk = str(k).strip().upper()
                    if not kk:
                        continue
                    if v is None:
                        acr[kk] = None
                    else:
                        vv = str(v).strip()
                        acr[kk] = vv if vv else None

            terms: Dict[str, str] = {}
            if isinstance(terms_raw, dict):
                for k, v in terms_raw.items():
                    kk = str(k).strip()
                    vv = str(v).strip()
                    if kk and vv:
                        terms[kk] = vv

            return acr, terms
        except Exception:
            return {}, {}


    def _merge_glossary() -> Tuple[Dict[str, Optional[str]], Dict[str, str]]:
        acr = dict(ACRONYMS_DEFAULT)
        terms = dict(TERMS_DEFAULT)
        custom_acr, custom_terms = _load_custom()
        if custom_acr:
            acr.update(custom_acr)
        if custom_terms:
            terms.update(custom_terms)
        return acr, terms


    def _already_has_parentheses(text: str, idx_after_token: int) -> bool:
        j = idx_after_token
        while j < len(text) and text[j] == " ":
            j += 1
        return j < len(text) and text[j] == "("


    def annotate_plain(text: str, enable_terms: bool = True) -> str:
        if not text:
            return text
        acr_map, term_map = _merge_glossary()
        out = text

        seen = set()
        for m in list(_ACR_RE.finditer(out)):
            tok = m.group(0).upper()
            if tok in seen:
                continue
            seen.add(tok)

            expansion = acr_map.get(tok, None)
            mm = re.search(rf"\\b{re.escape(tok)}\\b", out)
            if not mm:
                continue
            if expansion and (not _already_has_parentheses(out, mm.end())):
                out = out[:mm.end()] + f" ({expansion})" + out[mm.end():]

        if enable_terms and term_map:
            for term, meaning in term_map.items():
                mm = re.search(rf"(?<!\\w)({re.escape(term)})(?!\\w)", out)
                if not mm:
                    continue
                if _already_has_parentheses(out, mm.end(1)):
                    continue
                out = out[:mm.end(1)] + f" ({meaning})" + out[mm.end(1):]
        return out


    def annotate_html_escaped(escaped_text: str, enable_terms: bool = True) -> str:
        if not escaped_text:
            return escaped_text

        acr_map, term_map = _merge_glossary()
        out = escaped_text

        cursor = 0
        pieces = []
        while True:
            m = _ACR_RE.search(out, cursor)
            if not m:
                pieces.append(out[cursor:])
                break

            pieces.append(out[cursor:m.start()])
            tok = m.group(0).upper()
            expansion = acr_map.get(tok, None)
            colored = f'<span style="color:{ACRONYM_SKY_HEX}; font-weight:800;">{tok}</span>'

            if _already_has_parentheses(out, m.end()):
                pieces.append(colored)
            else:
                if expansion:
                    pieces.append(f"{colored} ({expansion})")
                else:
                    pieces.append(colored)

            cursor = m.end()

        out2 = "".join(pieces)

        if enable_terms and term_map:
            for term, meaning in term_map.items():
                mm = re.search(rf"(?<!\\w)({re.escape(term)})(?!\\w)", out2)
                if not mm:
                    continue
                if _already_has_parentheses(out2, mm.end(1)):
                    continue
                out2 = out2[:mm.end(1)] + f" ({meaning})" + out2[mm.end(1):]
        return out2
    """), encoding="utf-8")

    # -----------------------------
    # Patch TitanMainV2 untuk IDN postprocess + glossary + [UNIK]
    # -----------------------------
    tm2 = work / "TitanMainV2.py"
    if tm2.exists():
        patch_titanmainv2_idn(tm2)

    # -----------------------------
    # Buat model-model baru (V1Lite/V2Lite/V3 heavy/V3Lite/V5/V5Lite + *_IDN)
    # -----------------------------
    # V1Lite
    write_text(work / "TitanMainV1Lite.py", make_wrapper(
        "TitanMainV1Lite.py", "V1L", "TitanMainV1.py",
        "Model Versi 1 LITE: versi ringan (lebih hemat resource).",
        {"TITAN_AUTO_SNAPSHOT_MS": "240", "TITAN_AUTO_SNAPSHOT_MIN_MS": "140", "TITAN_VRAM_CHECK_MS": "3500"}
    ))

    # V2Lite
    write_text(work / "TitanMainV2Lite.py", make_wrapper(
        "TitanMainV2Lite.py", "V2L", "TitanMainV2.py",
        "Model Versi 2 LITE: seimbang tapi lebih ringan dibanding V2.",
        {"TITAN_AUTO_SNAPSHOT_MS": "220", "TITAN_AUTO_SNAPSHOT_MIN_MS": "130", "TITAN_VRAM_CHECK_MS": "3000"}
    ))

    # V3 HEAVY: pakai preset TITAN_ULTRA (lebih akurat tapi berat)
    v3_heavy = textwrap.dedent("""\
    # -*- coding: utf-8 -*-
    \"\"\"TitanMainV3.py (HEAVY ACCURACY / SLOW)

    Sesuai permintaan:
    - Model V3 mengutamakan akurasi walau lebih lambat.
    - Implementasi: menjalankan preset TITAN_ULTRA (biasanya lebih berat + refine).

    Run:
      py TitanMainV3.py
    \"\"\"

    from __future__ import annotations

    import os
    import sys
    import runpy

    from TitanIDN_PatchSuite import install_idn_patch  # safe, env-only


    def _force_utf8() -> None:
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


    def main() -> int:
        _force_utf8()
        os.environ.setdefault("PYTHONUTF8", "1")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        os.environ["TITAN_MODEL_KEY"] = "V3"
        os.environ.setdefault("TITAN_PROFILE", "V3_HEAVY")
        os.environ.setdefault("TITAN_LATENCY_HINT_MS", "800")

        # NOTE: IDN tidak otomatis di V3 heavy. Gunakan TitanMainV3_IDN.py jika perlu.
        try:
            import TITAN_ULTRA as base
        except Exception as e:
            print("[ERROR] Tidak bisa import TITAN_ULTRA.py. Pastikan file ada.")
            print(f"        detail: {e!r}")
            return 2

        if hasattr(base, "main"):
            try:
                out = base.main()
                return int(out) if out is not None else 0
            except SystemExit as se:
                try:
                    return int(se.code) if se.code is not None else 0
                except Exception:
                    return 0

        try:
            runpy.run_path(getattr(base, "__file__"), run_name="__main__")
            return 0
        except SystemExit as se:
            try:
                return int(se.code) if se.code is not None else 0
            except Exception:
                return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    """)
    write_text(work / "TitanMainV3.py", v3_heavy)

    # V3Lite: lebih ringan, pakai V4 hybrid (hasil cepat), tapi bisa dinaikkan akurasi via env
    write_text(work / "TitanMainV3Lite.py", make_wrapper(
        "TitanMainV3Lite.py", "V3L", "TitanMainV4.py",
        "Model Versi 3 LITE: lebih ringan, berbasis V4 Hybrid tapi preset condong akurat.",
        {"TITAN_V3_PREFER_ONLINE_MS": "1200", "TITAN_V3_ALL_TIMEOUT_MS": "2600"}
    ))

    # V5: naturalisasi maksimal (war-aware) berbasis V4 hybrid
    write_text(work / "TitanMainV5.py", make_wrapper(
        "TitanMainV5.py", "V5", "TitanMainV4.py",
        "Model Versi 5: naturalisasi Indonesia maksimal (war-aware untuk GFL2).",
        {"TITAN_IDN_MODE": "1", "TITAN_IDN_LEVEL": "MAX", "TITAN_IDN_GAME": "GFL2_EXILIUM", "TITAN_UNIQUE_LABEL": "1"}
    ))

    # V5Lite: naturalisasi maksimal tapi lebih ringan
    write_text(work / "TitanMainV5Lite.py", make_wrapper(
        "TitanMainV5Lite.py", "V5L", "TitanMainV4Lite.py",
        "Model Versi 5 LITE: naturalisasi maksimal tapi lebih ringan.",
        {"TITAN_IDN_MODE": "1", "TITAN_IDN_LEVEL": "MAX", "TITAN_IDN_GAME": "GFL2_EXILIUM", "TITAN_UNIQUE_LABEL": "1", "TITAN_AUTO_SNAPSHOT_MS": "230"}
    ))

    # *_IDN wrappers (alias)
    for fn, key, target, profile in [
        ("TitanMainV1Lite_IDN.py", "V1LITE_IDN", "TitanMainV1Lite.py", "V1_IDN"),
        ("TitanMainV2Lite_IDN.py", "V2LITE_IDN", "TitanMainV2Lite.py", "V2_IDN"),
        ("TitanMainV3_IDN.py", "V3_IDN", "TitanMainV3.py", "V3_IDN"),
        ("TitanMainV3Lite_IDN.py", "V3LITE_IDN", "TitanMainV3Lite.py", "V3_IDN"),
        ("TitanMainV5_IDN.py", "V5_IDN", "TitanMainV5.py", "V5_IDN"),
        ("TitanMainV5Lite_IDN.py", "V5LITE_IDN", "TitanMainV5Lite.py", "V5_IDN"),
    ]:
        write_text(work / fn, make_wrapper(
            fn, key, target,
            f"Wrapper IDN ({key}) -> menjalankan {target} dengan TITAN_IDN_MODE=1.",
            {"TITAN_IDN_MODE": "1", "TITAN_IDN_PROFILE": profile, "TITAN_IDN_LEVEL": "MAX", "TITAN_UNIQUE_LABEL": "1"}
        ))

    # -----------------------------
    # Rewrite TitanCore_V2.py -> tabel kategori per versi + Extras
    # -----------------------------
    core_path = work / "TitanCore_V2.py"
    core_path.write_text(textwrap.dedent("""\
    # -*- coding: utf-8 -*-
    \"\"\"TitanCore_V2.py
    ====================================================================================================
    TITANCORE V2  |  v8.0-V5-REMAP  |  2026-01-07
    ====================================================================================================

    Launcher + panduan cepat untuk menjalankan berbagai model TITAN Translator.

    KATEGORI (sesuai permintaan):
      - Model Versi 1  : V1 / V1 Lite / V1_IDN / V1 Lite_IDN
      - Model Versi 2  : V2 / V2 Lite / V2_IDN / V2 Lite_IDN
      - Model Versi 3  : V3 (HEAVY Accuracy) / V3 Lite / V3_IDN / V3 Lite_IDN
      - Model Versi 4  : V4 (HYBRID Online+Offline) / V4 Lite / V4_IDN / V4 Lite_IDN (+ FRAMED options)
      - Model Versi 5  : V5 (Naturalisasi maksimal) / V5 Lite / V5_IDN / V5 Lite_IDN
      - EXTRAS         : TITANMAIN, MODE_DEBUG, TITAN_DOCTOR, TITAN_ULTRA, TITAN_FAST, TITAN_LAUNCHER, legacy tools
    \"\"\"

    from __future__ import annotations

    import os
    import re
    import sys
    import time
    import subprocess
    from dataclasses import dataclass
    from pathlib import Path
    from typing import List, Optional, Dict

    from TitanTelemetry import Telemetry


    def _force_utf8_stdout() -> None:
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


    _force_utf8_stdout()

    BASE_DIR = Path(__file__).resolve().parent
    PY_EXE = sys.executable
    MS_RE = re.compile(r"\\|\\s*(\\d{1,5})ms\\s*\\|")


    def _ts() -> str:
        return time.strftime("%H:%M:%S", time.localtime())


    def _find_file(filename: str) -> Optional[Path]:
        p = BASE_DIR / filename
        if p.exists():
            return p
        candidates = list(BASE_DIR.rglob(filename))
        if not candidates:
            return None
        candidates.sort(key=lambda x: (len(x.parts), str(x)))
        return candidates[0]


    def _hr(ch: str = "-") -> str:
        return ch * 108


    @dataclass
    class Entry:
        num: int
        key: str
        title: str
        file: str
        meta: str
        best: str
        note: str
        group: str

        def resolved_path(self) -> Optional[Path]:
            return _find_file(self.file)


    def _status(e: Entry) -> str:
        return "OK" if e.resolved_path() else "MISS"


    def _entries() -> List[Entry]:
        e: List[Entry] = []

        # MODEL VERSI 1
        e += [
            Entry(1,  "V1",      "V1",          "TitanMainV1.py",        "spd=FAST | acc=LOW | nat=OFF",   "Super cepat (uji pipeline/UI).",         "Akurasi rendah, latency prioritas.", "MODEL VERSI 1"),
            Entry(2,  "V1L",     "V1 Lite",     "TitanMainV1Lite.py",    "spd=FAST++ | acc=LOW | nat=OFF", "Versi ringan (hemat resource).",          "Basis V1 + preset ringan.",         "MODEL VERSI 1"),
            Entry(3,  "V1_IDN",  "V1_IDN",      "TitanMainV1_IDN.py",    "spd=FAST | acc=LOW | nat=FAST",  "V1 + naturalisasi ringan.",               "IDN aktif hanya di wrapper.",       "MODEL VERSI 1"),
            Entry(4,  "V1L_IDN", "V1 Lite_IDN", "TitanMainV1Lite_IDN.py","spd=FAST++ | acc=LOW | nat=MAX", "Versi ringan + naturalisasi.",             "IDN MAX (best-effort).",            "MODEL VERSI 1"),
        ]

        # MODEL VERSI 2
        e += [
            Entry(11, "V2",      "V2",          "TitanMainV2.py",        "spd=BALANCED | acc=MID+ | nat=OFF","Seimbang, condong akurat.",               "Rekomendasi harian.",               "MODEL VERSI 2"),
            Entry(12, "V2L",     "V2 Lite",     "TitanMainV2Lite.py",    "spd=BALANCED-FAST | acc=MID | nat=OFF","Lebih ringan dari V2.",                "Cocok PC menengah.",                "MODEL VERSI 2"),
            Entry(13, "V2_IDN",  "V2_IDN",      "TitanMainV2_IDN.py",    "spd=BALANCED | acc=MID+ | nat=BAL","V2 + naturalisasi stabil.",               "IDN aktif hanya di wrapper.",       "MODEL VERSI 2"),
            Entry(14, "V2L_IDN", "V2 Lite_IDN", "TitanMainV2Lite_IDN.py","spd=BALANCED-FAST | acc=MID | nat=MAX","Lite + IDN.",                         "Ringan, tetap natural.",            "MODEL VERSI 2"),
        ]

        # MODEL VERSI 3 (HEAVY)
        e += [
            Entry(21, "V3",      "V3 (HEAVY)",  "TitanMainV3.py",        "spd=SLOW | acc=VERY HIGH | nat=OFF","Preset berat (ULTRA) untuk akurasi.",     "Paling akurat, lebih lambat.",      "MODEL VERSI 3"),
            Entry(22, "V3L",     "V3 Lite",     "TitanMainV3Lite.py",    "spd=MED | acc=HIGH | nat=OFF",      "Lebih ringan, basis V4 hybrid.",          "Lebih cepat.",                      "MODEL VERSI 3"),
            Entry(23, "V3_IDN",  "V3_IDN",      "TitanMainV3_IDN.py",    "spd=SLOW | acc=VERY HIGH | nat=MAX","V3 + naturalisasi maksimal.",             "Untuk dialog penting.",             "MODEL VERSI 3"),
            Entry(24, "V3L_IDN", "V3 Lite_IDN", "TitanMainV3Lite_IDN.py","spd=MED | acc=HIGH | nat=MAX",      "V3 Lite + naturalisasi.",                 "Ringan tapi natural.",              "MODEL VERSI 3"),
        ]

        # MODEL VERSI 4 (HYBRID)
        e += [
            Entry(31, "V4",      "V4 (HYBRID)", "TitanMainV4.py",        "spd=BALANCED | acc=HIGH | nat=OFF", "Hybrid online+offline (router).",         "Fast-first + fallback.",            "MODEL VERSI 4"),
            Entry(32, "V4L",     "V4 Lite",     "TitanMainV4Lite.py",    "spd=FAST | acc=MID-HIGH | nat=OFF", "Versi ringan V4.",                        "Cocok PC menengah.",                "MODEL VERSI 4"),
            Entry(33, "V4_IDN",  "V4_IDN",      "TitanMainV4_IDN.py",    "spd=BALANCED | acc=HIGH | nat=MAX", "V4 + naturalisasi.",                      "Default IDN MAX.",                  "MODEL VERSI 4"),
            Entry(34, "V4L_IDN", "V4 Lite_IDN", "TitanMainV4Lite_IDN.py","spd=FAST | acc=MID-HIGH | nat=MAX", "V4 Lite + naturalisasi.",                 "Lebih ringan.",                     "MODEL VERSI 4"),
            Entry(35, "V4A",     "V4 OptionA",  "TitanMainV4_OptionA_FRAMED.py","-", "Varian UI FRAMED OptionA.",        "Tampilan framed.",                   "MODEL VERSI 4"),
            Entry(36, "V4B",     "V4 OptionB",  "TitanMainV4_OptionB_FRAMED.py","-", "Varian UI FRAMED OptionB.",        "Tampilan framed.",                   "MODEL VERSI 4"),
            Entry(37, "V4C",     "V4 OptionC",  "TitanMainV4_OptionC_FRAMED.py","-", "Varian UI FRAMED OptionC.",        "Tampilan framed.",                   "MODEL VERSI 4"),
        ]

        # MODEL VERSI 5 (NATURALISASI)
        e += [
            Entry(41, "V5",      "V5",          "TitanMainV5.py",        "spd=BALANCED | acc=HIGH | nat=MAX", "Naturalisasi maksimal (war-aware GFL2).", "Paling natural Indonesia.",          "MODEL VERSI 5"),
            Entry(42, "V5L",     "V5 Lite",     "TitanMainV5Lite.py",    "spd=FAST | acc=MID-HIGH | nat=MAX", "V5 versi ringan.",                        "Natural + hemat resource.",          "MODEL VERSI 5"),
            Entry(43, "V5_IDN",  "V5_IDN",      "TitanMainV5_IDN.py",    "spd=BALANCED | acc=HIGH | nat=MAX", "Alias IDN untuk V5.",                      "Konsistensi penamaan.",              "MODEL VERSI 5"),
            Entry(44, "V5L_IDN", "V5 Lite_IDN", "TitanMainV5Lite_IDN.py","spd=FAST | acc=MID-HIGH | nat=MAX", "Alias IDN untuk V5 Lite.",                 "Konsistensi penamaan.",              "MODEL VERSI 5"),
        ]

        # EXTRAS
        extras = [
            (90, "TITANMAIN",       "TITANMAIN.py",                  "Main entrypoint (recommended default)"),
            (91, "MODE_DEBUG",      "MODE_DEBUG.py",                 "Debug core sync / developer mode"),
            (92, "TITAN_DOCTOR",    "TITAN_DOCTOR.py",               "Diagnose environment/dependencies"),
            (93, "TITAN_ULTRA",     "TITAN_ULTRA.py",                "Ultra preset (heavy)"),
            (94, "TITAN_FAST",      "TITAN_FAST.py",                 "Fast preset"),
            (95, "TITAN_LAUNCHER",  "TITAN_LAUNCHER.py",             "Interactive launcher"),
            (96, "LEGACY_ONLINE",   "TitanMainV3_OnlineOnly_Legacy.py","Legacy online-only (old V4)"),
            (97, "LEGACY_ONLINE_IDN","TitanMainV3_OnlineOnly_Legacy_IDN.py","Legacy online-only + IDN wrapper"),
            (98, "LEGACY_FAST_IDN", "TitanMainFAST_IDN_Legacy.py",    "Legacy IDN runner (FAST preset)"),
        ]
        for num, key, file, note in extras:
            e.append(Entry(num, key, key, file, "-", note, "Masuk kategori EXTRAS.", "EXTRAS"))

        return e


    ENTRIES = _entries()
    BY_NUM: Dict[int, Entry] = {e.num: e for e in ENTRIES}
    BY_KEY: Dict[str, Entry] = {e.key.upper(): e for e in ENTRIES}


    def _print_group(title: str, rows: List[Entry], t: Telemetry) -> None:
        print(_hr())
        print(title)
        print(_hr())
        print(f"{'NO':<4}{'KEY':<14}{'OK?':<6}{'AVG':<8}FILE")
        print(_hr("."))
        for e in rows:
            st = "OK" if e.resolved_path() else "MISS"
            avg = t.avg_for(e.key)
            avg_s = "-" if avg is None else f"{avg:.0f}ms"
            print(f"{e.num:<4}{e.key:<14}{st:<6}{avg_s:<8}{e.file}")
        print()


    def _parse_selection(s: str) -> List[Entry]:
        s = s.strip()
        if not s:
            return []
        up = s.upper()
        if up in BY_KEY:
            return [BY_KEY[up]]
        if s.isdigit():
            e = BY_NUM.get(int(s))
            return [e] if e else []
        if "-" in s:
            a, b = s.split("-", 1)
            if a.strip().isdigit() and b.strip().isdigit():
                a_i, b_i = int(a.strip()), int(b.strip())
                if a_i > b_i:
                    a_i, b_i = b_i, a_i
                return [BY_NUM[n] for n in range(a_i, b_i + 1) if n in BY_NUM]
        if "," in s:
            out: List[Entry] = []
            for part in [x.strip() for x in s.split(",") if x.strip()]:
                out.extend(_parse_selection(part))
            seen = set()
            uniq = []
            for e in out:
                if e.key not in seen:
                    uniq.append(e)
                    seen.add(e.key)
            return uniq
        return []


    def _run(e: Entry, t: Telemetry) -> int:
        p = e.resolved_path()
        if not p:
            print(f"[ERROR] File tidak ditemukan: {e.file}")
            return 2

        t.record_launch(e.key)

        print(_hr())
        print(f"[{_ts()}] [LAUNCH] {e.title} (key={e.key})")
        print(f"[{_ts()}] File   : {p}")
        print(f"[{_ts()}] Tujuan : {e.best}")
        print(_hr())

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["TITAN_LAUNCHED_BY_CORE"] = "1"
        env["TITAN_MODEL_KEY"] = e.key

        proc = subprocess.Popen(
            [PY_EXE, "-u", str(p)],
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        samples = 0
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            m = MS_RE.search(line)
            if m:
                try:
                    ms = int(m.group(1))
                    samples += 1
                    t.record_translation_ms(ms, model_key=e.key, source="core_parse")
                except Exception:
                    pass

        code = proc.wait()
        print(_hr())
        print(f"[{_ts()}] Program selesai. exit_code={code} | samples={samples}")
        return int(code)


    def main() -> int:
        t = Telemetry(BASE_DIR / "titan_usage_stats.json")

        while True:
            print("=" * 108)
            print("TITANCORE V2  |  v8.0-V5-REMAP  |  2026-01-07")
            print("=" * 108)
            print()

            groups = [
                ("MODEL VERSI 1", [x for x in ENTRIES if x.group == "MODEL VERSI 1" and x.num < 90]),
                ("MODEL VERSI 2", [x for x in ENTRIES if x.group == "MODEL VERSI 2" and x.num < 90]),
                ("MODEL VERSI 3", [x for x in ENTRIES if x.group == "MODEL VERSI 3" and x.num < 90]),
                ("MODEL VERSI 4", [x for x in ENTRIES if x.group == "MODEL VERSI 4" and x.num < 90]),
                ("MODEL VERSI 5", [x for x in ENTRIES if x.group == "MODEL VERSI 5" and x.num < 90]),
                ("EXTRAS",        [x for x in ENTRIES if x.group == "EXTRAS"]),
            ]
            for title, rows in groups:
                rows = sorted(rows, key=lambda x: x.num)
                if rows:
                    _print_group(title, rows, t)

            print(_hr())
            print("Input contoh:")
            print("  41              -> jalankan nomor 41")
            print("  V5              -> jalankan via key")
            print("  21,41,42        -> jalankan beberapa model")
            print("  1-4             -> jalankan range")
            print("  stats           -> statistik")
            print("  q               -> keluar")
            print(_hr())

            try:
                cmd = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0

            if not cmd:
                continue

            up = cmd.upper()
            if up in ("Q", "QUIT", "EXIT"):
                return 0
            if up == "STATS":
                print(_hr("="))
                print("STATS")
                print(_hr("="))
                for r in t.stats_rows():
                    avg = r["avg_ms"]
                    avg_s = "-" if avg is None else f"{avg:.0f}ms"
                    print(f"KEY: {r['key']} | launches: {r['launches']} | last_used: {r['last_used']} | avg: {avg_s} | samples: {r['samples']}")
                input("(Enter untuk kembali) ")
                t.load()
                continue

            selected = _parse_selection(cmd)
            if not selected:
                print(f"[WARN] Input tidak dikenali: {cmd}")
                input("(Enter untuk kembali) ")
                continue

            for e in selected:
                _run(e, t)
                input("(Enter untuk kembali ke menu) ")
                t.load()

        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    """), encoding="utf-8")

    # -----------------------------
    # Run scripts minimal (opsional)
    # -----------------------------
    def write_cmd(name: str, pyfile: str):
        write_text(work / name, f"""@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
python -u "{pyfile}"
endlocal
""")

    def write_ps1(name: str, pyfile: str):
        write_text(work / name, f"""$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
python -u "{pyfile}"
""")

    for nm, f in [
        ("Run_TitanMainV3.cmd", "TitanMainV3.py"),
        ("Run_TitanMainV4.cmd", "TitanMainV4.py"),
        ("Run_TitanMainV5.cmd", "TitanMainV5.py"),
        ("Run_TitanCore_V2.cmd", "TitanCore_V2.py"),
        ("Run_TitanMainV3.ps1", "TitanMainV3.py"),
        ("Run_TitanMainV4.ps1", "TitanMainV4.py"),
        ("Run_TitanMainV5.ps1", "TitanMainV5.py"),
        ("Run_TitanCore_V2.ps1", "TitanCore_V2.py"),
    ]:
        if nm.endswith(".cmd"):
            write_cmd(nm, f)
        else:
            write_ps1(nm, f)

    # -----------------------------
    # Zip output
    # -----------------------------
    if out_zip.exists():
        out_zip.unlink()

    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in work.rglob("*"):
            if p.is_file():
                z.write(p, arcname=str(p.relative_to(work)))

    # Cleanup workdir
    shutil.rmtree(work, ignore_errors=True)

    print("[OK] ZIP final dibuat:")
    print("     ", out_zip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
