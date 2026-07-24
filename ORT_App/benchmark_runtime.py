from pathlib import Path
import json, time
from status_manager import read_status, write_status, status_dir, status_summary
BASE_DIR=Path(__file__).resolve().parent
KEYS=["strategy","runtime_health","runtime_actions","core_bridge","core_profile","cache","fast_engine","online_assist","translation_engine","shutdown","session_log","online_config","dependency_check","benchmark_session"]
def main():
    data={k:read_status(k,BASE_DIR,{"missing":True}) for k in KEYS}
    rep={"version":"v7.9","ts":time.time(),"status_dir":str(status_dir(BASE_DIR)),"summary":status_summary(BASE_DIR),"files":data}
    write_status("benchmark", rep, BASE_DIR)
    txt="ORT Translation v7.9 Runtime Status Summary\n"+"\n".join(f"{k}: {'OK' if not v.get('missing') else 'MISSING'}" for k,v in data.items())
    (BASE_DIR/"status"/"benchmark.txt").write_text(txt,encoding="utf-8")
    print(txt); return 0
if __name__=="__main__": raise SystemExit(main())
