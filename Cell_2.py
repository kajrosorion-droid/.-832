
# =========================
# Cell 2: CulturalMemory, LogosObserver, ProtoLanguage, EchoSystem, FieldVoice
# ИСПРАВЛЕНО: Краш EchoSystem (range(5) -> range(8))
# ИСПРАВЛЕНО: Культурная память теперь сохраняет завершенные арки
# ИСПРАВЛЕНО: Конфликт имен deserialize_pattern (переименована в _dict)
# ИСПРАВЛЕНО: Размерность embed fallback (4 -> 32)
# ИСПРАВЛЕНО: calculate_boredom теперь корректно работает с deque (преобразует в список)
# ПАТЧ 9: EchoSystem.field_whisper добавляет цель introspect без дублирования
# =========================

import numpy as np
from collections import defaultdict, deque, Counter
import ast

def calculate_boredom(patterns, field):
    """
    Вычисляет уровень скуки системы на основе:
    - средней ошибки предсказания за последние BOREDOM_WINDOW шагов
    - среднего значения поля unknown
    - средней когнитивной напряжённости
    Возвращает число от 0 до 1.
    """
    if not patterns:
        return 0.0
    err_history = []
    for p in patterns:
        if p.alive and hasattr(p, 'pred_error_history') and p.pred_error_history:
            hist_list = list(p.pred_error_history)
            err_history.extend(hist_list[-Config.BOREDOM_WINDOW:])
    if not err_history:
        return 0.0
    avg_recent_err = np.mean(err_history)
    avg_unknown = safe_mean(field[:,:,CH['unknown']], 0.1)
    avg_tension = safe_mean([p.cognitive_tension for p in patterns if p.alive], 0.01)
    score = 0.0
    if avg_recent_err < Config.BOREDOM_ERR_THRESHOLD:
        score += 0.3
    if avg_unknown < Config.BOREDOM_UNKNOWN_THRESHOLD:
        score += 0.3
    if avg_tension < Config.BOREDOM_TENSION_THRESHOLD:
        score += 0.2

    # ДОБАВЛЕНО (24.07, см. анализ прогона v34.03): абсолютные пороги почти
    # никогда не пробивались в реальных прогонах (avg_recent_err держится
    # ~0.15-0.23, был порог 0.10) — boredom всегда был 0.000, несмотря на
    # 37.8% шагов в стагнации по Phase-классификатору. Добавлен
    # ОТНОСИТЕЛЬНЫЙ компонент: если ошибка/unknown почти не отличаются от
    # затухающего долгосрочного среднего (<15%) — система топчется на месте
    # относительно СВОЕЙ ЖЕ истории, абсолютный порог тут не при чём.
    # Состояние храним как атрибут функции (без изменения сигнатуры вызова
    # в двух местах, где она уже используется).
    if not hasattr(calculate_boredom, '_baseline'):
        calculate_boredom._baseline = {'err': avg_recent_err, 'unknown': avg_unknown}
    base = calculate_boredom._baseline
    if base['err'] > 1e-6 and abs(avg_recent_err - base['err']) / base['err'] < 0.15:
        score += 0.1
    if base['unknown'] > 1e-6 and abs(avg_unknown - base['unknown']) / base['unknown'] < 0.15:
        score += 0.1
    base['err'] = 0.98 * base['err'] + 0.02 * avg_recent_err
    base['unknown'] = 0.98 * base['unknown'] + 0.02 * avg_unknown
    score = min(1.0, score)
    return score

def ecosystem_pressure(field):
    energy = np.nan_to_num(field[:,:,CH['energy']], nan=0.0)
    avg = np.mean(energy)
    field[:,:,CH['energy']] += 0.002 * (avg - energy)
    field[:,:,CH['flux']] += 0.001 * (np.roll(energy, 1, axis=0) - energy) + 0.001 * (np.roll(energy, -1, axis=1) - energy)
    return field


# =========================
# CulturalMemory
# =========================
class CulturalMemory:
    def __init__(self):
        self.myth_pool = []

    def deposit(self, pattern, event_type, intensity=1.0):
        if not Config.ENABLE_CULTURAL_MEMORY:
            return
        if event_type not in ("arc_completed", "fold", "redemption"):
            return

        arc_name = pattern.arc_tracker.active_arc
        if arc_name is None:
            if pattern.arc_tracker.completed_arcs:
                arc_name = max(pattern.arc_tracker.completed_arcs, key=pattern.arc_tracker.completed_arcs.get)
            else:
                arc_name = "unknown"

        myth = {
            "arc": arc_name,
            "emotional_scent": pattern.emotional_memory.copy(),
            "phenomenal_essence": pattern.last_phenomenal_binding,
            "intensity": intensity
        }
        self.myth_pool.append(myth)
        if len(self.myth_pool) > Config.MYTH_POOL_SIZE:
            self.myth_pool.pop(0)

        type_counts = Counter(m['arc'] for m in self.myth_pool if m.get('arc'))
        total = len(self.myth_pool)
        if total > 0:
            for m in self.myth_pool:
                arc = m.get('arc')
                if arc and type_counts.get(arc, 0) / total > 0.6:
                    m['intensity'] *= 0.9
                elif arc and type_counts.get(arc, 0) / total < 0.1:
                    m['intensity'] *= 1.1

    def whisper_to_newborn(self, pattern):
        if not Config.ENABLE_CULTURAL_MEMORY or not self.myth_pool:
            return
        if phi_hash(pattern.id, 0, 999) < Config.MYTH_INFLUENCE_PROB:
            idx = int(phi_hash(pattern.id, 1, 1000) * len(self.myth_pool))
            myth = self.myth_pool[idx]
            pattern.emotional_memory['grief'] += myth['emotional_scent']['grief'] * Config.MYTH_WHISPER_STRENGTH
            pattern.emotional_memory['gratitude'] += myth['emotional_scent']['gratitude'] * Config.MYTH_WHISPER_STRENGTH
            pattern.emotional_memory['grief'] = np.clip(pattern.emotional_memory['grief'], 0.0, 1.0)
            pattern.emotional_memory['gratitude'] = np.clip(pattern.emotional_memory['gratitude'], 0.0, 1.0)

            if myth:
                myth['emotional_scent']['grief'] += (phi_hash(pattern.id, 0, 999) - 0.5) * 0.02
                myth['emotional_scent']['gratitude'] += (phi_hash(pattern.id, 1, 999) - 0.5) * 0.02
                if pattern.age > 500:
                    myth['intensity'] = min(2.0, myth.get('intensity', 1.0) * 1.01)

    def dream_whisper(self, pattern):
        if not Config.ENABLE_CULTURAL_MEMORY or not self.myth_pool:
            return
        if phi_hash(pattern.id, pattern.age, 999) < 0.05:
            idx = int(phi_hash(pattern.id, pattern.age+1, 1001) * len(self.myth_pool))
            myth = self.myth_pool[idx]
            pattern.scar_dream += myth['intensity'] * 0.01 * (phi_hash(pattern.id, pattern.age, 888) - 0.5)
            pattern.scar_dream = np.clip(pattern.scar_dream, -1.0, 1.0)


# =========================
# LogosObserver и ProtoLanguage УДАЛЕНЫ (наведение порядка): обе были пустыми
# оболочками без единого вызываемого метода -- их собственные методы .ask()
# и .exchange() уже были вычищены в более раннем аудите, instantiation в
# EvolutionEngine тоже уже была убрана тогда же. Сами классы просто
# оставались висеть мёртвым грузом. ENABLE_LOGOS_OBSERVER убран из Config
# отдельным изменением там же.
# =========================
# =========================
# EchoSystem
# =========================
class EchoSystem:
    def __init__(self):
        self.prison: list = []
        self.memory_echoes: dict = {}
        self.pantheon: list = []
        self._last_injection_t = -100

    def store_memory_echo(self, pattern: 'Pattern', event_type: str, intensity: float = 1.0):
        if pattern.id not in self.memory_echoes:
            self.memory_echoes[pattern.id] = []
        echo = {
            'type': event_type,
            'age': pattern.age,
            'coherence': pattern.coherence,
            'soul_weight': pattern.soul_weight,
            'unresolved_contradiction': pattern.unresolved_contradiction,
            'intensity': intensity,
            'concept_snapshot': list(pattern.concept_graph.nodes.keys())[:3] if pattern.concept_graph.nodes else []
        }
        self.memory_echoes[pattern.id].append(echo)
        if len(self.memory_echoes[pattern.id]) > 10:
            self.memory_echoes[pattern.id].pop(0)

    def field_whisper(self, pattern: 'Pattern', field, t):
        if pattern.spirit_gap > 0.3 or len(pattern.cells) < 2:
            return
        whispers = []
        if pattern.id in self.memory_echoes and self.memory_echoes[pattern.id]:
            echo = max(self.memory_echoes[pattern.id], key=lambda e: e['intensity'])
            whispers.append(f"Ты помнишь {echo['type']} (возраст {echo['age']})")
            if echo['type'] == 'death_disorganizer_lifespan':
                pattern.emotional_memory['grief'] += 0.05
            elif echo['type'] == 'redemption_complete':
                pattern.emotional_memory['gratitude'] += 0.05
        if not whispers and self.prison:
            idx = int(phi_hash(t, pattern.id, 33333) * len(self.prison))
            echo = self.prison[idx]
            whispers.append(f"Поле помнит: {echo.get('role', 'некто')} с болью {echo['unresolved_contradiction']:.2f}")
        if whispers:
            whisper_text = whispers[0]
            pattern._log_event("field_whisper", whisper=whisper_text)
            if phi_hash(t, pattern.id, 77777) < 0.05:
                # ИСПРАВЛЕНО: раньше эхо поля напрямую переписывало
                # pattern.intent — призрак диктовал агенту, ЧТО делать,
                # вместо того чтобы влиять на его внутреннее состояние
                # (нарушение принципа "эхо — не политика" из философии 832:
                # Active Echo не должен трогать intent/goals). Теперь эхо
                # оставляет след в теле и слегка смещает spirit_gap, но
                # выбор действия остаётся за самим агентом.
                old_gap = pattern.spirit_gap
                pattern.body_memory = min(1.0, pattern.body_memory + 0.05)
                gap_nudge = (phi_hash(t, pattern.id, 88888) - 0.5) * 0.1
                pattern.spirit_gap = max(0.0, pattern.spirit_gap + gap_nudge)
                pattern._log_event("sacred_dialogue_inversion",
                                   old_gap=round(old_gap, 3),
                                   new_gap=round(pattern.spirit_gap, 3),
                                   body_memory=round(pattern.body_memory, 3))

            # УБРАНО (рекомендация советника + принцип "эхо -- не политика",
            # тот же, что уже применили парой строк выше к intent/spirit_gap):
            # эхо здесь НАПРЯМУЮ добавляло агенту цель introspect -- это и
            # есть "применимый сигнал", который философия прямо запрещает
            # ("Echo carries no actionable signal"). Соседний блок (nudge
            # spirit_gap/body_memory) это уже соблюдал, а этот -- нет.
            # Эхо остаётся тем, что оно уже делает выше: след в теле,
            # запись в witness/культурную память -- без выбора за агента.
            pass

    def store_anomaly(self, pattern, anomaly_type="prophet"):
        if anomaly_type == "evolved_subject":
            pass
        else:
            if pattern.soul_weight < 0.3 or pattern.coherence < 0.4:
                return
        entry = {
            'id': pattern.id,
            'age': pattern.age,
            'type': anomaly_type,
            'identity': pattern.identity.copy(),
            'model': pattern.model.copy(),
            'belief': pattern.belief.copy(),
            'prediction': pattern.prediction.copy(),
            'spirit_gap': float(np.mean(np.abs(pattern.prediction - pattern.belief))),
            'coherence': pattern.coherence,
            'soul_weight': pattern.soul_weight,
            'emotional_memory': pattern.emotional_memory.copy(),
            'semantic_state': pattern.semantic_state,
            'unresolved_contradiction': pattern.unresolved_contradiction,
            'concept_graph_sample': list(pattern.concept_graph.nodes.keys())[:10],
            'timestamp': pattern.age
        }
        self.pantheon.append(entry)
        if len(self.pantheon) > 50:
            self.pantheon.pop(0)

    def store(self, pattern):
        if len(self.prison) > 45:
            self.prison.pop(0)
        entry = {
            'identity': pattern.identity.copy(),
            'model': pattern.model.copy(),
            'unresolved_contradiction': float(pattern.unresolved_contradiction) * 1.2,
            'role': pattern.role,
            'age': 0,
            'light_seed': False
        }
        if (Config.ENABLE_SEED_OF_LIGHT and
            pattern.arc_tracker.get_wisdom_weight() > 0.8 and
            len(pattern.arc_tracker.completed_arcs) > 5):
            entry['light_seed'] = True
            entry['phenomenal_essence'] = pattern.last_phenomenal_report
            entry['unresolved_contradiction'] *= 2.0
        self.prison.append(entry)

    def inject(self, field, patterns, t, scar):
        if not self.prison or len(patterns) == 0:
            return
        if t - self._last_injection_t < Config.ECHO_INJECTION_COOLDOWN:
            for e in self.prison:
                e['age'] += 1
            return

        self.prison = [e for e in self.prison if e['age'] < 150]
        if len(self.prison) > 40:
            self.prison.sort(key=lambda e: e['unresolved_contradiction'], reverse=True)
            self.prison = self.prison[:40]
        for e in self.prison:
            e['unresolved_contradiction'] *= (1.0 - Config.ECHO_DECAY_STRENGTH)

        boredom = calculate_boredom(patterns, field)

        if len(self.prison) >= 2 and phi_hash(t, 0, 3333) < 0.05:
            i1 = int(phi_hash(t, 1, 4444) * len(self.prison))
            i2 = int(phi_hash(t, 2, 5555) * len(self.prison))
            if i1 != i2:
                e1, e2 = self.prison[i1], self.prison[i2]
                if abs(float(e1['unresolved_contradiction']) - float(e2['unresolved_contradiction'])) <= 0.25:
                    new_model = (e1['model'] + e2['model']) / 2.0
                    new_model += np.array([phi_hash(t, i, 8888) - 0.5 for i in range(8)]) * 0.01
                    if phi_hash(t, i1, i2) < Config.ECHO_MUTATION_PROB:
                        new_model += np.array([phi_hash(t, i, 9999) - 0.5 for i in range(8)]) * Config.ECHO_MUTATION_STRENGTH
                    new_unresolved = float((e1['unresolved_contradiction'] + e2['unresolved_contradiction']) / 2.0)
                    new_role = e1['role'] if phi_hash(t, 3, 6666) < 0.5 else e2['role']
                    self.prison.append({
                        'identity': e1['identity'], 'model': new_model,
                        'unresolved_contradiction': new_unresolved, 'role': new_role,
                        'age': 0, 'light_seed': False
                    })

        prob = min(0.2, len(self.prison) * 0.02 + boredom * 0.1)
        if phi_hash(t, 0, 999) < prob:
            candidate_indices = [i for i, e in enumerate(self.prison) if e['age'] > 3]
            if not candidate_indices:
                candidate_indices = list(range(len(self.prison)))
            idx = candidate_indices[int(phi_hash(t, 1, 1001) * len(candidate_indices)) % len(candidate_indices)]
            echo = self.prison[idx]
            # ИСПРАВЛЕНО: раньше x,y выбирались чисто случайно по всему полю
            # 104x104, независимо от того, где реально живут агенты. Большая
            # часть инъекций попадала в пустоту, которую никто не почувствует
            # (агенты ощущают поле только рядом со своими клетками). Теперь
            # целимся рядом со случайным ЖИВЫМ агентом (с небольшим случайным
            # смещением) — эхо реально может достичь чьего-то восприятия.
            alive_patterns = [p for p in patterns if getattr(p, 'alive', False) and p.cells]
            if alive_patterns:
                anchor = alive_patterns[int(phi_hash(t, 7, 1003) * len(alive_patterns)) % len(alive_patterns)]
                ax, ay = next(iter(anchor.cells))
                offset = int(phi_hash(t, 2, 1002) * 11) - 5  # смещение -5..+5
                x = (ax + offset) % Config.WORLD_SIZE
                y = (ay + int(phi_hash(t, 8, 1004) * 11) - 5) % Config.WORLD_SIZE
            else:
                seed = int(phi_hash(t, 2, 1002) * Config.WORLD_SIZE * Config.WORLD_SIZE)
                x, y = seed % Config.WORLD_SIZE, (seed // Config.WORLD_SIZE) % Config.WORLD_SIZE
            field[x, y, CH['energy']] += 0.12
            field[x, y, CH['unknown']] = min(0.8, field[x, y, CH['unknown']] + 0.2)
            field[x, y, CH['binding']] += 0.35
            if echo.get('light_seed'):
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = (x+dx) % Config.WORLD_SIZE, (y+dy) % Config.WORLD_SIZE
                        field[nx, ny, CH['signal_gratitude']] = min(1.0, field[nx, ny, CH['signal_gratitude']] + 0.2)
                if Config.VERBOSE_LOGS:
                    print(f"[t={t}] ✨ SEED OF LIGHT injected at ({x},{y})")
            echo['unresolved_contradiction'] = float(echo['unresolved_contradiction']) * 0.88
            echo['age'] = 0
            if float(echo['unresolved_contradiction']) < 0.02:
                self.prison.pop(idx)
            else:
                if Config.VERBOSE_LOGS:
                    print(f"[t={t}] Echo injected at ({x},{y})")
            self._last_injection_t = t

        for p in patterns:
            if p.alive and p.unresolved_contradiction > 0.2:
                local_scar = safe_mean([scar[c[0], c[1]] for c in p.cells], 0)
                p.soul_weight = min(1.0, p.soul_weight + 0.01 * local_scar)

        for e in self.prison:
            e['age'] += 1

    def export_seed(self, pattern, filename: str = "seed_patterns.json"):
        import json
        seed = {
            "source": "pattern",
            "identity": pattern.identity.tolist(),
            "model": pattern.model.tolist(),
            "belief": pattern.belief.tolist(),
            "genome": pattern.genome,
            "concepts": list(pattern.concept_graph.nodes.keys()),
            "semantic_state": pattern.semantic_state,
            "emotional_memory": pattern.emotional_memory,
            "soul_weight": pattern.soul_weight
        }
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = []
        data.append(seed)
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)


# =========================
# FieldVoice
# =========================
class FieldVoice:
    def __init__(self):
        self.concepts = defaultdict(float)
        self.history = deque(maxlen=20)
        self._line = 0

    def update(self, field, t):
        e = np.mean(field[:,:,CH['energy']])
        g = np.mean(field[:,:,CH['signal_grief']])
        b = np.mean(field[:,:,CH['binding']])
        u = np.mean(field[:,:,CH['unknown']])
        self.history.append((e,g,b,u))
        if e > 0.3 and g > 0.4:
            self.concepts["storm"] += 1
        elif b > 0.5 and u < 0.2:
            self.concepts["silence"] += 1
        elif u > 0.5:
            self.concepts["void"] += 1
        else:
            self.concepts["flow"] += 1

    # ОЧИЩЕНО (аудит): .sing() и .get_report() нигде не вызывались --
    # только .update() реально используется движком каждый тик.
# =========================
# Функции сериализации/десериализации паттерна
# =========================
# ОЧИЩЕНО (аудит): здесь была ПЕРВАЯ версия deserialize (с помощниками
# _safe_parse_key/_safe_float_convert) для первой версии serialize_pattern.
# Первая serialize_pattern уже была отмечена как удалённая (см. ниже) в
# пользу объединённой версии в Cell 11 -- но её deserialize-двойник тогда
# не почистили, хотя он мёртв ровно по той же причине: нигде не вызывается,
# реальная десериализация идёт через свою локальную _safe_parse_key
# (определена заново внутри настоящей deserialize-функции дальше по проекту).
# УДАЛЕНО: здесь была первая версия ser


# ============================================================
# v4.2 (ДЕТЕРМИНИЗМ): calculate_boredom хранит baseline в атрибуте функции,
# то есть в состоянии процесса, а не мира. Второй engine.run() в той же
# сессии стартовал с чужой "скукой" -> прогоны с одним seed расходились
# (в тесте Cell 5 уже с t=10). SelfRegulationEngine.reset() (Cell 3e) теперь
# вызывает reset_boredom_baseline(); число сбросов видно в отчёте Cell 4b.
# ============================================================
_BOREDOM_DIAG = {'baseline_resets': 0}


def reset_boredom_baseline():
    if hasattr(calculate_boredom, '_baseline'):
        del calculate_boredom._baseline
    _BOREDOM_DIAG['baseline_resets'] += 1
