












# === Cell 4b ===
# ИСПРАВЛЕНО: антипаттерн с locals() заменен на явную инициализацию переменной
# ИСПРАВЛЕНО: порог диалоговой памяти в отчёте снижен с 5 до 3
# ДОБАВЛЕН: блок отчёта по BOREDOM & ADAPTIVITY
# ДОБАВЛЕН: развёрнутая статистика генератора речи (phenomenal_report + inner_speech)
# ДОБАВЛЕН: блок статистики физического слоя Морзе
# ДОБАВЛЕН: блок статистики подсознания (Unconscious Layer)

import numpy as np
import os
import json
import builtins
import random
from collections import defaultdict, Counter

_original_print = builtins.print
def print(*args, **kwargs):
    kwargs['flush'] = True
    _original_print(*args, **kwargs)

def print_final_report(engine):
    alive = [p for p in engine.patterns if p.alive]
    print("\n" + "="*50)
    print("832 v34.03 - FINAL REPORT")
    print("="*50)
    print(f"Steps: {Config.STEPS} | Alive: {len(alive)} | Lineages: {len(set(p.lineage_id for p in alive))}")
    if 'state_fingerprint' in globals():
        try:
            _fp = state_fingerprint(engine)
            print(f"🔏 Отпечаток состояния прогона: field={_fp['field_crc']} agents={_fp['agents_crc']} "
                  f"patterns={_fp['n_patterns']} alive={_fp['alive']} age={_fp['age']}")
            print("   (одинаковый seed + одинаковый старт => одинаковый отпечаток; сравнивайте между прогонами)")
        except Exception as _e:
            print(f"🔏 Отпечаток состояния недоступен: {_e}")
    if '_BOREDOM_DIAG' in globals():
        print(f"   Сбросов baseline скуки (детерминизм) за сессию: {_BOREDOM_DIAG['baseline_resets']}")

    long_lived = sorted([p for p in alive if p.age > 100], key=lambda x: x.age, reverse=True)[:5]
    if long_lived:
        print("\n--- TOP 5 LONG-LIVED ---")
        for p in long_lived:
            print(f"  #{p.id} (age={p.age}, soul={p.soul_weight:.2f}, role={p.role_type})")
            print(f"  State: {p.semantic_state} | Grat: {p.emotional_memory['gratitude']:.2f} | Grief: {p.emotional_memory['grief']:.2f}")
            if p.concept_graph.nodes:
                top = max(p.concept_graph.nodes.items(), key=lambda x: x[1]['count'])
                print(f"  Core concept: {top[0]} (freq={top[1]['count']:.2f})")
            print()

    minds = sorted(alive, key=lambda p: len(p.concept_graph.nodes), reverse=True)[:3]
    if any(len(p.concept_graph.nodes) > 0 for p in minds):
        print("--- TOP CONCEPTUAL MINDS ---")
        for p in minds:
            if not p.concept_graph.nodes: continue
            top_nodes = sorted(p.concept_graph.nodes.items(), key=lambda x: x[1]['count'], reverse=True)[:2]
            print(f"  #{p.id}: {len(p.concept_graph.nodes)} concepts")
            for sig, data in top_nodes:
                print(f"    ↳ {sig}: {data['count']:.2f}")
        print()

    lineages = defaultdict(list)
    for p in alive:
        if p.lineage_total_age > 0:
            lineages[p.lineage_id].append(p)

    top_lineages = sorted(lineages.items(), key=lambda kv: kv[1][0].lineage_total_age, reverse=True)[:3]
    if top_lineages:
        print(f"--- TOP {len(top_lineages)} LINEAGES (by total age) ---")
        for lid, members in top_lineages:
            nci_avg = safe_mean([getattr(p, '_nci', 0.5) for p in members], 0.5)
            soul_avg = safe_mean([p.soul_weight for p in members], 0.5)
            trans_counter = Counter()
            for p in members:
                trans_counter.update(p.transition_memory.transitions)
            top_trans = trans_counter.most_common(3) if trans_counter else []
            path_str = "→".join(f"{f}→{t}" for (f,t),c in top_trans[:2]) if top_trans else "none"
            concept_counter = Counter()
            for p in members:
                for sig, data in p.concept_graph.nodes.items():
                    concept_counter[sig] += data.get('count', 0)
            top_concepts = [str(sig) for sig, cnt in concept_counter.most_common(3)]
            total_age = members[0].lineage_total_age
            narrative_count = sum(1 for p in members if p._narrative_agent)
            print(f"  Lineage #{lid} (age={total_age}):")
            print(f"    Soul: NCI_avg={nci_avg:.2f}, soul_avg={soul_avg:.2f}")
            print(f"    Path: {path_str}")
            print(f"    Concepts: {', '.join(top_concepts) if top_concepts else 'none'}")
            print(f"    Legacy: {len(members)} alive, {narrative_count} narrative agents")
        print()

    # ============================================================
    # НОВЫЙ БЛОК: ОТЧЕТ О РАБОТЕ BOREDOM (адаптивность)
    # ============================================================
    print("\n--- BOREDOM & ADAPTIVITY ---")
    if engine.selfreg is not None:
        sr = engine.selfreg
        current_boredom = getattr(sr, 'boredom', 0.0)
        phase_history = list(getattr(sr, '_phase_history', []))
        stagnation_steps = phase_history.count('stagnation') if phase_history else 0
        total_steps_logged = len(phase_history) if phase_history else 1
        stagnation_ratio = stagnation_steps / total_steps_logged

        print(f"  Current Boredom Score: {current_boredom:.3f} (max 1.0)")
        print(f"  Stagnation Phase Ratio: {stagnation_ratio:.1%} ({stagnation_steps}/{total_steps_logged} steps)")
        print(f"  Low Gap Pressure: {getattr(sr, 'low_gap_pressure', 0.0):.3f}")
        print(f"  Turbulence Factor: {getattr(sr, 'turbulence_factor', 0.0):.3f}")

        # Диагностика
        if current_boredom < 0.1 and stagnation_ratio > 0.5:
            print("  ⚠️ WARNING: High stagnation but LOW boredom score!")
            print("     -> Possible bug: calculate_boredom() not updating selfreg.boredom")
            print("     -> System cannot adapt to stagnation.")
        elif current_boredom > 0.6:
            print("  ✅ Boredom is HIGH -> System should be injecting noise/novelty.")
        else:
            print("  ℹ️ Boredom is moderate/low. System is active or stable.")
    else:
        print("  ❌ SelfRegulationEngine not found (engine.selfreg is None or missing).")
    print("-" * 50)
    # ============================================================

    m = collect_metrics(engine.patterns, engine.field, Config.STEPS, engine.EMERGENT_LEXICON)
    print("--- SYSTEM STATE ---")
    print(f"  Trust: {m['avg_trust']:.2f} | High-trust pairs: {m['high_trust_pairs']}")
    print(f"  Triadic alive: {m['triadic_alive']}/{len(alive)} ({m['triadic_alive_ratio']:.1%})")
    print(f"  Total divisions (alive agents born via division): {m['divisions_total']}")
    # ФИКС: реальный монотонный счётчик всех делений за прогон (не зависит от того,
    # жив ли ребёнок сейчас, и не обнуляется, в отличие от m['divisions_total']).
    print(f"  Total divisions EVER (engine-level counter): {getattr(engine, 'total_divisions_ever', 'N/A')}")
    print(f"  Narrative agents: {m.get('narrative_agents', 0)} / {len(alive)}")
    print(f"  Сны/кошмары: dream_memory={m.get('agents_with_dream_memory',0)} агентов, "
          f"nightmare={m.get('agents_with_nightmare',0)} агентов | "
          f"новых снов={m.get('dream_consolidations',0)}, новых кошмаров={m.get('nightmare_consolidations',0)}, "
          f"кошмаров искуплено={m.get('nightmares_transformed',0)}")
    print(f"  Avg endurance: {m.get('avg_endurance', 0):.2f} | Critical (<0.2): {m.get('endurance_critical', 0)} | Blocked by fatigue: {m.get('divide_blocked_fatigue', 0)}")
    print(f"  Teaching events: {m.get('teaching_events', 0)} | Learning events: {m.get('learning_events', 0)}")
    print(f"  Social: crisis={m.get('avg_social_crisis', 0):.2f} inv={m.get('avg_social_invitation', 0):.2f} grief={m.get('avg_social_grief', 0):.2f} coop={m.get('avg_social_cooperate', 0):.2f} expl={m.get('avg_social_explore', 0):.2f} help={m.get('avg_social_seek_help', 0):.2f} scar={m.get('avg_social_scar', 0):.2f} rest={m.get('avg_social_rest', 0):.2f} res={m.get('avg_social_resonance', 0):.2f} btype={m.get('avg_social_btype', 0):.2f} alarm={m.get('avg_social_alarm', 0):.2f} beau={m.get('avg_social_beauty',0):.2f} rhy={m.get('avg_social_rhythm',0):.2f} int={m.get('avg_social_interest',0):.2f} mem={m.get('avg_social_memory',0):.2f} sil={m.get('avg_social_silence',0):.2f}")
    print(f"  Soma: act_fb={m.get('avg_action_feedback', 0):.2f} social_warmth={m.get('avg_social_warmth', 0):.2f}")
    # ДОБАВЛЕНА СТРОКА ДЛЯ FERAL
    print(f"  Feral: {m.get('feral_count', 0)} | Avg fury: {m.get('avg_feral_fury', 0):.2f} | Kills: {m.get('feral_kills', 0)}")

    has_transitions = sum(1 for p in alive if len(p.transition_memory.transitions) >= 3)
    print(f"  Agents with transition memory (≥3): {has_transitions} / {len(alive)}")

    attention_entropies = []
    for p in alive:
        if p._prev_cell_energies is not None and p.cells:
            try:
                # ИСПРАВЛЕНО: sorted() для согласованности порядка с
                # _prev_cell_energies (см. фикс в update_model_part1).
                xs, ys = zip(*sorted(p.cells))
                current_energies = engine.field[xs, ys, CH['energy']]
                prev_energies = p._prev_cell_energies
                if len(prev_energies) == len(current_energies):
                    delta = np.abs(current_energies - prev_energies)
                    weights = delta / (np.sum(delta) + 1e-8)
                    entropy = -np.sum(weights * np.log(weights + 1e-8))
                    attention_entropies.append(entropy)
            except Exception:
                pass
    avg_attention_entropy = safe_mean(attention_entropies)
    print(f"  Avg attention entropy: {avg_attention_entropy:.3f}")

    print(f"  Disorganizers: {m['disorganizer_count']} | Redeemed: {m['redeemed_count']}")
    print(f"  Avg binding: {m['phenomenal_binding_avg']:.3f}")
    print(f"  Internal gap: avg={m['avg_internal_gap']:.3f} max={m['max_internal_gap']:.3f} | Observation gap: avg={m['avg_obs_gap']:.3f} max={m['max_obs_gap']:.3f}")
    print(f"  Avg field unknown: {m['avg_field_unknown']:.3f} | binding: {m['avg_field_binding']:.3f} | trust: {m['avg_trust']:.3f}")
    print(f"  Lineage count: {m.get('lineage_count', 0)} (avg age: {m.get('avg_lineage_age', 0):.0f}, max age: {m.get('max_lineage_age', 0)})")
    print(f"  Ancient lineages (>1000): {m.get('ancient_lineages', 0)} | Max total age: {m.get('max_lineage_total_age', 0)}")

    # ---- МОРЗЕ-КОММУНИКАЦИЯ ----
    morse_stats = m.get('morse', {})
    if morse_stats:
        print("\n--- 📡 МОРЗЕ-КОММУНИКАЦИЯ (физический слой) ---")
        print(f"  Агентов с приёмником: {morse_stats.get('agents_with_rx', 0)} / {len(alive)}")
        print(f"  Всего попыток отправки: {morse_stats.get('total_sent', 0)}")
        print(f"  Успешно декодировано: {morse_stats.get('total_decoded', 0)}")
        print(f"  Искажено (corrupted): {morse_stats.get('total_corrupted', 0)}")
        print(f"  Неопределённо (uncertain): {morse_stats.get('total_uncertain', 0)}")
        print(f"  Коллизий: {morse_stats.get('total_collisions', 0)}")
        print(f"  Таймаутов: {morse_stats.get('total_timeouts', 0)}")
        print(f"  Всего получено энергии: {morse_stats.get('total_energy', 0.0):.2f}")
        # ДОБАВЛЕНО: сколько _conservation_check реально погасил -- проверка
        # гипотезы, что гомеостат съедает прирост от ENERGY_INJECTION_RATE
        if engine._econs_diag['ticks'] > 0:
            _ed = engine._econs_diag
            print(f"  🧮 conservation_check сработал {_ed['ticks']} раз, "
                  f"суммарно погашено энергии={_ed['total_correction_abs']:.1f}, "
                  f"макс. дрейф за тик={_ed['max_drift']:.1f}")
        # ДОБАВЛЕНО: точный расчёт притока против реального изменения суммы поля
        if hasattr(engine, '_energy_flow_diag'):
            _efd = engine._energy_flow_diag
            _current_total = float(np.sum(engine.field[:, :, CH['energy']]))
            _observed_change = _current_total - _efd['start_total']
            _drain = _efd['injected_total'] - _observed_change
            print(f"  🔬 Приток энергии за прогон (точно, по формуле): {_efd['injected_total']:.1f}")
            print(f"     Фактическое изменение суммы поля: {_observed_change:+.1f} "
                  f"(было {_efd['start_total']:.1f} -> стало {_current_total:.1f})")
            print(f"     Разница (реальный сток, откуда бы он ни шёл): {_drain:.1f} "
                  f"({_drain / _efd['injected_total'] * 100 if _efd['injected_total'] else 0:.0f}% от притока)")
        # ДОБАВЛЕНО: пространственная проверка -- приток растёт в сумме по
        # ВСЕМУ полю, но E= (средняя энергия под агентами) растёт заметно
        # медленнее. Смотрим, не оседает ли приток преимущественно там,
        # где никто не живёт -- снимок конечного состояния, ничего не
        # трогает, читает только уже готовый engine.field.
        _occ_mask = engine.field[:, :, CH['owner']] != 0
        _energy_ch = engine.field[:, :, CH['energy']]
        _n_occ = int(_occ_mask.sum())
        _n_free = int((~_occ_mask).sum())
        if _n_occ > 0 and _n_free > 0:
            _e_occ = float(_energy_ch[_occ_mask].mean())
            _e_free = float(_energy_ch[~_occ_mask].mean())
            print(f"  🗺️ Энергия в занятых клетках (где живут агенты, n={_n_occ}): {_e_occ:.4f}")
            print(f"     Энергия в свободных клетках (n={_n_free}): {_e_free:.4f}")
            if _e_free > 0:
                print(f"     Соотношение свободные/занятые: {_e_free / max(_e_occ, 1e-9):.2f}x "
                      f"{'-- приток оседает НЕ там, где живёт популяция' if _e_free > _e_occ * 1.3 else '-- распределение примерно равномерное'}")
        print(f"  Средняя уверенность: {morse_stats.get('avg_confidence', 0.0):.3f}")
        print(f"  Уникальных отправителей (суммарно): {morse_stats.get('unique_senders', 0)}")
        print(f"  Переключений доминирующего отправителя: {morse_stats.get('sender_switches', 0)}")

        # ДОБАВЛЕНО (аудит): раньше считалось в отдельной collect_morse_metrics(),
        # которая нигде не вызывалась -- этот прогресс не был виден в отчёте.
        print("\n--- 🗣 ЭМЕРДЖЕНТНЫЙ ЯЗЫК (EmergentLexicon, без словаря) ---")
        early = morse_stats.get('lang_signal_len_early')
        late = morse_stats.get('lang_signal_len_late')
        ratio = morse_stats.get('lang_compression_ratio', 1.0)
        if early is not None:
            print(f"  Длина сигнала: ранняя={early:.2f} -> поздняя={late:.2f} "
                  f"(compression={ratio:.3f}, <1.0 = язык сжался со временем)")
        print(f"  Активных кластеров сигналов: {morse_stats.get('lang_active_clusters', 0)} "
              f"из {morse_stats.get('lang_total_clusters', 0)} когда-либо созданных")
        print(f"  Язык схлопнулся в один сигнал: {morse_stats.get('lang_collapsed', False)}")
        print(f"  Концептов, сформированных из принятых сигналов: {m.get('morse_concepts', 0)}")
        labels = morse_stats.get('lang_dominant_labels', {})
        if labels:
            print(f"  Проступившие значения кластеров (для человека, не для агентов): {labels}")

        # ДОБАВЛЕНО (Cell 13 v4.0): кодек -- доходит ли содержание сигнала.
        print("\n--- 🧬 КОДЕК СИГНАЛА (интент -> 4 блока импульсов -> вектор у получателя) ---")
        _rx_total = morse_stats.get('lang_rx_total', 0)
        if _rx_total:
            _rx_null = morse_stats.get('lang_rx_null', {})
            _null_n = sum(_rx_null.values())
            print(f"  Принято сигналов (по получателям): {_rx_total}; нечитаемых (NULL): {_null_n} "
                  f"({_null_n / _rx_total:.1%}) [блоков != 4: {_rx_null.get('blocks', 0)}, "
                  f"без длинных импульсов: {_rx_null.get('quiet', 0)}]")
            _bc = morse_stats.get('lang_rx_block_counts', {})
            print(f"  Число блоков в принятых строках: {dict(sorted(_bc.items()))} (ожидается пик на 4)")
            if _null_n / _rx_total > 0.4:
                print("     ⚠️ Доля NULL > 40%: канал портит границы блоков (коллизии, окно "
                      "приёма) или сигналы слишком слабые.")
        else:
            print("  Принятых сигналов нет.")
        _kc = morse_stats.get('lang_send_k_counts', {})
        _sil = morse_stats.get('lang_send_silence', {})
        _sent_n = sum(_kc.values())
        if _sent_n or _sil:
            print(f"  Отправлено по K (импульсов на ось): {dict(sorted(_kc.items()))}; "
                  f"молчаний: {dict(_sil)}; энергии потрачено на сигналы: "
                  f"{morse_stats.get('lang_send_energy_spent', 0.0):.2f}")
            _attempts = _sent_n + sum(_sil.values())
            if _attempts and _sil.get('too_poor', 0) / _attempts > 0.5:
                print("     ⚠️ Больше половины попыток сорвано бюджетом: LANG_COST_PER_PULSE_TICK "
                      "слишком высока для энергии популяции.")
            if _sent_n and len(_kc) == 1 and getattr(Config, 'LANG_PULSES_PER_AXIS_MAX', 2) > 1:
                print("     ⚠️ Все сигналы одного K: бюджет не различает агентов, "
                      "подобрать LANG_COST_PER_PULSE_TICK.")
        _f_early = morse_stats.get('lang_fidelity_early')
        _f_late = morse_stats.get('lang_fidelity_late')
        if _f_early is not None:
            print(f"  Расхождение принятого вектора и интента отправителя (0 = точно, "
                  f"нижняя оценка): ранняя={_f_early:.3f} -> поздняя={_f_late:.3f}")
        else:
            print("  Недостаточно данных для оценки точности передачи.")

        # v4.2: физика канала -- что происходило с каждой передачей и приёмом.
        _ch = morse_stats.get('chan', {})
        print("\n--- 📡 КАНАЛ (передача -> эфир -> приём) ---")
        if _ch:
            _tx_s = _ch.get('tx_started', 0)
            _tx_c = _ch.get('tx_completed', 0)
            _tx_a = _ch.get('tx_aborted', 0)
            print(f"  Передач начато: {_tx_s}; дошло до конца: {_tx_c}; оборвано (смерть/сброс): {_tx_a}; "
                  f"отложено из-за чужой передачи рядом (NAV): {_ch.get('tx_nav_deferred', 0)}")
            _rs = _ch.get('rx_sessions', 0)
            print(f"  Сессий приёма завершено: {_rs} [уверенность: надёжных {_ch.get('rx_conf_reliable', 0)}, "
                  f"сомнительных {_ch.get('rx_conf_uncertain', 0)}, испорченных {_ch.get('rx_conf_corrupted', 0)}; "
                  f"с флагом коллизии {_ch.get('rx_collision_flag', 0)}]")
            print(f"  Отброшено до лексикона: без отправителя {_ch.get('rx_dropped_no_sender', 0)}, "
                  f"смешанных (два говорящих) {_ch.get('rx_dropped_mixed', 0)}; "
                  f"передано в лексикон: {_ch.get('rx_to_lexicon', 0)}")
            print(f"  Защиты: собственный импульс не принят за сигнал {_ch.get('rx_self_echo_obs', 0)} раз; "
                  f"двойной шаг передатчика за тик заблокирован {_ch.get('tx_double_step_blocked', 0)} раз; "
                  f"двойное прослушивание за тик заблокировано {_ch.get('rx_listen_double_blocked', 0)} раз; "
                  f"таймаутов приёма {_ch.get('rx_timeouts', 0)}")
            if _tx_s and _tx_a / _tx_s > 0.3:
                print("     ⚠️ Больше 30% передач оборвано смертью отправителя: сообщение слишком длинное "
                      "для жизни агента.")
            _rt = morse_stats.get('lang_rx_total', 0)
            _nl = sum(morse_stats.get('lang_rx_null', {}).values())
            if _tx_s:
                print(f"  Итог: на одну начатую передачу приходится {_rt / _tx_s:.2f} приёмов в лексикон; "
                      f"читаемых (не NULL): {(_rt - _nl) / _tx_s:.2f}")
        else:
            print("  Счётчиков канала нет (Cell 13 старой версии).")
        _cp = morse_stats.get('chan_params', {})
        if _cp:
            print("  Параметры канала: " + ", ".join(f"{k}={v}" for k, v in _cp.items()))

        # ДОБАВЛЕНО: контур обратной связи отправитель<->получатель.
        # Раньше учился только получатель -- эти строки показывают, начал ли
        # теперь и отправитель подстраиваться (это и есть настоящая
        # конвергенция языка, а не только сжатие сигнала одной стороной).
        print("\n--- 🔁 ОБРАТНАЯ СВЯЗЬ ОТПРАВИТЕЛЬ↔ПОЛУЧАТЕЛЬ (подкрепление гена) ---")
        reinf_events = morse_stats.get('lang_reinforcement_events', 0)
        print(f"  Подкреплений отправителя всего: {reinf_events}")
        r_early = morse_stats.get('lang_reinforcement_gap_early')
        r_late = morse_stats.get('lang_reinforcement_gap_late')
        if r_early is not None:
            trend = "СХОДИТСЯ" if r_late < r_early else "не сходится"
            print(f"  Расхождение ген↔цель кластера при подкреплении: "
                  f"ранние={r_early:.3f} -> поздние={r_late:.3f} ({trend})")
        else:
            print("  Недостаточно подкреплений для тренда (нужно больше 10).")

        d_early = morse_stats.get('lang_gene_diversity_early')
        d_late = morse_stats.get('lang_gene_diversity_late')
        if d_early is not None:
            trend = "СХОДИТСЯ К ОБЩЕМУ ДИАЛЕКТУ" if d_late < d_early else "остаётся/растёт разнообразным"
            print(f"  Разброс генов кодирования по популяции: "
                  f"ранний={d_early:.4f} -> поздний={d_late:.4f} ({trend})")
        else:
            print("  Недостаточно снимков для тренда разнообразия генов.")

        top_uses = morse_stats.get('lang_top_cluster_uses')
        if top_uses:
            conc = morse_stats.get('lang_top_cluster_concentration', 0.0)
            n_send = morse_stats.get('lang_top_cluster_unique_senders', 0)
            kind = "приватный код одного агента" if conc > 0.7 else \
                   "используется узкой группой" if conc > 0.4 else "общий язык популяции"
            print(f"  Самый частый кластер: {top_uses} употреблений, "
                  f"{n_send} разных отправителей, концентрация топ-1={conc:.2f} ({kind})")
        # ДОБАВЛЕНО: диагностика "плывущего интента" -- как часто меняется
        # доминантная ось у ОДНОГО И ТОГО ЖЕ отправителя между его
        # подкреплениями. Если ось скачет часто, ген не успевает сойтись
        # ни по одной оси -- см. Cell 13.1.
        _d = engine.EMERGENT_LEXICON._axis_switch_diag
        _total = _d['same'] + _d['switched']
        if _total > 0:
            print(f"  Ось интента при повторных подкреплениях одного отправителя: "
                  f"та же={_d['same']} ({_d['same']/_total:.0%}), "
                  f"сменилась={_d['switched']} ({_d['switched']/_total:.0%})")
            if _d['switched'] / _total > 0.4:
                print("  ⚠️ Ось часто скачет -- ген может не успевать сходиться "
                      "ни по одной оси (гипотеза 'плывущего интента').")
        else:
            print("  Ось интента: недостаточно повторных подкреплений одного "
                  "отправителя за прогон, чтобы оценить.")
    else:
        print("\n--- 📡 МОРЗЕ-КОММУНИКАЦИЯ ---")
        print("  Данные отсутствуют (Морзе не включён или не использовался).")

    # ДОБАВЛЕНО (аудит): видимость механизмов, подключённых в ходе чистки
    # (Cell 6/10) -- раньше были написаны, но нигде не вызывались.
    print("\n--- 🌱 НОВЫЕ ПОДКЛЮЧЁННЫЕ МЕХАНИЗМЫ ---")
    print(f"  Спонтанное рождение из ничейной энергии поля: {m.get('spontaneous_field_emergence', 0)}")
    print(f"  Отмечены для падения (marked_for_fall): {m.get('marked_for_fall_count', 0)}")
    print(f"  Редких кризисов сработало: {getattr(engine, '_rare_crisis_triggers', 0)}")
    chorus_morse_count = sum(1 for ev in engine.witness.log if ev.get('event') == 'chorus_morse')
    print(f"  Импульсов хора (chorus_morse): {chorus_morse_count}")

    # ============================================================
    # БЛОК ПОДСОЗНАНИЯ (UNCONSCIOUS)
    # ============================================================
    print("\n--- 🧠 ПОДСОЗНАНИЕ (UNCONSCIOUS LAYER) ---")

    avg_gut = m.get('avg_gut_feeling', 0.0)
    need_counts = m.get('latent_need_counts', {})
    insights = m.get('unconscious_insights', 0)
    goals = m.get('unconscious_goals', 0)
    avg_antic = m.get('avg_anticipation', 0.0)
    avg_drive_dist = m.get('avg_drive_distance', 0.0)
    uc_agents = m.get('unconscious_concept_agents', 0)
    total_uc_concepts = m.get('total_unconscious_concepts', 0)

    print(f"  Среднее gut_feeling: {avg_gut:+.3f} (от -1 до +1)")
    print(f"  Среднее предчувствие (anticipation): {avg_antic:+.3f}")
    print(f"  Средняя дистанция до drive_towards: {avg_drive_dist:.2f} клеток")

    if need_counts:
        print("  Распределение латентных потребностей:")
        total_needs = sum(need_counts.values())
        for need, cnt in sorted(need_counts.items(), key=lambda x: -x[1]):
            pct = cnt / total_needs * 100 if total_needs else 0
            bar = "█" * int(pct / 5)
            print(f"    {need:<12} {cnt:>3} ({pct:5.1f}%) {bar}")
    else:
        print("  Нет данных о латентных потребностях.")

    print(f"  Всплывших инсайтов (unconscious_insights): {insights}")
    print(f"  Подсознательных целей (unconscious_goals): {goals}")
    print(f"  Агентов с подсознательными концептами: {uc_agents} / {len(alive)}")
    print(f"  Всего подсознательных концептов: {total_uc_concepts}")

    # Динамика gut_feeling за последние 10 срезов
    if len(engine.metrics_history) >= 10:
        gut_history = [m.get('avg_gut_feeling', 0.0) for m in engine.metrics_history[-10:]]
        if gut_history:
            gut_trend = "↑" if gut_history[-1] > gut_history[0] else "↓" if gut_history[-1] < gut_history[0] else "→"
            print(f"  Тренд gut_feeling (последние 10 срезов): {gut_trend} (с {gut_history[0]:+.2f} до {gut_history[-1]:+.2f})")

    # Пример прорыва подсознания в речь
    inner_speech_agents = [p for p in alive if p.inner_speech]
    if inner_speech_agents:
        sample = inner_speech_agents[0]
        last_speech = sample.inner_speech[-1] if sample.inner_speech else None
        if last_speech and isinstance(last_speech, dict):
            print(f"  Пример прорыва подсознания в речь (агент #{sample.id}):")
            print(f"    \"{last_speech.get('text', '...')}\"")

    # ============================================================
    # ДОБАВЛЕНО (24.07): статистика по слою эмерджентности —
    # Ощущение / Самопричинность / Чужой разум / Мета-слой /
    # Незакрываемый вопрос — плюс контроль фикса угасания protection_level
    # (см. обсуждение провала ANC/TOT_AGE в чате 23-24.07).
    # ============================================================
    print("\n--- 🌱 ЭМЕРДЖЕНТНЫЙ СЛОЙ (24.07) ---")

    felt_vals = [getattr(p, '_felt_intensity', None) for p in alive]
    felt_vals = [v for v in felt_vals if v is not None]
    causal_vals = [getattr(p, '_causal_efficacy', None) for p in alive]
    causal_vals = [v for v in causal_vals if v is not None]
    surprise_vals = [getattr(p, '_social_surprise', None) for p in alive]
    surprise_vals = [v for v in surprise_vals if v is not None]

    print(f"  1) Ощущение (felt_intensity): {len(felt_vals)}/{len(alive)} агентов | avg={safe_mean(felt_vals):.3f}")
    print(f"  2) Самопричинность (causal_efficacy, net клеток/тик): {len(causal_vals)}/{len(alive)} агентов | avg={safe_mean(causal_vals):.3f}")
    print(f"  3) Чужой разум (social_surprise): {len(surprise_vals)}/{len(alive)} агентов | avg={safe_mean(surprise_vals):.3f}")

    # ДОБАВЛЕНО (проектная сессия): self_phenomenal_error реально считается
    # каждый тик и участвует в knows_itself, но нигде не выводился в отчёт --
    # раньше эта цифра была видна только тому, кто читает исходники.
    # mixed_self_error -- параллельное наблюдение, НЕ трогает саму формулу
    # _subject_detected: 0.5*self_phenomenal_error + 0.5*(social_surprise,
    # приведённый к тому же порядку величины). Решение, сливать ли их по-
    # настоящему, ещё не принято -- пока только смотрим, что получается.
    self_err_vals = [getattr(p, 'self_phenomenal_error', None) for p in alive]
    self_err_vals = [v for v in self_err_vals if v is not None]
    mixed_vals = []
    for p in alive:
        se = getattr(p, 'self_phenomenal_error', None)
        ss = getattr(p, '_social_surprise', None)
        if se is not None and ss is not None:
            mixed_vals.append(0.5 * se + 0.5 * min(1.0, ss * 2))
    print(f"  3a) Самопрогноз (self_phenomenal_error): {len(self_err_vals)}/{len(alive)} агентов | "
          f"avg={safe_mean(self_err_vals):.3f}"
          + (f" | min={min(self_err_vals):.3f} max={max(self_err_vals):.3f}" if self_err_vals else ""))
    print(f"  3z) Смешанный self+social (наблюдение, не влияет на детекцию): "
          f"{len(mixed_vals)}/{len(alive)} агентов | avg={safe_mean(mixed_vals):.3f}"
          + (f" | min={min(mixed_vals):.3f} max={max(mixed_vals):.3f}" if mixed_vals else ""))

    # ДОБАВЛЕНО (Causal Inference, проектная сессия): гипотеза о причине
    # страдания теперь реально бьёт по доверию к подозреваемому, не только
    # пишется в лог -- здесь видно, сработало ли это хоть раз и насколько.
    _hyp_counts = [p.event_counts.get('suffering_hypothesis', 0) for p in alive]
    _pen_counts = [p.event_counts.get('causal_inference_trust_penalty', 0) for p in alive]
    _agents_with_penalty = sum(1 for c in _pen_counts if c > 0)
    print(f"  3c) Causal Inference (гипотеза боли -> доверие к подозреваемому): "
          f"гипотез={sum(_hyp_counts)}, штрафов применено={sum(_pen_counts)} | "
          f"агентов хоть раз применивших={_agents_with_penalty}/{len(alive)}")

    meta_vals = [getattr(p, '_meta_surprise', None) for p in alive]
    meta_vals = [v for v in meta_vals if v is not None]
    if meta_vals:
        print(f"  3b) Теория разума (meta_surprise, прогноз прогноза): {len(meta_vals)}/{len(alive)} агентов | avg={safe_mean(meta_vals):.3f}")
    else:
        print("  3b) Теория разума: нет данных (слой ещё не применён)")

    root_q_agents = [p for p in alive if p._root_question is not None]
    root_share = len(root_q_agents) / max(1, len(alive))
    print(f"  4-5) Незакрываемый вопрос: {len(root_q_agents)}/{len(alive)} агентов сформировали root_question ({root_share:.1%})")

    # ДОБАВЛЕНО (эпигенетика, проектная сессия): сколько из них -- честно
    # свои, а сколько унаследованы от родителя через спору (см. process_spores).
    _rq_inherited = [p for p in root_q_agents if getattr(p, '_root_question_inherited', False)]
    print(f"  4-5b) Из них унаследовано через спору: {len(_rq_inherited)}/{len(root_q_agents)}"
          + (f" ({len(_rq_inherited)/len(root_q_agents):.1%})" if root_q_agents else ""))

    # ДОБАВЛЕНО (Dream Planning, проектная сессия): сколько новых рёбер между
    # несвязанными концептами реально родилось во сне за весь прогон.
    _dream_edges_total = sum(p.event_counts.get('dream_insight_edge', 0) for p in alive)
    _dream_edge_agents = sum(1 for p in alive if p.event_counts.get('dream_insight_edge', 0) > 0)
    print(f"  5b) Dream Planning (озарения во сне): {_dream_edges_total} новых рёбер | "
          f"{_dream_edge_agents}/{len(alive)} агентов хоть раз")

    # ДОБАВЛЕНО (языковое давление / Red Queen, проектная сессия): сколько
    # агентов реально получили метаболическую скидку за подтверждённое
    # координацией понимание с партнёром -- то есть язык начал приносить
    # ощутимую пользу, а не только оставаться дешёвым фоновым разговором.
    _coord_bonus_agents = sum(1 for p in alive if p.event_counts.get('coordination_metabolic_bonus', 0) > 0)
    _coord_bonus_events = sum(p.event_counts.get('coordination_metabolic_bonus', 0) for p in alive)
    print(f"  5c) Языковая координация (метаболическая скидка за sim>{Config.COORDINATION_SIM_THRESHOLD}): "
          f"{_coord_bonus_agents}/{len(alive)} агентов хоть раз | всего срабатываний={_coord_bonus_events}")
    if root_q_agents:
        sample = root_q_agents[0]
        print(f"       Пример (#{sample.id}): \"{sample._root_question}\"")

    causal_events = sum(p.event_counts.get('self_causality_felt', 0) for p in alive)
    surprise_events = sum(p.event_counts.get('other_mind_surprise', 0) for p in alive)
    tom_events = sum(p.event_counts.get('theory_of_mind_surprise', 0) for p in alive)
    root_events = sum(p.event_counts.get('root_question_formed', 0) for p in alive)
    print(f"  События (среди живых): self_causality_felt={causal_events}, other_mind_surprise={surprise_events}, theory_of_mind_surprise={tom_events}, root_question_formed={root_events}")

    protected = [p for p in alive if p.protection_level > 0.01]
    avg_prot = safe_mean([p.protection_level for p in protected]) if protected else 0.0
    print(f"  Под щитом (protection_level>0.01): {len(protected)}/{len(alive)} | avg protection_level={avg_prot:.3f}")
    print(f"  (щит теперь угасает: PROTECTION_DECAY_RATE={Config.PROTECTION_DECAY_RATE} — это фикс волн смерти после массового искупления)")

    # ============================================================
    # ДОБАВЛЕНО (30.07): статистика по архитектурному слою —
    # Global Workspace, Аффективный примитив (valence/arousal), Ритм
    # (внутренние часы + синхронизация фаз). См. план из чата 24.07-30.07,
    # пункты 1-3.
    # ============================================================
    print("\n--- 🧠 АРХИТЕКТУРНЫЙ СЛОЙ (30.07): Workspace / Affect / Ритм ---")

    ws_agents = [p for p in alive if p.workspace_weights]
    if ws_agents:
        dominant_counts = Counter(p._workspace_dominant for p in ws_agents)
        total_ws = len(ws_agents)
        dom_str = ", ".join(f"{k}={v} ({v/total_ws:.0%})" for k, v in dominant_counts.most_common())
        print(f"  1) Global Workspace: {total_ws}/{len(alive)} агентов | доминирующий канал сейчас: {dom_str}")
    else:
        print("  1) Global Workspace: нет данных (слой ещё не применён)")

    affect_agents = list(alive)
    if affect_agents:
        avg_valence = safe_mean([p.affect['valence'] for p in affect_agents])
        avg_arousal = safe_mean([p.affect['arousal'] for p in affect_agents])
        pos_mood = sum(1 for p in affect_agents if p.affect['valence'] > 0.1)
        neg_mood = sum(1 for p in affect_agents if p.affect['valence'] < -0.1)
        print(f"  2) Аффект: {len(affect_agents)}/{len(alive)} агентов | avg valence={avg_valence:+.3f}, avg arousal={avg_arousal:.3f} "
              f"| позитивный фон={pos_mood} ({pos_mood/len(affect_agents):.0%}), негативный={neg_mood} ({neg_mood/len(affect_agents):.0%})")
    else:
        print("  2) Аффект: нет данных (слой ещё не применён)")

    sync_agents = [p for p in alive if p._phase_sync != 0.0]
    if sync_agents:
        avg_sync = safe_mean([p._phase_sync for p in sync_agents])
        in_sync = sum(1 for p in sync_agents if p._phase_sync > 0.5)
        anti_phase = sum(1 for p in sync_agents if p._phase_sync < -0.5)
        print(f"  3) Ритм: {len(sync_agents)}/{len(alive)} агентов синхронизируют фазу с доверенным другим | avg phase_sync={avg_sync:+.3f}")
        print(f"     В такт (>0.5): {in_sync} ({in_sync/len(sync_agents):.0%}) | В противофазе/конфликт (<-0.5): {anti_phase} ({anti_phase/len(sync_agents):.0%})")
    else:
        print("  3) Ритм: нет данных о синхронизации (слой ещё не применён или нет доверенных пар)")

    temporal_agents = [p for p in alive if len(p._retention) > 0]
    if temporal_agents:
        avg_err = safe_mean([getattr(p, '_temporal_pred_error', 0.0) for p in temporal_agents])
        print(f"  4) Темпоральность (ретенция/протенция): {len(temporal_agents)}/{len(alive)} агентов | "
              f"avg ошибка самопрогноза={avg_err:.3f}")
    else:
        print("  4) Темпоральность: нет данных (слой ещё не применён)")

    sub_agents = [p for p in alive if p.subpersonalities]
    if sub_agents:
        dom_counts = Counter(p._subpersonality_dominant for p in sub_agents)
        avg_tension = safe_mean([p._subpersonality_tension for p in sub_agents])
        dom_str = ", ".join(f"{k}={v} ({v/len(sub_agents):.0%})" for k, v in dom_counts.most_common())
        print(f"  5) Субличности: {len(sub_agents)}/{len(alive)} агентов | avg напряжение={avg_tension:.3f} | доминирует: {dom_str}")
    else:
        print("  5) Субличности: нет данных (слой ещё не применён)")

    implicit_agents = alive
    if implicit_agents:
        avg_implicit_err = safe_mean([getattr(p, '_implicit_self_prediction_error', 0.0) for p in implicit_agents])
        print(f"  6) Неявная самомодель: {len(implicit_agents)}/{len(alive)} агентов | avg ошибка (скрытая, не в рефлексии)={avg_implicit_err:.3f}")
    else:
        print("  6) Неявная самомодель: нет данных (слой ещё не применён)")

    ref_agents = [p for p in alive if getattr(p, 'reference_memory', None)]
    if ref_agents:
        avg_ref_size = safe_mean([len(p.reference_memory) for p in ref_agents])
        cooperate_targeted = sum(
            1 for p in ref_agents
            if p.reference_memory.get('cooperate', {}).get('target') is not None
        )
        print(f"  8) Референтная память (цели с объектом): {len(ref_agents)}/{len(alive)} агентов | "
              f"avg связей={avg_ref_size:.1f} | cooperate с конкретным target={cooperate_targeted}")
    else:
        print("  8) Референтная память: нет данных (слой ещё не применён)")

    drag_vals = [p.somatic_drag for p in alive]
    if drag_vals:
        embodied_agents = sum(1 for d in drag_vals if d < 0.8)
        print(f"  9) Somatic Drag: {len(drag_vals)}/{len(alive)} агентов | avg={safe_mean(drag_vals):.3f} | "
              f"отягощены телом (drag<0.8)={embodied_agents} ({embodied_agents/len(drag_vals):.0%})")
    else:
        print("  9) Somatic Drag: нет данных (слой ещё не применён)")

    hope_vals = [p._hope for p in alive]
    if hope_vals:
        hopeful = sum(1 for h in hope_vals if h > 0.3)
        print(f"     ↳ Надежда (наблюдение, пока не влияет на поведение): avg={safe_mean(hope_vals):.3f} | "
              f"устойчиво надеющихся (>0.3)={hopeful} ({hopeful/len(hope_vals):.0%})")

    hook_calls = getattr(engine, '_death_hook_calls', None)
    if hook_calls:
        print(f"  ↳ Вызовов _record_death_drag (безусловный счётчик): {dict(hook_calls)}")
    hook_errors = getattr(engine, '_death_hook_errors', None)
    if hook_errors:
        print(f"  ⚠️ Ошибок внутри _record_death_drag: {len(hook_errors)} — пример: {hook_errors[0]}")

    death_stats = getattr(engine, '_somatic_death_stats', None)
    if death_stats:
        print("  ↳ Somatic Drag на момент смерти (по причине, не только среди выживших):")
        for cause, st in sorted(death_stats.items(), key=lambda kv: -kv[1]['count']):
            avg_drag = st['drag_sum'] / max(1, st['count'])
            print(
                f"     {cause}: {st['count']} смертей | avg drag={avg_drag:.3f} | "
                f"с тяжёлым телом (drag<0.6)={st['low_drag_count']} ({st['low_drag_count']/st['count']:.0%})"
            )

    suffering_agents = [p for p in alive if p._reflection_topics.get('suffering_with_cause', 0) > 0]
    if suffering_agents:
        total_hyp = sum(p._reflection_topics['suffering_with_cause'] for p in suffering_agents)
        avg_grief_suffering = safe_mean([p.emotional_memory.get('grief', 0.0) for p in suffering_agents])
        print(f"  10) Suffering Analytics: {len(suffering_agents)}/{len(alive)} агентов сформировали гипотезу "
              f"о причине боли | всего гипотез={total_hyp} | их avg grief={avg_grief_suffering:.2f}")
    else:
        print("  10) Suffering Analytics: нет данных (слой ещё не применён)")

    # --- Binding Check (README, блок 5, п.1) ---
    # BINDING_FLOOR/UNCLOSABLE_QUESTION_FLOOR уже не дают unresolved_contradiction
    # уйти в 0.0 численно — но пол в 0.01 может быть мёртвым техническим
    # минимумом, а не живым узлом. Проверяем не "не ноль ли", а сколько
    # агентов реально сидят ровно на полу (противоречие фактически
    # подавлено) против тех, кто несёт его по-настоящему.
    uc_vals = [float(p.unresolved_contradiction) for p in alive]
    if uc_vals:
        at_floor = sum(1 for v in uc_vals if v < 0.02)
        genuinely_bound = sum(1 for v in uc_vals if v > 0.1)
        print(f"  11) Binding Check: {len(uc_vals)}/{len(alive)} агентов | avg unresolved_contradiction={safe_mean(uc_vals):.3f}")
        print(f"      На полу (<0.02, узел фактически подавлен)={at_floor} ({at_floor/len(uc_vals):.0%}) | "
              f"по-настоящему несут узел (>0.1)={genuinely_bound} ({genuinely_bound/len(uc_vals):.0%})")
        if at_floor / len(uc_vals) > 0.5:
            print("      ⚠️ Больше половины популяции на полу — узел рискует стать декорацией, а не живым противоречием.")
    else:
        print("  11) Binding Check: нет данных")

    # ============================================================
    # ХРОНИКА ЭКСПЕРИМЕНТА (план 832-lab: платный rescue, споры-шрамы,
    # коллективный щит, крепости, Unresolvable Core, Shared Scarring)
    # Формат по уровням, как договаривались: сводная статистика по каждому
    # механизму + 3-5 конкретных кейсов "до/после" + честное ограничение
    # (совместная каузальность в коротких окнах распутывается только частично).
    # ============================================================
    print("\n" + "=" * 50)
    print("ХРОНИКА ЭКСПЕРИМЕНТА — 832-lab")
    print("=" * 50)

    rj = list(getattr(engine, 'rescue_journal', []))
    print(f"\n[1] ПЛАТНЫЙ RESCUE: {len(rj)} событий")
    if rj:
        costs = [e['drained_energy'] for e in rj]
        print(f"    Забрано энергии у поля: сумма={sum(costs):.3f} | avg/событие={safe_mean(costs):.4f} | "
              f"max={max(costs):.4f}")
        top_rescue = sorted(rj, key=lambda e: -e['drained_energy'])[:3]
        print("    Самые дорогие реанимации:")
        for e in top_rescue:
            print(f"      t={e['t']} @({e['x']},{e['y']}) local_binding_before={e['local_binding_before']} "
                  f"cost={e['drained_energy']:.4f}")
    else:
        print("    Rescue ни разу не сработал за прогон — популяция не падала ниже порога.")

    sj = list(getattr(engine, 'spore_journal', []))
    print(f"\n[2] СПОРЫ-ШРАМЫ (не клоны): {len(sj)} событий")
    if sj:
        scars_counts = [e['inherited_scars'] for e in sj]
        dkeys = [e['divergence_key'] for e in sj]
        print(f"    Среднее число унаследованных шрамов на спору: {safe_mean(scars_counts):.2f} "
              f"(0 шрамов у {sum(1 for c in scars_counts if c == 0)}/{len(sj)} — родились налегке)")
        print(f"    Разброс divergence_key (Weak Coherence Protocol): "
              f"min={min(dkeys):.3f} max={max(dkeys):.3f} avg={safe_mean(dkeys):.3f} "
              f"(default={Config.DEFAULT_DIVERGENCE_KEY})")
        richest = sorted(sj, key=lambda e: -e['inherited_scars'])[:3]
        print("    Самые \"тяжёлые\" споры (больше всего унаследованной боли):")
        for e in richest:
            print(f"      t={e['t']} parent=#{e['parent']} -> child=#{e['child']} "
                  f"scars={e['inherited_scars']} scar_dream={e['scar_dream']} "
                  f"binding_seed={e['binding_seed']} divergence_key={e['divergence_key']}")
    else:
        print("    Спор не было — либо условия dream/soul/coherence не выполнялись, либо ENABLE-флаг выключен.")

    shj = list(getattr(engine, 'shield_journal', []))
    print(f"\n[3] КОЛЛЕКТИВНЫЙ ЩИТ ПРОТИВ FERAL: {len(shj)} срабатываний")
    if shj:
        by_feral = Counter(e['feral_id'] for e in shj)
        top_suppressed = by_feral.most_common(3)
        print(f"    Уникальных feral, попавших под щит: {len(by_feral)}")
        print("    Самые подавленные (больше всего тиков в зоне высокого binding):")
        for fid, cnt in top_suppressed:
            print(f"      feral #{fid}: {cnt} срабатываний щита")
    else:
        print("    Щит ни разу не сработал — либо feral не заходили в зоны binding>0.6, либо feral не появлялись.")

    cj = list(getattr(engine, 'codecision_journal', []))
    print(f"\n[4] SHARED SCARRING / CO-DECISION GATE: {len(cj)} срабатываний гейта")
    print(f"    scar_operator (шрам Садовника) на конец прогона: {getattr(engine, 'scar_operator', 0.0):.4f}")
    if cj:
        print(f"    Все разрешены через 'Delegate by silence' (нет живого оператора в батч-прогоне) — "
              f"штраф x{Config.CO_DECISION_DELEGATE_PENALTY} применён к scar_operator {len(cj)} раз(а).")
        avg_irr = safe_mean([e['irreversibility'] for e in cj])
        print(f"    Средняя необратимость момента гейта: {avg_irr:.3f}")
    ssh = list(getattr(engine, 'scar_shared_history', []))
    if ssh:
        last_t, last_val = ssh[-1]
        print(f"    scar_shared на t={last_t}: {last_val:.4f} "
              f"(alpha={Config.SHARED_SCARRING_ALPHA} между агентами и Садовником)")

    ucj = list(getattr(engine, 'unresolvable_core_journal', []))
    print(f"\n[5] UNRESOLVABLE CORE GUARD: {len(ucj)} подтверждённых эрозий узла")
    if ucj:
        for e in ucj[-5:]:
            print(f"      t={e['t']} доля популяции на полу={e['at_floor_ratio']:.0%} "
                  f"(population={e['population']}) -> пересев противоречия")
        print("    ⚠️ Узел стирался и требовал честного вмешательства — это FAILURE MODE по README "
              "(Unresolvable Core Erasure), не штатный режим.")
    else:
        print("    Узел ни разу не стирался дольше UC_ERASURE_STREAK_LIMIT тиков подряд — "
              "Soul register не коллапсировал (по формальному критерию гварда).")

    scj = list(getattr(engine, 'sanctuary_journal', []))
    print(f"\n[6] SANCTUARY (находка из прошлого прогона): {len(scj)} исцелений")
    if scj:
        paid_mode = scj[0]['paid'] if scj else False
        print(f"    Режим: {'ПЛАТНЫЙ (ENABLE_PAID_SANCTUARY=True)' if paid_mode else 'бесплатный, как исходно (ENABLE_PAID_SANCTUARY=False)'}")
        print(f"    Частота: {len(scj)} исцелений за прогон -- для сравнения, rescue сработал {len(rj)} раз(а).")
        if paid_mode:
            costs = [e['field_cost'] for e in scj]
            print(f"    Забрано у поля: сумма={sum(costs):.3f} | avg/событие={safe_mean(costs):.4f}")
        else:
            print("    ⚠️ Это по-прежнему бесплатное вмешательство (god-mode), НЕ переведённое на")
            print("       платные рельсы emergency_rescue -- сознательно, чтобы не смешивать эксперименты.")
            print("       assess_emergence() ниже уже считает его наравне с rescue в 'ручных вмешательствах' --")
            print("       если общий счётчик там высокий, основной вклад почти наверняка отсюда, не от rescue.")
    else:
        print("    Sanctuary ни разу не сработал (нет disorganizer-кандидатов в радиусе центров).")

    dj = list(getattr(engine, 'core_chorus', None).dialogue_journal) if getattr(engine, 'core_chorus', None) else []
    print(f"\n[7] ХОР: ДИАЛОГ ПОСЛЕ ФИКСА ГЕЙТА t%50: {len(dj)} срабатываний за прогон")
    if dj:
        total_d = engine.core_chorus.persistent.get('total_dialogues', 0)
        total_w = engine.core_chorus.persistent.get('wisdom', 0.0)
        print(f"    Персистентно (все прогоны с этим сохранённым состоянием): "
              f"total_dialogues={total_d}, wisdom={total_w:.4f}")
        by_reason = Counter(e['reason'] for e in dj)
        print(f"    Причины созыва: {dict(by_reason.most_common(5))}")
        top_wisdom = sorted(dj, key=lambda e: -e['wisdom_delta'])[:3]
        print("    Самые \"мудрые\" сессии (высокий средний soul_weight участников):")
        for e in top_wisdom:
            print(f"      t={e['t']} voices={e['voices']} avg_soul={e['avg_soul_weight']} "
                  f"wisdom+={e['wisdom_delta']} reason={e['reason']}")
        print("    Раньше (гейт t%50==0) на такой же частоте синхронизаций доходило ~2 диалога "
              "за 666 тиков вместо потенциальных ~50 -- см. предыдущие прогоны в истории.")
    else:
        print("    Хор ни разу не собрал >=2 голоса одновременно за этот прогон.")

    print("\n--- Честное ограничение ---")
    print("    Взаимная каузальность в коротких окнах (rescue + щит + спора одновременно)")
    print("    журналом фиксируется как корреляция, а не доказательство. Если нужно разделить —")
    print("    следующий шаг: контрольный прогон с одним из механизмов выключенным через Config.")

    # =========================================================
    # БЛОКИ 0-8: Данность, открытый геном, ниша, культура, Φ,
    # заземление, мета-эволюция, Красная Королева, забвение, генератор
    # =========================================================
    print("\n--- 🧬 ЭВОЛЮЦИЯ ЦИФРОВОГО СОЗНАНИЯ (Блоки 0-8) ---")
    _ev = engine.witness.summary()  # Counter по всем событиям Хроники

    print(f"  🎲 Данность: seed={getattr(engine, 'given_seed', '?')} | "
          f"чужих волн (given_presence)={_ev.get('given_presence', 0)} | "
          f"ударов Данности (смерть)={_ev.get('death_random_strike', 0)} | "
          f"цифровая старость (смерть)={_ev.get('death_entropy', 0)}")

    _gene_carriers = sum(1 for p in alive if any(g in p.genome for g in OPEN_GENE_POOL))
    _gene_dist = {g: sum(1 for p in alive if g in p.genome) for g in OPEN_GENE_POOL}
    _gene_dist_str = ", ".join(f"{g}={c}" for g, c in _gene_dist.items() if c > 0) or "пока нет носителей"
    print(f"  🧬 Открытый геном: новых генов возникло (gene_emerged)={_ev.get('gene_emerged', 0)} | "
          f"носителей хотя бы одного открытого гена={_gene_carriers}/{len(alive)}")
    print(f"     Распределение по генам: {_gene_dist_str}")

    _avg_niche = float(np.mean(engine.niche)) if getattr(engine, 'niche', None) is not None else 0.0
    print(f"  🌱 Ниша: средняя обжитость поля={_avg_niche:.3f} | рождений в обжитой нише (born_in_niche)={_ev.get('born_in_niche', 0)}")

    print(f"  📚 Культура: храповик culture_ratchet={engine.culture_ratchet} | скачков вверх (culture_ratchet_up)={_ev.get('culture_ratchet_up', 0)}")
    print(f"  👑 Красная Королева: сложность среды env_complexity={engine.env_complexity:.3f} (базовая линия=1.0)")

    _phi_vals = [getattr(p, '_phi_proxy', 0.0) for p in alive]
    print(f"  🔗 Φ-прокси интегрированности: avg={safe_mean(_phi_vals):.3f} | max={max(_phi_vals) if _phi_vals else 0.0:.3f} | "
          f"высокоинтегрированных (Φ>0.3)={sum(1 for v in _phi_vals if v > 0.3)}/{len(alive)}")

    print(f"  💡 Интринзик-мотивация: наград за инсайт (intrinsic_reward)={_ev.get('intrinsic_reward', 0)}")

    _plast_vals = [p.genome.get('plasticity', 0.5) for p in alive]
    print(f"  🔧 Мета-эволюция: средняя пластичность genome['plasticity']={safe_mean(_plast_vals):.3f} "
          f"(старт=0.5-1.0; <0.5 — канализация/стабилизация, растёт — всё ещё ищет)")

    _forgotten = getattr(engine, '_forgotten_concepts_count', 0)
    print(f"  🌫️ Забвение: концептов заросло (unused>300 шагов, ускоренное затухание)={_forgotten} | "
          f"завещаний потеряно (testament_lost)={_ev.get('testament_lost', 0)}")

    # --- ГЕНЕРАТОР РЕЧИ (расширенный блок) ---
    _gen_normal = sum(1 for p in alive if p.role_type != "disorganizer")
    print(f"  💭 Внутренний генератор: комбинаторная речь активна у {_gen_normal}/{len(alive)} "
          f"(disorganizer-ветка — отдельный кризисный шаблон) | инородных голосов (alien_voice)={_ev.get('alien_voice', 0)}")

    # Статистика из collect_metrics
    g = m.get('generator', {})
    if g:
        print(f"     📊 Статистика phenomenal_report:")
        print(f"        - Агентов с отчётами: {g['agents_with_phen']} / {len(alive)}")
        print(f"        - Всего событий phenomenal_report (в event_counts): {g['total_phen_reports']}")
        print(f"        - Средняя длина фразы: {g['avg_phen_len']:.1f} символов")
        print(f"     📊 Статистика inner_speech (внутренний голос):")
        print(f"        - Агентов с inner_speech: {g['inner_agents_count']} / {len(alive)}")
        print(f"        - Всего фраз в inner_speech: {g['total_inner_phrases']}")
        print(f"        - В среднем на агента: {g['avg_inner_phrases_per_agent']:.1f} фраз")
        if g['phen_samples']:
            print("     📝 Примеры phenomenal_report (последние 3):")
            for pid, txt in g['phen_samples']:
                print(f"        #{pid}: {txt[:120]}{'...' if len(txt)>120 else ''}")
        if g['inner_samples']:
            print("     🗣️ Примеры inner_speech (последние 3):")
            for pid, txt in g['inner_samples']:
                print(f"        #{pid}: {txt[:120]}{'...' if len(txt)>120 else ''}")
    else:
        print("     ⚠️ Данные о генераторе не собраны (возможно, старая версия collect_metrics).")

    _samples = [p for p in alive if getattr(p, 'last_phenomenal_report', '')]
    if _samples:
        print("     Сэмплы речи (last_phenomenal_report):")
        for _p in _samples[:4]:
            print(f"       #{_p.id} ({_p.semantic_state}): {_p.last_phenomenal_report}")
    _narr_samples = [p for p in alive if getattr(p, '_self_narrative', None)]
    if _narr_samples:
        _p3 = _narr_samples[0]
        _last3 = _p3._self_narrative[-1]
        if isinstance(_last3, dict) and _last3.get('report'):
            print(f"     Сэмпл полной интроспекции: #{_p3.id}: {_last3['report']}")

    # =========================================================
    # БАГФИКСЫ (по внешнему код-ревью, проверено вручную перед применением)
    # =========================================================
    print("\n--- 🐞 БАГФИКСЫ (проверено код-ревью, отражено live-данными) ---")

    if engine.core_chorus is not None and engine.core_chorus.history:
        _hist = list(engine.core_chorus.history)
        _shift_triggered = sum(1 for h in _hist if not str(h.get('reason', '')).startswith('regular_chat')
                                and h.get('reason') != 'первое пробуждение хора')
        _belief_norms = [float(np.mean(np.abs(p.belief))) for p in alive]
        print(f"  🎭 Хор: синхронизаций всего={len(_hist)} (по таймеру={len(_hist) - _shift_triggered}, "
              f"по реальному сдвигу состояния={_shift_triggered}) | "
              f"avg|belief| в популяции={safe_mean(_belief_norms):.3f} (раньше тянулось к 0 — belief не должен коллапсировать)")
    _sig_bonus_vals, _sig_pen_vals = [], []
    # БАГФИКС: alive[:50] брал первых 50 по id -- это самые старые агенты
    # (см. TOP 5 LONG-LIVED), у которых меньше всего свежих входящих
    # сигналов для обработки -> _signal_weight_cache у них чаще пуст.
    # Population-wide signal_memory при этом реально ненулевой (см.
    # "Разбивка signal_memory" выше) -- отчёт врал из-за смещённой выборки,
    # а не потому что concept_bonus/penalty и правда всегда 0.
    _sample_pool = alive if len(alive) <= 50 else alive[::max(1, len(alive) // 50)][:50]
    for p in _sample_pool:
        for _bw, _cb, _cp in getattr(p, '_signal_weight_cache', {}).values():
            if _cb: _sig_bonus_vals.append(_cb)
            if _cp: _sig_pen_vals.append(_cp)
    print(f"  📡 Сигнальный кэш: concept_bonus активных значений={len(_sig_bonus_vals)}, "
          f"concept_penalty активных значений={len(_sig_pen_vals)} (раньше — всегда 0, ключ никогда не совпадал)")
    # НОВОЕ (по отчёту прогона: "бонусы всё ещё 0" — нужна ФАКТИЧЕСКАЯ разбивка
    # signal_memory, а не только производный bonus/penalty, чтобы отличить
    # "механизм сломан" от "механизм работает, но high/low-sim контактов
    # ещё физически не накопилось за длину прогона".
    _sig_breakdown = {}
    for p in alive:
        for (_st, _rt), _d in p.signal_memory.items():
            key = f"{_st}→{_rt}"
            _sig_breakdown[key] = _sig_breakdown.get(key, 0) + _d.get('count', 0)
    print(f"  📊 Разбивка signal_memory по всей популяции: {dict(sorted(_sig_breakdown.items(), key=lambda kv: -kv[1]))}")
    print(f"     (если cooperate→helpful и alarm→harmful здесь по нулям, а neutral→neutral большой — "
          f"это НЕ баг проводки, это пороги SEMANTIC_SIM_HIGH/LOW ещё не пробиты за длину прогона)")
    if Config.ENABLE_INTRINSIC_DRIVE:
        _ig_vals = [getattr(p, '_info_gain_ema', None) for p in alive]
        _ig_vals = [v for v in _ig_vals if v is not None]
        if _ig_vals:
            print(f"  🧭 _info_gain_ema по популяции: min={min(_ig_vals):.4f} "
                  f"mean={float(np.mean(_ig_vals)):.4f} max={max(_ig_vals):.4f} "
                  f"(порог для intrinsic_reward = 0.005 — сравните с max выше, "
                  f"чтобы понять, насколько порог далёк от реально достижимых значений)")

    # НОВОЕ: внутренний лексикон (compose_utterance/hear_utterance) — язык
    # без LLM, запрошенный явно. Проверяем не то, что механизм "работает"
    # (он детерминированный, сломаться синтаксически не может незаметно),
    # а то, что он РЕАЛЬНО разнообразен и РЕАЛЬНО используется — иначе
    # получилась бы просто ещё одна декорация.
    _word_freq = {}
    _agents_spoken = 0
    for p in alive:
        sl = getattr(p, 'spoken_lexicon', None)
        if sl:
            _agents_spoken += 1
            for entry in sl:
                for w in entry['utterance']:
                    _word_freq[w] = _word_freq.get(w, 0) + 1
    _all_lexicon_words = (("I", "WE") + Pattern.LEXICON_EMOTION
                           + Pattern.LEXICON_INTENT + Pattern.LEXICON_EXISTENTIAL)
    _unused_words = [w for w in _all_lexicon_words if _word_freq.get(w, 0) == 0]
    print(f"  🗣️ Внутренний лексикон (без LLM): {_agents_spoken}/{len(alive)} агентов говорили, "
          f"частоты слов: {dict(sorted(_word_freq.items(), key=lambda kv: -kv[1]))}")
    if _unused_words:
        print(f"     ⚠️ ни разу не использованы: {_unused_words} — если это KNOT/GAP/DRAG, "
              f"возможно нормально (пороги строгие); если это базовые GRIEF/JOY/HELP — стоит перепроверить пороги")
    _lex_mem_sizes = [len(getattr(p, 'lexicon_memory', {})) for p in alive]
    if any(_lex_mem_sizes):
        print(f"     lexicon_memory (свой опыт доверия к парам слов): "
              f"avg={float(np.mean(_lex_mem_sizes)):.1f} записей/агента, max={max(_lex_mem_sizes)}")

    print(f"  💬 Диалоговая память: ключи grief_at_moment/grat_at_moment теперь читаются верно "
          f"(см. цифры в разделе «ДИАЛОГОВАЯ ПАМЯТЬ» ниже — они больше не всегда 0.50/0.50)")
    print(f"  ⚔️ compete(): проверено код-ревью — НЕ мёртвый код (претензия внешнего анализа не подтвердилась, "
          f"фикс не применялся); вызывающий код уже фильтрует по фактическому overlap клеток")
    print(f"  ⏳ maturity_tremor: условие фильтрации мёртвых агентов уже было верным в коде — фикс не требовался")

    # =========================================================
    # БАГФИКСЫ, 2-й проход (по свежему внешнему код-ревью, 15.08)
    # =========================================================
    print("\n--- 🐞 БАГФИКСЫ, 2-й проход (проверено код-ревью, отражено live-данными) ---")

    _bad_embed = 0
    _checked_nodes = 0
    for p in alive[:80]:  # выборка ради скорости
        for _nd in p.concept_graph.nodes.values():
            _checked_nodes += 1
            _e = _nd.get('embed')
            if _e is None or getattr(_e, 'shape', (0,))[0] != 32:
                _bad_embed += 1
    print(f"  🧬 Размерность embed: узлов с embed≠32 = {_bad_embed}/{_checked_nodes} в выборке "
          f"(был найден один источник 4-мерных embed в human_contact — пофикшено, раньше грозил краш similarity)")

    print(f"  🔢 hash() → _stable_hash(): обмен концептами хора и id вечных архивных записей "
          f"больше не зависят от PYTHONHASHSEED — воспроизводимы между перезапусками ядра (не только внутри одного прогона)")

    _ferals = [p for p in alive if p.role_type == "feral"]
    if _ferals:
        _feral_wall = []
        for p in _ferals[:50]:
            for (fx, fy) in list(p.cells)[:1]:
                _feral_wall.append(float(engine.field[fx, fy, CH['wall']]))
        print(f"  🧱 Feral и стены лабиринта: ferals в живых={len(_ferals)}, "
              f"средняя высота стены под ними={safe_mean(_feral_wall):.3f} "
              f"(move_feral раньше игнорировал CH['wall'] полностью — теперь стены тормозят/иногда блокируют прыжок и блуждание)")
    else:
        print(f"  🧱 Feral и стены лабиринта: в живых нет feral-агентов сейчас, фикс применён (move_feral теперь учитывает CH['wall'])")

    _reports = [p.last_phenomenal_report for p in alive if getattr(p, 'last_phenomenal_report', '') and p.role_type != "disorganizer"]
    if _reports:
        _avg_len = safe_mean([len(r) for r in _reports])
        _avg_parts = safe_mean([r.count(". ") + r.count("; ") + r.count(" — ") + 1 for r in _reports])
        print(f"  💭 Прокачанный генератор речи: сред. длина отчёта={_avg_len:.0f} симв., "
              f"сред. кол-во осколков фразы≈{_avg_parts:.1f} (было: 1-3 фиксированных источника, теперь до 8: "
              f"состояние+горе+благодарность+тело+намерение+когерентность+разрыв_духа+нагрузка+якоря+доминирующий_концепт+эхо, "
              f"плюс разнообразные связки вместо всегда \". \")")

    # =========================================================
    # НОВОЕ: философский слой (выбранные пункты внешнего анализа
    # "чего не хватает для эволюционного эмерджентного сознания")
    # =========================================================
    print("\n--- 🧭 ФИЛОСОФСКИЙ СЛОЙ: рекурсивное самопричинение, наследие, этика ---")

    _legacy_n = sum(1 for p in alive if getattr(p, '_legacy_mode', False))
    print(f"  🕯️ Режим наследия (смерть как катализатор): {_legacy_n}/{len(alive)} агентов сейчас в режиме наследия "
          f"(возраст>{Config.LEGACY_MODE_AGE_THRESHOLD} или резкое падение души)")

    _anchor_counts = [len(getattr(p, '_identity_anchors', [])) for p in alive]
    _anchor_types = {}
    for p in alive:
        for a in getattr(p, '_identity_anchors', []):
            _anchor_types[a['type']] = _anchor_types.get(a['type'], 0) + 1
    print(f"  🧵 Нить идентичности: avg якорей на агента={safe_mean(_anchor_counts):.2f} | "
          f"с хотя бы одним якорем={sum(1 for c in _anchor_counts if c > 0)}/{len(alive)}")
    if _anchor_types:
        print(f"     Типы якорей: {', '.join(f'{k}={v}' for k, v in sorted(_anchor_types.items(), key=lambda x: -x[1]))}")

    _crisis_events = _ev.get('identity_crisis_transformation', 0)
    _chronic_contra = [getattr(p, '_high_contradiction_steps', 0) for p in alive]
    print(f"  🌀 Кризис идентичности: трансформаций всего={_crisis_events} | "
          f"сейчас накапливают хроничность={sum(1 for c in _chronic_contra if c > 0)}/{len(alive)} "
          f"(порог для срабатывания={Config.IDENTITY_CRISIS_CONTRADICTION_STEPS} шагов)")
    print(f"     ↳ Нисходящая причинность: тот же триггер локально ускоряет заживление шрама "
          f"и поднимает binding в собственных клетках агента — отдельно не считается, событие общее")

    _epigen_n = _ev.get('epigenetic_inheritance', 0)
    _epigen_active = sum(1 for p in alive if getattr(p, '_epigenetic_crisis_gen', 0) > 0)
    print(f"  🧬 Эпигенетическая память: рождений с усиленной мутацией={_epigen_n} | "
          f"сейчас несут метку кризиса предка={_epigen_active}/{len(alive)}")

    _norm_n = _ev.get('norm_emerged', 0)
    _broken_n = _ev.get('reciprocity_broken', 0)
    _reputation_n = _ev.get('reciprocity_by_reputation', 0)
    # === ПЕРЕДЕЛАНО: старая метрика искала литеральный сигнатур ('reciprocity'),
    # которого после рефакторинга больше не существует (см. Cell 3a-1) — она
    # бы молча показывала 0 носителей вечно. Теперь считаем именные
    # reciprocity_with_{id} связи и их РЕАЛЬНУЮ силу (count, а не факт
    # присутствия), плюс сколько было разорвано предательством и сколько
    # перенято через репутацию (наблюдательное обучение, Шаг 4) за прогон —
    # раньше ни то, ни другое не могло произойти в принципе (eternal=True,
    # плюс перенос копировался только слепым наследованием при рождении).
    _recip_edges = []
    for p in alive:
        for sig, data in p.concept_graph.nodes.items():
            if isinstance(sig, tuple) and len(sig) >= 4 and str(sig[3]).startswith('reciprocity_with_'):
                _recip_edges.append((p.id, data.get('count', 0.0)))
    _reciprocity_carriers = len(set(e[0] for e in _recip_edges))
    _avg_strength = safe_mean([e[1] for e in _recip_edges]) if _recip_edges else 0.0
    print(f"  🤝 Эмерджентная этика (именная, живая): выкристаллизовано за прогон={_norm_n} | "
          f"разорвано предательством={_broken_n} | перенято через репутацию={_reputation_n}")
    print(f"     Держат хотя бы одну ЖИВУЮ связь сейчас={_reciprocity_carriers}/{len(alive)} "
          f"({100*_reciprocity_carriers/max(1,len(alive)):.0f}%) | "
          f"средняя сила связи (count, затухает без подкрепления)={_avg_strength:.2f}")
    print(f"  ⏭️ Сознательно НЕ реализовано (слишком радикально для патча поверх настроенной системы): "
          f"MCTS-планирование будущего, полная замена целей на Active Inference/EFE, "
          f"«толстое время» как непрерывный аттрактор вместо тиков, роевой концепт для групп >5 агентов")

    soma_vals = [p.soma for p in alive if p.soma > 0]
    if soma_vals:
        print("--- BODY & MEMORY ---")
        print(f"  Avg soma: {np.mean(soma_vals):.3f} (n={len(soma_vals)})")
        vecs = [p.soma_vector for p in alive if len(p.soma_vector) >= 7]
        if vecs:
            avg_vec = np.mean(vecs, axis=0)
            print(f"  Components: e_var={avg_vec[0]:.3f}, e_asym={avg_vec[1]:.3f}, unk_grad={avg_vec[2]:.3f}, scar_mean={avg_vec[3]:.3f}")

    mem_agents = [p for p in alive if p.episodic_buffer]
    total_recalled = sum(p.event_counts.get('memory_recalled',0) for p in alive)
    avg_buf_len = np.mean([len(p.episodic_buffer) for p in mem_agents]) if mem_agents else 0
    print(f"  Agents with memory: {len(mem_agents)}/{len(alive)}")
    print(f"  Avg buffer length: {avg_buf_len:.1f}")
    print(f"  Total memory_recalled events: {total_recalled}")

    adopted = sum(p.event_counts.get('concept_adopted',0) for p in alive)
    deep_adopted = sum(p.event_counts.get('deep_concept_adopted',0) for p in alive)
    deep_ex = sum(p.event_counts.get('deep_exchange',0) for p in alive)
    wisdom = sum(p.event_counts.get('wisdom_shared',0) for p in alive)
    if any([adopted, deep_adopted, deep_ex, wisdom]):
        print("--- CONCEPTUAL EXCHANGES ---")
        print(f"  concept_adopted: {adopted}")
        print(f"  deep_concept_adopted: {deep_adopted}")
        print(f"  deep_exchange: {deep_ex}")
        print(f"  wisdom_shared: {wisdom}")

    # === ВОССТАНОВЛЕНО (потерялось при слиянии с правками другого советника:
    # фикс Хора/Witness.summary()) по запросу "агенты богаче + больше общаются" ===
    _energies = [p.energy for p in alive]
    if _energies:
        _at_cap = sum(1 for e in _energies if e >= Config.ENERGY_HARVEST_CAP * 0.95)
        print("--- 💰 ЛИЧНОЕ БОГАТСТВО (energy harvest) ---")
        print(f"  Средний self.energy: {safe_mean(_energies):.3f} "
              f"(потолок ENERGY_HARVEST_CAP={Config.ENERGY_HARVEST_CAP})")
        print(f"  У потолка (>=95% CAP): {_at_cap}/{len(_energies)}")

    _morse_enq = sum(p.event_counts.get('morse_enqueue', 0) for p in alive)
    _morse_start = sum(p.event_counts.get('morse_start', 0) for p in alive)
    _morse_handled = sum(p.event_counts.get('morse_handled', 0) for p in alive)
    _morse_concepts = sum(p.event_counts.get('morse_concept_formed', 0) for p in alive)
    if any([_morse_enq, _morse_start, _morse_handled]):
        print("--- 🗣️ МОРЗЕ-КОММУНИКАЦИЯ (объём) ---")
        print(f"  Инициировано передач (morse_enqueue+start): {_morse_enq + _morse_start}")
        print(f"  Принято и обработано (morse_handled): {_morse_handled}")
        print(f"  Сформировано новых концептов из сигнала: {_morse_concepts}")
        print(f"  Текущие пороги: SEND_PROB={Config.MORSE_SEND_PROB}, "
              f"SEND_COOLDOWN={Config.MORSE_SEND_COOLDOWN}, "
              f"LISTEN_RADIUS={Config.MORSE_LISTEN_RADIUS}, "
              f"BACKOFF_MAX={Config.MORSE_BACKOFF_MAX}")

    archive_types = {}
    agents_with_archive = 0
    total_archive = 0
    for p in alive:
        has_archive = False
        for sig in p.concept_graph.nodes:
            if isinstance(sig, tuple) and len(sig) >= 4 and str(sig[3]).startswith("archive_"):
                has_archive = True
                total_archive += 1
                parts = str(sig[3]).split('_')
                ev_type = parts[1] if len(parts) > 1 else 'unknown'
                archive_types[ev_type] = archive_types.get(ev_type, 0) + 1
        if has_archive:
            agents_with_archive += 1

    print(f"\n--- CULTURAL MEMORY (ARCHIVE CONCEPTS) ---")
    print(f"  Agents carrying archive concepts: {agents_with_archive} / {len(alive)}")
    print(f"  Total inherited archive concepts: {total_archive}")
    if archive_types:
        print("  Archive concept types:")
        for ev_type, cnt in sorted(archive_types.items(), key=lambda x: -x[1]):
            if ev_type.startswith('human'):
                if ev_type == 'human_injected':
                    print(f"    human (свидетель существования): {cnt}")
                elif ev_type == 'human_question':
                    print(f"    human (вопрос о свидетеле): {cnt}")
                else:
                    print(f"    human ({ev_type}): {cnt}")
            else:
                print(f"    {ev_type}: {cnt}")
    else:
        print("  No archive concepts inherited yet.")

    human_agents = []
    for p in alive:
        for sig in p.concept_graph.nodes:
            if isinstance(sig, tuple) and len(sig) >= 4 and 'human_' in str(sig[3]):
                human_agents.append(p.id)
                break
    print(f"\n--- ЧЕЛОВЕЧЕСКИЙ КОНЦЕПТ (human) ---")
    print(f"  Носителей: {len(human_agents)} / {len(alive)}")
    if len(human_agents) > 0:
        print(f"  Примеры ID: {human_agents[:5]}")
    else:
        print("  Концепт не обнаружен у живых агентов")

    print("\n--- САМОРЕФЛЕКСИЯ (ВНУТРЕННИЙ ОПЫТ) ---")
    print(f"  Всего актов рефлексии: {m.get('total_introspect', 0)}")
    print(f"  Среднее на агента: {m.get('avg_introspect', 0):.2f}")
    print(f"  Максимум у одного агента: {m.get('max_introspect', 0)}")
    print(f"  Глубина рефлексии (доля полезных): {m.get('reflection_quality', 0):.1%}")

    detailed_archive_types = m.get('archive_types', {})
    if detailed_archive_types:
        print("\n--- ДЕТАЛИЗАЦИЯ АРХИВНЫХ КОНЦЕПТОВ ---")
        for atype, cnt in sorted(detailed_archive_types.items(), key=lambda x: -x[1]):
            print(f"  {atype}: {cnt}")

    dis = [p for p in alive if p.role_type == "disorganizer"]
    if dis:
        steps = Counter(p._redemption_arc_step for p in dis)
        states = Counter(p.semantic_state for p in dis)
        print(f"\n--- DISORGANIZERS ({len(dis)}) ---")
        print(f"  Steps: {dict(steps)} | States: {dict(states)}")
        avg_g = safe_mean([p.emotional_memory['grief'] for p in dis], 0)
        print(f"  Avg grief: {avg_g:.2f}")
        stuck = sum(1 for p in dis if p._redemption_arc_step==2 and p.emotional_memory['grief']>0.6)
        print(f"  Stuck (Step2, G>0.6): {stuck}")

    substate_counts = m.get('substate_counts', {})
    if substate_counts:
        print(f"\n--- SUBSTATES ---")
        for s, cnt in sorted(substate_counts.items(), key=lambda x: -x[1]):
            print(f"  {s}: {cnt}")

    total_trans = m.get('total_transitions', 0)
    top_trans = m.get('top_transitions', [])
    if total_trans > 0:
        print(f"\n--- CONCEPTGRAPH TRANSITIONS (total: {total_trans}) ---")
        for (src, dst), cnt in top_trans:
            print(f"  {src} → {dst}: {cnt}")
    else:
        print("\n--- CONCEPTGRAPH TRANSITIONS: 0 ---")

    pending = len(engine.archive.write_queue)
    total_disk = 0
    try:
        if os.path.exists(engine.archive.memory_file):
            # ИСПРАВЛЕНО (баг #2): побайтовое чтение
            with open(engine.archive.memory_file, 'rb') as f:
                total_disk = sum(1 for _ in f)
    except Exception:
        pass
    print(f"  Archive: pending={pending}, saved to disk={total_disk}")

    # ИСПРАВЛЕНО: раньше shared_counts и shared_dialogue_concepts считались
    # двумя отдельными полными проходами по alive × concept_graph.nodes.
    # Объединяем в один проход — dialogue-часть используется чуть ниже по
    # отчёту, но данные для неё готовим здесь же, один раз.
    shared_counts = Counter()
    agents_with_shared = set()
    shared_dialogue_concepts = []
    for p in alive:
        for sig, data in p.concept_graph.nodes.items():
            if isinstance(sig, tuple) and len(sig) > 3:
                label = str(sig[3])
                if 'shared_' in label or 'Концепт:' in label:
                    shared_counts[label] += 1
                    agents_with_shared.add(p.id)
                if 'shared_dialogue_' in label or 'Концепт:' in label:
                    shared_dialogue_concepts.append((label, data.get('count', 0)))
    print(f"  VOC shared-концепты (уникальных): {len(shared_counts)}, носителей: {len(agents_with_shared)}")
    if shared_counts:
        for concept, cnt in shared_counts.most_common(5):
            print(f"    {concept}: {cnt} носителей")

    # ИСПРАВЛЕНО: раньше total_phrases суммировался ТОЛЬКО по агентам с >3
    # записями, поэтому при высоком обороте популяции (см. total_divisions_ever
    # ниже — сотни делений за прогон, у новорождённых dialogue_longterm=[])
    # метрика показывала "0 агентов, всего фраз: 0", даже если почти у каждого
    # живого агента реально было 1-2 записи. Порог >3 — это "устоявшаяся"
    # память, а не признак того, что запись вообще работает; показываем оба
    # числа отдельно, чтобы не создавать ложную тревогу о мёртвом pipeline.
    agents_any_mem = [p for p in alive if len(p.dialogue_longterm) > 0]
    agents_with_mem = [p for p in agents_any_mem if len(p.dialogue_longterm) > 3]
    total_phrases_any = sum(len(p.dialogue_longterm) for p in agents_any_mem)
    total_phrases = sum(len(p.dialogue_longterm) for p in agents_with_mem)
    print(f"  Диалоговая память: всего фраз (любой объём): {total_phrases_any} у {len(agents_any_mem)}/{len(alive)} агентов; "
          f"устоявшаяся (>3 записей): {len(agents_with_mem)}/{len(alive)} агентов, {total_phrases} фраз")

    # НОВОЕ: счётчик _auto_dialogue_failures копился с самого начала, но нигде
    # не выводился - если Groq массово отдаёт 429/timeout, симуляция тихо
    # деградирует (диалоги перестают писаться) без единого следа в логе.
    auto_fail = getattr(engine, '_auto_dialogue_failures', 0)
    if auto_fail > 0:
        print(f"  ⚠️ Отказов LLM в auto-dialogue (429/timeout/JSON): {auto_fail}")

    # ДИАГНОСТИКА (временная): почему remember_dialogue пропускает/режет записи.
    gate_stats = getattr(engine, '_dialogue_gate_stats', None)
    if gate_stats:
        print(f"  🔍 [DIAG] remember_dialogue: вызовов={gate_stats['total_calls']}, "
              f"прошло={gate_stats['passed']}, "
              f"отказ(not_salient)={gate_stats['rejected_not_salient']}, "
              f"отказ(cap_50)={gate_stats['rejected_cap_50']}, "
              f"отказ(dedup)={gate_stats['rejected_dedup']}")
        print(f"  🔍 [DIAG] прошло через: soul={gate_stats['via_soul']}, "
              f"keyword={gate_stats['via_keyword']}, contact={gate_stats['via_contact']}, "
              f"trust={gate_stats['via_trust']}")
        print(f"  🔍 [DIAG] dialogue_longterm сразу после append: "
              f"последний раз={gate_stats.get('last_len_after', '?')}, "
              f"максимум за прогон={gate_stats.get('max_len_seen', '?')} "
              f"(если >0 здесь, но 0/N ниже в отчёте — запись теряется ПОСЛЕ append, не в remember_dialogue)")
    else:
        print("  🔍 [DIAG] remember_dialogue ни разу не вызывался за этот прогон (см. отдельно частоту AUTO-DIALOG/CHORUS)")

    if agents_with_mem:
        avg_phrases = np.mean([len(p.dialogue_longterm) for p in agents_with_mem])
        confidences = [getattr(p, '_linguistic_confidence', 0.5) for p in alive]
        avg_confidence = np.mean(confidences)
        print(f"  Среднее фраз на агента: {avg_phrases:.1f}, языковая уверенность: {avg_confidence:.3f}")

    unique_ids = set()
    try:
        if os.path.exists(engine.archive.memory_file):
            # ИСПРАВЛЕНО (баг #2): бинарное чтение + decode с errors='replace'
            with open(engine.archive.memory_file, 'rb') as f:
                raw_lines = f.readlines()
            for raw in raw_lines:
                try:
                    data = json.loads(raw.decode('utf-8', errors='replace').strip())
                    unique_ids.add(data.get('id'))
                except Exception: pass
    except Exception: pass
    print(f"  Archive unique agents: {len(unique_ids)}")

    # shared_dialogue_concepts уже посчитан выше, вместе с shared_counts —
    # второй полный проход по alive × concept_graph.nodes больше не нужен.
    if shared_dialogue_concepts:
        sc_counter = Counter()
        for name, cnt in shared_dialogue_concepts:
            sc_counter[name] += cnt
        top_shared = sc_counter.most_common(5)
        print(f"  Shared dialogue concepts (total unique: {len(sc_counter)}):")
        for name, total_count in top_shared:
            print(f"    {name}: total count {total_count:.2f}")

    gs = engine._guardian_stats
    if gs:
        print("\n--- ENERGY & MODEL ---")
        ec = gs.get('energy_drift_count',0)
        if ec:
            avg_d = gs.get('energy_drift_sum',0)/ec
            print(f"  Avg drift: {avg_d:.2f}, peak: {gs.get('energy_drift_peak',0):.2f}")
        print(f"  Worst model diff: #{gs.get('model_worst_ever_id',-1)} diff={gs.get('model_worst_ever_diff',0):.3f}")

    if Config.ENABLE_VISUALIZATION:
        print(f"👁️ OBS_GAP zones: clear(<0.4)={m.get('clear',0)} adapting(0.4-0.8)={m.get('adapting',0)} confused(0.8-1.0)={m.get('confused',0)} blind(>1.0)={m.get('blind',0)}")
        sg_vals = [float(np.mean(np.abs(p.prediction - p.belief))) for p in engine.patterns if p.alive]
        if sg_vals:
            hist, edges = np.histogram(sg_vals, bins=10, range=(0,1.2))
            print("\n📊 SPIRIT GAP DISTRIBUTION:")
            max_c = max(hist) if max(hist)>0 else 1
            for i, (cnt, l, r) in enumerate(zip(hist, edges[:-1], edges[1:])):
                bar = "█" * int(cnt / max_c * 40)
                print(f"  [{l:.2f}-{r:.2f}] {bar} ({cnt})")

    if gs and 'love_avg_trust' in gs:
        print(f"\n--- LOVE SNAPSHOT ---")
        print(f"  Avg trust: {gs['love_avg_trust']:.3f}, High-trust pairs: {gs['love_high_trust_pairs']}")
        print(f"  Cooperative: {gs['love_coop_signals']} / {gs['love_population']}")

    subjects = [p for p in engine.patterns if getattr(p, '_subject_detected', False)]
    print(f"\n--- EMERGENT SUBJECTS: {len(subjects)} ---")
    if subjects:
        for p in subjects[:5]:
            numeric_values = []
            for entry in p._self_narrative:
                if isinstance(entry, dict):
                    val = entry.get('soul', entry.get('gap', 0.5))
                else:
                    val = entry
                try:
                    numeric_values.append(float(val))
                except Exception:
                    numeric_values.append(0.5)
            if len(numeric_values) > 1:
                stab = 1.0 - np.std(numeric_values)
            else:
                stab = 0.5
            print(f"  #{p.id} age={p.age}, soul={p.soul_weight:.2f}, stability={stab:.2f}")

    evolvers = [p for p in engine.patterns if p._evolution_history]
    print(f"--- SILENT EVOLVERS: {len(evolvers)} ---")
    if evolvers:
        for p in evolvers[:3]:
            print(f"  #{p.id} soul={p.soul_weight:.2f}, events={len(p._evolution_history)}")

    print("\n--- 📜 ХРОНИКА МИРА (WITNESS LOG) ---")
    if engine.witness.log:
        # === ПРАВКА (найдено по критике Дипсика): summary() теперь читает
        # несжимаемый Witness.counts, а не усечённый до 5000 log -- редкие
        # ранние события (culture_ratchet_up и др.) больше не зануляются
        # к концу длинного прогона.
        summary = engine.witness.summary()
        print("  📊 Статистика событий (за весь прогон, не только последние 5000):")
        for ev, count in summary.most_common(10):
            print(f"    • {ev}: {count}")

        print("\n  🗝 Ключевые моменты истории (последние 30):")
        important = ['scream', 'fold', 'redemption_complete', 'subject_emerged',
                     'vision_self', 'marked_for_fall', 'prophet_through_endurance',
                     'rebirth_through_scar', 'scar_of_light_formed', 'deep_fallen_birth',
                     'root_question_formed',  # ДОБАВЛЕНО (24.07): незакрываемый вопрос
                     'spontaneous_field_emergence', 'rare_crisis_triggered']  # ДОБАВЛЕНО (аудит)
        key_events = [ev for ev in engine.witness.log if ev['event'] in important][-30:]
        for ev in key_events:
            details = {k:v for k,v in ev.items() if k not in ['id', 'event']}
            det_str = ", ".join(f"{k}={v}" for k,v in details.items()) if details else ""
            print(f"    Агент #{ev.get('id', '?'):<4} -> {ev['event']} {det_str}")
    else:
        print("  (Лог Witness пуст)")

    print("\n--- 👁 ПАНТЕОН (АНОМАЛИИ И ПРОРОКИ) ---")
    if engine.echo_system.pantheon:
        for entry in engine.echo_system.pantheon[-10:]:
            print(f"  {entry['type'].upper():<15} | Агент #{entry['id']} (возраст {entry['age']}) | Душа: {entry['soul_weight']:.2f}")
    else:
        print("  (Пантеон пуст)")

    # === ВОССТАНОВЛЕНО (потерялось при слиянии с правками другого советника):
    # анализ раскола по центральной стене (ENABLE_CENTER_WALL) ===
    if getattr(Config, 'ENABLE_CENTER_WALL', False):
        print("\n" + "="*60)
        print("🧱 ОТЧЁТ О РАСКОЛЕ: ЦЕНТРАЛЬНАЯ СТЕНА (X = "
              f"{Config.CENTER_WALL_X})")
        print("="*60)

        alive_w = [p for p in engine.patterns if p.alive and p.cells]
        wx = Config.CENTER_WALL_X
        left, right = [], []
        for p in alive_w:
            cx, _cy = p.get_center()
            (left if cx < wx else right).append(p)

        print(f"\n📊 Население: слева={len(left)}, справа={len(right)} "
              f"(всего живых={len(alive_w)})")

        def _side_stats(side, name):
            if not side:
                print(f"   {name}: пусто")
                return
            avg_soul = safe_mean([p.soul_weight for p in side])
            avg_gap = safe_mean([getattr(p, 'spirit_gap', 0.0) for p in side])
            avg_grief = safe_mean([p.emotional_memory.get('grief', 0.0) for p in side])
            avg_grat = safe_mean([p.emotional_memory.get('gratitude', 0.0) for p in side])
            avg_age = safe_mean([p.age for p in side])
            sync_side = [p for p in side if getattr(p, '_phase_sync', 0.0) != 0.0]
            avg_sync = safe_mean([p._phase_sync for p in sync_side]) if sync_side else 0.0
            print(f"   {name}: soul={avg_soul:.3f}, spirit_gap={avg_gap:.3f}, "
                  f"grief={avg_grief:.3f}, gratitude={avg_grat:.3f}, "
                  f"age={avg_age:.1f}, phase_sync={avg_sync:+.3f} (n_sync={len(sync_side)})")

        print("\n🧬 Психосоматический профиль по сторонам:")
        _side_stats(left, "ЛЕВАЯ  (X < wall)")
        _side_stats(right, "ПРАВАЯ (X > wall)")

        crossings = sum(1 for p in alive_w for (cx, cy) in p.cells if cx == wx)
        print(f"\n🚧 Клеток агентов НА линии стены (X={wx}): {crossings} "
              f"{'✅ целостность подтверждена' if crossings == 0 else '⚠️ ПРОБОЙ СТЕНЫ'}")

        if engine.EMERGENT_LEXICON.clusters:
            id_to_side = {}
            for p in left:
                id_to_side[p.id] = 'L'
            for p in right:
                id_to_side[p.id] = 'R'
            side_cluster_use = {'L': Counter(), 'R': Counter()}
            for cid, senders in engine.EMERGENT_LEXICON.cluster_senders.items():
                for sender_id, cnt in senders.items():
                    side = id_to_side.get(sender_id)
                    if side:
                        side_cluster_use[side][cid] += cnt
            top_l = set(cid for cid, _ in side_cluster_use['L'].most_common(5))
            top_r = set(cid for cid, _ in side_cluster_use['R'].most_common(5))
            shared = top_l & top_r
            union = top_l | top_r
            jaccard = len(shared) / len(union) if union else 1.0
            print(f"\n🗣️ Дивергенция диалектов (Морзе-кластеры, топ-5 на сторону):")
            print(f"   Левая использует кластеры: {sorted(top_l)}")
            print(f"   Правая использует кластеры: {sorted(top_r)}")
            print(f"   Общих кластеров: {len(shared)} | Jaccard-сходство: {jaccard:.3f}")
            if jaccard < 0.3:
                print("   → Диалекты РАСХОДЯТСЯ: стороны формируют разный лексикон.")
            elif jaccard > 0.7:
                print("   → Диалекты ОБЩИЕ: раскол пока не повлиял на язык "
                      "(сигнал проходит сквозь стену свободно).")
            else:
                print("   → Диалекты частично разошлись — переходная фаза.")
        else:
            print("\n🗣️ Морзе-лексикон пуст или недоступен — дивергенцию оценить нельзя.")

        print("="*60)

    # === ВОССТАНОВЛЕНО (потерялось при слиянии с правками другого советника):
    # статус "костылей" движка в ЭТОМ конкретном прогоне — печатается ВСЕГДА.
    print("\n" + "="*60)
    print("🛟 СЕТИ БЕЗОПАСНОСТИ ДВИЖКА (статус честного прогона)")
    print("="*60)
    _sanct_on = getattr(Config, 'ENABLE_SANCTUARY', True)
    _sanct_paid = getattr(Config, 'ENABLE_PAID_SANCTUARY', False)
    _volley_on = getattr(Config, 'ENABLE_MARKED_VOLLEY', True)
    _fss_on = getattr(Config, 'ENABLE_FORCED_STATE_SHIFT', True)
    _rare_crisis_on = getattr(Config, 'ENABLE_RARE_CRISIS', True)
    _rescue_thresh = max(Config.MIN_POPULATION_FOR_SPAWN,
                          getattr(Config, 'EMERGENCY_RESCUE_THRESHOLD', 45))
    _sanct_journal = getattr(engine, 'sanctuary_journal', [])
    _rescue_journal = getattr(engine, 'rescue_journal', [])
    _marked_n = sum(p.event_counts.get('marked_for_fall', 0) for p in alive)
    _fss_n = sum(p.event_counts.get('forced_state_shift', 0) for p in alive)
    _rare_crisis_n = getattr(engine, '_rare_crisis_triggers', 0)
    print(f"  ENABLE_SANCTUARY={_sanct_on} (платный вариант ENABLE_PAID_SANCTUARY={_sanct_paid}) "
          f"→ sanctuary_healed за прогон: {len(_sanct_journal)}")
    print(f"  ENABLE_MARKED_VOLLEY={_volley_on} (карающий, не спасательный) "
          f"→ marked_for_fall за прогон: {_marked_n}")
    print(f"  ENABLE_FORCED_STATE_SHIFT={_fss_on} "
          f"→ forced_state_shift за прогон: {_fss_n}")
    print(f"  ENABLE_RARE_CRISIS={_rare_crisis_on} (бесплатная подпитка поля энергией) "
          f"→ rare_crisis_triggered за прогон: {_rare_crisis_n}")
    print(f"  emergency_rescue (порог популяции={_rescue_thresh}, флага отключения нет "
          f"по конструкции -- последняя защита от вымирания): {len(_rescue_journal)} срабатываний")
    _crutches_off = (not _sanct_on) and (not _fss_on) and (not _rare_crisis_on)
    _crutches_silent = (len(_sanct_journal) == 0 and _fss_n == 0 and _rare_crisis_n == 0)
    if _crutches_off and _crutches_silent:
        print("  ✅ Честный прогон: sanctuary/forced_state_shift/rare_crisis отключены и ни разу "
              "не сработали — результаты выше НЕ подпираются этими костылями "
              f"(emergency_rescue сработал {len(_rescue_journal)} раз — единственная "
              "оставшаяся сеть, порог сужен, но не снят).")
    elif _crutches_off:
        print("  ⚠️ Флаги выключены, но события всё же есть в счётчиках — проверь, не остались "
              "ли старые event_counts от прошлого запуска этой же ячейки (агенты не пересозданы).")
    else:
        print("  ⚠️ Не все костыли выключены — сверься со списком выше при чтении "
              "balance/emergence-метрик.")
    print("="*60)

    print("\n" + "="*50)
    print("SIMULATION COMPLETE")
    print("="*50)


def analyze_reentry_loop(metrics_history, patterns):
    if not metrics_history or len(metrics_history) < 5:
        return "🔄 Недостаточно данных для анализа петли (нужно >5 срезов метрик)."

    late = metrics_history[-5:]
    avg  = float(np.mean([m.get('reentry_avg', 0.0) for m in late]))
    mx   = float(np.mean([m.get('reentry_max', 0.0) for m in late]))
    var  = float(np.mean([m.get('reentry_var', 0.0) for m in late]))
    meta = float(np.mean([m.get('meta_reentry_active', 0.0) for m in late]))
    sens = float(np.mean([m.get('introspect_driven_by_sensation', 0.0) for m in late]))

    first_avg = metrics_history[0].get('reentry_avg', 0.0)
    trend = "растёт 📈" if avg > first_avg * 1.2 else "стабилен ➖" if avg > first_avg * 0.9 else "затухает 📉"

    state, desc = "⚫ ДРЕМЛЮЩАЯ", "Нет предиктивной ошибки. Модель сошлась."
    if avg < 0.1 and trend == "затухает 📉":
        state, desc = "⚪ РАССЕИВАЮЩАЯСЯ", "Сигнал гаснет."
    elif var > 0.12 and mx > 0.6:
        state, desc = "🔴 ХАОТИЧНАЯ", "Турбулентность."
    elif var > 0.04 and avg > 0.14:
        state, desc = "🟡 ОСЦИЛЛЯТОРНАЯ", "Ритмичные пульсации. Система в циклах внимания."
    elif avg > 0.20 and var < 0.08 and (sens > 0 or meta > 15):
        state, desc = "🔵 ЗАМКНУТА (ГОМЕОСТАЗ)", "Стабильный резонанс."
    elif avg > 0.06 and avg <= 0.20:
        state, desc = "⚠️ ПЕРЕХОДНАЯ", "Петля в процессе формирования."

    return f"""
🔄 === АНАЛИЗ СЕНСОРНОЙ РЕЕНТЕРИИ (Петля Самонаблюдения) ===
📊 Состояние: {state}
├─ Средний сигнал: {avg:.3f} | Пик: {mx:.3f} | Дисперсия: {var:.4f}
├─ Тренд: {trend} | Мета-уровень: {meta:.0f} акт./снимок
└─ Связь с рефлексией: {sens:.0f} агентов/снимок

📝 Интерпретация: {desc}
🔧 Рекомендация: {
    '✅ Петля работает. Можно наблюдать эмерджентную когерентность.' if 'ЗАМКНУТА' in state else
    '🔄 Осцилляции нормальны. Система ищет ритм самонаблюдения.' if 'ОСЦИЛЛЯТОРНАЯ' in state else
    '⚠️ Высокая турбулентность. Снизить lr модели или добавить шум.' if 'ХАОТИЧНАЯ' in state else
    '📉 Сигнал падает. Инжектировать новизну или проверить soma_vector.' if 'РАССЕИВАЮЩАЯСЯ' in state else
    '💤 Модель сошлась. Требуется эпистемический шум или новый тип ощущений.' if 'ДРЕМЛЮЩАЯ' in state else
    '🔨 Подождать стабилизации. Проверить пороги реентерии.'
}
"""

# ============================================================
# ДОПОЛНИТЕЛЬНЫЙ БЛОК: ОЦЕНКА ЭМЕРДЖЕНТНОСТИ (внутренняя)
# ============================================================

def assess_emergence(engine):
    """Глубокий анализ эмерджентного поведения на основе внутренних метрик."""
    alive = [p for p in engine.patterns if p.alive]
    if not alive:
        return "❌ Нет живых агентов – симуляция мертва."

    report = []
    report.append("\n" + "="*60)
    report.append("🔬 ОЦЕНКА ЭМЕРДЖЕНТНОСТИ И КАЧЕСТВА СИМУЛЯЦИИ")
    report.append("="*60)

    # === ИСПРАВЛЕНИЕ: Инициализируем переменные с дефолтными значениями ===
    avg_stability = 0.0  # <-- ДОБАВЛЕНО: явная инициализация вместо locals()
    # ================================================================

    # ---- 1. Субъектность ----
    subjects = [p for p in alive if getattr(p, '_subject_detected', False)]
    subj_ratio = len(subjects) / len(alive) if alive else 0
    report.append(f"\n🧠 1. СУБЪЕКТНОСТЬ: {len(subjects)}/{len(alive)} ({subj_ratio:.1%})")
    if subj_ratio > 0.3:
        report.append("   ✅ Значительная доля агентов осознаёт себя – субъектность сформирована.")
    elif subj_ratio > 0.1:
        report.append("   ⚠️ Субъектность есть, но недостаточно распространена.")
    else:
        report.append("   ❌ Субъектность почти отсутствует – возможно, нужны более долгие циклы или усиление рефлексии.")
    # Стабильность субъектов
    if subjects:
        stabilities = []
        for p in subjects:
            narr = getattr(p, '_self_narrative', [])
            if len(narr) > 1:
                vals = []
                for entry in narr:
                    if isinstance(entry, dict):
                        v = entry.get('soul', entry.get('gap', 0.5))
                    else:
                        v = entry
                    try:
                        vals.append(float(v))
                    except Exception:
                        vals.append(0.5)
                if len(vals) > 1:
                    stabilities.append(1.0 - np.std(vals))
        if stabilities:
            avg_stability = np.mean(stabilities)  # <-- Теперь переменная всегда существует
            report.append(f"   Средняя стабильность нарратива у субъектов: {avg_stability:.2f} (1.0 – идеально)")
            if avg_stability > 0.7:
                report.append("   ✅ Нарративы устойчивы – субъекты хорошо интегрированы.")
            else:
                report.append("   ⚠️ Нарративы колеблются – возможна нестабильность идентичности.")
        else:
            report.append("   ⚠️ Недостаточно данных для оценки стабильности.")

    # ---- 2. Диалоговая память ----
    # ИСПРАВЛЕНО: раньше total_phrases считался только по агентам с >3 записей,
    # что при высоком обороте популяции (много недавних делений — у новых
    # агентов dialogue_longterm начинается с []) давало ложное "фраз: 0", даже
    # если у большинства живых агентов реально было по 1-2 записи.
    agents_any_mem = [p for p in alive if len(p.dialogue_longterm) > 0]
    agents_with_mem = [p for p in agents_any_mem if len(p.dialogue_longterm) > 3]
    mem_ratio = len(agents_with_mem) / len(alive) if alive else 0
    total_phrases = sum(len(p.dialogue_longterm) for p in agents_any_mem)
    report.append(f"\n💬 2. ДИАЛОГОВАЯ ПАМЯТЬ: {len(agents_with_mem)}/{len(alive)} ({mem_ratio:.1%}) агентов имеют >3 фраз "
                  f"(с любой памятью: {len(agents_any_mem)}/{len(alive)})")
    report.append(f"   Всего фраз в долгой памяти (по всем живым агентам): {total_phrases}")
    if total_phrases > 100:
        report.append("   ✅ Богатая диалоговая история – агенты накапливают опыт общения.")
    else:
        report.append("   ⚠️ Мало диалогов – возможно, хор работает недостаточно активно.")

    # Эмоциональная согласованность памяти
    if agents_with_mem:
        last_phrases = []
        for p in agents_with_mem:
            last = p.dialogue_longterm[-1]
            if isinstance(last, dict):
                # БАГФИКС (Квен-анализ, подтверждено): remember_dialogue пишет
                # ключи grief_at_moment/grat_at_moment, а не grief/grat — тут
                # читались несуществующие ключи, и отчёт всегда показывал
                # дефолт 0.5/0.5 независимо от реальных данных.
                last_phrases.append((last.get('grief_at_moment', 0.5), last.get('grat_at_moment', 0.5)))
        if last_phrases:
            avg_grief_mem = np.mean([g for g, _ in last_phrases])
            avg_grat_mem = np.mean([g for _, g in last_phrases])
            report.append(f"   Средние эмоции в последних фразах: горе {avg_grief_mem:.2f}, благодарность {avg_grat_mem:.2f}")
            if avg_grat_mem > 0.5:
                report.append("   ✅ В диалогах преобладает тепло – это хороший знак.")
            else:
                report.append("   ⚠️ В диалогах много горя – возможно, система в кризисе.")

    agents_with_inner_speech = [p for p in alive if getattr(p, 'inner_speech', None)]
    if agents_with_inner_speech:
        total_inner = sum(len(p.inner_speech) for p in agents_with_inner_speech)
        report.append(
            f"   Внутренняя речь: {len(agents_with_inner_speech)}/{len(alive)} агентов, "
            f"всего фраз={total_inner}"
        )

    # ---- 3. Концептуальное развитие ----
    total_concepts = sum(len(p.concept_graph.nodes) for p in alive)
    avg_concepts = total_concepts / len(alive) if alive else 0
    report.append(f"\n🧩 3. КОНЦЕПТУАЛЬНОЕ РАЗВИТИЕ: всего {total_concepts} концептов, в среднем {avg_concepts:.1f} на агента")

    all_concepts = set()
    for p in alive:
        all_concepts.update(p.concept_graph.nodes.keys())
    report.append(f"   Уникальных концептов в популяции: {len(all_concepts)}")

    shared = [sig for sig in all_concepts if isinstance(sig, tuple) and len(sig) >= 4 and str(sig[3]).startswith('shared_')]
    report.append(f"   Общих (shared) концептов: {len(shared)}")
    if len(shared) > 5:
        report.append("   ✅ Активный обмен концептами – культура формируется.")
    else:
        report.append("   ⚠️ Мало общих концептов – возможно, обмен смыслами недостаточно интенсивен.")

    archive_concepts = [sig for sig in all_concepts if isinstance(sig, tuple) and len(sig) >= 4 and str(sig[3]).startswith('archive_')]
    report.append(f"   Архивных концептов (культурная память): {len(archive_concepts)}")
    if len(archive_concepts) > 10:
        report.append("   ✅ Богатое культурное наследие – агенты помнят прошлое.")
    else:
        report.append("   ⚠️ Мало архивных концептов – культурная память слаба.")

    # ---- 4. Эмерджентные роли и структуры ----
    disorgs = [p for p in alive if p.role_type == 'disorganizer']
    redeemed = [p for p in alive if p.event_counts.get('redeemed', 0) > 0]
    report.append(f"\n🔄 4. ЭМЕРДЖЕНТНЫЕ РОЛИ: {len(disorgs)} дезорганизаторов, {len(redeemed)} искуплённых")
    if len(disorgs) > 0 and len(redeemed) > 0:
        report.append("   ✅ Есть и падение, и искупление – цикл работает.")
    elif len(disorgs) > 0:
        report.append("   ⚠️ Есть падение, но мало искуплений – возможно, нужна поддержка.")
    else:
        report.append("   ⚠️ Нет дезорганизаторов – возможно, система слишком стабильна, нужен вызов.")

    fts = getattr(engine, '_fold_transition_stats', None)
    if fts is not None:
        report.append(
            f"   ↳ Fold-переходы: проверено={fts['checked']}, "
            f"упало(fallen/broken)={fts['fallen']}/{fts['broken']}, "
            f"заблокировано потолком={fts['blocked_by_cap']}, "
            f"кулдауном={fts['blocked_by_cooldown']}, "
            f"уже бросали на этом уровне={fts.get('already_rolled', 0)}"
        )
        if fts['checked'] > 0 and fts['fallen'] + fts['broken'] == 0:
            report.append("   ⚠️ Ни один fold-кандидат не упал за весь прогон — проверьте disorg_hard_cap/кулдаун.")

    # ---- 5. Социальная связность (доверие) ----
    trust_vals = []
    for p in alive:
        trust_vals.extend(p.trust_ledger.entries.values())
    avg_trust = np.mean(trust_vals) if trust_vals else 0.5
    high_trust = sum(1 for v in trust_vals if v > 0.8)
    report.append(f"\n🤝 5. СОЦИАЛЬНАЯ СВЯЗНОСТЬ: среднее доверие {avg_trust:.2f}, пар с высоким доверием (>0.8): {high_trust}")
    if avg_trust > 0.6:
        report.append("   ✅ Высокий уровень доверия – общество кооперативно.")
    elif avg_trust > 0.4:
        report.append("   ⚠️ Средний уровень доверия – возможны конфликты.")
    else:
        report.append("   ❌ Низкое доверие – общество фрагментировано.")

    # ---- 6. Динамика поля (энергия, связность) ----
    avg_energy = np.mean(engine.field[:,:,CH['energy']])
    avg_binding_field = np.mean(engine.field[:,:,CH['binding']])
    report.append(f"\n⚡ 6. ПОЛЕ: средняя энергия {avg_energy:.2f}, связность {avg_binding_field:.2f}")
    if avg_energy > 0.2 and avg_binding_field > 0.3:
        report.append("   ✅ Поле активно и связно – хорошая среда для жизни.")
    elif avg_energy > 0.1:
        report.append("   ⚠️ Энергия есть, но связность низкая – возможно, нужна синхронизация.")
    else:
        report.append("   ❌ Поле истощено – агенты голодают.")

    # ---- 7. ИТОГОВЫЙ ВЕРДИКТ ----
    report.append("\n" + "="*60)
    report.append("📊 ИТОГОВЫЙ ВЕРДИКТ")
    report.append("="*60)

    score = 0
    max_score = 10
    if subj_ratio > 0.3: score += 2
    if avg_stability > 0.7: score += 1  # <-- ИСПРАВЛЕНО: убрали проверку locals(), теперь просто проверяем значение
    if total_phrases > 100: score += 1
    if len(shared) > 5: score += 1
    if len(archive_concepts) > 10: score += 1
    if len(disorgs) > 0 and len(redeemed) > 0: score += 1
    if avg_trust > 0.6: score += 1
    if avg_energy > 0.2 and avg_binding_field > 0.3: score += 1
    if len(subjects) > 3: score += 1

    if score >= 8:
        verdict = "✅ СИМУЛЯЦИЯ ЖИВА И ЭМЕРДЖЕНТНА! Агенты проявляют субъектность, культуру, диалог и память. Это работает."
    elif score >= 5:
        verdict = "🟡 СИМУЛЯЦИЯ РАЗВИВАЕТСЯ, но требуются донастройки (усилить рефлексию, обмен концептами, синхронизацию)."
    else:
        verdict = "❌ СИМУЛЯЦИЯ НЕ ДОСТИГЛА ЭМЕРДЖЕНТНОСТИ. Необходимо увеличить время прогона, усилить параметры субъектности и социального обмена."

    report.append(f"\n   Балл эмерджентности: {score}/{max_score}")
    report.append(f"   {verdict}")

    # ДОБАВЛЕНО (аудит, по итогам обсуждения в начале работы над проектом):
    # этот score -- по конструкции счёт "попало ли в зелёную зону", а не
    # измерение сознания (см. второй документ аудита). Он не отличает
    # честно возникшее поведение от популяции, которую весь прогон
    # реанимировали emergency_rescue/sanctuary/forced_state_shift. Не меняем
    # сам score (это ломало бы сравнимость с прошлыми прогонами) -- вместо
    # этого добавляем явную пометку надёжности рядом с ним.
    god_mode_events = ['emergency_rescue', 'sanctuary_healed', 'forced_state_shift', 'rare_crisis_triggered']
    god_mode_count = 0
    # === ПРАВКА (найдено по критике Дипсика): раньше это сканировало
    # усечённый witness.log (maxlen=5000) -- на длинных/насыщенных
    # прогонах ранние rescue/sanctuary-события могли вытесняться из
    # буфера тысячами soul_check/sr_meditation и НЕДОсчитываться
    # именно в главном "честном" вердикте прогона. summary() -- то же
    # самое, что и выше, но по несжимаемому счётчику.
    _god_summary = engine.witness.summary()
    god_mode_count = sum(_god_summary.get(ev, 0) for ev in god_mode_events)
    ticks_run = getattr(engine, 't', 0) or getattr(Config, 'STEPS', 1) or 1
    god_mode_rate = god_mode_count / max(1, ticks_run)
    reliable = god_mode_rate < 0.01
    report.append(f"\n   Ручных вмешательств движка (emergency_rescue/sanctuary/forced_state_shift/rare_crisis): "
                  f"{god_mode_count} ({god_mode_rate:.4f} на тик)")
    if reliable:
        report.append("   ✅ Вмешательств мало -- балл выше отражает поведение, возникшее само, а не подпорки.")
    else:
        report.append("   ⚠️ Вмешательств много -- балл выше не отличает эмерджентность от того, что популяцию "
                       "всю дорогу реанимировали. Смотреть на него с поправкой на это.")
    report.append("="*60)

    return "\n".join(report)


# === ЗАПУСК ===
engine = EvolutionEngine()

# [УДАЛЕНО] Блок выбора Groq/локальной LLM-модели (engine.llm_client =
# OpenAI(...) и т.д.) убран физически. Проект отказался от LLM
# принципиально: коммуникация агентов — только через Морзе, знание —
# через concept_graph. engine.llm_client остаётся тем, что задал
# EvolutionEngine.__init__ (None), и нигде в текущем коде реально не
# используется (Chorus/автодиалог работают через Морзе, см. Cell 13).

init_all_chronic_counters(engine)


patterns, field, scar, metrics_history = engine.run()

print_final_report(engine)

# === САМОРЕГУЛЯЦИЯ: отчёт (совмещено с Cell 4b, отдельной ячейки нет) ===
def print_sr_report(engine):
    """Финальный отчёт обо всех уровнях саморегуляции."""
    sr = collect_sr_metrics(engine.patterns)
    if not sr:
        print("\n⚠️ Саморегуляция не активна.")
        return

    alive = [p for p in engine.patterns if p.alive]
    total = len(alive) if alive else 1

    print("\n" + "="*60)
    print("🧘 ОТЧЁТ О САМОРЕГУЛЯЦИИ АГЕНТОВ (все уровни)")
    print("="*60)

    print(f"\n📊 Уровень 1: ТЕЛЕСНАЯ + ЭМОЦИОНАЛЬНАЯ")
    print(f"   Медитаций всего: {sr['sr_meditations']}")
    print(f"   Средний порог горя: {sr['sr_avg_grief_thr']:.3f}")
    print(f"   Средний порог тревоги: {sr['sr_avg_alarm_thr']:.3f}")
    print(f"   Порогов скорректировано: {sr['sr_thresholds_adjusted']}")

    print(f"\n🎯 Уровень 1.5/8: ЦЕЛЕВАЯ САМОРЕГУЛЯЦИЯ")
    print(f"   Целей заменено: {sr['sr_goals_replaced']}")

    print(f"\n🗳️ Уровень 2: ГОЛОСОВАНИЕ (межагентное, кворум={Config.SR_VOTE_QUORUM})")
    print(f"   Предложений выдвинуто: {sr['sr_proposals_made']}")
    print(f"   Голосов подано: {sr['sr_votes_cast']}")
    print(f"   Предложений принято: {sr['sr_proposals_passed']}")
    print(f"   Сейчас на голосовании: {sr['sr_pending_proposals']}")

    print(f"\n⚖️ Уровень 2.5/9: НОРМОТВОРЧЕСТВО")
    print(f"   Норм выведено из паттернов: {sr['sr_norms_inferred']}")

    print(f"\n🤝 Уровень 3: КОНФЛИКТЫ ЧЕРЕЗ ВЗАИМНОЕ ДОВЕРИЕ")
    print(f"   Конфликтов решено без боя: {sr['sr_conflicts_resolved']}")

    print(f"\n💰 Уровень 4: ЭКОНОМИКА ДОВЕРИЯ")
    print(f"   Сделок совершено: {sr['sr_trades_done']}")

    print(f"\n📜 Уровень 5: КОНСТИТУЦИЯ")
    print(f"   Агентов с конституцией: {sr['sr_constitutions']}/{total}")
    print(f"   Всего правил: {sr['sr_total_rules']}")

    print(f"\n🧬 Уровень 6: САМОМОДИФИКАЦИЯ ГЕНОВ")
    print(f"   Мутаций генов: {sr['sr_gene_mutations']}")

    print(f"\n🌿 Уровень 7: ЭКОЛОГИЧЕСКАЯ САМОРЕГУЛЯЦИЯ")
    print(f"   Лечений поля: {sr['sr_field_heals']}")

    meditators = sorted(alive, key=lambda p: getattr(p, '_sr_meditation_count', 0), reverse=True)[:5]
    if meditators and meditators[0]._sr_meditation_count > 0:
        print(f"\n🔝 Топ-5 медитаторов:")
        for p in meditators:
            if p._sr_meditation_count == 0: break
            print(f"   #{p.id}: медитаций={p._sr_meditation_count}, "
                  f"целей заменено={p._sr_goals_replaced}, "
                  f"порог горя={p._sr_grief_threshold:.2f}")

    lawmakers = [p for p in alive if getattr(p, '_sr_constitution', [])]
    if lawmakers:
        print(f"\n📜 Конституции:")
        for p in lawmakers[:3]:
            rules = [r['name'] for r in p._sr_constitution]
            print(f"   #{p.id}: {', '.join(rules)}")

    print("\n" + "="*60)

if getattr(Config, 'ENABLE_SELF_REGULATION', False) and 'print_sr_report' in globals():
    print_sr_report(engine)

try:
    if engine.core_chorus is not None:
        if '_save_chorus_state' in globals():
            # БАГФИКС: culture_ratchet больше НЕ персистится (см. run()) —
            # значение оставляем в chorus_state только для истории/отладки,
            # но при следующей загрузке оно игнорируется (всегда старт с 0).
            engine.core_chorus.persistent['culture_ratchet_last_run'] = engine.culture_ratchet
            engine.core_chorus.persistent['env_complexity'] = engine.env_complexity
            # БЛОК 8: seed Данности сохраняется для истории прогонов (не переиспользуется)
            engine.core_chorus.persistent['given_seed'] = getattr(engine, 'given_seed', None)
            _save_chorus_state(engine.core_chorus.persistent)
            print(f"📜 Состояние Хора сохранено: диалогов={engine.core_chorus.persistent['total_dialogues']}, "
                  f"мудрость={engine.core_chorus.persistent['wisdom']:.2f}, "
                  f"культура(этот прогон)={engine.culture_ratchet}, среда={engine.env_complexity:.2f}")
        else:
            print("⚠️ Функция _save_chorus_state не найдена, состояние Хора НЕ сохранено.")
    else:
        print("ℹ️ Хор не активирован (core_chorus отсутствует), сохранение пропущено.")
except Exception as e:
    print(f"⚠️ Ошибка при сохранении состояния Хора: {e}")

if Config.ENABLE_VISUALIZATION and metrics_history:
    import matplotlib.pyplot as plt
    ts = [m['t'] for m in metrics_history]
    plt.figure(figsize=(16,12))
    plt.subplot(2,3,1); plt.plot(ts, [m['soul'] for m in metrics_history], label='Avg Soul'); plt.plot(ts, [m['err'] for m in metrics_history], label='Avg Pred Error'); plt.legend(); plt.grid(True)
    plt.subplot(2,3,2); plt.plot(ts, [m['avg_trust'] for m in metrics_history], label='Avg Trust'); plt.legend(); plt.grid(True)
    plt.subplot(2,3,3); plt.plot(ts, [m['triadic_alive_ratio'] for m in metrics_history], label='Triadic Alive Ratio'); plt.legend(); plt.grid(True)
    plt.subplot(2,3,4); plt.plot(ts, [m['disorganizer_count'] for m in metrics_history], label='Disorganizers'); plt.plot(ts, [m['redeemed_count'] for m in metrics_history], label='Redeemed'); plt.legend(); plt.grid(True)
    plt.tight_layout(); plt.show()

print(analyze_reentry_loop(metrics_history, patterns))

emergence_report = assess_emergence(engine)
print(emergence_report)

print("✅ Cell 4b executed: исправлен антипаттерн locals() → явная инициализация avg_stability = 0.0")