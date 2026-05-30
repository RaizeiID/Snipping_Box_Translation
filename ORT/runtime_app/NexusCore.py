import os
import json
import time
import importlib
import traceback
from difflib import SequenceMatcher

# ==============================================================================
#   TITAN X - NEXUS CORE v3.0 (EVOLVING PIPELINE)
#   Divisi: HEADQUARTERS
#   Fokus: sinkronisasi core, pipeline eksekusi, dan learning persistence.
# ==============================================================================

EXPECTED_CORES = [
    'CaptureSpecialist', 'VisionAnalyst', 'DuplicateSubtitleSuppressor',
    'TextStitcher', 'Sanitizer', 'SpellWeaver', 'EdgeCaseDetector',
    'Identity', 'EntityDiscovery', 'Narrative',
    'Sociologist', 'LoreKeeper', 'CharacterArc',
    'TimelineTracker', 'ContextBuffer',
    'PromptDirector', 'Semantics', 'MultiCandidateGenerator',
    'Helsinki', 'Failover',
    'ProfessorSyntax', 'ProfessorTone', 'ProfessorLogic',
    'StyleGuide', 'Dean',
    'QualityEstimation', 'TerminologyConstraint', 'BackTranslationVerifier',
    'BilingualConsistency', 'ConsistencyAuditor', 'ValidationGate',
    'SmartCacheRouter', 'MemoryVault',
    'ResourceSentinel', 'AdaptiveThrottle', 'PipelineOptimizer',
    'LatencyBudgetManager', 'DynamicBatching',
    'ConfigMaster', 'Synapse', 'AsyncOrchestrator', 'PriorityScheduler',
    'BlackBox', 'Overseer', 'RegressionTest',
    'LearningEngine', 'FeedbackCollector', 'LQAReport',
    'Formatter', 'UIConstraint', 'FallbackStrategy'
]

PIPELINE_ORDER = [
    'DuplicateSubtitleSuppressor',
    'TextStitcher',
    'Sanitizer',
    'SpellWeaver',
    'EdgeCaseDetector',
    'Identity',
    'EntityDiscovery',
    'SmartCacheRouter',
    'MemoryVault',
    'Helsinki',
    'Failover',
    'ProfessorSyntax',
    'ProfessorTone',
    'ProfessorLogic',
    'StyleGuide',
    'Dean',
    'TerminologyConstraint',
    'BackTranslationVerifier',
    'BilingualConsistency',
    'ConsistencyAuditor',
    'QualityEstimation',
    'ValidationGate',
    'UIConstraint',
    'Formatter',
]


def _atomic_json_write(path: str, data) -> None:
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _safe_json_read(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


class Brain:
    """Orkestrator seluruh core + learning persistence."""

    def __init__(self, logger=print, base_dir: str | None = None, strict: bool = False):
        self.log = logger
        self.strict = strict
        self.base_dir = base_dir or os.getcwd()

        self.cores = {name: None for name in EXPECTED_CORES}
        self.core_status = {name: {'status': 'INIT', 'error': ''} for name in EXPECTED_CORES}

        # Persistent caches
        self.translation_memory_path = os.path.join(self.base_dir, 'translation_memory.json')
        self.canonical_map_path = os.path.join(self.base_dir, 'ocr_canonical_map.json')
        self.usage_stats_path = os.path.join(self.base_dir, 'usage_stats.json')

        self.translation_memory = _safe_json_read(self.translation_memory_path, {})
        self.canonical_map = _safe_json_read(self.canonical_map_path, {})
        self.stats = _safe_json_read(self.usage_stats_path, {
            'seen_total': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'last_flush_ts': 0,
            'core_errors': {}
        })

        self._dirty_mem = False
        self._dirty_map = False
        self._dirty_stats = False

        self.log('[NEXUS] Initializing OMNI LEGION v3.0 (Evolving Pipeline)...')
        self.load_modules()
        self.sync_report()

    # ---------------------------------------------------------------------
    # Loading & Sync
    # ---------------------------------------------------------------------
    def load_modules(self):
        sys_path_added = False
        if self.base_dir not in os.sys.path:
            os.sys.path.insert(0, self.base_dir)
            sys_path_added = True

        for core_name in EXPECTED_CORES:
            module_name = f'{core_name}Core'
            module_file = os.path.join(self.base_dir, f'{module_name}.py')

            if not os.path.exists(module_file):
                self.core_status[core_name] = {'status': 'MISSING', 'error': ''}
                continue

            try:
                module = importlib.import_module(module_name)

                # Most modules use class <ModuleName> (e.g., IdentityCore) or <CoreName>Core
                cls = getattr(module, module_name, None) or getattr(module, f'{core_name}Core', None) or getattr(module, core_name, None)
                if cls is None:
                    # fallback: first class that endswith 'Core'
                    for k, v in module.__dict__.items():
                        if isinstance(v, type) and k.endswith('Core'):
                            cls = v
                            break

                if cls is None:
                    raise RuntimeError('No Core class found')

                self.cores[core_name] = cls()
                self.core_status[core_name] = {'status': 'OK', 'error': ''}

            except Exception as e:
                err = f'{type(e).__name__}: {e}'
                self.cores[core_name] = None
                self.core_status[core_name] = {'status': 'FAIL', 'error': err}
                self.stats.setdefault('core_errors', {})[core_name] = err
                self._dirty_stats = True

                bb = self.cores.get('BlackBox')
                if bb and hasattr(bb, 'log_event'):
                    try:
                        bb.log_event('Nexus', 'CORE_INIT_FAIL', f'{module_name} -> {err}')
                    except Exception:
                        pass

                if self.strict:
                    raise
                else:
                    self.log(f'[NEXUS] [!] Link Failed: {module_name} -> {err}')

        if sys_path_added:
            # keep path; useful for runtime imports
            pass

    def sync_report(self):
        ok = sum(1 for v in self.core_status.values() if v['status'] == 'OK')
        fail = sum(1 for v in self.core_status.values() if v['status'] == 'FAIL')
        missing = sum(1 for v in self.core_status.values() if v['status'] == 'MISSING')

        self.log('\n[SYNC] Core Initialization Report:')
        for name in EXPECTED_CORES:
            st = self.core_status[name]['status']
            if st == 'OK':
                self.log(f'  [OK]     {name}Core')
            elif st == 'MISSING':
                self.log(f'  [MISSING]{name}Core')
            else:
                self.log(f'  [FAIL]   {name}Core :: {self.core_status[name]["error"]}')

        self.log('\n[SYNC] Linking Pipeline Order:')
        last = None
        for step in PIPELINE_ORDER:
            if self.cores.get(step) is None:
                continue
            if last is None:
                last = step
                continue
            self.log(f'  [LINK] {last} -> {step}')
            last = step

        self.log(f'\n[SYNC] Summary: OK={ok} FAIL={fail} MISSING={missing}')
        self.log('[SYSTEM] Start Engine\n')

    # ---------------------------------------------------------------------
    # Cache & Learning
    # ---------------------------------------------------------------------
    def canonicalize(self, raw: str) -> str:
        raw = (raw or '').strip()
        if not raw:
            return ''
        return self.canonical_map.get(raw, raw)

    def remember_canonical(self, raw: str, canonical: str):
        raw = (raw or '').strip()
        canonical = (canonical or '').strip()
        if not raw or not canonical:
            return
        if raw != canonical and self.canonical_map.get(raw) != canonical:
            self.canonical_map[raw] = canonical
            self._dirty_map = True

    def cache_get(self, key: str):
        if key in self.translation_memory:
            self.stats['cache_hits'] = int(self.stats.get('cache_hits', 0)) + 1
            self._dirty_stats = True
            return True, self.translation_memory[key]
        self.stats['cache_misses'] = int(self.stats.get('cache_misses', 0)) + 1
        self._dirty_stats = True
        return False, ''

    def _fuzzy_cache_lookup(self, key: str, threshold: float = 0.94):
        """Cari key mirip di translation memory dan kembalikan (best_key, value, ratio).

        Dipakai untuk 'belajar' dari varian OCR yang hampir sama sehingga cache-hit meningkat."""
        try:
            mem = self.translation_memory
            if not mem:
                return None
            # jaga performa: matikan fuzzy bila memory sangat besar
            if len(mem) > 12000:
                return None
            if not key or len(key) < 4 or len(key) > 260:
                return None

            best_k = None
            best_v = None
            best_r = 0.0

            # ambil subset terakhir (insertion order dict di python3.7+)
            items = list(mem.items())[-2500:]
            for k, v in items:
                if not k:
                    continue
                if abs(len(k) - len(key)) > 14:
                    continue
                if k[0] != key[0]:
                    continue
                r = SequenceMatcher(None, k, key).ratio()
                if r > best_r:
                    best_r, best_k, best_v = r, k, v
                    if best_r >= 0.985:
                        break
            if best_r >= threshold and best_k is not None:
                return best_k, best_v, best_r
        except Exception:
            return None
        return None

    def cache_set(self, key: str, value: str):
        if not key:
            return
        if self.translation_memory.get(key) != value:
            self.translation_memory[key] = value
            self._dirty_mem = True

    def flush(self, reason: str = 'manual'):
        wrote = False
        try:
            if self._dirty_mem:
                _atomic_json_write(self.translation_memory_path, self.translation_memory)
                self._dirty_mem = False
                wrote = True
            if self._dirty_map:
                _atomic_json_write(self.canonical_map_path, self.canonical_map)
                self._dirty_map = False
                wrote = True
            if self._dirty_stats:
                self.stats['last_flush_ts'] = time.time()
                _atomic_json_write(self.usage_stats_path, self.stats)
                self._dirty_stats = False
                wrote = True

            # Ask MemoryVault to save as well (if available)
            vault = self.cores.get('MemoryVault')
            if vault and hasattr(vault, '_save_memory'):
                try:
                    # Trigger save attempt (it has interval guard)
                    vault._save_memory()
                except Exception:
                    pass

        except Exception as e:
            self.log(f'[CACHE] Flush error: {e}')

        if wrote:
            self.log(f'[CACHE] Saved ({reason}) | mem={len(self.translation_memory)} map={len(self.canonical_map)}')

    # ---------------------------------------------------------------------
    # Main Pipeline
    # ---------------------------------------------------------------------

    def translate_plain(self, text: str) -> str:
        """Translate teks tanpa formatting UI (dipakai Capture All Screen)."""
        if not text:
            return ''
        # Preprocess ringan (tanpa Identity stripping)
        t = str(text).strip()
        if self.cores.get('Sanitizer') and hasattr(self.cores['Sanitizer'], 'clean'):
            try:
                t = self.cores['Sanitizer'].clean(t)
            except Exception:
                pass
        if self.cores.get('SpellWeaver') and hasattr(self.cores['SpellWeaver'], 'fix'):
            try:
                t = self.cores['SpellWeaver'].fix(t)
            except Exception:
                pass
        t = (t or '').strip()
        if len(t) < 2:
            return ''
        canonical = self.canonicalize(t)
        eligible = True
        router = self.cores.get('SmartCacheRouter')
        if router and hasattr(router, 'check_cache_eligibility'):
            try:
                eligible = bool(router.check_cache_eligibility(canonical))
            except Exception:
                eligible = True
        if eligible:
            hit, cached = self.cache_get(canonical)
            if hit and cached:
                return cached
            vault = self.cores.get('MemoryVault')
            if vault and hasattr(vault, 'retrieve'):
                try:
                    v = vault.retrieve(canonical)
                    if v:
                        return v
                except Exception:
                    pass
        hel = self.cores.get('Helsinki')
        out = canonical
        if hel and hasattr(hel, 'translate'):
            try:
                out = hel.translate(canonical, context_tags=['AllScreen'])
            except Exception:
                out = canonical
        if eligible and out and out != canonical:
            self.cache_set(canonical, out)
            vault = self.cores.get('MemoryVault')
            if vault and hasattr(vault, 'store'):
                try:
                    vault.store(canonical, out)
                except Exception:
                    pass
        return out
    def refresh_engine(self):
        if self.cores.get('Helsinki') and hasattr(self.cores['Helsinki'], 'reload_device'):
            return self.cores['Helsinki'].reload_device()
        return 'N/A'

    def process_mission(self, ocr_raw_data, meta: dict | None = None):
        """Input boleh list[str] atau string. Return dict action/payload."""
        meta = meta or {}

        if not ocr_raw_data:
            return {'action': 'IGNORE', 'reason': 'NO_INPUT'}

        if isinstance(ocr_raw_data, list):
            raw_joined = ' '.join([str(x) for x in ocr_raw_data if str(x).strip()])
        else:
            raw_joined = str(ocr_raw_data)

        raw_joined = raw_joined.strip()
        if len(raw_joined) < 2:
            return {'action': 'IGNORE', 'reason': 'EMPTY'}

        packet = {
            'timestamp': time.time(),
            'raw_ocr': ocr_raw_data,
            'raw_text': raw_joined,
            'canonical_text': '',
            'clean_text': '',
            'speaker': None,
            'dialog_text': '',
            'translation_raw': '',
            'translation_final': '',
            'context_tags': meta.get('context_tags', []),
            'ui_render_html': '',
            'cache_hit': False,
            'meta': meta,
        }

        try:
            self.stats['seen_total'] = int(self.stats.get('seen_total', 0)) + 1
            self._dirty_stats = True

            # 1) Stitch lines
            text = packet['raw_text']
            if isinstance(ocr_raw_data, list) and self.cores.get('TextStitcher') and hasattr(self.cores['TextStitcher'], 'stitch'):
                text = self.cores['TextStitcher'].stitch(ocr_raw_data)

            # 2) Clean
            if self.cores.get('Sanitizer') and hasattr(self.cores['Sanitizer'], 'clean'):
                text = self.cores['Sanitizer'].clean(text)

            # 3) Fix
            if self.cores.get('SpellWeaver') and hasattr(self.cores['SpellWeaver'], 'fix'):
                text = self.cores['SpellWeaver'].fix(text)

            text = (text or '').strip()
            packet['clean_text'] = text
            if len(text) < 2:
                return {'action': 'IGNORE', 'reason': 'CLEAN_EMPTY'}

            # 4) Duplicate suppression
            sup = self.cores.get('DuplicateSubtitleSuppressor')
            if sup and hasattr(sup, 'should_process'):
                if not sup.should_process(text):
                    return {'action': 'IGNORE', 'reason': 'DUPLICATE'}

            # 5) Edge case safety
            edge = self.cores.get('EdgeCaseDetector')
            if edge and hasattr(edge, 'is_safe'):
                if not edge.is_safe(text):
                    le = self.cores.get('LearningEngine')
                    if le and hasattr(le, 'analyze_garbage_candidate'):
                        try:
                            le.analyze_garbage_candidate(text)
                        except Exception:
                            pass
                    return {'action': 'IGNORE', 'reason': 'EDGE_BLOCK'}

            # 6) Identify speaker
            ident = self.cores.get('Identity')
            speaker = None
            dialog = text
            if ident and hasattr(ident, 'identify'):
                speaker, dialog = ident.identify(text)
            packet['speaker'] = speaker
            packet['dialog_text'] = dialog

            # 7) Entity discovery (optional)
            disc = self.cores.get('EntityDiscovery')
            if disc and hasattr(disc, 'investigate') and ident and hasattr(ident, 'known_identities'):
                try:
                    new_name = disc.investigate(text, list(getattr(ident, 'known_identities', [])))
                    if new_name and hasattr(ident, 'known_identities'):
                        ident.known_identities.add(new_name)
                        if hasattr(ident, 'save_database'):
                            ident.save_database()
                except Exception:
                    pass

            # 8) Canonicalize for cache stability
            canonical = self.canonicalize(dialog)
            packet['canonical_text'] = canonical

            # Learn canonical mapping if text is very close to last canonical (optional)
            # (We keep simple; more advanced learning can be added later.)

            # 9) Cache eligibility
            eligible = True
            router = self.cores.get('SmartCacheRouter')
            if router and hasattr(router, 'check_cache_eligibility'):
                eligible = bool(router.check_cache_eligibility(canonical))

            # 10) Memory retrieval
            cache_hit = False
            cached = ''
            if eligible:
                cache_hit, cached = self.cache_get(canonical)
                # Learning: fuzzy match OCR-varian ke cache lama (mengurangi miss seiring waktu)
                if not cache_hit:
                    try:
                        fuzz = self._fuzzy_cache_lookup(canonical)
                        if fuzz:
                            k_best, v_best, r_best = fuzz
                            cache_hit, cached = True, v_best
                            self.remember_canonical(canonical, k_best)
                            packet['debug']['fuzzy_ratio'] = r_best
                    except Exception:
                        pass
                if not cache_hit:
                    vault = self.cores.get('MemoryVault')
                    if vault and hasattr(vault, 'retrieve'):
                        try:
                            v = vault.retrieve(canonical)
                            if v:
                                cache_hit, cached = True, v
                        except Exception:
                            pass

            packet['cache_hit'] = cache_hit

            # 11) Translate
            if cache_hit:
                packet['translation_raw'] = cached
            else:
                hel = self.cores.get('Helsinki')
                if hel and hasattr(hel, 'translate'):
                    packet['translation_raw'] = hel.translate(canonical, context_tags=packet.get('context_tags', []))
                else:
                    # absolute fallback
                    packet['translation_raw'] = canonical

            packet['translation_final'] = packet['translation_raw']

            # 12) Post-QA / validation gate (best-effort)
            gate = self.cores.get('ValidationGate')
            if gate and hasattr(gate, 'validate'):
                try:
                    verdict = gate.validate(packet['translation_final'])
                    if verdict is False:
                        return {'action': 'IGNORE', 'reason': 'VALIDATION_FAIL'}
                except Exception:
                    pass

            # 13) UI constraint
            ui_c = self.cores.get('UIConstraint')
            if ui_c and hasattr(ui_c, 'fit_text'):
                try:
                    packet['translation_final'] = ui_c.fit_text(packet['translation_final'])
                except Exception:
                    pass

            # 14) Render
            fmt = self.cores.get('Formatter')
            if fmt and hasattr(fmt, 'render'):
                packet['ui_render_html'] = fmt.render(packet)
            else:
                packet['ui_render_html'] = f"<span>{packet['translation_final']}</span>"

            # 15) Store cache & learn
            if eligible and not cache_hit:
                self.cache_set(canonical, packet['translation_final'])
                vault = self.cores.get('MemoryVault')
                if vault and hasattr(vault, 'store'):
                    try:
                        vault.store(canonical, packet['translation_final'])
                    except Exception:
                        pass

            # 16) LearningEngine hooks
            le = self.cores.get('LearningEngine')
            if le:
                # garbage learning
                if hasattr(le, 'analyze_garbage_candidate'):
                    try:
                        le.analyze_garbage_candidate(packet['raw_text'])
                    except Exception:
                        pass

            return {
                'action': 'DISPLAY',
                'payload': packet['ui_render_html'],
                'throttle_sleep': 0.0,
                'packet': packet,
            }

        except Exception as e:
            err = traceback.format_exc(limit=2)
            self.stats.setdefault('core_errors', {})['process_mission'] = str(e)
            self._dirty_stats = True

            bb = self.cores.get('BlackBox')
            if bb and hasattr(bb, 'log_event'):
                try:
                    bb.log_event('Nexus', 'PIPELINE_ERROR', err)
                except Exception:
                    pass

            return {'action': 'IGNORE', 'reason': f'EXCEPTION: {e}'}
