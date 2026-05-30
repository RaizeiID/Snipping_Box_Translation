from __future__ import annotations
import argparse, json, shutil, time
from pathlib import Path

BLOCK = {"Thelr","Rashly","Clack","Along","Tothat","Helen Hehe","Helen's","Helens","Helenve","Paradeus'",
 "Familiar","Kalinais","Shortly","Afaint","Ablade","Arasping","Facing","Conference","Character","Girls'",
 "Programming","TEAM","VIDEO","Sunborn","Designer","AUDIO","Still","Feeling","Foreven","Late","Noticing",
 "Betterto","Haha","Reasons","Allow","Pretty","Sensing","Every","Hereyes","Her","Tillthe","Ah","Ail",
 "Ohnoare","Another","Decommisslon","Griffin's","Asimple","Yeah","Ten","Soshes","Dontworry",
 "Decommission","Analarm","Don't","Finally","Gazing"}
MIGRATE = {"DP":"DP-12", "Dp":"DP-12", "dp":"DP-12"}
# Helen and Helena are both valid distinct characters and are never merged.
PROTECTED = {"DP-12","KSVK","Helen","Helena","Melanie","Balthilde","Phaetusa","Alya Kujou"}

def cleanup(base_dir=None, backup: bool=True, dry_run: bool=False):
    base=Path(base_dir or Path(__file__).resolve().parents[1]); p=base/'npc_database.json'
    if not p.exists(): return 'NPC cleanup: npc_database.json tidak ditemukan.'
    try: data=json.loads(p.read_text(encoding='utf-8-sig'))
    except Exception as exc: return f'NPC cleanup gagal membaca database: {exc}'
    known=list(data.get('known',[])); counts=data.get('counts',{}) if isinstance(data.get('counts',{}),dict) else {}
    removed=[]; kept=list(PROTECTED)
    for name in known:
        text=str(name or '').strip()
        if text in PROTECTED: kept.append(text); continue
        if text in MIGRATE:
            kept.append(MIGRATE[text]); removed.append((text,f'merged_to_{MIGRATE[text]}')); continue
        if not text or text in BLOCK or text.endswith("'s"):
            removed.append((text,'legacy_untrusted')); continue
        kept.append(text)
    proposed=sorted(dict.fromkeys(kept), key=len, reverse=True)
    mode='DRY-RUN' if dry_run else 'APPLIED'; out=None
    if not dry_run:
        if backup:
            out=base/'backups'/f'npc_database_backup_before_v8_7_4_{time.strftime("%Y%m%d_%H%M%S")}.json'; out.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,out)
        data['known']=proposed; data['v8_7_4_note']='Helen and Helena preserved as distinct canonical speakers; live Name ROI uses trusted registry only.'
        p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=[f'NPC cleanup v8.7.4 {mode} (legacy separated; Helen/Helena dual canonical protected).',f'Sebelum: {len(known)}',f'Sesudah usulan: {len(proposed)}',f'Dibersihkan/merge: {len(removed)}','Dilindungi: '+', '.join(sorted(PROTECTED))]
    if out: lines.append(f'Backup: {out}')
    if removed:
        lines.append('\nEntries removed/merged:'); lines.extend(f'- {n or "<empty>"}: {r}' for n,r in removed[:120])
    return '\n'.join(lines)

def main():
    ap=argparse.ArgumentParser(description='Clean legacy NPC entries for ORT v8.7.4 without merging Helen/Helena.')
    ap.add_argument('--base-dir', default=None); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--no-backup', action='store_true'); a=ap.parse_args()
    print(cleanup(a.base_dir, backup=not a.no_backup, dry_run=a.dry_run)); return 0
if __name__=='__main__': raise SystemExit(main())
