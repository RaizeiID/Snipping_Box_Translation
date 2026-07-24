"""Dry-run/apply semantic cache rotation for ORT v8.7.9 Faithfulness v2."""
from __future__ import annotations
import argparse, re, shutil, time
from pathlib import Path
NEW_NAMESPACE="v8_7_9_responsive_turn_safe_ct2"
OLD_NAMESPACES=("v8_7_2","v8_7_3_identity_guard","v8_7_4_entity_span_responsive","v8_7_5_verified_exact_entity_safe","v8_7_6_adaptive_ocr_exact_safe","v8_7_7_faithful_complete_ct2_safe","v8_7_8_faithfulness_v2_strict_ct2_safe")
CONTAMINATED_RE=re.compile(r"(?:__|_\s*_).*?ORT|\bORT\s*[_ -]+\s*(?:ENTITY|BKEND|BKED|BEND|BACKEND)\b|Phaedusa|Balthalde|Helena\s+Helen|para\s+nabi|al\s*[- ]?qur\s*['’ ]*a?n|\bqur\s*['’ ]*a?n\b|\bAlquran\b|\bQuran\b|\bayat\b|\bzakat\b|\bsurat\s+al\b|\bNabi\s+(?:Luth|Syuaib)\b|\bMekah\b|\bmalaikat\b|\bkafir\b|\bmukmin\b|\bneraka\b|\bkiamat\b|sekaratul\s+maut|\bmakkiy+ah\b|\bmubtada\b|Al[- ]?masy[aâ]riq|al[- ]?magh[aâ]rib", re.I)
def scan(base:Path):
    rows=[]
    for path in sorted((base/'cache').glob('*.json')) if (base/'cache').exists() else []:
        try: text=path.read_text(encoding='utf-8-sig',errors='replace')
        except Exception: continue
        reasons=[]
        if any(x in path.name or x in text for x in OLD_NAMESPACES): reasons.append('old_namespace')
        if CONTAMINATED_RE.search(text): reasons.append('faithfulness_v2_semantic_or_internal_contamination')
        if reasons: rows.append((path, sorted(set(reasons))))
    return rows
def run(base_dir='.', apply=False):
    base=Path(base_dir).resolve(); rows=scan(base)
    lines=['ORT Translation v8.7.9 Semantic Cache Rotation '+('APPLY' if apply else 'DRY-RUN'), f'Target namespace: {NEW_NAMESPACE}', f'Candidates: {len(rows)}']
    for p,reasons in rows: lines.append(f'- {p.name}: {", ".join(reasons)}')
    if not apply:
        lines.append('Gunakan --apply hanya pada clone TEST; cache v8.7.7 dapat memuat varian tafsir/al-Qur/zakat yang harus diisolasi.')
        return '\n'.join(lines)
    backup=base/'backups'/f'cache_before_v8_7_9_faithfulness_v2_{time.strftime("%Y%m%d_%H%M%S")}'
    backup.mkdir(parents=True, exist_ok=True)
    for p,_ in rows: shutil.move(str(p), str(backup/p.name))
    lines.append(f'Backup dibuat: {backup.relative_to(base)}')
    return '\n'.join(lines)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--base-dir',default='.'); ap.add_argument('--apply',action='store_true'); a=ap.parse_args(); print(run(a.base_dir,a.apply)); return 0
if __name__=='__main__': raise SystemExit(main())
