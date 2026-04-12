from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List
ROOT = Path(__file__).resolve().parent
@dataclass(frozen=True)
class ModelPreset:
    key: str; title: str; script: str; family: str; tier: str; order: int; summary: str; details: str; default_interval_ms: int=220; default_game: str='GFL2_EXILIUM'
    @property
    def path(self)->Path: return ROOT / self.script
    @property
    def exists(self)->bool: return True
GAME_PRESETS = {
 'GFL2_EXILIUM': {'label':'GFL2','theme':'gfl2','log_hint':'Profil hijau GFL2 aktif. Nama dan panggilan karakter bisa diolah setelah sesi selesai.','env':{'TITAN_GAME_OVERRIDE':'gfl2','TITAN_GAME_PROFILE':'GFL2_EXILIUM'}},
}
MODEL_PRESETS = [
 ModelPreset('v1','ORTCore V1','TITANMAIN.py','V1','basic',10,'Paling ringan.','Model dasar tercepat untuk perangkat lemah.',180),
 ModelPreset('v2','ORTCore V2','TITANMAIN.py','V2','basic',20,'Seimbang.','Versi seimbang untuk penggunaan umum.',220),
 ModelPreset('v3','ORTCore V3','TITANMAIN.py','V3','basic',30,'Berat dan akurat.','Model fokus akurasi.',300),
 ModelPreset('v4','ORTCore V4','TITANMAIN.py','V4','basic',40,'Hybrid online + offline.','Mode hybrid cepat dan akurat.',220),
 ModelPreset('v5','ORTCore V5','TITANMAIN.py','V5','basic',45,'Naturalisasi maksimal.','V5 naturalisasi maksimal.',220),
 ModelPreset('v5lv1','ORTCore V5 Lv1','TITANMAIN.py','V5','basic',50,'Naturalisasi ringan.','Paket naturalisasi V5 berbasis V1.',180),
 ModelPreset('v5lv2','ORTCore V5 Lv2','TITANMAIN.py','V5','basic',51,'Naturalisasi seimbang.','Paket naturalisasi V5 berbasis V2.',220),
 ModelPreset('v5lv3','ORTCore V5 Lv3','TITANMAIN.py','V5','basic',52,'Naturalisasi akurat.','Paket naturalisasi V5 berbasis V3.',300),
 ModelPreset('v5lv4','ORTCore V5 Lv4','TITANMAIN.py','V5','basic',53,'Naturalisasi hybrid maksimal.','Paket naturalisasi V5 berbasis V4.',220),
 ModelPreset('v1lite','ORTCore V1 Lite','TITANMAIN.py','V1','lite',110,'V1 versi lebih hemat.','Untuk perangkat sangat terbatas.'),
 ModelPreset('v2lite','ORTCore V2 Lite','TITANMAIN.py','V2','lite',120,'V2 versi hemat.','Menjaga karakter V2 dengan beban lebih rendah.'),
 ModelPreset('v3lite','ORTCore V3 Lite','TITANMAIN.py','V3','lite',130,'V3 lebih ringan.','Mempertahankan karakter V3 sambil memangkas beban.'),
 ModelPreset('v4lite','ORTCore V4 Lite','TITANMAIN.py','V4','lite',140,'Hybrid lebih ringan.','Pilihan hybrid untuk perangkat menengah ke bawah.'),
 ModelPreset('v5lite','ORTCore V5 Lite','TITANMAIN.py','V5','lite',145,'V5 lebih hemat.','Naturalisasi V5 dengan beban lebih rendah.'),
 ModelPreset('v5lv1lite','ORTCore V5 Lv1 Lite','TITANMAIN.py','V5','lite',150,'V5 Lv1 lebih hemat.','Naturalisasi ringan dengan beban paling rendah.'),
 ModelPreset('v5lv2lite','ORTCore V5 Lv2 Lite','TITANMAIN.py','V5','lite',151,'V5 Lv2 lebih hemat.','Naturalisasi seimbang dengan beban dipangkas.'),
 ModelPreset('v5lv3lite','ORTCore V5 Lv3 Lite','TITANMAIN.py','V5','lite',152,'V5 Lv3 lebih hemat.','Akurasi kuat dengan beban sedikit lebih ringan.'),
 ModelPreset('v5lv4lite','ORTCore V5 Lv4 Lite','TITANMAIN.py','V5','lite',153,'V5 Lv4 lebih hemat.','Hybrid naturalisasi kuat dengan efisiensi lebih baik.'),
 ModelPreset('v1idn','ORTCore V1 IDN','TITANMAIN.py','V1','idn',210,'V1 dengan naturalisasi dasar.','Basis sangat ringan namun hasil lebih rapi.'),
 ModelPreset('v1liteidn','ORTCore V1 Lite IDN','TITANMAIN.py','V1','idn',211,'V1 Lite dengan naturalisasi.','Lite + IDN.'),
 ModelPreset('v2idn','ORTCore V2 IDN','TITANMAIN.py','V2','idn',220,'V2 dengan naturalisasi.','Pilihan seimbang dengan susunan bahasa Indonesia lebih halus.'),
 ModelPreset('v2liteidn','ORTCore V2 Lite IDN','TITANMAIN.py','V2','idn',221,'V2 Lite dengan naturalisasi.','Lite + IDN.'),
 ModelPreset('v3idn','ORTCore V3 IDN','TITANMAIN.py','V3','idn',230,'V3 dengan naturalisasi.','Akurasi tinggi dengan rasa bahasa Indonesia lebih matang.'),
 ModelPreset('v3liteidn','ORTCore V3 Lite IDN','TITANMAIN.py','V3','idn',231,'V3 Lite dengan naturalisasi.','Lite + IDN.'),
 ModelPreset('v4idn','ORTCore V4 IDN','TITANMAIN.py','V4','idn',240,'V4 hybrid dengan naturalisasi.','Hybrid cepat dengan hasil lebih halus.'),
 ModelPreset('v4liteidn','ORTCore V4 Lite IDN','TITANMAIN.py','V4','idn',241,'V4 Lite IDN.','Lite + IDN.'),
 ModelPreset('v5idn','ORTCore V5 IDN','TITANMAIN.py','V5','idn',250,'V5 IDN.','Naturalisasi maksimal + IDN.'),
 ModelPreset('v5liteidn','ORTCore V5 Lite IDN','TITANMAIN.py','V5','idn',251,'V5 Lite IDN.','Lite + IDN.'),
]
INDEX={m.key:m for m in MODEL_PRESETS}
def list_models(group: str|None=None)->List[ModelPreset]:
    items=sorted(MODEL_PRESETS,key=lambda x:x.order)
    if group: items=[m for m in items if m.tier==group]
    return items
def get_model(key: str)->ModelPreset:
    return INDEX[key.lower()]
def available_model_choices(group: str|None=None)->List[str]:
    return [m.title for m in list_models(group)]
def choice_to_key(title: str)->str:
    for m in MODEL_PRESETS:
        if m.title == title: return m.key
    raise KeyError(title)
def get_model_by_title(title: str)->ModelPreset: return get_model(choice_to_key(title))
