"""ORT Translation v8.7.8 benchmark from real structured session JSONL logs."""
from __future__ import annotations
import json, statistics, time, re
from pathlib import Path
from typing import Any, Dict, List
from status_manager import write_status
from event_deduplicator import iter_unique_events
BASE_DIR = Path(__file__).resolve().parent
_GFL_ARTIFACT_RE = re.compile(r"\b(?:gFn|ngf|nifn|ni5e|nfe|ylf|Sn|S5gg)\b|[吊另墨]", re.I)
_GFL_CREDIT_RE = re.compile(r"CHARACTER\s+VO|ON\s+SCENE|GAME\s+DESIGN|MICA[- ]?TEAM|SUNBORN|TRUE\s+ENDING|PROGRAMMING|VIDEO\s+DESIGN|AUDIO\s+DESIGN", re.I)


def _latest_jsonl(log_dir: Path) -> Path | None:
    files = sorted(log_dir.glob("session_*_events.jsonl"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return files[0] if files else None

def _avg(xs: List[float]) -> float:
    return round(statistics.mean(xs), 2) if xs else 0.0

def _p95(xs: List[float]) -> float:
    if not xs: return 0.0
    xs = sorted(xs)
    return round(xs[min(len(xs)-1, int(len(xs)*0.95))], 2)

def _looks_ocr_noisy_text(text: str) -> bool:
    try:
        from app.ocr.ocr_noise_normalizer import looks_ocr_noisy
        return looks_ocr_noisy(text)
    except Exception:
        s = str(text or "")
        return bool(s.startswith(("I ", "|", "川")) or "thelr" in s.lower() or "volce" in s.lower())


def _recommend(out: Dict[str, Any]) -> List[str]:
    rec = []
    avg_ocr = float(out.get("avg_ocr_ms") or 0)
    avg_tr = float(out.get("avg_translation_ms") or 0)
    hit_rate = float(out.get("cache_hit_rate") or 0)
    runtime_pressure = int(out.get("runtime_pressure_events") or 0)
    ocr_noise = int(out.get("ocr_noise_events") or 0)
    speaker_holds = int(out.get("speaker_candidate_holds") or 0)
    fast_events = int(out.get("fast_engine_events") or 0)
    argos_events = int(out.get("argos_fallback_events") or 0)
    naturalized_hits = int(out.get("naturalized_cache_hits") or 0)
    number_gaps = int(out.get("number_gap_events") or 0)
    lite_events = int(out.get("lite_events") or 0)
    scheduler_holds = int(out.get("dialog_scheduler_holds") or 0)
    hash_skips = int(out.get("ocr_hash_skips") or 0)
    gfl_footer = int(out.get("gfl_footer_artifact_events") or 0)
    gfl_credit = int(out.get("gfl_credit_text_events") or 0)
    gfl_skips = int(out.get("gfl_non_dialog_skips") or 0) + int(out.get("gfl_frame_skips") or 0)
    stable_stores = int(out.get("stable_final_cache_stores") or 0)
    stable_hits = int(out.get("stable_final_cache_hits") or 0)
    progressive_skips = int(out.get("progressive_cache_skips") or 0)
    duplicate_suppressed = int(out.get("duplicate_ocr_suppressed") or 0)
    idn_eval = int(out.get("idn_evaluation_events") or 0)
    gfl2_roi = int(out.get("gfl2_speaker_roi_events") or 0)
    if avg_ocr > 500:
        rec.append("OCR lambat (>500 ms). Turunkan OCR Resolution 5-10%, gunakan CPU/Safe Game untuk WUWA, atau pakai Freeze mode.")
    elif avg_ocr > 300:
        rec.append("OCR agak berat. Untuk WUWA, jaga OCR Resolution 50-58% dan interval 450-700 ms.")
    if avg_tr > 700:
        rec.append("Translate lambat. Pastikan Fast CT2 benar-benar ACTIVE; jika Fast fallback Argos, performa tetap lamban.")
    if argos_events > 0 and fast_events == 0:
        rec.append("Fast fallback Argos terdeteksi. Jalankan Fast Engine Setup Wizard dan lengkapi model CT2 sebelum mengandalkan mode Fast.")
    if scheduler_holds > 5:
        rec.append("Dialog Scheduler aktif menahan teks parsial. Ini normal untuk story yang teksnya mengetik; turunkan stable ms hanya jika dialog terlalu terlambat.")
    if hash_skips > 10:
        rec.append("Image Hash Gate sering skip OCR karena frame dialog tidak berubah. Ini bagus untuk voice-hold dan mengurangi beban.")
    if hit_rate < 0.10 and out.get("translation_samples",0) >= 10 and stable_stores == 0:
        rec.append("Stable Final Cache belum pernah STORE. Periksa commit dialog final sebelum menilai performa model.")
    elif stable_stores > 0 and stable_hits == 0:
        rec.append("Stable Final Cache sudah menyimpan output, tetapi belum HIT. Ulangi scene/dialog sama pada model yang sama untuk validasi replay.")
    elif stable_hits > 0:
        rec.append(f"Stable Final Cache efektif: {stable_hits} HIT dan {duplicate_suppressed} OCR duplicate disuppress.")
    if progressive_skips > 0:
        rec.append(f"Cache melewati {progressive_skips} preview progresif; ini benar untuk Auto mode agar cache tidak tercemar fragmen mengetik.")
    if runtime_pressure > 0:
        rec.append("Runtime pressure terdeteksi. Untuk game berat gunakan Lite IDN V2/V3 + GPU Efficient; hindari V5 sebagai default.")
    if lite_events > 0 and naturalized_hits == 0:
        rec.append("Lite/Lite IDN aktif. Biarkan naturalized cache belajar beberapa sesi agar output IDN lebih konsisten dan CPU lebih ringan.")
    elif naturalized_hits > 0:
        rec.append(f"Naturalized IDN cache mulai efektif ({naturalized_hits} hit). Ini bagus untuk Lite IDN dan dialog berulang.")
    if naturalized_hits > 0:
        rec.append("IDN Quality Layer v8.6: cache naturalisasi aktif; lanjut uji IDN V2/V3/V5 untuk menentukan profil gaya terbaik.")
    if number_gaps > 0:
        rec.append("Masih ada number gap/OCR angka. Setelah v8.5.1 ini dianggap known minor limitation kecuali ada regresi besar.")
    if ocr_noise >= 5:
        rec.append("OCR noise cukup sering. Gunakan OCR Resolution 45-60%, area snip lebih sempit, aktifkan OCR dictionary/game profile, dan bersihkan learning quarantine.")
    if speaker_holds >= 3:
        rec.append("Speaker/NPC kandidat sering tertahan. Gunakan NPC Alias/Merge dan Learning Quarantine agar typo tidak masuk database.")
    if gfl_footer > 0:
        rec.append(f"Terdeteksi {gfl_footer} event artifact footer khas GFL. Pilih game GFL agar GFsystem/footer mask dan artifact filter v8.7.6 aktif.")
    if gfl_credit > 0:
        rec.append(f"Terdeteksi {gfl_credit} event credit/non-dialog GFL. Scene Guard v8.7.6 harus menahan OCR dan learning pada ending/menu.")
    if gfl_skips > 0:
        rec.append(f"GFL Scene Guard aktif dan sudah menahan {gfl_skips} frame/teks non-dialog; ini mencegah database NPC tercemar.")
    if gfl2_roi > 0:
        rec.append(f"GFL2 Speaker ROI membaca/menahan label pada {gfl2_roi} event; tinjau apakah official exact-speaker tampil konsisten.")
    if int(out.get("ocr_readability_rescue_events") or 0) > 0:
        rec.append(f"Adaptive OCR Readability Rescue aktif pada {int(out.get('ocr_readability_rescue_events') or 0)} frame; bandingkan selected OCR% dan keterbacaan overlay.")
    if int(out.get("false_speaker_blocked") or 0) > 0:
        rec.append(f"Exact-only fallback memblok {int(out.get('false_speaker_blocked') or 0)} kandidat speaker palsu; periksa apakah tidak ada label DP/Name/TC/Hybrid.")
    if idn_eval == 0 and out.get("translation_samples", 0) > 0:
        rec.append("IDN Evaluation belum terekam; aktifkan export agar source/backend/final IDN dapat dibandingkan akurasinya.")
    if int(out.get("entity_residual_blocked") or 0) > 0:
        rec.append("Entity residual marker diblok; kirim Debug Bundle karena placeholder internal tidak boleh mencapai overlay/cache.")
    if int(out.get("latest_frame_wins") or 0) > 0:
        rec.append(f"Mode Responsif membuang {int(out.get('latest_frame_wins') or 0)} pekerjaan lama; bandingkan final-output dan latency untuk story cepat.")
    if int(out.get("semantic_hallucination_blocked") or 0) > 0:
        rec.append(f"Faithfulness v2 memblok {int(out.get('semantic_hallucination_blocked') or 0)} output tidak setia; tinjau debug bundle untuk memastikan tidak ada injection lolos.")
    if int(out.get("qur_corruption_repaired") or 0) + int(out.get("qur_corruption_quarantined") or 0) > 0:
        rec.append("Qur OCR quarantine aktif; tinjau frame sumber untuk mengonfirmasi perbaikan our/your tidak salah konteks.")
    if int(out.get("argos_progressive_suppressed") or 0) > 0:
        rec.append("Strict CT2 Story menahan fallback Argos pada source progressive/noisy; bandingkan completeness dan delay overlay final.")
    if not rec:
        rec.append("Sesi terlihat sehat. Lanjutkan pengujian dengan durasi lebih lama untuk validasi stabilitas.")
    return rec

def analyze_session(path: str | Path | None = None, base_dir: str | Path | None = None) -> Dict[str, Any]:
    base = Path(base_dir or BASE_DIR).resolve()
    p = Path(path) if path else _latest_jsonl(base / "logs")
    if not p or not p.exists():
        out = {"version":"v8.7.8", "ok":False, "reason":"No session JSONL found", "path":""}
        write_status("benchmark_session", out, base); return out
    raw_events = []
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                item = json.loads(line)
                if isinstance(item, dict): raw_events.append(item)
            except Exception:
                continue
    events = list(iter_unique_events(raw_events))
    counts: Dict[str,int] = {}
    by_source: Dict[str,int] = {}
    trans_ms: List[float] = []
    ocr_ms: List[float] = []
    capture_ms: List[float] = []
    preprocess_ms: List[float] = []
    body_ocr_ms: List[float] = []
    name_roi_ms: List[float] = []
    numeric_retry_ms: List[float] = []
    thin_glyph_ms: List[float] = []
    entity_match_ms: List[float] = []
    backend_translate_ms: List[float] = []
    idn_post_ms: List[float] = []
    queue_wait_ms: List[float] = []
    cache_hits = cache_miss = online = fast = runtime_pressure = engine_switch = vault_hits = 0
    naturalized_cache_hits = number_gap_events = lite_events = 0
    ocr_noise_events = speaker_candidate_holds = 0
    dialog_scheduler_holds = ocr_hash_skips = argos_fallback_events = 0
    gfl_footer_artifact_events = gfl_credit_text_events = gfl_non_dialog_skips = gfl_frame_skips = 0
    stable_final_cache_stores = stable_final_cache_hits = progressive_cache_skips = duplicate_ocr_suppressed = 0
    idn_evaluation_events = idn_warmup_events = gfl2_speaker_roi_events = ocr_resolution_changes = 0
    residual_entity_blocked = entity_fallback_used = latest_frame_wins = responsive_coalesced = 0
    ocr_readability_rescue_events = false_speaker_blocked = fallback_speaker_rejected = 0
    semantic_blocked = semantic_cache_rejected = preview_held = omission_suspected = ct2_job_fallback = idn_quality_lock_held = 0
    qur_repaired = qur_quarantined = strict_ct2_held = argos_progressive_suppressed = training_safety_blocked = 0
    for item in events:
        typ = str(item.get("type") or "LOG")
        counts[typ] = counts.get(typ,0)+1
        srcmod = str(item.get("source_module") or "unknown")
        by_source[srcmod] = by_source.get(srcmod,0)+1
        payload = item.get("payload") or {}
        if not isinstance(payload, dict): payload = {}
        lm = payload.get("latency_ms") or payload.get("ms") or payload.get("total_ms")
        if typ.startswith("TRANSLATION") and lm not in (None, ""):
            try: trans_ms.append(float(lm))
            except Exception: pass
        if typ.startswith("OCR"):
            text = str(payload.get("text") or payload.get("source") or "")
            if _looks_ocr_noisy_text(text):
                ocr_noise_events += 1
            if _GFL_ARTIFACT_RE.search(text):
                gfl_footer_artifact_events += 1
            if _GFL_CREDIT_RE.search(text):
                gfl_credit_text_events += 1
            for key, bucket in [("latency_ms", ocr_ms),("ocr_ms", ocr_ms),("total_ms", ocr_ms)]:
                val = payload.get(key)
                if val not in (None, ""):
                    try: bucket.append(float(val)); break
                    except Exception: pass
            for key, bucket in [("capture_ms", capture_ms),("preprocess_ms", preprocess_ms),("body_ocr_ms", body_ocr_ms),("name_roi_ms", name_roi_ms),("numeric_retry_ms", numeric_retry_ms),("thin_glyph_ms", thin_glyph_ms),("queue_wait_ms", queue_wait_ms)]:
                val = payload.get(key)
                if val not in (None, ""):
                    try: bucket.append(float(val))
                    except Exception: pass
        for key, bucket in [("entity_match_ms", entity_match_ms),("backend_translate_ms", backend_translate_ms),("idn_post_ms", idn_post_ms),("queue_wait_ms", queue_wait_ms)]:
            val = payload.get(key)
            if val not in (None, ""):
                try: bucket.append(float(val))
                except Exception: pass
        cache = str(payload.get("cache") or payload.get("cache_status") or "").upper()
        if "NATURALIZED" in cache: naturalized_cache_hits += 1
        if "VAULT_HIT" in cache: vault_hits += 1
        if "HIT" in cache: cache_hits += 1
        if "MISS" in cache: cache_miss += 1
        engine = str(payload.get("engine") or "").lower()
        if "online" in engine: online += 1
        if "ct2" in engine or "fast" in engine: fast += 1
        joined_model = (json.dumps(payload, ensure_ascii=False) + " " + str(payload.get("strategy", ""))).lower()
        if "lite" in joined_model: lite_events += 1
        if "number_gap" in joined_model or "missing_degree_value" in joined_model or "missing_meter_value" in joined_model: number_gap_events += 1
        if typ in {"RUNTIME_PRESSURE", "RUNTIME_ACTION", "RUNTIME_HEALTH_WARNING"}: runtime_pressure += 1
        if typ == "ENGINE_SWITCH": engine_switch += 1
        if typ == "DIALOG_SCHEDULER_HOLD": dialog_scheduler_holds += 1
        if typ == "OCR_HASH_SKIPPED": ocr_hash_skips += 1
        if typ == "GFL_NON_DIALOG_TEXT_SKIPPED": gfl_non_dialog_skips += 1
        if typ == "GFL_NON_DIALOG_FRAME_SKIPPED": gfl_frame_skips += 1
        if typ == "CACHE_STORE_STABLE_FINAL": stable_final_cache_stores += 1
        if typ == "CACHE_HIT_STABLE_FINAL": stable_final_cache_hits += 1
        if typ == "CACHE_SKIP_PROGRESSIVE": progressive_cache_skips += 1
        if typ == "CACHE_DUPLICATE_OCR_SUPPRESSED": duplicate_ocr_suppressed += 1
        if typ == "IDN_EVALUATION": idn_evaluation_events += 1
        if typ == "IDN_WARMUP_DONE": idn_warmup_events += 1
        if typ in {"GFL2_SPEAKER_ROI", "GFL2_SPEAKER_SELECTED", "GFL2_RAW_NAME_ROI"}: gfl2_speaker_roi_events += 1
        if typ == "OCR_RESOLUTION_CHANGED": ocr_resolution_changes += 1
        if typ == "ENTITY_RESIDUAL_BLOCKED": residual_entity_blocked += 1
        if typ == "ENTITY_FALLBACK_USED": entity_fallback_used += 1
        if typ == "LATEST_FRAME_WINS": latest_frame_wins += 1
        if typ == "RESPONSIVE_QUEUE_COALESCED": responsive_coalesced += 1
        if typ == "OCR_READABILITY_RESCUE": ocr_readability_rescue_events += 1
        if typ == "FALSE_SPEAKER_BLOCKED": false_speaker_blocked += 1
        if typ == "SEMANTIC_HALLUCINATION_BLOCKED": semantic_blocked += 1
        if typ == "SEMANTIC_CACHE_REJECTED": semantic_cache_rejected += 1
        if typ == "PREVIEW_HELD_INCOMPLETE": preview_held += 1
        if typ == "OMISSION_SUSPECTED": omission_suspected += 1
        if typ == "CT2_JOB_FALLBACK": ct2_job_fallback += 1
        if typ == "IDN_QUALITY_LOCK_HELD": idn_quality_lock_held += 1
        if typ == "OCR_QUR_CORRUPTION_REPAIRED": qur_repaired += 1
        if typ == "QUR_CORRUPTION_QUARANTINED": qur_quarantined += 1
        if typ == "STRICT_CT2_STORY_HELD": strict_ct2_held += 1
        if typ == "STRICT_CT2_STORY_FALLBACK_SUPPRESSED": argos_progressive_suppressed += 1
        if typ == "TRAINING_SAMPLE_BLOCKED_BY_SAFETY_GATE": training_safety_blocked += 1
        if typ == "GFL2_FALLBACK_SPEAKER_REJECTED": fallback_speaker_rejected += 1
        if "argos" in engine: argos_fallback_events += 1
        joined = (typ + " " + json.dumps(payload, ensure_ascii=False)).lower()
        if "speaker candidate held" in joined or "candidate_hold" in joined:
            speaker_candidate_holds += 1
    out = {
        "version":"v8.7.8", "ok":True, "ts":time.time(), "path":str(p),
        "raw_events": len(raw_events), "unique_events": len(events), "deduped_events": max(0, len(raw_events)-len(events)),
        "counts": counts, "by_source_module": by_source,
        "avg_translation_ms": _avg(trans_ms), "p95_translation_ms": _p95(trans_ms),
        "avg_ocr_ms": _avg(ocr_ms), "p95_ocr_ms": _p95(ocr_ms),
        "avg_capture_ms": _avg(capture_ms), "avg_preprocess_ms": _avg(preprocess_ms),
        "avg_body_ocr_ms": _avg(body_ocr_ms), "avg_name_roi_ms": _avg(name_roi_ms), "avg_numeric_retry_ms": _avg(numeric_retry_ms), "avg_thin_glyph_ms": _avg(thin_glyph_ms),
        "avg_entity_match_ms": _avg(entity_match_ms), "avg_backend_translate_ms": _avg(backend_translate_ms), "avg_idn_post_ms": _avg(idn_post_ms), "avg_queue_wait_ms": _avg(queue_wait_ms),
        "translation_samples": len(trans_ms), "ocr_samples": len(ocr_ms),
        "cache_hits": cache_hits, "cache_miss": cache_miss,
        "cache_hit_rate": round(cache_hits / max(1, cache_hits + cache_miss), 4),
        "online_assist_events": online, "fast_engine_events": fast, "legacy_vault_hits": vault_hits,
        "runtime_pressure_events": runtime_pressure, "engine_switch_events": engine_switch,
        "ocr_noise_events": ocr_noise_events, "speaker_candidate_holds": speaker_candidate_holds,
        "dialog_scheduler_holds": dialog_scheduler_holds, "ocr_hash_skips": ocr_hash_skips, "argos_fallback_events": argos_fallback_events,
        "naturalized_cache_hits": naturalized_cache_hits, "number_gap_events": number_gap_events, "lite_events": lite_events,
        "gfl_footer_artifact_events": gfl_footer_artifact_events, "gfl_credit_text_events": gfl_credit_text_events,
        "gfl_non_dialog_skips": gfl_non_dialog_skips, "gfl_frame_skips": gfl_frame_skips,
        "stable_final_cache_stores": stable_final_cache_stores, "stable_final_cache_hits": stable_final_cache_hits,
        "progressive_cache_skips": progressive_cache_skips, "duplicate_ocr_suppressed": duplicate_ocr_suppressed,
        "idn_evaluation_events": idn_evaluation_events, "idn_warmup_events": idn_warmup_events,
        "gfl2_speaker_roi_events": gfl2_speaker_roi_events, "ocr_resolution_changes": ocr_resolution_changes,
        "entity_residual_blocked": residual_entity_blocked, "entity_fallback_used": entity_fallback_used, "latest_frame_wins": latest_frame_wins, "responsive_queue_coalesced": responsive_coalesced,
        "ocr_readability_rescue_events": ocr_readability_rescue_events, "false_speaker_blocked": false_speaker_blocked, "fallback_speaker_rejected": fallback_speaker_rejected,
        "semantic_hallucination_blocked": semantic_blocked, "semantic_cache_rejected": semantic_cache_rejected, "preview_held_incomplete": preview_held, "omission_suspected": omission_suspected, "ct2_job_fallback": ct2_job_fallback, "idn_quality_lock_held": idn_quality_lock_held,
        "qur_corruption_repaired": qur_repaired, "qur_corruption_quarantined": qur_quarantined, "strict_ct2_story_held": strict_ct2_held, "argos_progressive_suppressed": argos_progressive_suppressed, "training_safety_blocked": training_safety_blocked,
    }
    out["recommendations"] = _recommend(out)
    write_status("benchmark_session", out, base)
    txt = ["ORT Translation v8.7.8 Session Benchmark", "====================================", f"Log: {p}", f"Raw events: {len(raw_events)}", f"Unique events: {len(events)}", f"Deduped: {out['deduped_events']}", f"Avg OCR ms: {out['avg_ocr_ms']} | p95: {out['p95_ocr_ms']}", f"Avg Translate ms: {out['avg_translation_ms']} | p95: {out['p95_translation_ms']}", f"Stage ms avg: body={out['avg_body_ocr_ms']} nameROI={out['avg_name_roi_ms']} entity={out['avg_entity_match_ms']} backend={out['avg_backend_translate_ms']} idn={out['avg_idn_post_ms']} queue={out['avg_queue_wait_ms']}", f"Entity residual blocked/fallback: {residual_entity_blocked}/{entity_fallback_used}", f"Responsive latest/coalesced: {latest_frame_wins}/{responsive_coalesced}", f"Adaptive OCR rescue / false speaker blocked: {ocr_readability_rescue_events}/{false_speaker_blocked}", f"Semantic blocked / semantic cache rejected: {semantic_blocked}/{semantic_cache_rejected}", f"Preview held / omission suspected: {preview_held}/{omission_suspected}", f"CT2 job fallback / IDN quality lock held: {ct2_job_fallback}/{idn_quality_lock_held}", f"Qur repaired/quarantined: {qur_repaired}/{qur_quarantined}", f"Strict CT2 held / Argos progressive suppressed: {strict_ct2_held}/{argos_progressive_suppressed}", f"Training blocked by safety gate: {training_safety_blocked}", f"Cache hit rate: {out['cache_hit_rate']}", f"Runtime pressure events: {runtime_pressure}", f"OCR noise events: {ocr_noise_events}", f"Speaker candidate holds: {speaker_candidate_holds}", f"Dialog scheduler holds: {dialog_scheduler_holds}", f"OCR hash skips: {ocr_hash_skips}", f"Argos fallback events: {argos_fallback_events}", f"Legacy vault hits: {vault_hits}", f"Naturalized cache hits: {naturalized_cache_hits}", f"Number gap events: {number_gap_events}", f"Lite events: {lite_events}", f"GFL footer artifact events: {gfl_footer_artifact_events}", f"GFL credit/non-dialog OCR events: {gfl_credit_text_events}", f"GFL text skips: {gfl_non_dialog_skips}", f"GFL frame skips: {gfl_frame_skips}", f"Online events: {online}", f"Fast events: {fast}", f"Stable final cache stores: {stable_final_cache_stores}", f"Stable final cache hits: {stable_final_cache_hits}", f"Progressive cache skips: {progressive_cache_skips}", f"Duplicate OCR suppressed: {duplicate_ocr_suppressed}", f"IDN evaluation events: {idn_evaluation_events}", f"IDN warmup events: {idn_warmup_events}", f"GFL2 speaker ROI events: {gfl2_speaker_roi_events}", f"OCR resolution changes: {ocr_resolution_changes}", "", "Recommendations:"]
    txt += [f"- {r}" for r in out["recommendations"]]
    txt += ["", "Event counts:"] + [f"- {k}: {v}" for k,v in sorted(counts.items())]
    txt += ["", "Source modules:"] + [f"- {k}: {v}" for k,v in sorted(by_source.items())]
    (base/"status").mkdir(exist_ok=True)
    (base/"status"/"benchmark_session.txt").write_text("\n".join(txt), encoding="utf-8")
    (base/"status"/"benchmark_session_recommendation.txt").write_text("\n".join(out["recommendations"]), encoding="utf-8")
    return out

def main() -> int:
    data = analyze_session()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
