# ORT Translation Strategy Memory — Mode Buffer, Prediction Guard, Offline Replay Benchmark

Date: 2026-06-01
Purpose: Preserve current roadmap and strategic decisions so they can be recovered after ChatGPT memory reset or when continuing from a future ORT ZIP.

## 1. Core Direction

The project is moving toward a stable release by reducing these recurring issues:

- Translation output not full / only 20–90% of visible game dialog.
- Overlay blank/stale while game dialog is still active.
- Auto mode still not fully natural like visual novel text progression.
- Interval and Freeze modes not yet separated clearly enough from Auto.
- Low OCR models at 40–45% still producing severe OCR churn.
- Cache sometimes trusting corrupted OCR.
- Name/term OCR errors creating risk of wrong correction or hallucination.
- Need for long-session recording logs to improve future story sessions.

Important principle:
Accuracy improvements must not make Auto Story feel slow, stuttery, or heavy. Preview must remain responsive. Heavy checks, consensus, replay analysis, and final-quality work must be placed on final lane or offline tooling when possible.

## 2. Mode Buffer

User selected the feature name:

```text
☐ Mode Buffer
```

UI placement:
- Put checkbox under/after `Pilih Model`.
- Label: `Mode Buffer`.
- Add a small `?` help button/icon beside it.
- Hovering the label/checkbox for a moment should show a tooltip.
- Hovering or pressing the `?` button should show the same explanation.

Suggested tooltip:

```text
Mode Buffer menambahkan jeda kecil terkontrol untuk membantu hasil terjemahan tampil lebih lengkap dan stabil saat rekaman story. Mode ini cocok untuk perekaman, tetapi dapat menambah sedikit latensi. Jika dimatikan, program kembali ke mode normal.
```

Runtime requirements:
- Default OFF.
- ON means controlled buffer is enabled, for example 500–1000 ms for final/recording stability.
- OFF means normal runtime immediately, with:
  - no pending buffer timer left,
  - no delayed final state left,
  - no hidden recording state left,
  - no stale mode flag,
  - no “lupa mode” bug.

State should be explicit:

```json
{
  "mode_buffer_enabled": false,
  "mode_buffer_ms": 0
}
```

When ON:

```json
{
  "mode_buffer_enabled": true,
  "mode_buffer_ms": 700
}
```

Mode Buffer must not freeze the entire pipeline. Preview remains fast; only final/commit timing is buffered.

## 3. Temporal OCR Consensus

Temporal OCR Consensus is not guaranteed to be zero cost. It must be designed so it does not make Auto feel slow.

Correct architecture:

```text
OCR fast frame -> fast preview lane -> overlay quickly
OCR frames over short window -> consensus/final lane -> best_source_consensus -> final commit
```

Forbidden architecture:

```text
OCR -> wait for consensus -> translate -> overlay
```

Rules:
- Do not block preview.
- Store only a small window, for example last 3–7 OCR strings per turn.
- Compare strings/tokens lightly.
- Do not translate every candidate.
- Translate only best source / consensus source for final lane.
- Use time budget, for example 50–120 ms for low-cost consensus work.
- Final commit may replace preview when source is more complete.

Goal:
- Reduce OCR frame noise.
- Help low OCR 40–45% without raising global OCR level.
- Improve final completeness.
- Avoid stutter.

## 4. Prediction / Repair Text

Prediction / Repair Text must be built as a guarded confidence system, not blind auto-correct.

Sources:
1. Known registry:
   - verified character names,
   - NPC names,
   - user-configured Commander,
   - official terms,
   - retained story terms.
2. Offline Replay Benchmark analysis:
   - recurring OCR aliases,
   - character-name confusion,
   - term confusion,
   - false positives,
   - negative rules.
3. Runtime context:
   - speaker ROI,
   - temporal consensus,
   - repeated occurrence,
   - exact registry match,
   - OCR corruption score.

Confidence labels:
- Green: very high confidence, exact or near-exact with strong context.
- Yellow: plausible prediction, allowed for guarded preview/review, should not be blindly cached as final.
- Red: uncertain, do not auto-fix; log/review only.

Critical anti-hallucination guard:
- Do not auto-correct names from very weak OCR.
- `Helen` and `Helena` must remain separate.
- OCR fragments such as `heln`, `helm`, `hlena`, `elena`, `helna` must NOT be automatically decided as Helen/Helena unless strong speaker ROI or temporal evidence supports it.
- Prediction in yellow/red must not enter final cache as if verified.
- Commander/profile names must be scoped per user/profile.

Examples of allowed guarded candidates:
- `Nlkketa -> Nikketa` with confidence Yellow/Green only if registry/context supports.
- `Blig Sls -> Big Sis` with confidence Yellow because phrase prediction can be risky.
- `LvIv/Lvh/LvN -> Lviv` with confidence Yellow/Green if location/story context supports.
- `Belf-audit -> self-audit` as guarded term correction.
- `Berryfleld/Borryflold -> Berryfield` with exact-aware guard.
- `Hlon -> Helen` only with strong speaker ROI, never blind global mapping.

Negative rules:
- Do not map `Hlon` to Helen if Helena is also plausible and context is weak.
- Do not map ARVITA/ATVITA/AFVITA cluster to main Commander.
- Do not treat prediction candidates as official NPCs.
- Do not auto-promote unseen candidate names globally.
- Do not repair common words aggressively if it can alter meaning.

## 5. Offline Replay Benchmark

Offline Replay Benchmark should process uploaded long logs/recordings to identify patterns of failure, not memorize old story lines.

Correct use:
- Analyze story 1 and story 2 logs.
- Extract general error patterns.
- Convert those patterns into reusable guards/rules/metrics.
- Improve story 3 even if story 3 has never been tested.

Wrong use:
- Hard-code exact old story sentences.
- Build cache that only passes old logs.
- Overfit to previous OCR text.

Patterns to extract:
- OCR churn pattern.
- Final miss pattern.
- Source longer suppressed.
- Stale overlay / excessive repaint_last_good.
- Bad cache hit risk.
- Name prediction ambiguity.
- UI/non-dialog leakage.
- Turn expired before final_complete.
- Low OCR corruption patterns.
- Speaker ROI failure.

Replay-derived rules should include:
- If valid source grows longer, it should override MIN_VISIBLE.
- If OCR corruption score is high, do not trust stable/fuzzy/naturalized cache.
- If name is ambiguous, label Yellow/Red instead of auto-fix.
- If turn has not committed final_complete, do not expire silently.
- If last_good is reused too long, force final/source fallback.
- If UI/non-dialog text is detected, do not commit as story dialog.

## 6. Commander and Identity Rules

Main user Commander:

```text
Raizei
```

This must be treated as the current main user-configured Commander name.

ARVITA/ATVITA/AFVITA cluster:

```text
ARVITA ID
ArVITA ID
ATVITA ID
AFVITA ID
ArVITAID
ATVITA IO
```

This cluster is NOT the main Commander. It belongs to another account/example/alternate profile candidate. It must not be promoted as main Commander and must not be added to global NPC roster.

`Commander` is a generic title/role, not a profile name.

## 7. Roadmap Placement

Recommended next updates:

### v8.8.6
- Mandatory Final Commit v2.
- Temporal OCR Consensus on final lane only.
- Low-OCR Visual Rescue.
- Stale Overlay Limit.
- Bad Cache Shield v2.
- Experimental `☐ Mode Buffer` default OFF.

### v8.8.7
- Name/Term Prediction Guard.
- Helen/Helena ambiguity guard.
- Commander Profile Resolver.
- Green/Yellow/Red confidence label.
- Prediction review queue / telemetry.

### v8.8.8
- Offline Replay Benchmark tool.
- Long-session analyzer.
- Auto/Interval/Freeze policy separation.
- Recording story benchmark metrics.

### v8.9.0
- Stable Candidate.

Stable criteria:
- Final complete ratio high, ideally 75–85%+ on Normal/IDN models.
- No blank overlay while dialog is active.
- Reduced stale overlay.
- Low OCR 40–45% usable with rescue.
- Argos story fallback 0 when CT2 available.
- Prediction does not create hallucination.
- Cache guarded against corrupted OCR.
- UI leakage minimized.

## 8. Key Principle for Future ChatGPT Sessions

If this file is read in a future conversation after memory reset, continue with this rule:

```text
Do not solve OCR/translation quality by making Auto Story slow.
Keep preview fast, put consensus/final checks in final lane, use Mode Buffer only when user enables it, and keep prediction/repair guarded with confidence labels.
```
