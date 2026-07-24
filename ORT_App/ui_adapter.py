from __future__ import annotations
from typing import Any, Dict

def build_ui_payload(core_name: str, raw_result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'source_text': raw_result.get('source_text', raw_result.get('src', '')),
        'translated_text': raw_result.get('translated_text', raw_result.get('dst', '')),
        'speaker': raw_result.get('speaker', ''),
        'game': raw_result.get('game', ''),
        'model': core_name,
        'engine': raw_result.get('engine', ''),
        'latency_ms': raw_result.get('latency_ms', raw_result.get('ms')),
        'ping_ms': raw_result.get('ping_ms'),
        'status': raw_result.get('status', 'running'),
        'extra': raw_result.get('extra', {}),
    }
