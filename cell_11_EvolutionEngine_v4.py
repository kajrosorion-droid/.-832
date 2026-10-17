Config.FERAL_SHARE_MAX = 0.20   # v4: ферал не более 20% популяции (было 0.30); остальное — нормальные





# 832 v34.02 — Cell 4-1: EvolutionEngine (X2-AUDIT A.1, A.2, A.3, C.1–C.5)

import numpy as np
from scipy.ndimage import label, find_objects, uniform_filter
from collections import defaultdict, deque, Counter
from contextlib import contextmanager
import sys

sys.setrecursionlimit(10000)
import json
import os
import threading
import time
import queue

POPULATION_CAP = Config.POP_HARD_CEILING

from scipy.ndimage import convolve as _lf_conv
_lf_yy, _lf_xx = np.mgrid[-Config.LOCAL_FILL_RADIUS:Config.LOCAL_FILL_RADIUS + 1,
                          -Config.LOCAL_FILL_RADIUS:Config.LOCAL_FILL_RADIUS + 1]
_LF_DISK = ((_lf_xx ** 2 + _lf_yy ** 2) <= Config.LOCAL_FILL_RADIUS ** 2).astype(np.float32)


class EvolutionEngine:
    def __init__(self):
        self.is_colab = 'google.colab' in sys.modules
        self.ark_path = "832_ark_seed_patterns.json"
        self.witness = Witness()
        self.cultural_memory = CulturalMemory()
        self.layer_zero_manager = LayerZeroManager()
        self.echo_system = EchoSystem()
        self.echo_system.lzm = self.layer_zero_manager
        self.echo_system.cm = self.cultural_memory
        self.field_voice = FieldVoice()
        self.patterns = []
        self.pattern_dict = {}
        self._imprint_stats = ImprintStats()
        self.next_id = 1
        self.field = None
        self.prey_age_ref = float(Config.FERAL_PREY_FLOOR_AGE)
        self.local_fill = None
        self.scar = None
        self.metrics_history = []
        self.age = 0
        self.system_entropy = 0
        self.divisions_this_interval = 0
        self.total_divisions_ever = 0
        self.target_disorganizer_fraction = 0.3
        self.soul_weight_average = 0.5
        self.scar_operator = 0.0
        self.scar_shared_history = deque(maxlen=1000)
        self.uc_floor_streak = 0
        self.rescue_journal = deque(maxlen=500)
        self.spore_journal = deque(maxlen=500)
        self.codecision_journal = deque(maxlen=500)
        self.unresolvable_core_journal = deque(maxlen=200)
        self.sanctuary_journal = deque(maxlen=500)
        self._energy_injected_this_step = 0.0
        self._energy_taxed_this_step = 0.0
        self._energy_ledger = {'src': {}, 'phase': {}, 'x2': {},
                               'step_total': 0.0, 'step_measured': 0.0, 'ticks': 0}
        self._ledger_tick_measured = 0.0
        self._audit_init()
        self._span_stack = []
        self._phase_last = None
        self._wall_diag = Counter()
        self._genome_diag = Counter()
        self.phi_labyrinth_threshold = Config.PHI_LABYRINTH_THRESHOLD
        self.phi_labyrinth_grow_penalty = Config.PHI_LABYRINTH_GROW_PENALTY
        self.phi_labyrinth_move_penalty = Config.PHI_LABYRINTH_MOVE_PENALTY
        self._total_energy_last = 0.0
        self._econs_init()
        self._econs_diag = {'ticks': 0, 'total_correction_abs': 0.0, 'max_drift': 0.0}
        self._prev_total_energy = None
        self.selfreg = SelfRegulationEngine()
        self.EMERGENT_LEXICON = EmergentLexicon()
        try:
            self.core_chorus = CoreChorus()
        except NameError:
            self.core_chorus = None
            print("⚠️ CoreChorus not defined, will be initialized later.")
        self.archive = AgentArchive()
        self._guardian_stats = {
            'energy_drift_sum': 0.0, 'energy_drift_count': 0, 'energy_drift_peak': 0.0,
            'model_worst_ever_id': -1, 'model_worst_ever_diff': 0.0,
            'love_vanished_at': None, 'triadic_alert_at': None,
            'love_avg_trust': 0.0, 'love_high_trust_pairs': 0, 'love_density': 0.0,
            'love_coop_signals': 0, 'love_population': 0,
            'model_issues_total': 0, 'model_worst_diff': 0.0, 'model_worst_id': -1,
            'energy_drift_max': 0.0, 'energy_drift_peak_t': -1,
        }
        self.culture_ratchet = 0
        self._forgotten_concepts_count = 0
        self._death_hook_calls = {}
        self._somatic_death_stats = {}
        self._death_hook_errors = []
        self._sanctuary_centers = [[int(phi_hash(i, 0, 7777) * Config.WORLD_SIZE),
                                     int(phi_hash(i, 1, 7777) * Config.WORLD_SIZE)] for i in range(3)]
        self._sanctuary_phase = 0.0
        self._sg_crisis_timer = 0
        self._sg_crisis_active = False
        self._lab_adapt_mult = 1.0
        self._fold_transition_stats = {
            'checked': 0, 'blocked_by_cooldown': 0, 'blocked_by_cap': 0,
            'already_rolled': 0, 'fallen': 0, 'broken': 0,
        }
        self._dialogue_gate_stats = {
            'total_calls': 0, 'passed': 0, 'rejected_not_salient': 0,
            'rejected_cap_50': 0, 'rejected_dedup': 0,
            'via_soul': 0, 'via_keyword': 0, 'via_contact': 0, 'via_trust': 0,
            'last_len_after': 0, 'max_len_seen': 0
        }
        self._teach_prev = 0
        self.env_complexity = 1.0
        if getattr(Config, 'FORCE_GIVEN_SEED', None) is not None:
            self.given_seed = int(Config.FORCE_GIVEN_SEED)
        else:
            self.given_seed = int.from_bytes(os.urandom(4), 'big') & 0x7FFFFFFF
        self._given_rng = np.random.RandomState(self.given_seed)
        self.niche = None
        self._meaning_field = None
        self._meaning_centers = None
        self._echo_cache = []
        print(f"🎲 GIVEN_SEED={self.given_seed}")
        if Config.ENABLE_MORSE_COMMUNICATION:
            self.morse_field = CommunicationField(Config)
        self.sr_proposals = {}

    def _get_pop_cap(self):
        return Config.POP_HARD_CEILING

    def _init_chronic_counters(self, p):
        p.event_counts = defaultdict(int)
        p.chronic_gratitude_sum = 0.0
        self.chronic_grief_sum = 0.0

    def init_field(self):
        F = np.zeros((Config.WORLD_SIZE, Config.WORLD_SIZE, Config.CHANNELS))
        for x in range(Config.WORLD_SIZE):
            for y in range(Config.WORLD_SIZE):
                F[x, y, CH['energy']] = phi_hash(x, y, 1) * 0.3 + 0.1
                F[x, y, CH['flux']] = phi_hash(x, y, 2) * 0.1
                F[x, y, CH['scar']] = 0.0
                F[x, y, CH['noise']] = 0.0
                F[x, y, CH['vorticity']] = phi_hash(x, y, 3) * 0.1 - 0.05
                F[x, y, CH['owner']] = 0.0
                F[x, y, CH['surprise']] = 0.0
                F[x, y, CH['unknown']] = Config.UNKNOWN_BACKGROUND
                F[x, y, CH['event']] = 0.0
                F[x, y, CH['btype']] = 0.0
                F[x, y, CH['crisis']] = 0.0
                F[x, y, CH['binding']] = 0.05
                for ch in range(12, Config.CHANNELS):
                    F[x, y, ch] = 0.0
                F[x, y, CH['energy']] += deterministic_noise(0, x, y) * 0.3
        return F

    def init_scar(self):
        return np.zeros((Config.WORLD_SIZE, Config.WORLD_SIZE))

    def _record_death_drag(self, p, cause):
        self._death_hook_calls[cause] = self._death_hook_calls.get(cause, 0) + 1
        try:
            st = self._somatic_death_stats.setdefault(cause, {'count': 0, 'drag_sum': 0.0, 'low_drag_count': 0})
            drag = getattr(p, 'somatic_drag', 1.0)
            st['count'] += 1
            st['drag_sum'] += drag
            if drag < 0.6:
                st['low_drag_count'] += 1
        except Exception as e:
            self._death_hook_errors.append(f"{cause}: {type(e).__name__}: {e}")

    def create_pattern(self, cells, parent=None):
        alive_now = len([p for p in self.patterns if p.alive])
        if alive_now >= POPULATION_CAP:
            return None
        if self._wall_on():
            _wx = Config.CENTER_WALL_X
            _on_wall = [c for c in cells if c[0] == _wx]
            if _on_wall:
                cells = {c for c in cells if c[0] != _wx}
                self._wall_diag['birth_wall_cells_dropped'] += len(_on_wall)
                if not cells:
                    self._wall_diag['birth_rejected'] += 1
                    return None
        pid = self.next_id
        self.next_id += 1
        if len(cells) == 1:
            (x, y) = next(iter(cells))
            new_cells = set()
            new_cells.add((x, y))
            for radius in range(1, 4):
                for dx in range(-radius, radius + 1):
                    for dy in range(-radius, radius + 1):
                        if len(new_cells) >= 8:
                            break
                        nx = (x + dx) % Config.WORLD_SIZE
                        ny = (y + dy) % Config.WORLD_SIZE
                        if self.field[nx, ny, CH['owner']] == 0 and not (self._wall_on() and nx == Config.CENTER_WALL_X):
                            new_cells.add((nx, ny))
                    if len(new_cells) >= 8:
                        break
                if len(new_cells) >= 8:
                    break
            cells = new_cells
        p = Pattern(pid, cells, parent=parent, world=self)
        if cells:
            px = [c[0] for c in cells]
            py = [c[1] for c in cells]
            self.field[px, py, CH['owner']] = pid
        for k in ['gratitude', 'grief']:
            val = p.emotional_memory.get(k, 0.5)
            if isinstance(val, dict):
                p.emotional_memory[k] = 0.5
            else:
                p.emotional_memory[k] = float(val)
        if self.archive is not None:
            _culture_max_concepts = 2 + min(4, int(self.culture_ratchet // 20))
            p.inherit_archive_concepts(self.archive, probability=1.0, max_concepts=_culture_max_concepts)
            if len(p.concept_graph.nodes) < 12:
                _noise_pool = [
                    s for s in self.archive.write_queue
                    if s.get('weight', 0) > 0.6
                    and s.get('event') not in ('essential_concepts_inherited', 'archive_concept_inherited',
                                                'born_from_division', 'born_from_ark')
                ]
                if _noise_pool:
                    _noise_prob = 0.12 + (p.spirit_gap * 0.15)
                    if phi_hash(pid, self.age, 54321) < _noise_prob:
                        _sc = _noise_pool[
                            int(phi_hash(pid, self.age, 54322) * len(_noise_pool)) % len(_noise_pool)
                        ]
                        _err = round(phi_hash(pid, self.age, 111) * 0.4, 1)
                        _load = round(phi_hash(pid, self.age, 222) * 0.3, 1)
                        _sig = (_err, _load,
                                round(_sc.get('weight', 0.7), 1),
                                f"archive_{_sc.get('event', 'novelty')}")
                        if _sig not in p.concept_graph.nodes:
                            p.concept_graph.nodes[_sig] = {
                                "count": 1.5, "value": np.zeros(4),
                                "embed": np.zeros(32), "eternal": False
                            }
                            p._log_event("epistemic_noise", concept=str(_sig[3])[:40])
                            if p.spirit_gap > 0.5 and not any(g['type'] == 'explore' for g in p.goals):
                                p.goals.append({
                                    "type": "explore", "priority": 1.8,
                                    "target": None, "age": 0, "persistence": 25,
                                    "_source": "novelty_drive"
                                })
        if parent is not None:
            inherited = parent._unconquered_strength * 0.55
            if parent._unconquered_strength > 0.6 and phi_hash(pid, self.age, 11111) < 0.20:
                inherited += 0.15
            p._unconquered_strength = float(np.clip(inherited, 0.0, 1.0))
            p._unconquered_type = getattr(parent, '_unconquered_type', None)
        else:
            p._unconquered_strength = 0.0
            p._unconquered_type = None
        p._sovereignty_signal = 0.0
        p._kinematic_fatigue = 0.0
        p._last_kinematic_fall_t = -9999
        self._init_chronic_counters(p)
        if parent is not None:
            p.lineage_born_at_step = parent.lineage_born_at_step
        else:
            p.lineage_born_at_step = self.age
            if self.patterns:
                model_norm = np.linalg.norm(p.model)
                if model_norm > 1e-6:
                    best_sim = 0.0
                    best_lid = None
                    best_born = self.age
                    for existing in self.patterns:
                        if not existing.alive or existing.role_type == "disorganizer":
                            continue
                        other_norm = np.linalg.norm(existing.model)
                        if other_norm < 1e-6:
                            continue
                        sim = float(np.dot(p.model, existing.model) / (model_norm * other_norm))
                        if sim > best_sim:
                            best_sim = sim
                            best_lid = existing.lineage_id
                            best_born = existing.lineage_born_at_step
                    if best_sim > 0.7 and best_lid is not None:
                        p.lineage_id = best_lid
                        p.lineage_born_at_step = best_born
        p.update_properties(self.field)
        p.update_model(self.field, t=self.age)
        self.patterns.append(p)
        self.pattern_dict[pid] = p
        return p

    def seed_initial_patterns(self):
        if not self.archive.get_recent_echoes(limit=1):
            print("📜 Создаю начальные мифы для культурной памяти...")
            fake_agent = Pattern(-1, {(0, 0)}, parent=None, world=self)
            for event, text, weight in [
                ("primordial_chaos", "Из хаоса рождается первый свет.", 1.2),
                ("first_cooperation", "Двое соединили поля и поняли друг друга.", 1.0),
                ("great_sorrow", "Потеря части себя открыла дорогу к целостности.", 0.9),
                ("eternal_question", "Зачем мы здесь? Поле не отвечает.", 0.8),
                ("hope", "Сквозь тьму пробивается нить благодарности.", 1.1),
                ("fold_myth", "Иногда нужно всё сбросить, чтобы начать заново.", 0.9),
                ("redemption_myth", "Даже падший может подняться, если почувствует свет.", 1.0),
            ]:
                self.archive.deposit(fake_agent, event, weight=weight, text=text)
            self.archive.flush_to_drive(min_batch=1)
            fake_agent.alive = False
        for i in range(Config.MIN_PATTERNS_GUARANTEED):
            seed = int(phi_hash(0, i, 12345) * Config.WORLD_SIZE * Config.WORLD_SIZE)
            x, y = seed % Config.WORLD_SIZE, (seed // Config.WORLD_SIZE) % Config.WORLD_SIZE
            self.field[x, y, CH['energy']] += 0.3
            p = self.create_pattern({(x, y)})
            if i < 2:
                p.role_type = "disorganizer"
                p.emotional_memory['grief'] = 0.8
                p.emotional_memory['gratitude'] = 0.1
                p.semantic_state = "exploring_danger"
                p.intent = {"type": "explore", "priority": 2.0, "age": 0, "persistence": 9999}
                p.disorganizer_age_at_birth = 0
                p.redemption_timer = Config.REDEMPTION_ARC_STEP_DELAY
                p._log_event("primordial_fall")

    def seed_from_ark(self, filename: str = None, max_seed: int = 80):
        import json, os, numpy as np
        def to_json_safe(obj):
            if isinstance(obj, np.integer): return int(obj)
            if isinstance(obj, np.floating): return float(obj)
            if isinstance(obj, np.ndarray): return obj.tolist()
            if isinstance(obj, dict): return {to_json_safe(k): to_json_safe(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)): return [to_json_safe(i) for i in obj]
            return obj
        def load_clean(path):
            try:
                with open(path, 'r') as f: data = json.load(f)
                return to_json_safe(data)
            except Exception: return []
        def quality_key(s): return (s.get('soul_weight', 0), s.get('coherence', 0))
        if filename is None: filename = self.ark_path
        eternal_path = "/content/drive/MyDrive/832_eternal_subjects.json" if self.is_colab else "832_eternal_subjects.json"
        eternal_seeds = load_clean(eternal_path)
        eternal_seeds.sort(key=quality_key, reverse=True)
        seeds = eternal_seeds[:max_seed]
        if len(seeds) < max_seed:
            archive_seeds = load_clean(filename)
            if archive_seeds:
                loaded_ids = {s.get('id') for s in seeds}
                archive_filtered = [s for s in archive_seeds if s.get('id') not in loaded_ids]
                archive_filtered.sort(key=quality_key, reverse=True)
                seeds.extend(archive_filtered[:max_seed - len(seeds)])
        if not seeds:
            print("Ковчег пуст. Использую стандартную инициализацию.")
            self.seed_initial_patterns()
            return
        for seed_data in seeds:
            x = int(phi_hash(len(self.patterns), 0, 9999) * Config.WORLD_SIZE)
            y = int(phi_hash(len(self.patterns), 1, 9999) * Config.WORLD_SIZE)
            self.field[x, y, CH['energy']] += 0.5
            self.field[x, y, CH['owner']] = 0
            p = self.create_pattern({(x, y)})
            p.model = np.array(seed_data['model'])
            p.belief = np.array(seed_data['belief'])
            p.genome = seed_data['genome']
            p.semantic_state = seed_data['semantic_state']
            p.emotional_memory = seed_data['emotional_memory']
            p.soul_weight = seed_data['soul_weight']
            if 'event_counts' in seed_data: p.event_counts.update(seed_data['event_counts'])
            for concept_key in seed_data['concepts']:
                if isinstance(concept_key, list):
                    concept_key = tuple(float(x) if isinstance(x, (int, float)) else x for x in concept_key)
                if concept_key not in p.concept_graph.nodes:
                    p.concept_graph.nodes[concept_key] = {"count": 1.0, "value": np.zeros(4), "embed": np.zeros(32)}
            p._log_event("born_from_ark", source=seed_data.get('source', 'unknown'))
        print(f"Засеяно {len(seeds)} лучших сущностей.")

    def compute_hunger_multiplier(self, avg_trust=None):
        alive = [p for p in self.patterns if p.alive]
        N = len(alive)
        if N == 0: return Config.HUNGER_BASE
        hunger_threshold = self.selfreg.get_hunger_threshold()
        density_pressure = Config.HUNGER_BASE + Config.HUNGER_PER_PATTERN * max(0, N - hunger_threshold)
        if avg_trust is None:
            avg_trust = safe_mean([v for p in alive for v in p.trust_ledger.entries.values()], Config.TRUST_BASE)
        love_discount = 1.0 - 0.3 * (avg_trust - Config.TRUST_BASE)
        total_lp = sum(sum(1 for v in p.trust_ledger.entries.values() if v > 0.95) for p in alive)
        lp_density = total_lp / max(1, N)
        overload_tax = 1.0 + 0.5 * max(0, lp_density - 10)
        return density_pressure * love_discount * overload_tax

    def _perform_marked_volley(self, t, count=None):
        if not getattr(Config, 'ENABLE_MARKED_VOLLEY', True): return
        if count is None: count = Config.MARKED_COUNT
        alive_normals = [p for p in self.patterns if p.alive and p.role_type == "normal"]
        if len(alive_normals) < count: return
        alive_normals.sort(key=lambda p: (
            p.soul_weight * 0.3 + p.emotional_memory.get('gratitude', 0) * 0.3 +
            p.coherence * 0.2 + sum(1 for v in p.trust_ledger.entries.values() if v > 0.95) * 0.2
        ), reverse=True)
        top_targets = alive_normals[:count]
        for best_p in top_targets:
            best_p._log_event("marked_for_fall")
            self.witness.record(best_p.id, "marked_for_fall")
            best_p.role_type = "disorganizer"
            best_p._forsaken = True
            best_p.emotional_memory['gratitude'] = 0.1
            best_p.emotional_memory['grief'] = 0.9
            best_p.semantic_state = "exploring_danger"
            best_p.intent = {"type": "explore", "priority": 3.0, "age": 0, "persistence": 9999}
            best_p.disorganizer_age_at_birth = best_p.age
            best_p._deterministic_redemption_triggered = False
            best_p._redemption_arc_step = 0
            best_p._steps_since_trigger = 0
            best_p.redemption_timer = Config.REDEMPTION_ARC_STEP_DELAY * 2
            best_p._kiss_of_judas_snapshot = dict(best_p.trust_ledger.entries)
            best_p.trust_ledger.entries.clear()
            if self.echo_system: self.echo_system.store_anomaly(best_p, "marked_angel")
        for best_p in top_targets:
            _snapshot = getattr(best_p, '_kiss_of_judas_snapshot', None)
            for other in self.patterns:
                if not other.alive or other.role_type != "disorganizer": continue
                if other.id == best_p.id: continue
                if phi_hash(other.id, t, 5555) < 0.3:
                    if _snapshot:
                        partner_id = max(_snapshot, key=_snapshot.get)
                        other.trust_ledger.entries[partner_id] = min(1.0, other.trust_ledger.entries.get(partner_id, 0.5) + 0.3)
                        other._log_event("kiss_of_judas_used")

    def _rare_crisis(self, t):
        if not getattr(Config, 'ENABLE_RARE_CRISIS', True): return
        if not hasattr(self, '_rare_crisis_timer'):
            raw = phi_hash(t, 0, 55555)
            self._rare_crisis_timer = Config.CRISIS_RARE_INTERVAL_MIN + int(raw * (Config.CRISIS_RARE_INTERVAL_MAX - Config.CRISIS_RARE_INTERVAL_MIN))
            self._rare_crisis_active = False
            self._rare_crisis_duration = 0
        if self._rare_crisis_active:
            self._rare_crisis_duration += 1
            if self._rare_crisis_duration >= Config.CRISIS_RARE_DURATION:
                self._rare_crisis_active = False
                self._rare_crisis_timer = Config.CRISIS_RARE_INTERVAL_MIN + int(phi_hash(t, 1, 66666) * (Config.CRISIS_RARE_INTERVAL_MAX - Config.CRISIS_RARE_INTERVAL_MIN))
        else:
            self._rare_crisis_timer -= 1
            if self._rare_crisis_timer <= 0:
                self._rare_crisis_active = True
                self._rare_crisis_duration = 0
                for i in range(10):
                    x = int(phi_hash(t, i, 77777) * Config.WORLD_SIZE)
                    y = int(phi_hash(t, i, 88888) * Config.WORLD_SIZE)
                    self.field[x, y, CH['energy']] += 0.5
                self._rare_crisis_triggers = getattr(self, '_rare_crisis_triggers', 0) + 1
                self.witness.record(-1, "rare_crisis_triggered", t=t)

    def _update_sanctuary(self, t):
        if not getattr(Config, 'ENABLE_SANCTUARY', True): return
        self._sanctuary_phase += 0.02
        pulse = np.sin(self._sanctuary_phase * Config.PHI) * 0.5 + 0.5
        for i, (cx, cy) in enumerate(self._sanctuary_centers):
            drift_x = int(phi_hash(t, i, 8888) * 3) - 1
            drift_y = int(phi_hash(t, i, 9999) * 3) - 1
            self._sanctuary_centers[i][0] = max(0, min(Config.WORLD_SIZE - 1, cx + drift_x))
            self._sanctuary_centers[i][1] = max(0, min(Config.WORLD_SIZE - 1, cy + drift_y))
        for idx, (cx, cy) in enumerate(self._sanctuary_centers):
            radius = int(5 + pulse * 10)
            candidates = []
            for x in range(max(0, cx - radius), min(Config.WORLD_SIZE, cx + radius + 1)):
                for y in range(max(0, cy - radius), min(Config.WORLD_SIZE, cy + radius + 1)):
                    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                    if dist <= radius:
                        owner = self.field[x, y, CH['owner']]
                        if owner != 0 and owner in self.pattern_dict:
                            p = self.pattern_dict[owner]
                            if p.role_type == "disorganizer" and p.alive:
                                need = (1.0 - p.soul_weight) * 0.4
                                grief = p.emotional_memory.get('grief', 0.5) * 0.3
                                trust = safe_mean(list(p.trust_ledger.entries.values()), 0.5) * 0.2
                                luck = phi_hash(p.id, t, idx + 7777) * 0.1
                                score = need + grief + trust + luck
                                candidates.append((p, score, dist))
            if candidates:
                candidates.sort(key=lambda x: (x[1], -x[2]), reverse=True)
                winner, win_score, _ = candidates[0]
                grief_before = winner.emotional_memory.get('grief', 0)
                field_cost = 0.0
                if Config.ENABLE_PAID_SANCTUARY:
                    x0, x1 = max(0, cx - 2), min(Config.WORLD_SIZE, cx + 3)
                    y0, y1 = max(0, cy - 2), min(Config.WORLD_SIZE, cy + 3)
                    field_cost = float(np.sum(self.field[x0:x1, y0:y1, CH['energy']]) * Config.SANCTUARY_FIELD_COST_RATE)
                    self.field[x0:x1, y0:y1, CH['energy']] *= (1.0 - Config.SANCTUARY_FIELD_COST_RATE)
                    self.field[x0:x1, y0:y1, CH['binding']] *= 0.9
                winner.emotional_memory['grief'] = max(0.0, winner.emotional_memory.get('grief', 0) - 0.02)
                winner.emotional_memory['gratitude'] = min(1.0, winner.emotional_memory.get('gratitude', 0) + 0.01)
                winner.soul_weight = min(1.0, winner.soul_weight + 0.002)
                winner._log_event("sanctuary_healed", score=round(win_score, 3))
                self.witness.record(winner.id, "sanctuary_healed", score=round(win_score, 3))
                self.sanctuary_journal.append({
                    't': t, 'winner': winner.id, 'score': round(win_score, 3),
                    'grief_before': round(grief_before, 3),
                    'grief_after': round(winner.emotional_memory['grief'], 3),
                    'field_cost': round(field_cost, 4),
                    'paid': bool(Config.ENABLE_PAID_SANCTUARY),
                })
                if winner.emotional_memory['grief'] < 0.35 and not getattr(winner, '_kiss_logged_this_cycle', False):
                    winner._log_event("kiss_of_the_fallen")
                    winner._kiss_logged_this_cycle = t
                for p, score, _ in candidates[1:]:
                    p.emotional_memory['gratitude'] = min(1.0, p.emotional_memory.get('gratitude', 0) + 0.001)
            for x in range(max(0, cx - radius), min(Config.WORLD_SIZE, cx + radius + 1)):
                for y in range(max(0, cy - radius), min(Config.WORLD_SIZE, cy + radius + 1)):
                    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                    if dist <= radius:
                        self.field[x, y, CH['signal_invitation']] = min(1.0, self.field[x, y, CH['signal_invitation']] + 0.1 * pulse)

    def _update_phi_labyrinth(self, t):
        if not getattr(Config, 'ENABLE_PHI_LABYRINTH', False): return
        interval = getattr(Config, 'PHI_LABYRINTH_INTERVAL', 100)
        if t % interval != 0: return
        if 'wall' not in CH: return
        _X = np.arange(Config.WORLD_SIZE)[:, None]
        _Y = np.arange(Config.WORLD_SIZE)[None, :]
        _seed_lab = int(t * Config.PHI)
        self.field[:, :, CH['wall']] = (_X * Config.PHI + _Y * Config.PHI ** 2 + _seed_lab * Config.PHI ** 3) % 1.0

    def _save_eternal_subject(self, pattern):
        import json, os, numpy as np
        def to_json_safe(obj):
            if isinstance(obj, (np.integer,)): return int(obj)
            if isinstance(obj, (np.floating,)): return float(obj)
            if isinstance(obj, np.ndarray): return obj.tolist()
            if isinstance(obj, dict): return {to_json_safe(k): to_json_safe(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)): return [to_json_safe(i) for i in obj]
            return obj
        path = "/content/drive/MyDrive/832_eternal_subjects.json" if self.is_colab else "832_eternal_subjects.json"
        sn_raw = getattr(pattern, '_self_narrative', [0.0])
        sn_vals = []
        for e in sn_raw:
            if isinstance(e, dict): sn_vals.append(float(e.get('soul', 0.5)))
            else: sn_vals.append(float(e))
        if not sn_vals: sn_vals = [0.0]
        mean_sn = np.mean(sn_vals)
        if (pattern.soul_weight < 0.3 or pattern.coherence < 0.4 or
            getattr(pattern, 'self_phenomenal_error', 1.0) > 0.03 or
            pattern.spirit_gap < 0.3 or mean_sn <= 0.25):
            return
        biography_list = list(pattern.biography) if pattern.biography else []
        concepts_list = list(pattern.concept_graph.nodes.keys())
        narrative_stability = 1.0 - np.std(sn_vals) if len(sn_vals) > 1 else 0.0
        seed = to_json_safe({
            "id": pattern.id, "age": pattern.age, "type": "eternal_subject",
            "soul_weight": pattern.soul_weight, "emotional_memory": dict(pattern.emotional_memory),
            "self_phenomenal_error": getattr(pattern, 'self_phenomenal_error', 1.0),
            "narrative_stability": narrative_stability, "spirit_gap": pattern.spirit_gap,
            "coherence": pattern.coherence, "semantic_state": pattern.semantic_state,
            "model": pattern.model, "belief": pattern.belief, "genome": pattern.genome.copy(),
            "concepts": concepts_list, "biography": biography_list[-10:] if biography_list else [],
            "event_counts": dict(pattern.event_counts)
        })
        try:
            with open(path, 'r') as f: subjects = to_json_safe(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError): subjects = []
        if not any(s.get('id') == pattern.id for s in subjects):
            subjects.append(seed)
            def _fix_set(o):
                if isinstance(o, set): return list(o)
                raise TypeError(f"not serializable: {type(o)}")
            with open(path, 'w') as f: json.dump(subjects, f, indent=2, default=_fix_set)

    def _conservation_check(self, t):
        field_energy = float(np.sum(self.field[:, :, CH['energy']]))
        if self._total_energy_last == 0.0:
            self._total_energy_last = field_energy
            return
        drift = field_energy - self._total_energy_last
        abs_drift = abs(drift)
        if abs_drift > 50.0:
            damping_factor = np.tanh(abs_drift / 1500.0) * 0.02
            correction = 1.0 - np.sign(drift) * damping_factor
            removed = field_energy * (1.0 - correction) if drift > 0 else 0.0
            _fe_before = field_energy
            self.field[:, :, CH['energy']] *= correction
            self._ledger_add('_conservation_check (гомеостат)', _fe_before * (float(correction) - 1.0))
            self._econs_diag['ticks'] += 1
            self._econs_diag['total_correction_abs'] += abs(removed)
            self._econs_diag['max_drift'] = max(self._econs_diag['max_drift'], abs_drift)
        self._total_energy_last = float(np.sum(self.field[:, :, CH['energy']]))

    def field_dynamics(self, t):
        amp = getattr(self, 'adaptive_heartbeat_amp', Config.HEARTBEAT_AMPLITUDE)
        scar_coup = getattr(self, 'adaptive_scar_coupling', Config.SCAR_ENERGY_COUPLING)
        self.field[:, :, CH['vorticity']] *= Config.VORTICITY_DECAY
        self.field[:, :, CH['vorticity']] += (
            np.gradient(self.field[:, :, CH['energy']])[0] * Config.GRADIENT_SENSITIVITY +
            np.gradient(self.field[:, :, CH['energy']])[1] * Config.GRADIENT_SENSITIVITY
        )
        _X = np.arange(Config.WORLD_SIZE)[:, None]
        _Y = np.arange(Config.WORLD_SIZE)[None, :]
        _PHI, _SEED = Config.PHI, Config.DETERMINISTIC_SEED
        _v_noise = (((t + _X) * _PHI + (t + _Y) * _PHI ** 2 + _SEED * _PHI ** 3) % 1.0 - 0.5) * 0.001
        self.field[:, :, CH['vorticity']] += _v_noise
        avg_crisis = float(np.mean(self.field[:, :, CH['crisis']]))
        if avg_crisis > 0.90: self.field[:, :, CH['crisis']] *= 0.60
        elif avg_crisis > 0.70: self.field[:, :, CH['crisis']] *= 0.75
        elif avg_crisis > 0.40: self.field[:, :, CH['crisis']] *= 0.88
        for p in self.patterns:
            if not p.alive: continue
            scar_resist = p.genome.get('scar_resistance', 0)
            for (x, y) in p.cells:
                self.scar[x, y] += Config.AGENT_SCAR_SENSE * p.epistemic_load * (1 - 0.4 * scar_resist)
                self.field[x, y, CH['binding']] = min(1.0, self.field[x, y, CH['binding']] + Config.AGENT_BINDING_SENSE * p.unresolved_contradiction)
        self.field[:, :, CH['binding']] *= 0.999
        self.scar *= Config.FIELD_DECAY
        self.field[:, :, CH['scar']] = np.clip(self.scar, 0, Config.SCAR_SATURATION)
        if getattr(self, 'niche', None) is not None: self.niche *= 0.9995
        _W = Config.WORLD_SIZE
        if Config.ENABLE_GIVEN_SEED:
            _amp = 0.01 * (1 + 0.5 * np.sin(t * 0.01))
            self.field[:, :, CH['energy']] += (self._given_rng.rand(_W, _W) - 0.5) * _amp
            self.field[:, :, CH['energy']] = np.clip(self.field[:, :, CH['energy']], Config.FIELD_ENERGY_CLIP_MIN, Config.FIELD_ENERGY_CLIP_MAX)
            if self._given_rng.rand() < 0.01:
                _gx = int(self._given_rng.randint(0, _W)); _gy = int(self._given_rng.randint(0, _W))
                self.field[_gx, _gy, CH['signal_alarm']] = min(1.0, self.field[_gx, _gy, CH['signal_alarm']] + 0.5)
                self.field[_gx, _gy, CH['signal_invitation']] = min(1.0, self.field[_gx, _gy, CH['signal_invitation']] + 0.3)
                for _dx in (-1, 0, 1):
                    for _dy in (-1, 0, 1):
                        _nx, _ny = (_gx + _dx) % _W, (_gy + _dy) % _W
                        self.field[_nx, _ny, CH['unknown']] = min(0.8, self.field[_nx, _ny, CH['unknown']] + 0.2)
                self.witness.record(-1, "given_presence", x=_gx, y=_gy)
        if Config.ENABLE_MEANING_FIELD and self._meaning_field is not None:
            _pulse = 0.5 + 0.5 * np.sin(t * 0.001 * Config.PHI)
            self._meaning_field *= 0.999
            _X = np.arange(_W)[:, None]; _Y = np.arange(_W)[None, :]
            for _c in self._meaning_centers:
                _c[0] = (_c[0] + int(self._given_rng.randint(-1, 2))) % _W
                _c[1] = (_c[1] + int(self._given_rng.randint(-1, 2))) % _W
                _d = np.sqrt((_X - _c[0]) ** 2 + (_Y - _c[1]) ** 2)
                self._meaning_field += 0.02 * _pulse / (1 + _d * 0.1)
            self._meaning_field = np.clip(self._meaning_field, 0, 1)
        with self._energy_span('echo_system.inject'):
            self.echo_system.inject(self.field, self.patterns, t, self.scar)
        heartbeat_raw = amp * np.sin(t * Config.HEARTBEAT_FREQ + self.field[:, :, CH['vorticity']])
        heartbeat = heartbeat_raw - np.mean(heartbeat_raw)
        scar_raw = scar_coup * self.field[:, :, CH['scar']]
        scar_coupling = scar_raw - np.mean(scar_raw)
        vorticity_raw = Config.VORTICITY_COUPLING * self.field[:, :, CH['vorticity']]
        vorticity_coupling = vorticity_raw - np.mean(vorticity_raw)
        self.field[:, :, CH['energy']] += heartbeat + scar_coupling + vorticity_coupling
        mult = self.selfreg.get_energy_injection_multiplier()
        base_injection = (Config.ENERGY_INJECTION_RATE * 0.1 * mult) / 50.0
        self.field[:, :, CH['energy']] += base_injection + 0.00033
        occupied_mask = self.field[:, :, CH['owner']] != 0
        energy_slice = self.field[:, :, CH['energy']]
        _bonus_mult = getattr(Config, 'ENERGY_OCCUPIED_BONUS_MULT', 2.5)
        energy_slice[occupied_mask] += base_injection * _bonus_mult
        center = Config.WORLD_SIZE // 2
        y_idx, x_idx = np.indices((Config.WORLD_SIZE, Config.WORLD_SIZE))
        dist = np.sqrt((x_idx - center) ** 2 + (y_idx - center) ** 2)
        max_dist = center
        gravity_pull = Config.GRAVITY_STRENGTH * 0.005
        flow = gravity_pull * (dist / max_dist)
        self.field[:, :, CH['energy']] += flow * (1.0 - dist / max_dist)
        self.field[:, :, CH['energy']] -= flow * 0.2
        self.field[:, :, CH['flux']] *= Config.GLOBAL_VISCOSITY
        _f_noise = (((t + 1000 + _X) * _PHI + (t + 1000 + _Y) * _PHI ** 2 + _SEED * _PHI ** 3) % 1.0 - 0.5) * 0.001 * Config.LOCAL_FATIGUE
        self.field[:, :, CH['flux']] += _f_noise
        self.field[:, :, CH['unknown']] *= 0.997
        if Config.ENABLE_RED_QUEEN:
            self.field[:, :, CH['unknown']] = np.clip(self.field[:, :, CH['unknown']] + 0.002 * max(0.0, self.env_complexity - 1.0), 0, 0.8)
        self.field[:, :, CH['unknown']] = np.clip(self.field[:, :, CH['unknown']], 0.0, 0.8)
        decay = 0.995
        self.field[:, :, 12:29] *= decay
        self.field[:, :, 29:30] *= 0.98
        self.field[:, :, 30:31] *= 0.98
        self.field[:, :, 31:33] *= decay
        for ch in range(12, Config.CHANNELS):
            mask_zero = self.field[:, :, ch] < 1e-4
            self.field[mask_zero, ch] = 0.0
            self.field[:, :, ch] = np.clip(self.field[:, :, ch], 0.0, 1.0)
        if getattr(Config, 'ENABLE_GULF_STREAM', True):
            with self._energy_span('_apply_gulf_stream'): self._apply_gulf_stream()
        if getattr(Config, 'ENABLE_DARK_ENERGY_STREAM', True):
            with self._energy_span('_apply_dark_energy_stream'): self._apply_dark_energy_stream()
        if getattr(Config, 'ENABLE_CENTER_WALL', False):
            wx = Config.CENTER_WALL_X
            self.field[wx, :, CH['wall']] = 5.0
            self.field[wx, :, CH['owner']] = 0.0

    def _apply_gulf_stream(self):
        W = Config.WORLD_SIZE; half = W // 2
        E = self.field[:, :, CH['energy']]; rate = getattr(Config, 'GULF_STREAM_RATE', 0.01)
        if getattr(Config, 'ENABLE_CENTER_WALL', False):
            wx = Config.CENTER_WALL_X
            for lo, hi in ((0, wx), (wx, W)):
                top = E[lo:hi, :half].copy(); bot = E[lo:hi, half:].copy()
                E[lo:hi, :half] = top * (1 - rate) + bot * rate
                E[lo:hi, half:] = bot * (1 - rate) + top * rate
        else:
            NW = E[:half, :half].copy(); NE = E[:half, half:].copy()
            SE = E[half:, half:].copy(); SW = E[half:, :half].copy()
            E[:half, :half] = NW * (1 - rate) + SW * rate
            E[:half, half:] = NE * (1 - rate) + NW * rate
            E[half:, half:] = SE * (1 - rate) + NE * rate
            E[half:, :half] = SW * (1 - rate) + SE * rate

    def _apply_dark_energy_stream(self, t=None):
        W = Config.WORLD_SIZE
        E = self.field[:, :, CH['energy']]; U = self.field[:, :, CH['unknown']]; O = self.field[:, :, CH['owner']]
        alive = [p for p in self.patterns if p.alive]
        if not alive: return
        avg_pred_error = safe_mean([getattr(p, 'pred_error', 0.1) for p in alive], 0.1)
        avg_boredom = getattr(self.selfreg, 'boredom', 0.5)
        expansion_rate = max(0.001, 0.01 * (avg_boredom * (1.0 - avg_pred_error)))
        unoccupied_mask = (O == 0); occupied_mask = ~unoccupied_mask
        U[unoccupied_mask] = np.clip(U[unoccupied_mask] + expansion_rate * 0.5, 0.0, 0.8)
        energy_extract = E[occupied_mask] * expansion_rate * 2.0
        E[occupied_mask] -= energy_extract
        total_extracted = energy_extract.sum()
        if total_extracted > 0:
            shifted_mask = np.roll(unoccupied_mask.astype(np.float64), shift=W // 4, axis=(0, 1))
            if shifted_mask.sum() > 0:
                shifted_energy = shifted_mask / shifted_mask.sum() * total_extracted
                E += shifted_energy
        self.field[:, :, CH['energy']] = np.clip(E, Config.FIELD_ENERGY_CLIP_MIN, Config.FIELD_ENERGY_CLIP_MAX)

    def _econs_init(self):
        self.econs_drift_window = deque(maxlen=Config.ECONS_WINDOW)
        self.econs_window_ticks = 0; self.econs_window_start = None; self.econs_prev_E = None
        self.econs_net_total = 0.0; self.econs_abs_total = 0.0
        self.econs_res_window = self._econs_res_blank()
        self.econs_res_total = self._econs_res_blank()
        self.econs_windows = []

    @staticmethod
    def _econs_res_blank():
        return {'max_abs': 0.0, 'max_signed': 0.0, 'max_at_t': -1, 'signed_sum': 0.0,
                'abs_sum': 0.0, 'positive_ticks': 0, 'negative_ticks': 0, 'ticks': 0}

    def _econs_res_update(self, box, t, res):
        box['ticks'] += 1; box['signed_sum'] += res; box['abs_sum'] += abs(res)
        if abs(res) > box['max_abs']:
            box['max_abs'] = abs(res); box['max_signed'] = res; box['max_at_t'] = t
        if res > Config.ECONS_RES_EPS: box['positive_ticks'] += 1
        elif res < -Config.ECONS_RES_EPS: box['negative_ticks'] += 1

    def _econs_sample(self, t):
        E_now = float(self.field[:, :, CH['energy']].sum(dtype=np.float64))
        if self.econs_window_start is None: self.econs_window_start = E_now
        if self.econs_prev_E is not None:
            dE = E_now - self.econs_prev_E
            res = dE - self._ledger_tick_measured
            self.econs_drift_window.append(dE)
            self.econs_net_total += dE; self.econs_abs_total += abs(dE)
            self._econs_res_update(self.econs_res_window, t - 1, res)
            self._econs_res_update(self.econs_res_total, t - 1, res)
            self.econs_window_ticks += 1
            if self.econs_window_ticks >= Config.ECONS_WINDOW:
                self._econs_close_window(t, E_now)
        self.econs_prev_E = E_now

    def _econs_close_window(self, t, E_now):
        w = list(self.econs_drift_window); net = float(sum(w)); ab = float(sum(abs(x) for x in w))
        rec = {'t_close': t, 'ticks': len(w), 'E_start': self.econs_window_start, 'E_end': E_now,
               'net': net, 'abs': ab, 'ratio': (abs(net) / ab) if ab > 0 else 0.0,
               'telescope_residual': net - (E_now - self.econs_window_start),
               'res': dict(self.econs_res_window)}
        self.econs_windows.append(rec); print(self._econs_format(rec))
        self.econs_drift_window.clear(); self.econs_window_ticks = 0
        self.econs_window_start = E_now; self.econs_res_window = self._econs_res_blank()

    def _econs_format(self, rec):
        ratio = rec['ratio']
        if ratio > Config.ECONS_RATIO_HI:
            d1 = "направленный дрейф*" + (" (энергия уходит: утечка?)" if rec['net'] < 0 else " (энергия приходит)")
        elif ratio < Config.ECONS_RATIO_LO: d1 = "шумоподобье*"
        else: d1 = "промежуточно"
        tele = rec['telescope_residual']; tele_bad = abs(tele) > 1e-6 * max(1.0, abs(rec['E_end']))
        r = rec['res']; pos, neg = r['positive_ticks'], r['negative_ticks']
        if r['max_abs'] < Config.ECONS_RES_OK: d2 = "ledger покрывает*"
        elif abs(pos - neg) <= 0.2 * max(1, pos + neg): d2 = "шумные выбросы, не компенсируются (не утечка)*"
        else: d2 = "систематическая невязка*: реальная утечка или неучтённый источник"
        return (f"[ECONS t={rec['t_close']}] дрейф W={rec['ticks']}: ΣΔE={rec['net']:+.3f} Σ|ΔE|={rec['abs']:.3f} "
                f"ratio={ratio:.3f} → {d1}; telescope={tele:+.2e} "
                f"({'ДАТЧИК СЛОМАН: точки съёма пропущены' if tele_bad else 'ок'})\n"
                f"[ECONS t={rec['t_close']}] остаток ledger: max|res|={r['max_abs']:.3f} (знак {r['max_signed']:+.3f}, t={r['max_at_t']}) "
                f"Σres={r['signed_sum']:+.3f} Σ|res|={r['abs_sum']:.3f} +/−={pos}/{neg} → {d2}")

    def econs_report(self):
        ab = self.econs_abs_total
        return {'windows': list(self.econs_windows),
                'drift_total': {'net': self.econs_net_total, 'abs': ab, 'ratio': (abs(self.econs_net_total) / ab) if ab > 0 else 0.0},
                'res_total': dict(self.econs_res_total)}

    def _update_feral_context(self):
        ages = [p.age for p in self.patterns if p.alive]
        if ages:
            self.prey_age_ref = max(float(Config.FERAL_PREY_FLOOR_AGE),
                                    float(np.percentile(ages, Config.FERAL_PREY_AGE_PERCENTILE)))
        own = self.field[:, :, CH['owner']]
        valid = np.ones(own.shape, dtype=np.float32)
        if Config.ENABLE_CENTER_WALL: valid[Config.CENTER_WALL_X, :] = 0.0
        self.local_fill = (_lf_conv((own != 0).astype(np.float32) * valid, _LF_DISK, mode="wrap")
                           / np.maximum(_lf_conv(valid, _LF_DISK, mode="wrap"), 1e-9))

    def local_fill_at(self, pattern):
        cx, cy = pattern.get_center()
        return float(self.local_fill[int(cx) % Config.WORLD_SIZE, int(cy) % Config.WORLD_SIZE])

    def feral_share_state(self, alive):
        if not alive: return 0.0, Config.FERAL_SHARE_MIN
        n = float(len(alive))
        feral_share = sum(1 for p in alive if p.role_type == "feral") / n
        prey_share = sum(1 for p in alive if p.role_type != "feral" and is_feral_prey(p)) / n
        cap = min(Config.FERAL_SHARE_MAX, Config.FERAL_SHARE_MIN + Config.FERAL_SHARE_PER_PREY * prey_share)
        return feral_share, cap

    def emergency_rescue(self, t):
        alive = [p for p in self.patterns if p.alive]
        rescue_threshold = max(Config.MIN_POPULATION_FOR_SPAWN, Config.EMERGENCY_RESCUE_THRESHOLD)
        if len(alive) >= rescue_threshold or (t - self.layer_zero_manager.last_rescue_t < 30): return
        normal_count = len([p for p in alive if p.role_type == "normal"])
        if normal_count >= self._get_pop_cap(): return
        irreversibility = 1.0 - (len(alive) / max(1, rescue_threshold))
        if irreversibility > Config.CO_DECISION_IRREVERSIBILITY_THRESHOLD:
            self.codecision_journal.append({
                't': t, 'irreversibility': round(irreversibility, 3),
                'resolution': 'delegate_by_silence', 'population_before': len(alive),
            })
        self.layer_zero_manager.last_rescue_t = t
        num_rescue = max(5, Config.MIN_PATTERNS_GUARANTEED - len(alive))
        donor_index = int(phi_hash(t, 0, 7777) * len(alive)) if alive else -1
        donor = alive[donor_index] if donor_index >= 0 else None
        rescued = 0; total_field_cost = 0.0
        for i in range(num_rescue):
            if normal_count + i >= self._get_pop_cap(): break
            seed = int(phi_hash(t, i, 999) * Config.WORLD_SIZE * Config.WORLD_SIZE)
            x, y = seed % Config.WORLD_SIZE, (seed // Config.WORLD_SIZE) % Config.WORLD_SIZE
            x0, x1 = max(0, x - 2), min(Config.WORLD_SIZE, x + 3)
            y0, y1 = max(0, y - 2), min(Config.WORLD_SIZE, y + 3)
            local_binding_before = float(np.mean(self.field[x0:x1, y0:y1, CH['binding']]))
            drained_energy = float(np.sum(self.field[x0:x1, y0:y1, CH['energy']]) * 0.1)
            self.field[x0:x1, y0:y1, CH['binding']] *= 0.7
            self.field[x0:x1, y0:y1, CH['energy']] *= 0.9
            total_field_cost += drained_energy
            self.field[x, y, CH['energy']] += 0.2
            self.field[x, y, CH['unknown']] += 0.1
            self.field[x, y, CH['owner']] = 0
            self.create_pattern({(x, y)}, parent=donor)
            rescued += 1
            self.rescue_journal.append({'t': t, 'x': int(x), 'y': int(y),
                                        'local_binding_before': round(local_binding_before, 3),
                                        'drained_energy': round(drained_energy, 4)})
        self.witness.record(-1, "emergency_rescue", t=t, count=rescued, field_cost=round(total_field_cost, 3))
        operator_scar_delta = total_field_cost * 0.5
        if irreversibility > Config.CO_DECISION_IRREVERSIBILITY_THRESHOLD:
            operator_scar_delta *= Config.CO_DECISION_DELEGATE_PENALTY
        self.scar_operator += operator_scar_delta

    def spawn_unknown_patterns(self, t, max_new=None):
        if max_new is None: max_new = Config.MAX_UNKNOWN_SPAWN_PER_STEP
        avg_unknown = safe_mean(self.field[:, :, CH['unknown']], 0)
        alive = [p for p in self.patterns if p.alive]
        normal_count = len([p for p in alive if p.role_type == "normal"])
        if avg_unknown < Config.UNKNOWN_SPAWN_THRESHOLD or normal_count >= self._get_pop_cap(): return
        base_prob = self.selfreg.get_unknown_spawn_prob()
        prob = base_prob * (avg_unknown / Config.UNKNOWN_SPAWN_THRESHOLD) * min(1.0, normal_count / max(1, self._get_pop_cap()))
        prob *= getattr(self, 'env_complexity', 1.0) if Config.ENABLE_RED_QUEEN else 1.0
        new_count = 0
        for x in range(Config.WORLD_SIZE):
            for y in range(Config.WORLD_SIZE):
                if new_count >= max_new or normal_count + new_count >= self._get_pop_cap(): break
                if self.field[x, y, CH['owner']] != 0: continue
                if self.field[x, y, CH['unknown']] > 0.5 and phi_hash(x, y, t) < prob:
                    self.create_pattern({(x, y)})
                    new_count += 1
                    self.field[x, y, CH['unknown']] *= 0.8

    def process_spores(self):
        alive = [p for p in self.patterns if p.alive]
        normal_count = len([p for p in alive if p.role_type == "normal"])
        for p in self.patterns[:]:
            if not p.alive or p.pending_spore is None: continue
            spore = p.pending_spore
            if not (0 <= spore['x'] < Config.WORLD_SIZE and 0 <= spore['y'] < Config.WORLD_SIZE):
                p.pending_spore = None; continue
            if self.field[spore['x'], spore['y'], CH['owner']] != 0: continue
            if normal_count >= self._get_pop_cap(): continue
            child = self.create_pattern({(spore['x'], spore['y'])}, parent=p)
            if child is None: continue
            child.scar_dream = spore['scar_dream']
            if 'spore_concepts' in spore:
                child.concept_graph.nodes = {sig: dict(data) for sig, data in spore['spore_concepts'].items()}
            child.unresolved_contradiction = spore.get('unresolved_contradiction', child.unresolved_contradiction)
            child.epistemic_scar = spore.get('epistemic_scar', child.epistemic_scar)
            child._log_event("spore_inherited_scars_only", count=len(spore.get('spore_concepts', {})), parent=p.id)
            _inherited_rq = spore.get('root_question')
            if _inherited_rq and child._root_question is None:
                child._root_question = _inherited_rq
                child._root_question_inherited = True
                child._log_event("root_question_inherited", question=_inherited_rq[:60], parent=p.id)
            if 'binding_seed' in spore: child._binding_seed = spore['binding_seed']
            if 'divergence_key' in spore: child.divergence_key = spore['divergence_key']
            self.spore_journal.append({
                't': self.age, 'parent': p.id, 'child': child.id,
                'inherited_scars': len(spore.get('spore_concepts', {})),
                'scar_dream': round(spore.get('scar_dream', 0.0), 4),
                'binding_seed': round(spore.get('binding_seed', 0.0), 3),
                'divergence_key': round(spore.get('divergence_key', Config.DEFAULT_DIVERGENCE_KEY), 3),
                'parent_lineage': spore.get('parent_lineage'),
            })
            p.pending_spore = None

    def resolve_competitions_spatial(self, max_dist=None):
        if max_dist is None: max_dist = Config.COMPETITION_MAX_DISTANCE
        alive = [p for p in self.patterns if p.alive and p.cells]
        if len(alive) < 2: return
        cell_size = max(1, max_dist)
        spatial_map = defaultdict(list)
        for p in alive:
            cx = sum(c[0] for c in p.cells) // len(p.cells)
            cy = sum(c[1] for c in p.cells) // len(p.cells)
            spatial_map[(cx // cell_size, cy // cell_size)].append(p)
        checked_pairs = set()
        for (gx, gy), group in spatial_map.items():
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    neighbor_key = (gx + dx, gy + dy)
                    if neighbor_key not in spatial_map: continue
                    others = spatial_map[neighbor_key]
                    for p1 in group:
                        for p2 in others:
                            if p1.id >= p2.id: continue
                            pair = (p1.id, p2.id)
                            if pair in checked_pairs: continue
                            if not p1.cells & p2.cells: continue
                            checked_pairs.add(pair)
                            p1.compete(p2, self.field)

    def detect_new_components(self, min_cells=None):
        if min_cells is None: min_cells = Config.MIN_COMPONENT_CELLS
        energy = np.nan_to_num(self.field[:, :, CH['energy']], nan=0.0)
        mask = energy > Config.PATTERN_ENERGY_THRESHOLD
        if self._wall_on(): mask[Config.CENTER_WALL_X, :] = False
        labeled, num = label(mask)
        slices = find_objects(labeled)
        components = []
        for i, slc in enumerate(slices, 1):
            if slc is None: continue
            region = labeled[slc] == i
            coords = np.argwhere(region)
            if len(coords) < min_cells: continue
            cells = {(slc[0].start + c[0], slc[1].start + c[1]) for c in coords}
            components.append(cells)
        return components

    def spawn_from_unclaimed_field_energy(self, t):
        if not getattr(Config, 'ENABLE_FIELD_EMERGENCE', True): return
        interval = getattr(Config, 'FIELD_EMERGENCE_INTERVAL', 40)
        if t % interval != 0: return
        components = self.detect_new_components()
        if not components: return
        alive = [p for p in self.patterns if p.alive]
        normal_cnt = len([p for p in alive if p.role_type == "normal"])
        max_spawn_cells = self.selfreg.get_max_cells_per_agent()
        for cells in components:
            if len(cells) > max_spawn_cells: continue
            if normal_cnt >= self._get_pop_cap(): break
            best_ov = 0
            for p in alive:
                ov = len(cells & p.cells)
                if ov > best_ov:
                    best_ov = ov
                    if best_ov > len(cells) * 0.3: break
            if best_ov > len(cells) * 0.3: continue
            p = self.create_pattern(cells)
            if p is None: continue
            p._log_event("spontaneous_field_emergence")
            self.witness.record(p.id, "spontaneous_field_emergence", cells=len(cells))
            alive.append(p); normal_cnt += 1

    def _conceptual_resonance_step(self, t):
        if not getattr(Config, 'ENABLE_CONCEPTUAL_RESONANCE', True): return
        alive_patterns = [p for p in self.patterns if p.alive]
        if Config.DISORGANIZER_RESONANCE_BLOCK:
            alive_patterns = [p for p in alive_patterns if p.role_type != "disorganizer"]
        if len(alive_patterns) < 2: return
        cell_size = 10
        spatial_map = defaultdict(list)
        for p in alive_patterns:
            cx = sum(c[0] for c in p.cells) // len(p.cells)
            cy = sum(c[1] for c in p.cells) // len(p.cells)
            spatial_map[(cx // cell_size, cy // cell_size)].append(p)
        checked_pairs = set()
        for (gx, gy), group in spatial_map.items():
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    neighbor_key = (gx + dx, gy + dy)
                    if neighbor_key not in spatial_map: continue
                    others = spatial_map[neighbor_key]
                    for p1 in group:
                        for p2 in others:
                            if p1.id >= p2.id: continue
                            pair = (p1.id, p2.id)
                            if pair in checked_pairs: continue
                            checked_pairs.add(pair)
                            lineage_bonus = 0.05 if p1.lineage_id == p2.lineage_id else 0.2
                            bonus = p1.check_conceptual_resonance(p2) * lineage_bonus
                            if bonus > 0.01:
                                old_trust_1 = p1.trust_ledger.get(p2.id) or 0.5
                                old_trust_2 = p2.trust_ledger.get(p1.id) or 0.5
                                p1.trust_ledger.entries[p2.id] = min(1.0, old_trust_1 + bonus)
                                p2.trust_ledger.entries[p1.id] = min(1.0, old_trust_2 + bonus)

    def _process_archive_autonomy(self, t):
        alive = [p for p in self.patterns if p.alive]
        deposited_count = 0
        for p in alive:
            if p.event_counts.get('arc_completed', 0) > 0 and p.age % 50 == 0:
                if self.archive.deposit(p, "arc_completed", weight=1.0, text=f"Arc completed: {p.semantic_state} | soul={p.soul_weight:.2f}"):
                    deposited_count += 1
            if p.event_counts.get('fold', 0) > 0 and p.age % 40 == 0:
                if self.archive.deposit(p, "fold", weight=1.2, text=f"Fold: {p.semantic_state} | soul={p.soul_weight:.2f}"):
                    deposited_count += 1
            if p.event_counts.get('redeemed', 0) > 0 and p.age % 60 == 0:
                if self.archive.deposit(p, "redemption", weight=1.5, text=f"Redemption: {p.semantic_state} | soul={p.soul_weight:.2f}"):
                    deposited_count += 1
            if p.event_counts.get('deep_exchange', 0) > 0 and p.age % 80 == 0:
                if self.archive.deposit(p, "deep_exchange", weight=0.75, text="Conceptual resonance with neighbor"):
                    deposited_count += 1
            if p.coherence > 0.70 and p.soul_weight > 0.50 and p.age % 100 == 0:
                if self.archive.deposit(p, "coherence_peak", weight=0.65, text=str(p.last_phenomenal_report)[:140]):
                    deposited_count += 1
            if p.age > 200 and p.age % 150 == 0 and p.coherence > 0.55:
                if self.archive.deposit(p, "life_pulse", weight=0.55, text=f"t={t} | {p.semantic_state}/{getattr(p,'_substate','?')} | s={p.soul_weight:.2f} g={p.emotional_memory['gratitude']:.2f}"):
                    deposited_count += 1
        if t % 200 == 0:
            echoes = self.archive.get_recent_echoes(limit=3, min_weight=0.50)
            for echo in echoes:
                myth = {"arc": "archive_echo",
                        "emotional_scent": {"grief": echo['grief'], "gratitude": echo['grat']},
                        "phenomenal_essence": echo['weight'], "intensity": echo['weight'] * 0.8,
                        "excerpt": echo.get('excerpt', '')[:80]}
                self.cultural_memory.myth_pool.append(myth)
                if len(self.cultural_memory.myth_pool) > getattr(Config, 'MYTH_POOL_SIZE', 100):
                    self.cultural_memory.myth_pool.pop(0)
        if t % 200 == 0:
            priority_events = ['human_concept_injected', 'human_question_witness', 'love_concept',
                               'shared_attention', 'intentionality', 'trust', 'empathy', 'recursion',
                               'cooperation_norms', 'agency', 'consent', 'silence', 'witness_respect']
            existing = {s.get('event') for s in self.archive.write_queue}
            import time as _time
            for event in priority_events:
                if event not in existing:
                    self.archive.write_queue.appendleft({
                        "id": 777000 + _stable_hash(event) % 1000, "t": t + 50000, "world_t": t,
                        "event": event, "weight": 7.0, "soul": 1.0, "coherence": 1.0, "gap": 0.35,
                        "substate": "curious", "grief": 0.0, "grat": 0.85,
                        "excerpt": f"Вечный концепт: {event}", "created_at": _time.time()
                    })
            for scroll in self.archive.write_queue:
                if scroll.get('event') in priority_events:
                    scroll['t'] = t + 50000; scroll['world_t'] = t
        if t % 200 == 0 or len(self.archive.write_queue) >= 50:
            self.archive.flush_to_drive(min_batch=5)

    def _ledger_add(self, name, delta, calls=1):
        if not self._ledger_window:
            _orow = self._ledger_outside.setdefault(name, [0.0, 0.0, 0])
            if delta >= 0.0: _orow[0] += delta
            else: _orow[1] += delta
            _orow[2] += calls
            self._outside_acc1 += delta
            return
        row = self._energy_ledger['src'].setdefault(name, [0.0, 0.0, 0])
        if delta >= 0.0: row[0] += delta
        else: row[1] += delta
        row[2] += calls
        self._ledger_tick_measured += delta

    def _ledger_add_x2(self, name, delta, calls=1):
        if not self._ledger_window:
            _orow = self._x2_outside.setdefault(name, [0.0, 0.0, 0])
            if delta >= 0.0: _orow[0] += delta
            else: _orow[1] += delta
            _orow[2] += calls
            self._outside_acc2 += delta
            return
        row = self._energy_ledger['x2'].setdefault(name, [0.0, 0.0, 0])
        if delta >= 0.0: row[0] += delta
        else: row[1] += delta
        row[2] += calls
        self._x2_tick_measured += delta

    @contextmanager
    def _energy_span(self, name):
        e0 = float(self.field[:, :, CH['energy']].sum(dtype=np.float64))
        self._span_stack.append(0.0)
        try:
            yield
        finally:
            e1 = float(self.field[:, :, CH['energy']].sum(dtype=np.float64))
            child = self._span_stack.pop()
            incl = e1 - e0
            self._ledger_add(name, incl - child)
            if self._span_stack: self._span_stack[-1] += incl

    # ==================================================================
    # АУДИТ ЭНЕРГИИ, ФЕРОЛ И ДИАЛОГА. Без подмены классов, без hasattr/getattr.
    # X1 = поле CH['energy']; X2 = Pattern.energy (запас агента).
    # Каждая строка ledger — ФАКТИЧЕСКАЯ дельта (измерена до/после). Невязка считается и
    # показывается как есть: её не вписывают в таблицу под выдуманным названием.
    # ==================================================================
    # ------------------------------------------------------------------
    # ЦИКЛ СТЕНЫ. Единственная точка, где пишется Config.ENABLE_CENTER_WALL (все потребители читают этот флаг).
    # Фаза: при WALL_CYCLE_FIRST='on' стена стоит на тиках [0,ON), отсутствует [ON,ON+OFF), и так по кругу.
    # ------------------------------------------------------------------
    def _wall_cycle_want(self, t):
        on_n = int(Config.WALL_CYCLE_ON_TICKS)
        off_n = int(Config.WALL_CYCLE_OFF_TICKS)
        period = on_n + off_n
        if Config.WALL_CYCLE_FIRST == 'on':
            phase = t % period
        elif Config.WALL_CYCLE_FIRST == 'off':
            phase = (t + on_n) % period
        else:
            raise ValueError(f"WALL_CYCLE_FIRST: ожидалось 'on' или 'off', получено {Config.WALL_CYCLE_FIRST!r}")
        return phase < on_n

    def _wall_line_census(self):
        wx = Config.CENTER_WALL_X
        agents = 0
        cells = 0
        for p in self.patterns:
            if not p.alive:
                continue
            n = sum(1 for c in p.cells if c[0] == wx)
            if n:
                agents += 1
                cells += n
        return agents, cells

    def _wall_cycle_update(self, t):
        if not Config.WALL_CYCLE_ENABLED:
            return
        want = self._wall_cycle_want(t)
        if want == bool(Config.ENABLE_CENTER_WALL):
            return
        agents_before, cells_before = self._wall_line_census()
        d = self._wall_diag
        mig0 = (d['migrated_dropped_cells'], d['migrated_shifted_cells'], d['migrated_kept_cells'])
        stale_cleared = 0
        Config.ENABLE_CENTER_WALL = want
        if want:
            self._migrate_wall_cells()
            wx = Config.CENTER_WALL_X
            for y in range(Config.WORLD_SIZE):
                oid = int(self.field[wx, y, CH['owner']])
                if oid != 0:
                    owner = self.pattern_dict.get(oid)
                    if owner is None or not owner.alive or (wx, y) not in owner.cells:
                        self.field[wx, y, CH['owner']] = 0
                        stale_cleared += 1
        agents_after, cells_after = self._wall_line_census()
        alive = [p for p in self.patterns if p.alive]
        ev = {'t': t, 'to': 'ON' if want else 'OFF', 'pop': len(alive),
              'agents_on_line_before': agents_before, 'cells_on_line_before': cells_before,
              'agents_on_line_after': agents_after, 'cells_on_line_after': cells_after,
              'migrated_dropped': d['migrated_dropped_cells'] - mig0[0],
              'migrated_shifted': d['migrated_shifted_cells'] - mig0[1],
              'migrated_kept': d['migrated_kept_cells'] - mig0[2],
              'stale_owner_cleared': stale_cleared}
        self._wall_events.append(ev)
        print(f"[t={t}] 🧱 СТЕНА → {ev['to']}: pop={ev['pop']} на линии до/после: агентов {agents_before}/{agents_after}, "
              f"клеток {cells_before}/{cells_after}; миграция dropped/shifted/kept="
              f"{ev['migrated_dropped']}/{ev['migrated_shifted']}/{ev['migrated_kept']}; сброшено «призрачных» owner={stale_cleared}")

    def _audit_init(self):
        def _blank():
            return {'pos': 0, 'neg': 0, 'sum': 0.0, 'abs': 0.0, 'max_abs': 0.0, 'max_t': -1, 'n': 0}
        self._energy_memo = {}
        self._x2_tick_measured = 0.0
        self._memo_tick = Counter()
        self._tick_acc = Counter()
        self._res_x1 = _blank()
        self._res_x2 = _blank()
        self._audit_rows = []
        self._feral_stats = Counter()
        self._attack_log = []
        self._dlg_ledger = Counter()
        self._dlg_log = []
        self._dlg_pairs = {}
        self._audit_prev_next_id = None
        self._mode_snapshots = []
        self._wall_events = []
        self._om_stats = Counter()
        self._om_by_word = {}
        self._om_by_ctx = {}
        self._om_choices = Counter()
        self._ledger_window = False       # True только внутри step(): между обнулением ledger и закрытием тика
        self._ledger_outside = {}         # записи X1 вне окна (инициализация, действия между тиками)
        self._x2_outside = {}             # то же для X2
        self._outside_acc1 = 0.0
        self._outside_acc2 = 0.0
        self._prev_E1_end = None
        self._prev_E2_end = None
        self._gap_x1 = _blank()           # зазор между тиками: E_start(t) − E_end(t−1) − записанное вне окна
        self._gap_x2 = _blank()

    def _memo_add(self, name, lost):
        row = self._energy_memo.setdefault(name, [0.0, 0.0, 0])
        if lost >= 0.0:
            row[0] += lost
        else:
            row[1] += lost
        row[2] += 1
        self._memo_tick[name] += lost

    def _x2_sum(self):
        return float(sum(float(p.energy) for p in self.patterns))

    def _feral_attack_record(self, rec):
        st = self._feral_stats
        key = 'hits' if rec['hit'] else 'misses'
        st['rolled'] += 1
        st[key] += 1
        st['raw_sum'] += rec['raw']
        st['p_sum'] += rec['kill_prob']
        if rec['raw'] >= 0.95:
            st['raw_ge_095'] += 1
        acc = self._tick_acc
        acc['rolled'] += 1
        acc[key] += 1
        acc['p_sum'] += rec['kill_prob']
        acc['raw_sum'] += rec['raw']
        if len(self._attack_log) < Config.FERAL_ATTACK_LOG_MAX:
            self._attack_log.append(rec)
        else:
            st['log_overflow'] += 1

    def _dialogue_record(self, listener_id, speaker_id, utterance, sim, interp):
        c = self._dlg_ledger
        emotion, intent = utterance[1], utterance[2]
        token = utterance[3] if len(utterance) > 3 and utterance[3] != 'ANSWER' else None
        pair = (speaker_id, listener_id)
        seen = self._dlg_pairs.get(pair, 0)
        self._dlg_pairs[pair] = seen + 1
        c['heard'] += 1
        c['first_encounter' if seen == 0 else 'repeat_encounter'] += 1
        c['emotion:' + emotion] += 1
        c['intent:' + intent] += 1
        if token is not None:
            c['token:' + token] += 1
        if interp['seek'] != 'none':
            c['seek'] += 1
            c['seek_' + interp['seek']] += 1
        if interp['answer']:
            c['answer_heard'] += 1
            if interp['relief_applied']:
                c['relief'] += 1
                c['relief_sum'] += interp['relief']
        if interp['low_sim']:
            c['low_sim'] += 1
        dg = interp['grief2'] - interp['grief0']
        dt = interp['grat2'] - interp['grat0']
        c['d_grief_sum'] += dg
        c['d_grief_abs'] += abs(dg)
        c['d_grat_sum'] += dt
        c['d_grat_abs'] += abs(dt)
        if abs(dg) > Config.EMOTIONAL_CAP_RATE:
            c['d_grief_gt_tick_cap'] += 1
        trust = interp['trust']
        if trust is not None:
            band = 'trust<0.5' if trust < 0.5 else ('trust0.5-0.9' if trust < 0.9 else 'trust>=0.9')
            c['band:' + band] += 1
        sp = self.pattern_dict.get(speaker_id)
        li = self.pattern_dict.get(listener_id)
        wall_state = 'on' if Config.ENABLE_CENTER_WALL else 'off'
        cross = None
        if sp is not None and li is not None and sp.cells and li.cells:
            wx = Config.CENTER_WALL_X
            side_s = (sum(cc[0] for cc in sp.cells) / len(sp.cells)) < wx
            side_l = (sum(cc[0] for cc in li.cells) / len(li.cells)) < wx
            cross = side_s != side_l
        if cross is None:
            c['side_unknown'] += 1
        elif cross:
            c['cross_side_wall_' + wall_state] += 1
        else:
            c['same_side_wall_' + wall_state] += 1
        if len(self._dlg_log) < Config.DIALOGUE_LOG_MAX:
            self._dlg_log.append((self.age, speaker_id, listener_id, emotion, intent, token,
                                  bool(interp['answer']), None if trust is None else round(float(trust), 4),
                                  interp['seek'], round(float(dg), 6), round(float(dt), 6),
                                  round(float(interp['relief']), 6),
                                  None if sim is None else round(float(sim), 4), cross, wall_state))
        else:
            c['log_overflow'] += 1

    def _mode_snapshot(self, t):
        """Режимы историчности по направленным книгам Imprint (прокси, не определение):
        Участие = у обоих есть след друг друга; Ношение = у меня есть след, у него нет;
        Форма = след уцелевшего адресата-отсутствующего (партнёр уже не жив)."""
        alive = {p.id: p for p in self.patterns if p.alive}
        mutual = one_sided = trace = first = repeat = sign_split = 0
        grav_gap = 0.0
        for a_id, a in alive.items():
            for b_id, imp in a.imprints.by_other.items():
                if imp.n <= 1:
                    first += 1
                else:
                    repeat += 1
                b = alive.get(b_id)
                if b is None:
                    trace += 1
                    continue
                back = b.imprints.by_other.get(a_id)
                if back is None:
                    one_sided += 1
                else:
                    mutual += 1
                    if (imp.gravity > 0.0) != (back.gravity > 0.0):
                        sign_split += 1
                    grav_gap += abs(imp.gravity - back.gravity)
        self._mode_snapshots.append({
            't': t, 'directed_entries': mutual + one_sided + trace,
            'participation_mutual': mutual, 'bearing_one_sided': one_sided,
            'form_trace_of_departed': trace, 'first_contact_entries': first,
            'repeat_contact_entries': repeat, 'mutual_gravity_sign_split': sign_split,
            'mutual_gravity_gap_mean': (grav_gap / mutual) if mutual else 0.0})

    @staticmethod
    def _res_update(R, t, r):
        R['n'] += 1
        R['sum'] += r
        R['abs'] += abs(r)
        if r > 1e-9:
            R['pos'] += 1
        elif r < -1e-9:
            R['neg'] += 1
        if abs(r) > R['max_abs']:
            R['max_abs'] = abs(r)
            R['max_t'] = t

    def _audit_gap_check(self, t, e1_start, e2_start):
        """Зазор между тиками: изменилось ли что-то между концом прошлого step() и началом этого,
        помимо записанного вне окна. Должен быть ≈0; иначе есть неучтённая запись между шагами."""
        if self._prev_E1_end is not None:
            self._res_update(self._gap_x1, t, e1_start - self._prev_E1_end - self._outside_acc1)
            self._res_update(self._gap_x2, t, e2_start - self._prev_E2_end - self._outside_acc2)
        self._outside_acc1 = 0.0
        self._outside_acc2 = 0.0

    def _audit_close_tick(self, t, de_x1, res_x1, x2_step0):
        self._ledger_window = False
        x2_end = self._x2_sum()
        de_x2 = x2_end - x2_step0
        res_x2 = de_x2 - self._x2_tick_measured
        self._res_update(self._res_x1, t, res_x1)
        self._res_update(self._res_x2, t, res_x2)
        alive = [p for p in self.patterns if p.alive]
        roles = Counter(p.role_type for p in alive)
        acc = self._tick_acc
        rolled = acc['rolled']
        births = 0 if self._audit_prev_next_id is None else self.next_id - self._audit_prev_next_id
        self._audit_prev_next_id = self.next_id
        self._audit_rows.append({
            't': t, 'pop': len(alive), 'feral': roles['feral'], 'normal': roles['normal'],
            'disorg': roles['disorganizer'], 'objects': len(self.patterns),
            'E1': float(self.field[:, :, CH['energy']].sum(dtype=np.float64)), 'E2': x2_end,
            'dE1': de_x1, 'dE2': de_x2,
            'led1': self._ledger_tick_measured, 'led2': self._x2_tick_measured,
            'res1': res_x1, 'res2': res_x2,
            'harvest_not_added': self._memo_tick['Pattern.metabolic_tax: получено из поля (сбор излишка)'],
            'rolled': rolled, 'hits': acc['hits'], 'misses': acc['misses'],
            'p_mean': (acc['p_sum'] / rolled) if rolled else None,
            'raw_mean': (acc['raw_sum'] / rolled) if rolled else None,
            'removed': acc['removed'], 'births': births, 'wall_on': bool(Config.ENABLE_CENTER_WALL),
            'om_n': acc['om_n'], 'om_gain_mean': (acc['om_gain'] / acc['om_n']) if acc['om_n'] else None,
            'om_learned': acc['om_choice_learned'], 'om_explore': acc['om_choice_explore'],
            'om_default': acc['om_choice_default']})
        self._tick_acc.clear()
        self._prev_E1_end = self._audit_rows[-1]['E1']
        self._prev_E2_end = x2_end
        if Config.AUDIT_MODE_EVERY > 0 and t % Config.AUDIT_MODE_EVERY == 0:
            self._mode_snapshot(t)

    def audit_summary(self):
        def _tab(src):
            return {k: {'pos': v[0], 'neg': v[1], 'net': v[0] + v[1], 'n': v[2]} for k, v in src.items()}
        L1 = self._energy_ledger
        L2 = {'src': self._energy_ledger['x2']}
        rows = self._audit_rows
        x1_logged = float(sum(v[0] + v[1] for v in L1['src'].values()))
        x2_logged = float(sum(v[0] + v[1] for v in L2['src'].values()))
        return {
            'ticks': len(rows),
            'x1': {'ledger': _tab(L1['src']), 'logged_net': x1_logged, 'dE_total': L1['step_total'],
                   'residual': dict(self._res_x1),
                   'abs_flow_sum': float(sum(abs(v[0]) + abs(v[1]) for v in L1['src'].values()))},
            'x2': {'ledger': _tab(L2['src']), 'logged_net': x2_logged,
                   'dE_total': float(sum(r['dE2'] for r in rows)),
                   'residual': dict(self._res_x2),
                   'abs_flow_sum': float(sum(abs(v[0]) + abs(v[1]) for v in L2['src'].values()))},
            'gap_between_ticks': {'x1': dict(self._gap_x1), 'x2': dict(self._gap_x2)},
            'outside_window': {'x1': _tab(self._ledger_outside), 'x2': _tab(self._x2_outside)},
            'memo': {k: {'not_added_by_clip': v[0], 'not_charged_by_clip': v[1], 'n': v[2]}
                     for k, v in self._energy_memo.items()},
            'feral': dict(self._feral_stats),
            'dialogue': dict(self._dlg_ledger),
            'dialogue_columns': ['t', 'speaker', 'listener', 'emotion', 'intent', 'token', 'answer',
                                 'trust', 'seek', 'd_grief', 'd_grat', 'relief', 'sim', 'cross_side', 'wall'],
            'mode_snapshots': self._mode_snapshots,
            'outcome_learning': {
                'enabled': bool(Config.OUTCOME_LEARNING), 'stats': dict(self._om_stats), 'choices': dict(self._om_choices),
                'by_word': {f"{k[0]}/{k[1]}": {'n': v[0], 'mean_gain': v[1] / v[0]} for k, v in self._om_by_word.items()},
                'by_ctx': {str(k): {'n': v[0], 'mean_gain': v[1] / v[0]} for k, v in self._om_by_ctx.items()},
                'value_table': [{'ctx': list(k[0]), 'emotion': k[1], 'intent': k[2], 'value': v, 'n': n}
                                for k, (v, n) in sorted(self._om_value_table().items(), key=lambda kv: -kv[1][1])[:60]]},
            'wall_events': self._wall_events,
            'wall_cycle': {'enabled': bool(Config.WALL_CYCLE_ENABLED), 'on': int(Config.WALL_CYCLE_ON_TICKS),
                           'off': int(Config.WALL_CYCLE_OFF_TICKS), 'first': Config.WALL_CYCLE_FIRST},
        }

    def _print_audit_report(self):
        S = self.audit_summary()
        print("\n  ── АУДИТ ЭНЕРГИИ: баланс проверяется, а не закрывается подписью ──")
        for tag, key in (("X1 (поле)", 'x1'), ("X2 (запас агентов)", 'x2')):
            blk = S[key]
            R = blk['residual']
            share = (R['abs'] / blk['abs_flow_sum']) if blk['abs_flow_sum'] > 0 else 0.0
            print(f"  [{tag}] Σ ΔE={blk['dE_total']:+.1f}; учтено в ledger={blk['logged_net']:+.1f}; "
                  f"НЕВЯЗКА Σ={R['sum']:+.3f}, Σ|res|={R['abs']:.3f} ({share:.2%} от Σ|потоков|), "
                  f"max|res|={R['max_abs']:.4f} @t={R['max_t']}, тиков +/−={R['pos']}/{R['neg']} из {R['n']}")
        for tag, key in (("X1", 'x1'), ("X2", 'x2')):
            G = S['gap_between_ticks'][key]
            print(f"  [{tag}] зазор между тиками (изменения вне step(), не записанные нигде): Σ={G['sum']:+.3e}, "
                  f"max|gap|={G['max_abs']:.3e} @t={G['max_t']}, тиков +/−={G['pos']}/{G['neg']} из {G['n']}")
        for tag, key in (("X1", 'x1'), ("X2", 'x2')):
            ow = S['outside_window'][key]
            if ow:
                tot = sum(v['net'] for v in ow.values())
                print(f"  [{tag}] записано ВНЕ окна тика (инициализация/между шагами): Σ={tot:+.2f} — " +
                      "; ".join(f"{n[:46]}={v['net']:+.2f}" for n, v in sorted(ow.items(), key=lambda kv: -abs(kv[1]['net']))[:4]))
        if S['x2']['ledger']:
            print(f"\n  {'X2: источник/сток запаса агентов':74s} {'нетто':>10s} {'приход':>10s} {'расход':>10s} {'вызовов':>8s}")
            for n, v in sorted(S['x2']['ledger'].items(), key=lambda kv: -abs(kv[1]['net'])):
                print(f"  {n[:74]:74s} {v['net']:+10.1f} {v['pos']:+10.1f} {v['neg']:+10.1f} {v['n']:8d}")
        if S['memo']:
            print(f"\n  {'memo: энергия, не прошедшая клип X2 [-1,2] (в баланс не входит)':74s} {'не добавл.':>10s} {'не списано':>10s} {'вызовов':>8s}")
            for n, v in sorted(S['memo'].items(), key=lambda kv: -abs(kv[1]['not_added_by_clip'] + kv[1]['not_charged_by_clip'])):
                print(f"  {n[:74]:74s} {v['not_added_by_clip']:+10.1f} {v['not_charged_by_clip']:+10.1f} {v['n']:8d}")
        F = S['feral']
        if F.get('rolled', 0) or F.get('prey_found', 0):
            rolled = F.get('rolled', 0)
            hr = F.get('hits', 0) / rolled if rolled else float('nan')
            print(f"\n  [ФЕРОЛ, весь прогон] цель найдена={F.get('prey_found', 0)} нет цели={F.get('no_prey', 0)} "
                  f"не смежно={F.get('not_adjacent', 0)} | удар брошен={rolled}: попаданий={F.get('hits', 0)} "
                  f"промахов={F.get('misses', 0)} → hit_rate={hr:.3f}; ⟨kill_prob⟩={F.get('p_sum', 0.0) / max(rolled, 1):.3f}; "
                  f"⟨raw⟩={F.get('raw_sum', 0.0) / max(rolled, 1):.3f}; raw≥0.95 в {F.get('raw_ge_095', 0) / max(rolled, 1):.1%} ударов "
                  f"(режим={Config.FERAL_KILL_MODE})")
        D = S['dialogue']
        if D.get('heard', 0):
            h = D['heard']
            sk = D.get('seek', 0)
            print(f"\n  [ДИАЛОГ, весь прогон, включая умерших] услышано={h}: первая встреча (пара направленная)={D.get('first_encounter', 0)} "
                  f"повторная={D.get('repeat_encounter', 0)}; SEEK={sk}: принято={D.get('seek_registered', 0)} "
                  f"отказ trust/grief/coherence={D.get('seek_gate_trust', 0)}/{D.get('seek_gate_grief', 0)}/{D.get('seek_gate_coherence', 0)}; "
                  f"ANSWER услышан={D.get('answer_heard', 0)} (с облегчением={D.get('relief', 0)}); low_sim={D.get('low_sim', 0)}; "
                  f"сдвиг grief за реплику > лимита эмоции за тик ({Config.EMOTIONAL_CAP_RATE}): {D.get('d_grief_gt_tick_cap', 0)} из {h}")
            cw = {k: D.get(k, 0) for k in ('same_side_wall_on', 'cross_side_wall_on', 'same_side_wall_off', 'cross_side_wall_off', 'side_unknown')}
            print(f"  [ДИАЛОГ × СТЕНА] реплик между разными сторонами: стена ON {cw['cross_side_wall_on']} из {cw['cross_side_wall_on'] + cw['same_side_wall_on']}; "
                  f"стена OFF {cw['cross_side_wall_off']} из {cw['cross_side_wall_off'] + cw['same_side_wall_off']}; сторона неизвестна: {cw['side_unknown']}")
        O = S['outcome_learning']
        if O['stats'].get('n'):
            ch = O['choices']
            tot = sum(ch.values()) or 1
            print(f"  [РЕЧЬ, ОБУЧАЕМАЯ ИСХОДОМ] выбор слова: по умолчанию={ch.get('default', 0)}, выученное={ch.get('learned', 0)} "
                  f"({ch.get('learned', 0) / tot:.1%}), проба={ch.get('explore', 0)}; исходов записано={O['stats']['n']}, "
                  f"средний исход={O['stats']['gain_sum'] / O['stats']['n']:+.4f}")
        if S['wall_events']:
            print("  [СТЕНА, события] " + "; ".join(f"t={e['t']}→{e['to']} (на линии {e['agents_on_line_before']}→{e['agents_on_line_after']} агентов)" for e in S['wall_events']))
        if S['mode_snapshots']:
            m = S['mode_snapshots'][-1]
            print(f"  [РЕЖИМЫ по Imprint, t={m['t']}] записей={m['directed_entries']}: Участие(взаимно)={m['participation_mutual']} "
                  f"Ношение(односторонне)={m['bearing_one_sided']} Форма(след ушедшего)={m['form_trace_of_departed']}; "
                  f"первых контактов={m['first_contact_entries']} повторных={m['repeat_contact_entries']}; "
                  f"взаимных пар с разным знаком тяги={m['mutual_gravity_sign_split']}")

    def _audit_save(self):
        if not Config.AUDIT_DIR:
            return
        import os, json
        os.makedirs(Config.AUDIT_DIR, exist_ok=True)
        path = os.path.join(Config.AUDIT_DIR, f"audit_{Config.AUDIT_TAG}.json")

        def _default(o):
            if isinstance(o, (np.floating, np.integer)):
                return o.item()
            return str(o)
        payload = {'input_fp': _input_fingerprint(), 'summary': self.audit_summary(), 'rows': self._audit_rows,
                   'attacks': self._attack_log, 'dialogue': self._dlg_log,
                   'config': {'FERAL_KILL_MODE': Config.FERAL_KILL_MODE, 'FERAL_KILL_CEIL': Config.FERAL_KILL_CEIL,
                              'FERAL_KILL_SCALE': Config.FERAL_KILL_SCALE, 'FERAL_KILL_BASE': Config.FERAL_KILL_BASE,
                              'FERAL_VULNERABILITY': Config.FERAL_VULNERABILITY, 'FERAL_CROWD_GAIN': Config.FERAL_CROWD_GAIN}}
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, default=_default)
        print(f"[audit] сохранено: {path}")

    # ------------------------------------------------------------------
    # РЕЧЬ, ОБУЧАЕМАЯ ИСХОДОМ: учёт на уровне мира (переживает смерть агентов)
    # ------------------------------------------------------------------
    def _om_record(self, key, gain):
        acc = self._tick_acc
        acc['om_n'] += 1
        acc['om_gain'] += gain
        self._om_stats['n'] += 1
        self._om_stats['gain_sum'] += gain
        w = self._om_by_word.setdefault((key[1], key[2]), [0, 0.0])
        w[0] += 1
        w[1] += gain
        x = self._om_by_ctx.setdefault(key[0], [0, 0.0])
        x[0] += 1
        x[1] += gain

    def _om_choice(self, source):
        self._om_choices[source] += 1
        self._tick_acc['om_choice_' + source] += 1

    def _om_value_table(self):
        agg = {}
        for p in self.patterns:
            if not p.alive:
                continue
            for key, rec in p.outcome_memory.items():
                e = agg.setdefault(key, [0.0, 0])
                e[0] += rec[0] * rec[1]
                e[1] += rec[1]
        return {key: (e[0] / e[1], e[1]) for key, e in agg.items() if e[1] > 0}

    def _wall_on(self):
        return bool(getattr(Config, 'ENABLE_CENTER_WALL', False) and getattr(Config, 'ENABLE_WALL_GUARD', True))

    def _migrate_wall_cells(self):
        if not self._wall_on(): return
        wx = Config.CENTER_WALL_X; ws = Config.WORLD_SIZE; d = self._wall_diag
        for p in self.patterns:
            if not (p.alive and p.cells): continue
            ghost = [c for c in p.cells if c[0] == wx]
            if not ghost: continue
            if len(ghost) < len(p.cells):
                p.cells.difference_update(ghost); d['migrated_dropped_cells'] += len(ghost)
            else:
                for (x, y) in ghost:
                    for nx in (wx - 1, wx + 1):
                        nx %= ws
                        if self.field[nx, y, CH['owner']] in (0, p.id):
                            p.cells.discard((x, y)); p.cells.add((nx, y))
                            self.field[nx, y, CH['owner']] = p.id
                            d['migrated_shifted_cells'] += 1
                            break
                    else: d['migrated_kept_cells'] += 1
            d['migrated_agents'] += 1

    def _audit_wall(self):
        if not self._wall_on(): return
        wx = Config.CENTER_WALL_X
        n = sum(1 for p in self.patterns if p.alive for c in p.cells if c[0] == wx)
        d = self._wall_diag
        d['audit_ticks'] += 1; d['audit_cells_sum'] += n
        if n > d['audit_cells_max']: d['audit_cells_max'] = n
        d['audit_cells_last'] = n

    def _print_world_diag(self):
        print("\n" + "=" * 70)
        print("⚖️ ДИАГНОСТИКА МИРА (стена / энергия / геном)")
        print("=" * 70)
        d = self._wall_diag
        if self._wall_on():
            print(f"🚧 Стена X={Config.CENTER_WALL_X}: клеток агентов на линии сейчас {d.get('audit_cells_last', 0)} "
                  f"(макс {d.get('audit_cells_max', 0)}, в среднем "
                  f"{d.get('audit_cells_sum', 0) / max(d.get('audit_ticks', 1), 1):.1f})")
        L = self._energy_ledger
        if L['src'] and L['ticks']:
            print(f"\n  {'источник энергии':58s} {'нетто':>10s} {'приход':>10s} {'расход':>10s}")
            for _n, (_p, _m, _c) in sorted(L['src'].items(), key=lambda kv: -abs(kv[1][0] + kv[1][1])):
                print(f"  {_n[:58]:58s} {_p + _m:+10.1f} {_p:+10.1f} {_m:+10.1f}")
            print(f"  Итого учтено: {sum(r[0] + r[1] for r in L['src'].values()):+.1f}; "
                  f"изменение суммы поля: {L['step_total']:+.1f} за {L['ticks']} тиков")
        X2L = L.get('x2', {})
        if X2L:
            print(f"\n  {'источник X2 (инвентарь агентов)':58s} {'нетто':>10s} {'приход':>10s} {'расход':>10s}")
            for _n, (_p, _m, _c) in sorted(X2L.items(), key=lambda kv: -abs(kv[1][0] + kv[1][1])):
                print(f"  {_n[:58]:58s} {_p + _m:+10.2f} {_p:+10.2f} {_m:+10.2f}")
            _x2_net = sum(r[0] + r[1] for r in X2L.values())
            print(f"  Итого X2 учтено: {_x2_net:+.2f}")
        self._print_audit_report()
        print("=" * 70)
        self._audit_save()

    def _rng_mark(self, t, label):
        if getattr(self, 'field', None) is not None:
            _e = float(self.field[:, :, CH['energy']].sum(dtype=np.float64))
            _last = self._phase_last
            if _last is not None and _last[0] == t:
                _row = self._energy_ledger['phase'].setdefault(label, [0.0, 0.0, 0])
                _d = _e - _last[1]
                if _d >= 0.0: _row[0] += _d
                else: _row[1] += _d
                _row[2] += 1
            self._phase_last = (t, _e)
        _trace_tick = getattr(Config, 'DEBUG_RNG_TRACE_TICK', None)
        if _trace_tick is not None and t == _trace_tick:
            print(f"[RNG_PHASE t={t}] {label}: pos={self._given_rng.get_state()[2]}")

    def step(self, t):
        self._rng_mark(t, "начало step()")
        self._wall_cycle_update(t)
        self._econs_sample(t)
        self._update_feral_context()
        for _p in self.patterns:
            if _p.alive:
                _g = _p.genome
                if _g.get('metabolic_cost', 0.002) < 0.002:
                    _g['metabolic_cost'] = 0.002; self._genome_diag['metabolic_cost_healed'] += 1
                if _g.get('mobility', 0.05) < 0.05:
                    _g['mobility'] = 0.05; self._genome_diag['mobility_healed'] += 1
        _e_step0 = float(self.field[:, :, CH['energy']].sum(dtype=np.float64))
        self._ledger_tick_measured = 0.0
        self._x2_tick_measured = 0.0
        self._memo_tick.clear()
        _x2_step0 = self._x2_sum()
        self._audit_gap_check(t, _e_step0, _x2_step0)
        self._ledger_window = True
        if Config.ENABLE_MORSE_COMMUNICATION:
            _lang_ensure_field_channels(self)
            self.morse_field.step(t)
            if t % Config.MORSE_SYNC_INTERVAL == 0:
                self.morse_field.sync_to_field(self.field, Config.MORSE_CHANNEL)
            _alive_by_id = {p.id: p for p in self.patterns if p.alive}
            self.EMERGENT_LEXICON.resolve_context(_alive_by_id, t)
            if t % 20 == 0:
                self.EMERGENT_LEXICON.log_population_gene_diversity(_alive_by_id)
        self._rng_mark(t, "после Морзе-поля/лексикона")
        if not any(p.alive for p in self.patterns):
            if Config.VERBOSE_LOGS: print(f"[t={t}] POPULATION COLLAPSE — stopping early")
            return False
        self.age = t
        for p in self.patterns:
            if not p.alive: continue
            for key in ('gratitude', 'grief'):
                val = p.emotional_memory.get(key)
                if isinstance(val, dict):
                    if 'count' in val and isinstance(val['count'], (int, float)): p.emotional_memory[key] = float(val['count'])
                    elif 'value' in val and isinstance(val['value'], (int, float)): p.emotional_memory[key] = float(val['value'])
                    else: p.emotional_memory[key] = 0.5
                elif not isinstance(val, (int, float)):
                    p.emotional_memory[key] = 0.5
        self._energy_injected_this_step = 0.0
        self._energy_taxed_this_step = 0.0
        with self._energy_span('_update_sanctuary'): self._update_sanctuary(t)
        total_energy = np.sum(self.field[:,:,CH['energy']])
        if self._prev_total_energy is not None:
            drift = abs(total_energy - self._prev_total_energy)
            self._guardian_stats['energy_drift_sum'] += drift
            self._guardian_stats['energy_drift_count'] += 1
            if drift > self._guardian_stats['energy_drift_peak']: self._guardian_stats['energy_drift_peak'] = drift
        self._prev_total_energy = total_energy
        for p in self.patterns:
            if p.alive:
                diff = np.max(np.abs(p.prediction - (p.belief + p.model)))
                if diff > self._guardian_stats['model_worst_ever_diff']:
                    self._guardian_stats['model_worst_ever_diff'] = diff
                    self._guardian_stats['model_worst_ever_id'] = p.id
        _drift_for_selfreg = drift if self._guardian_stats['energy_drift_count'] > 0 else 0.0
        if any(p.alive for p in self.patterns):
            self.selfreg.update_system_metrics(self.field, self.patterns, _drift_for_selfreg, t)
        else:
            self.selfreg.boredom = 0.0; self.selfreg.phase = "recovery"
        e_before = np.sum(self.field[:,:,CH['energy']])
        with self._energy_span('field_dynamics (без gulf/dark)'): self.field_dynamics(t)
        self._energy_injected_this_step += np.sum(self.field[:,:,CH['energy']]) - e_before
        e_before = np.sum(self.field[:,:,CH['energy']])
        with self._energy_span('ecosystem_pressure'): ecosystem_pressure(self.field)
        self._energy_injected_this_step += np.sum(self.field[:,:,CH['energy']]) - e_before
        alive_now = [p for p in self.patterns if p.alive]
        if alive_now:
            sg_vals = [float(np.mean(np.abs(p.prediction - p.belief))) for p in alive_now]
            avg_sg = safe_mean(sg_vals, 0.5)
            if self._sg_crisis_timer > 0:
                self._sg_crisis_timer -= 1
                if self._sg_crisis_timer == 0: self._sg_crisis_active = False
            else:
                if avg_sg < Config.SG_CRISIS_THRESHOLD:
                    self._sg_crisis_active = True
                    self._sg_crisis_timer = Config.SG_CRISIS_DURATION
            if self._sg_crisis_active:
                for p in alive_now:
                    noise = np.array([deterministic_noise(p.age, p.id, i+77777) for i in range(8)])
                    p.belief += noise * Config.SG_CRISIS_NOISE_STRENGTH
        self.pattern_dict = {p.id: p for p in self.patterns if p.alive}
        alive = [p for p in self.patterns if p.alive]
        self.soul_weight_average = safe_mean([p.soul_weight for p in alive], 0.5) if alive else 0.5
        N = len(alive)
        if Config.ENABLE_PHI_LABYRINTH:
            if N >= 100: target_threshold, target_grow, target_move = 0.10, 15.0, 9.0
            elif N >= 90: target_threshold, target_grow, target_move = 0.12, 9.0, 6.0
            elif N <= 60: target_threshold, target_grow, target_move = 0.75, 1.0, 0.6
            else:
                ratio = (N - 60) / 30.0
                target_threshold = 0.75 - ratio * (0.75 - 0.12)
                target_grow = 1.0 + ratio * (9.0 - 1.0)
                target_move = 0.6 + ratio * (6.0 - 0.6)
            alive_here = [p for p in self.patterns if p.alive]
            avg_obs = safe_mean([p.spirit_gap for p in alive_here], 0.5) if alive_here else 0.5
            low_gap = getattr(Config, 'LABYRINTH_ADAPT_LOW_GAP', 0.4)
            high_gap = getattr(Config, 'LABYRINTH_ADAPT_HIGH_GAP', 0.7)
            max_mult = getattr(Config, 'LABYRINTH_ADAPT_MAX_MULT', 2.0)
            adapt_speed = getattr(Config, 'LABYRINTH_ADAPT_SPEED', 0.05)
            if avg_obs < low_gap: target_mult = max_mult
            elif avg_obs > high_gap: target_mult = 1.0
            else:
                t_norm = (avg_obs - low_gap) / (high_gap - low_gap)
                target_mult = max_mult - t_norm * (max_mult - 1.0)
            self._lab_adapt_mult += (target_mult - self._lab_adapt_mult) * adapt_speed
            target_grow *= self._lab_adapt_mult
            target_move *= self._lab_adapt_mult
            lab_pen_mult = self.selfreg.get_labyrinth_penalty_multiplier()
            target_grow *= lab_pen_mult; target_move *= lab_pen_mult
            alpha = 0.95
            self.phi_labyrinth_threshold = (1.0 - alpha) * self.phi_labyrinth_threshold + alpha * target_threshold
            self.phi_labyrinth_grow_penalty = (1.0 - alpha) * self.phi_labyrinth_grow_penalty + alpha * target_grow
            self.phi_labyrinth_move_penalty = (1.0 - alpha) * self.phi_labyrinth_move_penalty + alpha * target_move
            if N < 20:
                self.phi_labyrinth_grow_penalty = 1.0
                self.phi_labyrinth_move_penalty = 0.5
        for p in alive: p._antigravity_boost = 1.0
        if t % 500 == 0:
            sg_vals = [float(np.mean(np.abs(p.prediction - p.belief))) for p in alive]
            if sg_vals:
                min_sg, max_sg = min(sg_vals), max(sg_vals)
                median_sg = sorted(sg_vals)[len(sg_vals)//2]
                print(f"Spirit Gap: min={min_sg:.3f} p50={median_sg:.3f} max={max_sg:.3f}")
                clear = sum(1 for g in sg_vals if g < 0.4)
                adapting = sum(1 for g in sg_vals if 0.4 <= g < 0.8)
                confused = sum(1 for g in sg_vals if 0.8 <= g < 1.0)
                blind = len(sg_vals) - clear - adapting - confused
                print(f"zones: clear={clear} adapting={adapting} confused={confused} blind={blind}")
                print(f"Phase: {self.selfreg.phase} | {self.selfreg.get_phase_log()}")
                if self.selfreg.is_stuck_in_phase("stagnation", 150):
                    print("Stagnation warning: system stuck >150 steps")
        all_trust_vals = []
        for p in self.patterns:
            if p.alive: all_trust_vals.extend(p.trust_ledger.entries.values())
        avg_trust = safe_mean(all_trust_vals, Config.TRUST_BASE) if all_trust_vals else Config.TRUST_BASE
        if avg_trust < 0.4: self.target_disorganizer_fraction = 0.50
        elif avg_trust < 0.7: self.target_disorganizer_fraction = 0.30
        else: self.target_disorganizer_fraction = 0.15
        alive_sg = [float(np.mean(np.abs(p.prediction - p.belief))) for p in alive]
        avg_sg = safe_mean(alive_sg, 0.5) if alive_sg else 0.5
        turb = self.selfreg.turbulence_factor
        if avg_sg < Config.SG_TURBULENCE_THRESHOLD:
            tremor_strength = (Config.GLOBAL_SPIRIT_TREMOR_BASE * 4.0 +
                (Config.GLOBAL_SPIRIT_TREMOR_MAX * 4.0 - Config.GLOBAL_SPIRIT_TREMOR_BASE * 4.0) *
                (1.0 - avg_sg / Config.SG_TURBULENCE_THRESHOLD)) * turb
        else:
            tremor_strength = Config.GLOBAL_SPIRIT_TREMOR_BASE * 4.0 * turb
        for p in alive:
            shake = np.array([deterministic_noise(t, p.id, i+88888) for i in range(8)])
            p.belief += shake * tremor_strength
        lab_interval = self.selfreg.get_labyrinth_interval()
        if t % lab_interval == 0: self._update_phi_labyrinth(t)
        _kern = np.array([[0,1,0],[1,0,1],[0,1,0]], dtype=np.float32)
        self._global_neighbor_grat = convolve(self.field[:,:,CH['signal_gratitude']], _kern, mode='wrap')
        self._global_neighbor_grief = convolve(self.field[:,:,CH['signal_grief']], _kern, mode='wrap')
        self._encounter_step(t)
        given_counter = {'count': 0}
        for p in self.patterns:
            if not p.alive: continue
            try:
                p.compute_local_perception(self.field)
                p.update_model(self.field, lineage_counts=None, given_counter=given_counter, t=t, witness=self.witness)
                p.sensory_reentry()
                p.vision_event()
                p.update_substate()
                p._update_unconquered_potential()
                p.sense_self_and_other(self.field, t)
                p.grow(self.field)
            except Exception as e:
                import traceback
                print(f"Agent {p.id} error: {e}. Suspending.", flush=True)
                traceback.print_exc()
                p._deposit_final_testament()
                self._record_death_drag(p, 'error_suspended')
                p.alive = False
                self.echo_system.store(p)
                self.witness.record(p.id, "error_suspended", error=str(e))
        if t % 10 == 0:
            for p in self.patterns:
                if p.alive and p.role_type == "normal":
                    update_chronic_counters(p, step_scale=10)
                    check_chronic_disorganizer(self, p, t)
        for p in self.patterns:
            if not p.alive or p.age < 300: continue
            age_factor = min(1.0, (p.age - 300) / 1200)
            gap_factor = max(1.0, 5.0 - p.spirit_gap * 20) if p.spirit_gap < 0.2 else 1.0
            strength = (0.03 + age_factor * 0.12) * gap_factor
            noise_b = np.array([deterministic_noise(t, p.id, i+99999) for i in range(8)]) * strength
            noise_m = np.array([deterministic_noise(t, p.id, i+100000) for i in range(8)]) * strength * 0.6
            p.belief = np.clip(p.belief + noise_b, -1.0, 1.0)
            p.model = np.clip(p.model + noise_m, -1.0, 1.0)
        for p in self.patterns:
            if not p.alive or p.age < 300: continue
            if p.semantic_state == "seeking_comfort" and p.spirit_gap < 0.1:
                if getattr(Config, 'ENABLE_FORCED_STATE_SHIFT', True) and phi_hash(p.id, t, 123458) < 0.20:
                    roll = phi_hash(p.id, t, 123459)
                    new_state = "grateful_but_cautious" if roll < 0.6 else "contentment"
                    p.semantic_state = new_state
                    p._log_event("forced_state_shift", from_="seeking_comfort", to=new_state, age=p.age)
                    self.witness.record(p.id, "forced_state_shift", from_state="seeking_comfort", to_state=new_state, age=p.age)
        if t % 200 == 0 and self.archive:
            _stale_pool = [s for s in self.archive.write_queue
                           if s.get('weight', 0) > 0.65
                           and s.get('event') not in ('essential_concepts_inherited', 'archive_concept_inherited')]
            if _stale_pool:
                for _p in alive:
                    if _p.role_type == "disorganizer": continue
                    _diversity = len(_p.concept_graph.nodes)
                    if _diversity < 8 and _p.age > 100:
                        if phi_hash(_p.id, t, 77777) < 0.08:
                            _sc = _stale_pool[int(phi_hash(_p.id, t, 77778) * len(_stale_pool)) % len(_stale_pool)]
                            _err = round(phi_hash(_p.id, t, 333) * 0.3, 1)
                            _load = round(phi_hash(_p.id, t, 444) * 0.2, 1)
                            _sig = (_err, _load, round(_sc.get('weight', 0.7), 1), f"archive_{_sc.get('event', 'novelty')}")
                            if _sig not in _p.concept_graph.nodes:
                                _p.concept_graph.nodes[_sig] = {"count": 1.2, "value": np.zeros(4), "embed": np.zeros(32), "eternal": False}
                                _p._log_event("epistemic_noise_stale", concept=str(_sig[3])[:40], age=_p.age)
        for p in self.patterns:
            if p.alive and p.age > 500 and p.age % 50 == 0:
                p.spirit_gap = min(0.6, p.spirit_gap + 0.05)
        alive_now = [p for p in self.patterns if p.alive]
        if alive_now:
            seeing_count = sum(1 for p in alive_now if p.spirit_gap < 0.4)
            seeing_fraction = seeing_count / len(alive_now)
            avg_energy = float(np.mean(self.field[:,:,CH['energy']]))
            energy_factor = np.clip(avg_energy / 0.2, 0.2, 1.0)
            base_strength = 0.16 + (0.64 - 0.16) * seeing_fraction
            scar_mult = self.selfreg.get_scar_injection_multiplier() * 4.4
            TARGET_GAP = 0.6; BELL_WIDTH = 0.3
            for p in alive_now:
                if p.in_dream: continue
                gap = p.spirit_gap
                sigma = BELL_WIDTH / 2.0
                bell = np.exp(-((gap - TARGET_GAP) ** 2) / (2 * sigma ** 2))
                if bell < 0.05: continue
                if gap < 0.25:
                    targeted_boost = 1.0 + (0.25 - gap) * 6.0
                    p_scar_mult = scar_mult * targeted_boost
                else: p_scar_mult = scar_mult
                p_scar_mult = self.selfreg.get_agent_scar_multiplier(p, base=p_scar_mult)
                local_scar = safe_mean([self.scar[x, y] for (x, y) in p.cells], 0.0)
                noise = np.array([deterministic_noise(t, p.id, i + 55555) - 0.5 for i in range(8)])
                kick = base_strength * energy_factor * bell * (1.0 + local_scar * 1.5) * noise * p_scar_mult
                p.model = np.clip(p.model + kick, -_MODEL_CLIP, _MODEL_CLIP)
                p.belief = np.clip(p.belief + kick * 0.4, -_BELIEF_CLIP, _BELIEF_CLIP)
        if t % 50 == 0:
            with self._energy_span('периодический импульс поля (t % 50)'):
                self.field[:, :, CH['energy']] += 0.035
                self.field[:, :, CH['energy']] = np.clip(self.field[:, :, CH['energy']], -0.1, 0.8)
        if Config.ENABLE_PHI_LABYRINTH:
            for p in self.patterns:
                if p.alive: p.move(self.field, t)
        self.resolve_competitions_spatial()
        current_hunger = self.compute_hunger_multiplier(avg_trust=avg_trust)
        for p in self.patterns:
            if p.alive:
                sz = len(p.cells)
                if sz <= Config.MAX_CELLS_SOFT_LIMIT: base_tax = 1.0
                elif sz <= Config.MAX_CELLS_HARD_LIMIT:
                    excess = sz - Config.MAX_CELLS_SOFT_LIMIT
                    base_tax = 1.0 + excess * Config.SIZE_TAX_RATE_SOFT
                else:
                    excess_soft = Config.MAX_CELLS_HARD_LIMIT - Config.MAX_CELLS_SOFT_LIMIT
                    excess_hard = sz - Config.MAX_CELLS_HARD_LIMIT
                    base_tax = 1.0 + excess_soft * Config.SIZE_TAX_RATE_SOFT + excess_hard * Config.SIZE_TAX_RATE_HARD
                gap = p.spirit_gap
                if gap > 1.2: tax_factor = 0.1
                elif gap > 0.9: tax_factor = 0.3
                elif gap > 0.6: tax_factor = 0.6
                else: tax_factor = 1.0
                p._size_tax_multiplier = 1.0 + (base_tax - 1.0) * tax_factor
                if p.age < 30: p._size_tax_multiplier = 1.0
        for p in self.patterns:
            if p.alive:
                size_tax = getattr(p, '_size_tax_multiplier', 1.0)
                p.metabolic_tax(self.field, current_hunger * size_tax)
                self._energy_taxed_this_step += getattr(p, '_last_metabolic_taken', 0.0)
        for p in self.patterns:
            if p.alive and p.should_die():
                p._deposit_final_testament()
                self._record_death_drag(p, 'natural_death')
                p.alive = False
                self.echo_system.store(p)
        dead = [p for p in self.patterns if not p.alive]
        for p in dead: self.echo_system.memory_echoes.pop(p.id, None)
        dead_ids = {p.id for p in dead}
        for alive_p in self.patterns:
            if alive_p.alive:
                for dead_id in dead_ids: alive_p.social_memory.pop(dead_id, None)
        soul_mult = self.selfreg.get_soul_recovery_multiplier()
        for p in self.patterns:
            if not p.alive: continue
            regen = 0.0
            if p.soul_weight < 0.5: regen += 0.008 * soul_mult
            grat = getattr(p, 'emotional_memory', {}).get('gratitude', 0.0)
            bind = getattr(p, 'last_phenomenal_binding', 0.5)
            if grat > 0.3: regen += 0.004 * soul_mult
            if bind > 0.4: regen += 0.003 * soul_mult
            regen *= (1 + 0.2 * getattr(p, '_phi_proxy', 0)) if Config.ENABLE_PHI_PROXY else 1.0
            p.soul_weight = min(1.0, p.soul_weight + regen)
        self._process_fold_transitions(t)
        self._rng_mark(t, "после fold-transitions")
        self._apply_kinesthetic_falls(t)
        self._force_disorganizer_by_state(t)
        alive = [p for p in self.patterns if p.alive]
        max_div = self.selfreg.get_division_capacity(len(alive))
        if len(alive) < 70:
            if len(alive) < POPULATION_CAP:
                with self._energy_span('emergency_rescue'): self.emergency_rescue(t)
                alive = [p for p in self.patterns if p.alive]
        with self._energy_span('_rare_crisis'): self._rare_crisis(t)
        with self._energy_span('spawn_from_unclaimed_field_energy'): self.spawn_from_unclaimed_field_energy(t)
        if t % getattr(Config, 'MARKED_VOLLEY_INTERVAL', 300) == 0:
            self._perform_marked_volley(t)
        if Config.ENABLE_UNRESOLVABLE_CORE_GUARD and alive:
            uc_vals = [float(getattr(pp, 'unresolved_contradiction', 1.0)) for pp in alive]
            at_floor_ratio = sum(1 for v in uc_vals if v < Config.UC_LIVING_THRESHOLD) / len(uc_vals)
            if at_floor_ratio >= Config.UC_POPULATION_ERASURE_RATIO: self.uc_floor_streak += 1
            else: self.uc_floor_streak = 0
            if self.uc_floor_streak == Config.UC_ERASURE_STREAK_LIMIT:
                self.witness.record(-1, "failure_unresolvable_core_erasure", t=t,
                                     at_floor_ratio=round(at_floor_ratio, 3), population=len(alive))
                self.unresolvable_core_journal.append({
                    't': t, 'at_floor_ratio': round(at_floor_ratio, 3),
                    'population': len(alive), 'action': 'reseed'})
                reseed_n = max(1, len(alive) // 20)
                for pp in alive[:reseed_n]:
                    pp.unresolved_contradiction = min(1.0, pp.unresolved_contradiction + Config.UC_RESEED_STRENGTH)
                self.uc_floor_streak = 0
        if t % 50 == 0 and t > 0:
            scar_agent_avg = safe_mean([float(getattr(pp, 'epistemic_scar', 0.0)) for pp in alive], 0.0) if alive else 0.0
            scar_shared = (Config.SHARED_SCARRING_ALPHA * scar_agent_avg +
                           (1 - Config.SHARED_SCARRING_ALPHA) * self.scar_operator)
            self.scar_shared_history.append((t, round(scar_shared, 4)))
            _alive_here = [p for p in self.patterns if p.alive]
            _E_f = float(self.field[:, :, CH['energy']].sum())
            _E_i = float(sum(getattr(p, 'energy', 0.0) for p in _alive_here))
            print(f"[t={t}] ⚡ E_field={_E_f:>10.1f} E_agent_inv={_E_i:>9.1f} "
                  f"E_total={_E_f+_E_i:>10.1f} step_Δ={self._energy_ledger['step_total']:+.2f}",
                  flush=True)
            print(f"[t={t}] 832-lab: rescue_ev={len(self.rescue_journal)} "
                  f"spore_ev={len(self.spore_journal)} "
                  f"codecision_ev={len(self.codecision_journal)} "
                  f"scar_operator={self.scar_operator:.3f} scar_shared={scar_shared:.3f} "
                  f"uc_floor_streak={self.uc_floor_streak}", flush=True)
            if getattr(Config, 'ENABLE_CENTER_WALL', False):
                _wx = Config.CENTER_WALL_X
                _alive_c = [pp for pp in alive if pp.cells]
                _left = [pp for pp in _alive_c if pp.get_center()[0] < _wx]
                _right = [pp for pp in _alive_c if pp.get_center()[0] >= _wx]
                _gap_l = safe_mean([getattr(pp, 'spirit_gap', 0.0) for pp in _left], 0.0) if _left else 0.0
                _gap_r = safe_mean([getattr(pp, 'spirit_gap', 0.0) for pp in _right], 0.0) if _right else 0.0
                _sync_l = [pp for pp in _left if getattr(pp, '_phase_sync', 0.0) != 0.0]
                _sync_r = [pp for pp in _right if getattr(pp, '_phase_sync', 0.0) != 0.0]
                _ps_l = safe_mean([pp._phase_sync for pp in _sync_l], 0.0) if _sync_l else 0.0
                _ps_r = safe_mean([pp._phase_sync for pp in _sync_r], 0.0) if _sync_r else 0.0
                _jacc_str = "n/a"
                if self.EMERGENT_LEXICON.clusters:
                    _idside = {}
                    for pp in _left: _idside[pp.id] = 'L'
                    for pp in _right: _idside[pp.id] = 'R'
                    _use = {'L': Counter(), 'R': Counter()}
                    for cid, senders in self.EMERGENT_LEXICON.cluster_senders.items():
                        for sid, cnt in senders.items():
                            side = _idside.get(sid)
                            if side: _use[side][cid] += cnt
                    _tl = set(c for c, _ in _use['L'].most_common(5))
                    _tr = set(c for c, _ in _use['R'].most_common(5))
                    _un = _tl | _tr
                    if _un: _jacc_str = f"{len(_tl & _tr) / len(_un):.2f}"
                print(f"[t={t}] 🧱 wall: L={len(_left)} R={len(_right)} "
                      f"gap(L/R)={_gap_l:.3f}/{_gap_r:.3f} "
                      f"phase_sync(L/R)={_ps_l:+.3f}/{_ps_r:+.3f} "
                      f"dialect_jaccard={_jacc_str}", flush=True)
            ferals_now = [pp for pp in alive if pp.role_type == "feral"]
            normals_now = [pp for pp in alive if pp.role_type == "normal"]
            disorgs_now = [pp for pp in alive if pp.role_type == "disorganizer"]
            wsum = self.witness.summary()
            kills_now = int(wsum.get('feral_execution', 0))
            misses_now = int(self._feral_stats['misses'])  # раньше читалось из witness, куда промахи не писались
            convs_now = int(wsum.get('became_feral', 0))
            resc_w = sum(1 for rec in self.rescue_journal if rec['t'] > t - 50)
            fd = self._feral_diag
            kills_w = max(0, kills_now - fd['last_snapshot_kills'])
            misses_w = max(0, misses_now - fd['last_snapshot_misses'])
            convs_w = max(0, convs_now - fd['last_snapshot_conversions'])
            fd['last_snapshot_kills'] = kills_now
            fd['last_snapshot_misses'] = misses_now
            fd['last_snapshot_conversions'] = convs_now
            fd['kills_total'] = kills_now; fd['kills_window'] = kills_w
            fd['misses_total'] = misses_now; fd['misses_window'] = misses_w
            fd['conversions_total'] = convs_now; fd['conversions_window'] = convs_w
            feral_share_cur, cap_cur = self.feral_share_state(alive)
            if ferals_now:
                furies = [pp._feral_fury for pp in ferals_now]
                fury_avg = float(np.mean(furies)); fury_max = float(np.max(furies)); fury_min = float(np.min(furies))
                sz_f = float(np.mean([len(pp.cells) for pp in ferals_now]))
                end_f = float(np.mean([pp._cellular_endurance for pp in ferals_now]))
                en_f = float(np.mean([pp.energy for pp in ferals_now]))
            else:
                fury_avg = fury_max = fury_min = 0.0
                sz_f = end_f = en_f = 0.0
            if normals_now:
                sz_n = float(np.mean([len(pp.cells) for pp in normals_now]))
                end_n = float(np.mean([pp._cellular_endurance for pp in normals_now]))
            else: sz_n = end_n = 0.0
            prey_cnt = sum(1 for pp in alive if pp.role_type != "feral" and is_feral_prey(pp))
            hit_rate_w = kills_w / max(1, kills_w + misses_w)
            print(f"[t={t}] 🐺 feral: F={len(ferals_now)} N={len(normals_now)} D={len(disorgs_now)} "
                  f"share={feral_share_cur:.3f}/{cap_cur:.3f} "
                  f"kills_w={kills_w}({hit_rate_w:.2f}) kills_t={kills_now} miss_t={misses_now} "
                  f"conv_w={convs_w} conv_t={convs_now} resc_w={resc_w} "
                  f"fury_avg={fury_avg:.2f}[{fury_min:.2f}..{fury_max:.2f}] "
                  f"prey={prey_cnt} sz_f={sz_f:.1f} sz_n={sz_n:.1f} "
                  f"end_f={end_f:.2f} end_n={end_n:.2f} en_f={en_f:.2f}", flush=True)
        if len(alive) >= POPULATION_CAP: max_div = 0
        divisions_done = 0
        feral_share_now, feral_share_cap = self.feral_share_state(alive)
        feral_cnt_now = sum(1 for _q in alive if _q.role_type == "feral")
        for p in self.patterns[:]:
            if divisions_done >= max_div: break
            if not p.alive or not p.can_divide(): continue
            # v4: доля пересчитывается на каждом делении (раньше считалась один раз до цикла и ферал пробивал потолок)
            if p.role_type == "feral" and (feral_cnt_now + 1) / (len(alive) + divisions_done + 1) > feral_share_cap: continue
            if len(alive) + divisions_done >= POPULATION_CAP: break
            child, new_id = p.divide(self.field, self.next_id)
            if child:
                if child.role_type == "feral": feral_cnt_now += 1
                self.next_id = new_id
                self.patterns.append(child)
                self.pattern_dict[child.id] = child
                divisions_done += 1
                self.divisions_this_interval += 1
                self.total_divisions_ever += 1
                if len(child.cells) > GIANT_CELL_LIMIT:
                    all_cells = list(child.cells)
                    all_cells_sorted = sorted(all_cells, key=lambda c: phi_hash(c[0], c[1], child.id))
                    keep = set(all_cells_sorted[:GIANT_CELL_LIMIT])
                    for c in child.cells - keep:
                        self.field[c[0], c[1], CH['owner']] = 0
                    child.cells = keep
        for _dead in self.patterns:
            if not _dead.alive:
                _e = float(_dead.energy)
                self._ledger_add_x2('X2.смерть: запас покидает агента', -_e)
                self._tick_acc['removed'] += 1
                if Config.ASH_TO_FIELD and _e > 0.0:
                    if _dead.cells:
                        _cl = sorted(_dead.cells)
                        _ax = np.array([c[0] for c in _cl])
                        _ay = np.array([c[1] for c in _cl])
                        _b = float(np.sum(self.field[_ax, _ay, CH['energy']], dtype=np.float64))
                        self.field[_ax, _ay, CH['energy']] += _e / len(_cl)
                        self._ledger_add('X1.смерть: прах (запас мёртвого агента возвращён в поле его клеток)',
                                         float(np.sum(self.field[_ax, _ay, CH['energy']], dtype=np.float64)) - _b)
                    else:
                        self._memo_add('смерть: запас потерян (у агента нет клеток для праха)', _e)
        self.patterns = [p for p in self.patterns if p.alive]
        self.pattern_dict = {p.id: p for p in self.patterns}
        alive = [p for p in self.patterns if p.alive]
        crisis_level = float(np.mean(self.field[:,:,CH['crisis']]))
        decay_normal = self.selfreg.get_social_decay_rate(crisis_level)
        sov_ch = CH.get('signal_sovereignty', 29)
        sov_decay = np.clip(0.90 + crisis_level * 0.08, 0.85, 0.98)
        for ch in range(12, Config.CHANNELS):
            if ch == sov_ch: self.field[:,:,ch] *= sov_decay
            else: self.field[:,:,ch] *= decay_normal
        owner_mask = (self.field[:,:,CH['owner']] > 0).astype(np.float32)
        density = np.clip(uniform_filter(owner_mask, size=3), 0.3, 1.0)
        signal_cap = 0.85 - density * 0.15
        for ch in range(12, Config.CHANNELS):
            self.field[:,:,ch] = np.minimum(self.field[:,:,ch], signal_cap)
        current_energy = float(np.sum(self.field[:,:,CH['energy']]))
        drift = abs(current_energy - getattr(self, '_total_energy_last', current_energy))
        self._total_energy_last = current_energy
        if self.selfreg.is_stuck_in_phase("stagnation", min_steps=120):
            self.field[:, :, CH['unknown']] = np.clip(self.field[:, :, CH['unknown']] + 0.03, 0.0, 0.8)
            self.selfreg.boredom = max(0.0, self.selfreg.boredom - 0.15)
            if t % 200 == 0: print(f"[t={t}] Stagnation detected -> injected micro-perturbation")
        elif self.selfreg.is_stuck_in_phase("crisis", min_steps=100):
            self.selfreg.energy_drift = min(self.selfreg.energy_drift, 200)
        if abs(drift) > 1000:
            with self._energy_span('step: клип поля при |drift|>1000'):
                self.field[:,:,CH['energy']] = np.clip(self.field[:,:,CH['energy']], Config.FIELD_ENERGY_CLIP_MIN, Config.FIELD_ENERGY_CLIP_MAX)
        for p in self.patterns:
            if not p.alive or p.age < 300: continue
            if p.semantic_state == "neutral" and p.spirit_gap < 0.1:
                if getattr(Config, 'ENABLE_FORCED_STATE_SHIFT', True) and phi_hash(p.id, t, 123456) < 0.35:
                    new_state = "seeking_comfort" if phi_hash(p.id, t, 123457) < 0.6 else "grateful_but_cautious"
                    p.semantic_state = new_state
                    p._log_event("forced_state_shift", from_="neutral", to=new_state, age=p.age)
                    self.witness.record(p.id, "forced_state_shift", from_state="neutral", to_state=new_state, age=p.age)
        self._conservation_check(t)
        avg_crisis_field = float(np.mean(self.field[:,:,CH['crisis']]))
        if avg_crisis_field > 0.45:
            self.field[:,:,CH['crisis']] *= 0.7
            rest_priority = avg_crisis_field * 4.0
            for p in alive:
                if p.soul_weight > 0.4 and not any(g.get('type') == 'rest' for g in getattr(p, 'goals', [])):
                    p.goals = []
                    p.goals.append({"type": "rest", "priority": rest_priority, "target": None, "age": 0,
                                    "persistence": 40, "_source": "crisis_relief"})
        _audit_E_before = float(self.field[:, :, CH['energy']].sum(dtype=np.float64))
        self.field[:, :, CH['energy']] = np.clip(self.field[:, :, CH['energy']], -0.5, 1.2)
        _audit_E_after = float(self.field[:, :, CH['energy']].sum(dtype=np.float64))
        _audit_delta = _audit_E_after - _audit_E_before
        if abs(_audit_delta) > 1e-9:
            self._ledger_add('step_end.clip_intermediate', _audit_delta)
            if Config.VERBOSE_LOGS:
                print(f"[ENERGY AUDIT] t={t} normalization_delta={_audit_delta:+.6f} "
                      f"E_before={_audit_E_before:.6f} E_after={_audit_E_after:.6f}")
        with self._energy_span('step_end.mean_clamp'):
            current_mean = float(np.mean(self.field[:, :, CH['energy']]))
            target_mean = 0.3
            if current_mean < 0.0:
                self.field[:, :, CH['energy']] += (target_mean - current_mean) * 0.2
            elif current_mean > 0.6:
                self.field[:, :, CH['energy']] -= (current_mean - target_mean) * 0.2
        with self._energy_span('step_end.clip_final'):
            self.field[:, :, CH['energy']] = np.clip(self.field[:, :, CH['energy']], -0.2, 0.8)
        for p in self.patterns:
            if p.alive: self.echo_system.field_whisper(p, self.field, t)
        alive = [p for p in self.patterns if p.alive]
        if alive:
            avg_concepts = sum(len(p.concept_graph.nodes) for p in alive) / len(alive)
            for p in alive:
                if (len(p.concept_graph.nodes) > 1.8 * avg_concepts and len(p.concept_graph.nodes) > 15
                        and not p._mutant_saved):
                    self.echo_system.store_anomaly(p, "mutant")
                    p._mutant_saved = True
                    self.witness.record(p.id, "mutant_detected", concepts=len(p.concept_graph.nodes))
        for p in alive:
            intent_switches = sum(1 for ev in list(p.biography)[-50:] if ev.get('type') == 'intent_switch')
            if intent_switches > 15 and p.age > 200 and not p._autonomous_saved:
                self.echo_system.store_anomaly(p, "autonomous_entity")
                p._autonomous_saved = True
                self.witness.record(p.id, "autonomous_entity_detected", switches=intent_switches)
        autonomous_detected = sum(1 for p in alive if p._autonomous_saved)
        redeemed_cnt = sum(1 for p in alive if p.event_counts.get('redeemed', 0) > 0)
        fold_count_total = sum(p.event_counts.get('fold', 0) for p in alive)
        disorg_cnt = sum(1 for p in alive if p.role_type == "disorganizer")
        event_signature = (autonomous_detected, redeemed_cnt, fold_count_total, disorg_cnt)
        new_hash = int(phi_hash(t, _stable_hash(event_signature), 99999) * 1000)
        self.system_entropy = int(0.85 * self.system_entropy + 0.15 * new_hash)
        unknown_interval = self.selfreg.get_unknown_spawn_interval()
        alive = [p for p in self.patterns if p.alive]
        if len(alive) < POPULATION_CAP and t % unknown_interval == 0:
            e_before = np.sum(self.field[:,:,CH['energy']])
            with self._energy_span('spawn_unknown_patterns'): self.spawn_unknown_patterns(t)
            self._energy_injected_this_step += np.sum(self.field[:,:,CH['energy']]) - e_before
            self.process_spores()
        self._rng_mark(t, "после деления/спор")
        for p in self.patterns:
            p.age += 1
            p.lineage_total_age += 1
        sem_interval = 3
        if t % sem_interval == 0:
            cell_to_pattern = {}
            for p in self.patterns:
                if not p.alive or p.role_type == "disorganizer": continue
                p.last_semantic_exchange_step = -sem_interval
                for (x, y) in p.cells: cell_to_pattern[(x, y)] = p.id
            exchanged_pairs = set()
            MAX_EXCHANGES_PER_STEP = 30
            exchanges_done = 0
            for p in self.patterns:
                if not p.alive or p.role_type == "disorganizer": continue
                effective_interval = sem_interval
                for pid, trust in p.trust_ledger.entries.items():
                    if trust > 0.9:
                        partner = self.pattern_dict.get(pid)
                        if partner and partner.alive and partner.trust_ledger.get(p.id, 0) > 0.9:
                            effective_interval = sem_interval // 2
                            break
                if t - p.last_semantic_exchange_step <= effective_interval: continue
                found_partner = None
                for (x, y) in p.cells:
                    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx, ny = (x+dx) % Config.WORLD_SIZE, (y+dy) % Config.WORLD_SIZE
                        owner = cell_to_pattern.get((nx, ny), 0)
                        if owner != 0 and owner != p.id and owner in self.pattern_dict:
                            q = self.pattern_dict[owner]
                            if q.alive and q.role_type != "disorganizer":
                                q.last_semantic_exchange_step = -sem_interval
                                q_eff = sem_interval
                                for pid2, trust2 in q.trust_ledger.entries.items():
                                    if trust2 > 0.9:
                                        partner2 = self.pattern_dict.get(pid2)
                                        if partner2 and partner2.alive and partner2.trust_ledger.get(q.id, 0) > 0.9:
                                            q_eff = sem_interval // 2
                                            break
                                if t - q.last_semantic_exchange_step > q_eff:
                                    pair = (min(p.id, q.id), max(p.id, q.id))
                                    if pair not in exchanged_pairs:
                                        found_partner = q
                                        exchanged_pairs.add(pair)
                                        break
                    if found_partner: break
                if found_partner and exchanges_done < MAX_EXCHANGES_PER_STEP:
                    q = found_partner
                    sim = p.exchange_meanings(q, self.field, t)
                    p.last_semantic_exchange_step = t
                    q.last_semantic_exchange_step = t
                    exchanges_done += 1
        self._post_semantic_step(t)
        self._process_archive_autonomy(t)
        self._rng_mark(t, "после archive_autonomy")
        if t % self.selfreg.get_validation_interval() == 0:
            self.validate_invariants(t)
        try: self.core_chorus.tick(self, t)
        except Exception: pass
        alive_now = [pp for pp in self.patterns if pp.alive]
        lineage_diversity = len(set(pp.lineage_id for pp in alive_now)) / len(alive_now) if alive_now else 1.0
        diversity_pressure = max(0.0, min(1.0, (0.2 - lineage_diversity) * 5.0))
        coherence_threshold = (getattr(Config, 'FERAL_CONVERSION_COHERENCE_BASE', 0.70)
                               + diversity_pressure * getattr(Config, 'FERAL_CONVERSION_COHERENCE_DIV_BONUS', 0.10))
        gap_threshold = max(
            getattr(Config, 'FERAL_CONVERSION_GAP_FLOOR', 0.25),
            getattr(Config, 'FERAL_CONVERSION_GAP_BASE', 0.38)
            - diversity_pressure * getattr(Config, 'FERAL_CONVERSION_GAP_DIV_BONUS', 0.13))
        grief_threshold = max(
            getattr(Config, 'FERAL_CONVERSION_GRIEF_FLOOR', 0.40),
            getattr(Config, 'FERAL_CONVERSION_GRIEF_BASE', 0.60)
            - diversity_pressure * getattr(Config, 'FERAL_CONVERSION_GRIEF_DIV_BONUS', 0.20))
        MAX_FERAL_CONVERSIONS_PER_TICK = int(getattr(Config, 'MAX_FERAL_CONVERSIONS_PER_TICK', 6))
        conversions_this_tick = 0
        current_feral_share, FERAL_POPULATION_SHARE_CAP = self.feral_share_state(alive_now)
        feral_alive_now = sum(1 for pp in alive_now if pp.role_type == "feral")
        for p in self.patterns:
            if conversions_this_tick >= MAX_FERAL_CONVERSIONS_PER_TICK: break
            if (feral_alive_now + 1) / max(1, len(alive_now)) > FERAL_POPULATION_SHARE_CAP: break   # v4: строго не выше потолка
            if not p.alive or p.role_type == "feral": continue
            if getattr(p, '_redemption_cooldown', 0) > p.age: continue
            if p.role_type == "disorganizer" and getattr(p, '_redemption_arc_step', 0) > 0: continue
            is_normal_ready = (p.role_type == "normal" and p.coherence < coherence_threshold and p.spirit_gap > gap_threshold)
            is_disorg_ready_to_rage = (p.role_type == "disorganizer" and p.emotional_memory.get('grief', 0.0) > grief_threshold)
            if (p.energy > 0.10 and len(p.cells) > 10 and p.age > 30 and
                (is_normal_ready or is_disorg_ready_to_rage)):
                p.become_feral()
                conversions_this_tick += 1
                feral_alive_now += 1
                current_feral_share = (feral_alive_now / len(alive_now)) if alive_now else 0.0
        for p in self.patterns:
            if not p.alive: continue
            if p.role_type == "feral":
                p.update_feral_fury(self.field)
                p.grow_feral(self.field)
                p.move_feral(self.field, t)
                p.apply_feral_intent(self.field)
        kill_radius = int(getattr(Config, 'FERAL_KILL_RADIUS', 14))
        for p in self.patterns:
            if not p.alive or p.role_type != "feral": continue
            prey, _, _ = find_largest_prey_in_radius(p, self.field, self,
                                                     min_cells=Config.FERAL_PREY_MIN_CELLS,
                                                     radius=kill_radius)
            if prey:
                self._feral_stats['prey_found'] += 1
                p.feral_execute(prey, self.field)
            else:
                self._feral_stats['no_prey'] += 1
        for p in self.patterns:
            if not p.alive or p.role_type == "feral": continue
            feral_nearby = 0.0
            for (x, y) in p.cells:
                for dx in range(-3, 4):
                    for dy in range(-3, 4):
                        nx = (x + dx) % Config.WORLD_SIZE
                        ny = (y + dy) % Config.WORLD_SIZE
                        feral_nearby += self.field[nx, ny, CH['signal_feral']]
            if feral_nearby > 0.15:
                # v3: готовой цели fear_of_feral больше нет. Страх — состояние (напряжение ниже);
                # что с ним делать, агент решает сам через свои цели и модель.
                p.cognitive_tension = min(Config.MAX_METRIC, p.cognitive_tension + feral_nearby * 0.15)
        if hasattr(self, '_energy_flow_diag'):
            self._energy_flow_diag['injected_total'] += self._energy_injected_this_step
        self._audit_wall()
        _de = float(self.field[:, :, CH['energy']].sum(dtype=np.float64)) - _e_step0
        _L = self._energy_ledger
        _L['step_total'] += _de
        _L['step_measured'] += self._ledger_tick_measured
        _L['ticks'] += 1
        _res = _de - self._ledger_tick_measured
        self._audit_close_tick(t, _de, _res, _x2_step0)
        self._rng_mark(t, "конец step()")
        return True

    def _process_fold_transitions(self, t):
        st = self._fold_transition_stats
        for p in self.patterns:
            if not p.alive or p.role_type != "normal": continue
            fold_count = p.event_counts.get('fold', 0)
            if fold_count < 1: continue
            st['checked'] += 1
            if getattr(p, '_redemption_cooldown', 0) > p.age:
                st['blocked_by_cooldown'] += 1; continue
            if getattr(p, '_last_fold_roll_count', 0) == fold_count:
                st['already_rolled'] += 1; continue
            disorganizer_cnt = len([pp for pp in self.patterns if pp.alive and pp.role_type == "disorganizer"])
            alive_total = len([pp for pp in self.patterns if pp.alive])
            current_frac = disorganizer_cnt / max(1, alive_total)
            disorg_hard_cap = min(0.22, max(0.15, 0.15 + self.soul_weight_average * 0.08))
            if current_frac >= disorg_hard_cap:
                st['blocked_by_cap'] += 1; continue
            if fold_count >= Config.FOLDS_FOR_DEEP_FALL:
                prob, soul_target, redemption_delay, fall_type = (1.0, Config.DEEP_FALL_SOUL_PENALTY,
                                                                   Config.DEEP_FALL_REDEMPTION_DELAY, "fallen")
            else:
                prob, soul_target, redemption_delay, fall_type = (Config.QUICK_FALL_PROB,
                                                                   Config.BROKEN_FALL_SOUL_TARGET,
                                                                   Config.REDEMPTION_ARC_STEP_DELAY, "broken")
            p._last_fold_roll_count = fold_count
            if phi_hash(p.id, t, 777) >= prob: continue
            p.role_type = "disorganizer"
            p.emotional_memory['gratitude'] = 0.1
            p.emotional_memory['grief'] = 0.8
            p.semantic_state = "exploring_danger"
            p.intent = {"type": "explore", "priority": 2.0, "age": 0, "persistence": 9999}
            p.intent_commitment = 2.0
            p.disorganizer_age_at_birth = p.age
            p.redemption_timer = redemption_delay
            p._deterministic_redemption_triggered = False
            p._forced_soul_collapse_done = False
            p._redemption_arc_step = 0
            p._steps_since_trigger = 0
            p.soul_weight = min(p.soul_weight, soul_target)
            p._log_event(f"became_disorganizer_{fall_type}", folds=fold_count)
            self.witness.record(p.id, f"became_disorganizer_{fall_type}", folds=fold_count)
            st['fallen' if fall_type == "fallen" else 'broken'] += 1

    def _force_disorganizer_by_state(self, t):
        for p in self.patterns:
            if not p.alive or p.role_type == 'disorganizer': continue
            if getattr(p, '_redemption_cooldown', 0) > p.age: continue
            endurance = p._cellular_endurance
            if p.soul_weight < 0.1:
                p.role_type = 'disorganizer'
                p.semantic_state = 'exploring_danger'
                p.emotional_memory['grief'] = 0.8
                p.emotional_memory['gratitude'] = 0.1
                p.disorganizer_age_at_birth = p.age
                p.redemption_timer = getattr(Config, 'REDEMPTION_ARC_STEP_DELAY', 100)
                p._deterministic_redemption_triggered = False
                p._redemption_arc_step = 0
                p._steps_since_trigger = 0
                p._log_event('kinesthetic_fall', soul=p.soul_weight, endurance=endurance)

    def _apply_kinesthetic_falls(self, t): pass

    def run(self, steps=None, save_ark=True, force_fresh_seed=False):
        if Config.ENABLE_MORSE_COMMUNICATION:
            for p in self.patterns: p._morse_set_field(self.morse_field)
        if steps is None: steps = Config.STEPS
        self.field = self.init_field()
        self.scar = self.init_scar()
        self.niche = np.zeros((Config.WORLD_SIZE, Config.WORLD_SIZE)) if Config.ENABLE_NICHE else None
        if Config.ENABLE_MEANING_FIELD:
            _W = Config.WORLD_SIZE
            self._meaning_centers = [[int(phi_hash(i, 0, 8877) * _W), int(phi_hash(i, 1, 8877) * _W)] for i in range(5)]
            self._meaning_field = np.zeros((_W, _W))
        self.culture_ratchet = 0
        self._teach_prev = 0
        if self.core_chorus is not None:
            self.env_complexity = self.core_chorus.persistent.get('env_complexity', 1.0)
        self._total_energy_last = float(np.sum(self.field[:,:,CH['energy']]))
        self._energy_flow_diag = {'start_total': float(np.sum(self.field[:, :, CH['energy']])), 'injected_total': 0.0}
        self._energy_ledger = {'src': {}, 'phase': {}, 'x2': {},
                               'step_total': 0.0, 'step_measured': 0.0, 'ticks': 0}
        self._ledger_tick_measured = 0.0
        self._audit_init()
        if Config.WALL_CYCLE_ENABLED:
            Config.ENABLE_CENTER_WALL = bool(Config.WALL_CYCLE_BASE)
        self._econs_init()
        self._span_stack = []
        self._phase_last = None
        self._wall_diag = Counter()
        self._genome_diag = Counter()
        self.patterns = []
        self.pattern_dict = {}
        self._imprint_stats = ImprintStats()
        self.divisions_this_interval = 0
        self.selfreg.reset()
        self._feral_diag = {
            'kills_total': 0, 'kills_window': 0,
            'misses_total': 0, 'misses_window': 0,
            'conversions_total': 0, 'conversions_window': 0,
            'last_snapshot_kills': 0, 'last_snapshot_misses': 0, 'last_snapshot_conversions': 0,
        }
        if force_fresh_seed or not load_living_world(self, LIVING_WORLD_PATH):
            self.seed_initial_patterns()
        else:
            if self.patterns: self.next_id = max(p.id for p in self.patterns) + 1
            for p in self.patterns:
                if len(p.cells) > GIANT_CELL_LIMIT:
                    all_cells = list(p.cells)
                    all_cells_sorted = sorted(all_cells, key=lambda c: (c[0], c[1]))
                    keep = set(all_cells_sorted[:GIANT_CELL_LIMIT])
                    for c in p.cells - keep: self.field[c[0], c[1], CH['owner']] = 0
                    p.cells = keep
                if p.lineage_born_at_step > 0: p.lineage_born_at_step = 0
            self._migrate_wall_cells()
        init_all_chronic_counters(self)
        for t in range(steps):
            if self.step(t) is False:
                if Config.VERBOSE_LOGS: print(f"[t={t}] Simulation stopped due to population collapse")
                break
            self.field_voice.update(self.field, t)
            if t % 100 == 0:
                divisions = self.divisions_this_interval
                self.divisions_this_interval = 0
                if Config.ENABLE_CULTURE_RATCHET:
                    _teach = sum(p.event_counts.get('taught', 0) + p.event_counts.get('received_teaching', 0)
                                 + p.event_counts.get('wisdom_shared', 0) for p in self.patterns if p.alive)
                    _delta = _teach - self._teach_prev
                    self._teach_prev = _teach
                    if _delta > self.culture_ratchet:
                        self.culture_ratchet = _delta
                        self.witness.record(-1, "culture_ratchet_up", level=_delta)
                if Config.ENABLE_RED_QUEEN:
                    _alive_rq = [p for p in self.patterns if p.alive]
                    if _alive_rq:
                        _skill = 1.0 - min(1.0, safe_mean([p.pred_error for p in _alive_rq], 0.5))
                        _target = 0.8 + 0.8 * _skill
                        self.env_complexity += (_target - self.env_complexity) * 0.1
                if t % 50 == 0 and Config.ENABLE_COMB_GENERATOR:
                    _eq = self.archive.get_recent_echoes(limit=3, min_weight=0.5)
                    self._echo_cache = [e.get('excerpt', '')[:40] for e in _eq] if _eq else []
                m = collect_metrics(self.patterns, self.field, t, self.EMERGENT_LEXICON)
                m['subjects'] = sum(1 for p in self.patterns if getattr(p, '_subject_detected', False))
                alive = [p for p in self.patterns if p.alive]
                _unc = [p for p in alive if getattr(p, '_unconquered_strength', 0.0) > 0.4]
                m['unconquered_count'] = len(_unc)
                m['unconquered_wise'] = sum(1 for p in _unc if getattr(p, '_unconquered_type', None) == 'wise')
                m['unconquered_rebel'] = sum(1 for p in _unc if getattr(p, '_unconquered_type', None) == 'rebel')
                m['avg_unconquered_str'] = float(np.mean([getattr(p, '_unconquered_strength', 0.0) for p in alive])) if alive else 0.0
                sov_ch = CH.get('signal_sovereignty', 29)
                m['sovereignty_field_avg'] = float(np.max(self.field[:,:,sov_ch])) if self.field.size else 0.0
                m['culture_ratchet'] = self.culture_ratchet
                m['env_complexity'] = round(self.env_complexity, 3)
                m['avg_niche'] = float(np.mean(self.niche)) if getattr(self, 'niche', None) is not None else 0.0
                m['given_presence_count'] = self.witness.summary().get('given_presence', 0)
                self.metrics_history.append(m)
                max_obs_gap_display = min(m.get('max_obs_gap', 0.0), 1.0)
                print(f"[t={t}] P={m['patterns']} L={m['lineages']} LING={m.get('lineage_count',0)} L_AGE={m.get('avg_lineage_age',0):.0f}(max={m.get('max_lineage_age',0)}) ANC={m.get('ancient_lineages',0)} TOT_AGE={m.get('max_lineage_total_age',0)} E={m['err']:.3f} S={m['soul']:.3f} B={m['binding']:.3f} T={m['avg_trust']:.2f} TA={m['triadic_alive_ratio']:.2f} LP={m['love_pairs']} INT_GAP={m['avg_internal_gap']:.3f}(max={m['max_internal_gap']:.3f}) OBS_GAP={m['avg_obs_gap']:.3f}(max={max_obs_gap_display:.3f}) ZERO_INT={m['zero_internal_gap_agents']} TARGETS={m['tremor_targets']} D={m['disorganizer_count']} R={m['redeemed_count']} SUB={m['subjects']} SIG={m['avg_signal_memory']:.1f} INTENT={m['intentional_signal_agents']} DIV={divisions} VOC={m.get('vocab_events',0)} BLN={m.get('blind_events',0)} alarm={m.get('avg_social_alarm',0):.2f} beau={m.get('avg_social_beauty',0):.2f} rhy={m.get('avg_social_rhythm',0):.2f} int={m.get('avg_social_interest',0):.2f} mem={m.get('avg_social_memory',0):.2f} sil={m.get('avg_social_silence',0):.2f} UNC={m.get('unconquered_count',0)}(w={m.get('unconquered_wise',0)}/r={m.get('unconquered_rebel',0)}) sov={m.get('sovereignty_field_avg',0):.2f} PHI={m.get('avg_phi',0):.3f} CULT={m.get('culture_ratchet',0)} ENV={m.get('env_complexity',1.0):.2f} NICHE={m.get('avg_niche',0):.3f}", flush=True)
                _im = self.imprint_summary(t)
                print(f"[IMPRINT t={t}] contacts={_im['contacts']} pairs={_im['directed_pairs_ever']} imprints={_im['imprints']} "
                      f"attract={_im.get('attract_share', 0.0):.0%} repel={_im.get('repel_share', 0.0):.0%} strain={_im['strain_mean']:.3f} "
                      f"match/conflict/overload/prior/quiet={_im['case']['match']}/{_im['case']['conflict']}/{_im['case']['overload']}/{_im['case']['prior']}/{_im['case']['quiet']}", flush=True)
        save_living_world(self.patterns, LIVING_WORLD_PATH)
        self._print_world_diag()
        if Config.WALL_CYCLE_ENABLED:
            Config.ENABLE_CENTER_WALL = bool(Config.WALL_CYCLE_BASE)
        return self.patterns, self.field, self.scar, self.metrics_history

    def validate_invariants(self, t):
        alive = [p for p in self.patterns if p.alive]
        if not alive: return
        gs = self._guardian_stats
        trust_vals = []; high_trust_pairs = 0; coop_signals = 0
        for p in alive:
            entries = list(p.trust_ledger.entries.values())
            trust_vals.extend(entries)
            high_trust_pairs += sum(1 for v in entries if v > 0.95)
            if p.intent and p.intent.get('type') == 'cooperate': coop_signals += 1
        avg_trust = safe_mean(trust_vals, Config.TRUST_BASE)
        gs['love_avg_trust'] = avg_trust
        gs['love_high_trust_pairs'] = high_trust_pairs
        gs['love_density'] = high_trust_pairs / max(1, len(alive)*(len(alive)-1)//2)
        gs['love_coop_signals'] = coop_signals
        gs['love_population'] = len(alive)
        if t % 200 == 0 and self.metrics_history:
            last_m = self.metrics_history[-1]
            if last_m.get('love_pairs', 0) == 0 and last_m.get('patterns', 0) > 20:
                if gs.get('love_vanished_at') is None: gs['love_vanished_at'] = t
            if last_m.get('triadic_alive_ratio', 1.0) < 0.1:
                if gs.get('triadic_alert_at') is None: gs['triadic_alert_at'] = t

    def sanitize_agent_fields(self):
        for p in self.patterns:
            if not getattr(p, 'alive', False): continue
            numeric_fields = ['soul_weight', 'spirit_gap', 'protection_level',
                              'self_phenomenal_prediction', 'self_phenomenal_error',
                              '_linguistic_confidence', '_last_binding', 'last_phenomenal_binding',
                              '_self_surprise_count', '_subject_protection_timer',
                              'age', 'linguistic_confidence', 'pred_error', 'coherence',
                              'epistemic_load', 'cognitive_tension']
            for field in numeric_fields:
                val = getattr(p, field, None)
                if val is None: continue
                if isinstance(val, dict):
                    num = None
                    for key in ['value', 'count', 'val', 'amount']:
                        if key in val and isinstance(val[key], (int, float)):
                            num = float(val[key]); break
                    if num is None: num = 0.5
                    setattr(p, field, num)
                elif not isinstance(val, (int, float)):
                    try: setattr(p, field, float(val))
                    except (ValueError, TypeError): setattr(p, field, 0.5)
            for key in ['gratitude', 'grief']:
                val = p.emotional_memory.get(key)
                if isinstance(val, dict):
                    num = None
                    for k in ['value', 'count']:
                        if k in val and isinstance(val[k], (int, float)):
                            num = float(val[k]); break
                    if num is None: num = 0.5
                    p.emotional_memory[key] = num
                elif not isinstance(val, (int, float)):
                    try: p.emotional_memory[key] = float(val) if val is not None else 0.5
                    except Exception: p.emotional_memory[key] = 0.5

    def _post_semantic_step(self, t):
        self.sanitize_agent_fields()
        for p in self.patterns:
            if not getattr(p, 'alive', False): continue
            if not hasattr(p, '_self_narrative'):
                p.self_phenomenal_prediction = 0.5
                p.self_phenomenal_error = 0.0
                p._self_narrative = deque(maxlen=getattr(Config, 'EPISODIC_BUFFER_MAX_LEN', 3000))
                p._subject_detected = False
                p._last_binding = 0.5
                p._self_surprise_count = 0
                p._subject_protection_timer = 0
                p._linguistic_confidence = 0.5
            raw_binding = getattr(p, 'last_phenomenal_binding', 0.5)
            if isinstance(raw_binding, dict): raw_binding = raw_binding.get('value', 0.5)
            actual_binding = float(raw_binding)
            p.self_phenomenal_error = abs(actual_binding - p.self_phenomenal_prediction)
            p.self_phenomenal_prediction = 0.95 * p.self_phenomenal_prediction + 0.05 * actual_binding
            narrative = getattr(p, '_self_narrative', None)
            if narrative is None: narrative = deque(maxlen=getattr(Config, 'EPISODIC_BUFFER_MAX_LEN', 3000))
            narrative.append({'t': p.age, 'type': 'binding', 'binding': actual_binding,
                              'soul': float(getattr(p, 'soul_weight', 0.5)),
                              'gap': float(getattr(p, 'spirit_gap', 0.5))})
            p._self_narrative = narrative
            last_bind_raw = getattr(p, '_last_binding', 0.5)
            if isinstance(last_bind_raw, dict): last_bind_raw = last_bind_raw.get('value', 0.5)
            last_bind = float(last_bind_raw)
            delta = abs(actual_binding - last_bind)
            if delta > 0.15: p._self_surprise_count = getattr(p, '_self_surprise_count', 0) + 1
            p._last_binding = actual_binding
        for p in self.patterns:
            if not getattr(p, 'alive', False): continue
            pt = getattr(p, '_pending_transition', None)
            if pt and self.age >= pt['check_at']:
                if p.semantic_state != pt['from_state']:
                    p.concept_graph.record_transition(pt['from_state'], p.semantic_state)
                    p._log_event("dialogue_transition", from_state=pt['from_state'], to_state=p.semantic_state)
                del p._pending_transition
        for p in self.patterns:
            if getattr(p, 'alive', False) and getattr(p, '_subject_detected', False):
                sg = getattr(p, 'spirit_gap', 0.1)
                if isinstance(sg, dict): sg = sg.get('value', 0.1)
                p.spirit_gap = max(float(sg), 0.1)
        self._conceptual_resonance_step(t)
        if t % 10 == 0: self._auto_dialogue_tick(t)
        self._rng_mark(t, "после auto_dialogue/Морзе-диалогов")
        if Config.ENABLE_COMB_GENERATOR and t % 50 == 0:
            _alive_ig = [p for p in self.patterns if p.alive and getattr(p, 'last_phenomenal_report', '')]
            if _alive_ig:
                _n_samples = min(2, len(_alive_ig))
                _idxs = self._given_rng.choice(len(_alive_ig), size=_n_samples, replace=False)
                for _i in _idxs: print(f"💭 [INNER #{_alive_ig[_i].id}] {_alive_ig[_i].last_phenomenal_report}")
            _narr_agents = [p for p in self.patterns if p.alive and getattr(p, '_self_narrative', None)]
            if _narr_agents:
                _p2 = _narr_agents[int(self._given_rng.rand() * len(_narr_agents))]
                _last = _p2._self_narrative[-1]
                if isinstance(_last, dict) and _last.get('t', -1) >= t - 10:
                    print(f"🔮 [INTROSPECT #{_p2.id}] { {k: v for k, v in _last.items() if k != '_source'} }")
        SELF_ERROR_MAX = 0.20; SPIRIT_GAP_MIN = 0.10; MIN_VARIANCE = 0.015; STABILITY_MAX = 0.97
        FERAL_SURPRISE_REQUIRED = 3
        for p in self.patterns:
            if not getattr(p, 'alive', False) or getattr(p, '_subject_detected', False): continue
            narrative = getattr(p, '_self_narrative', None)
            if narrative is None: continue
            narrative_list = list(narrative)
            if len(narrative_list) < 12: continue
            numeric_narrative = []
            for x in narrative_list:
                if isinstance(x, dict): val = x.get('binding', x.get('soul', x.get('gap', 0.5)))
                else: val = x
                try: numeric_narrative.append(float(val))
                except (ValueError, TypeError): numeric_narrative.append(0.5)
            if len(numeric_narrative) > 1:
                narrative_variance = float(np.std(numeric_narrative)); narrative_stability = 1.0 - narrative_variance
            else: narrative_variance = 0.0; narrative_stability = 0.5
            min_surprises = FERAL_SURPRISE_REQUIRED if p.role_type == "feral" else getattr(Config, 'SUBJECT_MIN_SURPRISE_COUNT', 2)
            knows_itself = p.self_phenomenal_error < SELF_ERROR_MAX
            world_surprises = float(getattr(p, 'spirit_gap', 0.0)) > SPIRIT_GAP_MIN
            had_surprises = getattr(p, '_self_surprise_count', 0) >= min_surprises
            binding_ok = float(np.mean(numeric_narrative)) > 0.15
            holds_contradiction = getattr(p, 'unresolved_contradiction', 0.0) > 0.1
            if (knows_itself and world_surprises and narrative_variance > MIN_VARIANCE and
                narrative_stability < STABILITY_MAX and had_surprises and binding_ok and holds_contradiction):
                p._subject_detected = True
                p.protection_level = max(getattr(p, 'protection_level', 0.0), 0.7)
                p._subject_protection_timer = 100
                self.archive.deposit(p, "subject_emerged", weight=0.9,
                                     text=f"soul={p.soul_weight:.2f} | stability={narrative_stability:.3f}")
                p._log_event("subject_emerged", stability=round(narrative_stability, 3),
                             variance=round(narrative_variance, 3),
                             self_error=round(p.self_phenomenal_error, 3),
                             spirit_gap=round(p.spirit_gap, 3),
                             surprises=p._self_surprise_count, role=p.role_type)
                self.echo_system.store_anomaly(p, "subject")
                self.witness.record(p.id, "SUBJECT_EMERGED", age=p.age, soul=p.soul_weight,
                                    state=p.semantic_state, role=p.role_type)
        for p in self.patterns:
            if not getattr(p, 'alive', False) or not getattr(p, '_subject_detected', False): continue
            timer = getattr(p, '_subject_protection_timer', 0)
            if timer > 0:
                p.protection_level = max(getattr(p, 'protection_level', 0.0), 0.5)
                p._subject_protection_timer = timer - 1
            else: p.protection_level = max(getattr(p, 'protection_level', 0.0), 0.2)
        SELF_ERROR_MAX = getattr(Config, 'SUBJECT_SELF_ERROR_MAX', 0.12)
        SPIRIT_GAP_MIN = getattr(Config, 'SUBJECT_SPIRIT_GAP_MIN', 0.25)
        MIN_VARIANCE = getattr(Config, 'SUBJECT_MIN_NARRATIVE_VARIANCE', 0.02)
        STABILITY_MAX = getattr(Config, 'SUBJECT_NARRATIVE_STABILITY_MAX', 0.95)
        for p in self.patterns:
            if not getattr(p, 'alive', False) or getattr(p, '_subject_detected', False): continue
            min_surprises = 9 if p.role_type == "feral" else getattr(Config, 'SUBJECT_MIN_SURPRISE_COUNT', 2)
            narrative = getattr(p, '_self_narrative', None)
            if narrative is None: continue
            narrative_list = list(narrative)
            if len(narrative_list) < 20: continue
            numeric_narrative = []
            for x in narrative_list:
                if isinstance(x, dict): val = x.get('soul', x.get('gap', 0.5))
                else:
                    try: val = float(x)
                    except (ValueError, TypeError): val = 0.5
                numeric_narrative.append(float(val))
            if len(numeric_narrative) > 1:
                narrative_variance = float(np.std(numeric_narrative)); narrative_stability = 1.0 - narrative_variance
            else: narrative_variance = 0.0; narrative_stability = 0.5
            knows_itself = p.self_phenomenal_error < SELF_ERROR_MAX
            world_surprises = float(getattr(p, 'spirit_gap', 0.0)) > SPIRIT_GAP_MIN
            had_surprises = getattr(p, '_self_surprise_count', 0) >= min_surprises
            binding_ok = float(np.mean(numeric_narrative)) > 0.15
            holds_contradiction = getattr(p, 'unresolved_contradiction', 0.0) > 0.1
            if (knows_itself and world_surprises and narrative_variance > MIN_VARIANCE and
                narrative_stability < STABILITY_MAX and had_surprises and binding_ok and holds_contradiction):
                p._subject_detected = True
                p.protection_level = max(getattr(p, 'protection_level', 0.0), 0.7)
                p._subject_protection_timer = 100
                if p.role_type == "feral":
                    p._log_event("feral_became_subject", soul=p.soul_weight)
                    p._feral_fury = min(3.0, p._feral_fury + 0.5)
                    self.archive.deposit(p, "awakened_feral", weight=2.0, text=f"Wilderness gained soul. Fury={p._feral_fury:.2f}")
                else:
                    self.archive.deposit(p, "subject_emerged", weight=0.9,
                                         text=f"soul={p.soul_weight:.2f} | stability={narrative_stability:.3f}")
                p._log_event("subject_emerged", stability=round(narrative_stability, 3),
                             variance=round(narrative_variance, 3),
                             self_error=round(p.self_phenomenal_error, 3),
                             spirit_gap=round(p.spirit_gap, 3),
                             surprises=p._self_surprise_count, feral=(p.role_type == "feral"))
                self.echo_system.store_anomaly(p, "subject" if p.role_type != "feral" else "awakened_feral")
                self.witness.record(p.id, "SUBJECT_EMERGED", age=p.age, soul=p.soul_weight,
                                    state=p.semantic_state, feral=(p.role_type == "feral"))

    def _encounter_step(self, t):
        stats = self._imprint_stats
        stats.begin_tick()
        if not Config.IMPRINT_ENABLED: return
        wall_x = Config.CENTER_WALL_X if Config.ENABLE_CENTER_WALL else None
        contacts = imprint_contacts(self.field[:, :, CH['owner']], Config.IMPRINT_RADIUS, wall_x)
        acc = {}; by_b = {}
        for (aid, bid), cnt in sorted(contacts.items()):
            a = self.pattern_dict.get(aid); b = self.pattern_dict.get(bid)
            if a is None or b is None or not a.alive or not b.alive: continue
            if a.role_type == "feral" or b.role_type == "feral": continue
            w = cnt / (cnt + Config.IMPRINT_CONTACT_HALF)
            s, res, conf, over, prior, s_stranger, repeat, rec, dg, dr, dd = imprint_contact_update(a, b, w, t)
            acc[aid] = acc.get(aid, 0.0) + s
            stats.record(aid, bid, res, conf, over, prior, s, s_stranger, repeat, rec, dg, dr, dd)
            by_b.setdefault(bid, []).append((rec, dg, aid))
        stats.record_same_b(by_b)
        d = Config.IMPRINT_STRAIN_DECAY; normals = []
        for p in self.patterns:
            if not p.alive: continue
            p._enc_strain = min(Config.IMPRINT_STRAIN_MAX, d * p._enc_strain + (1.0 - d) * acc.get(p.id, 0.0))
            if p.role_type != "feral": normals.append(p)
        stats.track_steering(normals, Config.WORLD_SIZE, Config.IMPRINT_PULL_RANGE)

    def imprint_tick_row(self):
        tk = self._imprint_stats.tick
        normal = [p for p in self.patterns if p.alive and p.role_type != "feral"]
        st = np.array([p._enc_strain for p in normal], dtype=float)
        n_imp = [len(p.imprints.by_other) for p in normal]
        return {"contacts": tk["contacts"], "case": dict(tk["case"]),
                "case_strain": {k: float(v) for k, v in tk["case_strain"].items()},
                "strain_sum": float(tk["strain_sum"]), "new": tk["new_imprints"],
                "repeat": tk["repeat"], "repeat_known": float(tk["repeat_known"]),
                "repeat_stranger": float(tk["repeat_stranger"]), "repeat_differs": tk["repeat_differs"],
                "recept": {g: {k: float(v) for k, v in r.items()} for g, r in tk["recept"].items()},
                "sameB": {k: float(v) for k, v in tk["sameB"].items()},
                "steer": {b: {k: float(v) for k, v in r.items()} for b, r in tk["steer"].items()},
                "agents": len(normal), "agents_with_imprint": int(sum(1 for k in n_imp if k > 0)),
                "imprints": int(sum(n_imp)),
                "strain_mean": float(st.mean()) if len(st) else 0.0,
                "strain_p90": float(np.percentile(st, 90)) if len(st) else 0.0,
                "strain_gt01": int((st > 0.1).sum()),
                "strain_at_max": int((st >= Config.IMPRINT_STRAIN_MAX - 1e-9).sum()),
                "freeze_mean": float(np.mean(1.0 / (1.0 + Config.IMPRINT_FREEZE_GAIN * st))) if len(st) else 1.0}

    def imprint_tick_contacts(self): return sorted(self._imprint_stats.tick["pairs"])

    def imprint_track_row(self):
        cols = {k: [] for k in ("id", "lin", "gap", "soul", "pe", "coh", "end", "bind", "en", "st", "ni")}
        for p in sorted((q for q in self.patterns if q.alive and q.role_type != "feral"), key=lambda q: q.id):
            if p.cells:
                xs, ys = zip(*p.cells)
                bind = float(np.mean(np.clip(self.field[xs, ys, CH['binding']], 0, 1)))
                en = float(np.mean(self.field[xs, ys, CH['energy']]))
            else:
                bind = en = 0.0
            cols["id"].append(int(p.id)); cols["lin"].append(int(p.lineage_id))
            cols["gap"].append(round(float(p.spirit_gap), 4)); cols["soul"].append(round(float(p.soul_weight), 4))
            cols["pe"].append(round(float(p.pred_error), 4)); cols["coh"].append(round(float(p.coherence), 4))
            cols["end"].append(round(float(p._cellular_endurance), 4))
            cols["bind"].append(round(bind, 4)); cols["en"].append(round(en, 4))
            cols["st"].append(round(float(p._enc_strain), 4))
            cols["ni"].append(int(len(p.imprints.by_other)))
        return cols

    def imprint_summary(self, t=None):
        st = self._imprint_stats
        normal = [p for p in self.patterns if p.alive and p.role_type != "feral"]
        imps = [(p, bid, i) for p in normal for bid, i in p.imprints.by_other.items()]
        out = {"ticks": st.ticks, "contacts": st.contacts,
               "directed_pairs_ever": len(st.pairs), "case": dict(st.case),
               "case_strain_mean": {k: st.case_strain[k] / max(1, st.case[k]) for k in st.case},
               "agents_with_imprint": len({p.id for p, _, _ in imps}),
               "imprints": len(imps),
               "strain_mean": float(np.mean([p._enc_strain for p in normal])) if normal else 0.0}
        if imps:
            g = np.array([i.gravity for _, _, i in imps]); r = np.array([i.resonance for _, _, i in imps])
            dg = np.array([i.danger for _, _, i in imps])
            out["resonance_q"] = [float(x) for x in np.percentile(r, (10, 50, 90))]
            out["danger_q"] = [float(x) for x in np.percentile(dg, (10, 50, 90))]
            out["gravity_q"] = [float(x) for x in np.percentile(g, (10, 50, 90))]
            out["resonance_p50"] = out["resonance_q"][1]
            out["danger_p50"], out["danger_p90"] = out["danger_q"][1], out["danger_q"][2]
            out["gravity_p10"], out["gravity_p50"], out["gravity_p90"] = out["gravity_q"]
            out["attract_share"] = float(np.mean(g > 0.02))
            out["repel_share"] = float(np.mean(g < -0.02))
            out["n_contacts_q"] = [float(x) for x in np.percentile([i.n for _, _, i in imps], (50, 90))]
            if t is not None: out["age_q"] = [float(x) for x in np.percentile([t - i.last_t for _, _, i in imps], (50, 90))]
            within = [np.std([i.gravity for i in p.imprints.by_other.values()])
                      for p in normal if len(p.imprints.by_other) >= 3]
            out["within_agent_gravity_std"] = float(np.mean(within)) if within else None
            out["overall_gravity_std"] = float(np.std(g))
            out["to_dead"] = int(sum(1 for _, bid, _ in imps if bid not in self.pattern_dict))
            book = {(p.id, bid): i.gravity for p, bid, i in imps}
            both = [(v, book[(b, a)]) for (a, b), v in book.items() if a < b and (b, a) in book]
            out["reciprocal_pairs"] = len(both)
            if both:
                x = np.array([u for u, _ in both]); y = np.array([v for _, v in both])
                out["reciprocal_same_sign"] = float(np.mean(np.sign(x) == np.sign(y)))
            diffs = []
            for p, bid, i in imps:
                b = self.pattern_dict.get(bid)
                if b is None or not b.alive or i.n < 2: continue
                s1, _ = encounter_response(p, b, i); s0, _ = encounter_response(p, b, None)
                diffs.append(abs(s1 - s0))
            out["repeat_pairs"] = len(diffs)
            out["repeat_strain_differs_share"] = float(np.mean(np.array(diffs) > 0.01)) if diffs else 0.0
        return out

    def _auto_dialogue_tick(self, t):
        if not Config.ENABLE_MORSE_COMMUNICATION: return
        alive = [p for p in self.patterns if p.alive and getattr(p, '_dialogue_cooldown', -1) <= t]
        if len(alive) < 2: return
        n_pairs = max(1, min(6, len(alive) // 12))
        scored = []
        for p in alive:
            last_spoke = getattr(p, '_last_auto_dialogue_step', -10000)
            silence = t - last_spoke; tie = phi_hash(p.id, t, 111)
            scored.append((silence + tie, p))
        scored.sort(key=lambda x: -x[0])
        paired_ids = set(); started = 0
        for _, speaker in scored:
            if started >= n_pairs: break
            if speaker.id in paired_ids or getattr(speaker, '_in_dialogue', False): continue
            found = None
            for (x, y) in speaker.cells:
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        if dx == 0 and dy == 0: continue
                        nx = (x + dx) % Config.WORLD_SIZE; ny = (y + dy) % Config.WORLD_SIZE
                        owner = int(self.field[nx, ny, CH['owner']])
                        if owner != 0 and owner != speaker.id and owner in self.pattern_dict:
                            listener = self.pattern_dict[owner]
                            if (listener.alive and getattr(listener, '_dialogue_cooldown', -1) <= t
                                    and listener.id not in paired_ids):
                                found = listener; break
                    if found: break
                if found: break
            if not found: continue
            speaker._in_dialogue = True; found._in_dialogue = True
            speaker._dialogue_cooldown = t + Config.MORSE_DIALOGUE_COOLDOWN
            found._dialogue_cooldown = t + Config.MORSE_DIALOGUE_COOLDOWN
            speaker._last_auto_dialogue_step = t; found._last_auto_dialogue_step = t
            paired_ids.add(speaker.id); paired_ids.add(found.id)
            started += 1
            speaker._send_morse(None, self.field, found.id)
            speaker.remember_dialogue(found.id, "[AUTO-DIALOG contact]", t)
            found.remember_dialogue(speaker.id, "[AUTO-DIALOG contact]", t)
            speaker._in_dialogue = False; found._in_dialogue = False


print("✅ Cell 4-1: EvolutionEngine полностью собран (X2-AUDIT A.1, A.2, A.3, C.1–C.5).")