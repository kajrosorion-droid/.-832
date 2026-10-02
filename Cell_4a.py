




# ============================================================
# Cell 4a – collect_metrics (ИСПРАВЛЕНО: баг метрики blind + IndexError + защита current_social)
# ДОБАВЛЕНО: статистика генератора речи (phenomenal_report + inner_speech)
# ДОБАВЛЕНО: статистика физического слоя Морзе
# ДОБАВЛЕНО: статистика подсознания (Unconscious Layer) — исправлено
# ============================================================

import numpy as np

def collect_metrics(patterns, field, t, lexicon=None):
    alive = [p for p in patterns if p.alive]
    if not alive:
        return {
            't': t, 'patterns': 0, 'lineages': 0, 'err': 0, 'soul': 0, 'binding': 0,
            'echo': 0, 'signals': np.zeros(6), 'states': {}, 'intents': {}, 'epi_scar': 0,
            'unique_concepts': 0, 'stagnation_ratio': 0.0, 'divisions_possible': 0,
            'arc_completions': 0, 'folds': 0, 'avg_trust': 0.5, 'high_trust_pairs': 0,
            'trust_distribution': {'low': 0, 'mid': 0, 'high': 0}, 'disorganizer_count': 0,
            'redeemed_count': 0, 'quarantined_count': 0, 'deterministic_redemptions': 0,
            'phenomenal_binding_avg': 0.0, 'state_emotion_mismatch': 0.0, 'forced_collapses': 0,
            'myth_pool_size': 0, 'triadic_alive': 0, 'triadic_alive_ratio': 0.0,
            'avg_internal_gap': 0.0, 'max_internal_gap': 0.0, 'zero_internal_gap_agents': 0,
            'avg_obs_gap': 0.0, 'max_obs_gap': 0.0,
            'tremor_targets': 0, 'avg_coherence_with_gap': 0.0, 'love_pairs': 0,
            'avg_soma': 0.0, 'mem_agents': 0, 'avg_buf_len': 0.0, 'total_recalled': 0,
            'concept_adopted': 0, 'deep_concept_adopted': 0, 'deep_exchange': 0, 'wisdom_shared': 0,
            'avg_signal_memory': 0.0, 'intentional_signal_agents': 0, 'top_signal_pairs': {},
            'lineage_count': 0, 'avg_lineage_age': 0.0, 'max_lineage_age': 0, 'ancient_lineages': 0,
            'max_lineage_total_age': 0, 'divisions_total': 0,
            'avg_field_unknown': 0.0, 'avg_field_binding': 0.0,
            'narrative_agents': 0, 'teaching_events': 0, 'learning_events': 0,
            'dream_consolidations': 0, 'nightmare_consolidations': 0, 'nightmares_transformed': 0,
            'agents_with_nightmare': 0, 'agents_with_dream_memory': 0,
            'avg_endurance': 0.0, 'endurance_critical': 0, 'divide_blocked_fatigue': 0,
            'blind': 0, 'confused': 0, 'adapting': 0, 'clear': 0,
            'avg_social_crisis': 0.0, 'avg_social_invitation': 0.0, 'avg_social_grief': 0.0,
            'avg_social_cooperate': 0.0, 'avg_social_explore': 0.0, 'avg_social_seek_help': 0.0,
            'avg_social_scar': 0.0, 'avg_social_rest': 0.0, 'avg_social_resonance': 0.0,
            'avg_social_btype': 0.0, 'avg_social_alarm': 0.0,
            'avg_social_beauty': 0.0, 'avg_social_rhythm': 0.0, 'avg_social_interest': 0.0,
            'avg_social_memory': 0.0, 'avg_social_silence': 0.0,
            'vocab_concepts': 0, 'blind_events': 0, 'concept_anticipations': 0, 'vocab_events': 0,
            'avg_action_feedback': 0.0, 'avg_social_warmth': 0.0,
            'substate_counts': {},
            'total_transitions': 0, 'top_transitions': [],
            'archive_concept_agents': 0, 'total_archive_concepts': 0, 'archive_types': {},
            'total_introspect': 0, 'avg_introspect': 0.0, 'max_introspect': 0,
            'reflection_quality': 0.0,
            'ethical_coherence': 0.0,
            'global_concept_entropy': 0.0,
            'introspection_synchrony': 0.0,
            'narrative_continuity': 0.0,
            'unconquered_count': 0,
            'unconquered_wise': 0,
            'unconquered_rebel': 0,
            'avg_unconquered_str': 0.0,
            'sovereignty_field_avg': 0.0,
            'lang_compression_ratio': 1.0, 'lang_active_clusters': 0,
            'lang_total_clusters': 0, 'lang_collapsed': False,
            'morse_concepts': 0, 'spontaneous_field_emergence': 0,
            'marked_for_fall_count': 0,
            'reentry_avg': 0.0,
            'reentry_max': 0.0,
            'reentry_var': 0.0,
            'meta_reentry_active': 0,
            'introspect_driven_by_sensation': 0,
            'feral_count': 0,
            'avg_feral_fury': 0.0,
            'feral_kills': 0,
            'avg_phi': 0.0,
            'gene_carriers': 0,
            'gene_carrier_counts': {},
            'generator': {},
            'morse': {},
            # ---- ПОДСОЗНАНИЕ (дефолтные значения) ----
            'avg_gut_feeling': 0.0,
            'latent_need_counts': {},
            'unconscious_insights': 0,
            'unconscious_goals': 0,
            'avg_anticipation': 0.0,
            'avg_drive_distance': 0.0,
            'unconscious_concept_agents': 0,
            'total_unconscious_concepts': 0,
        }

    avg_field_unknown = safe_mean(field[:, :, CH['unknown']], 0.0)
    avg_field_binding = safe_mean(field[:, :, CH['binding']], 0.0)

    lineage_registry = {}
    for p in alive:
        lid = p.lineage_id
        born = getattr(p, 'lineage_born_at_step', 0)
        if lid not in lineage_registry or born < lineage_registry[lid]:
            lineage_registry[lid] = born

    lineage_ages = [t - born for born in lineage_registry.values()]
    avg_lineage_age = float(np.mean(lineage_ages)) if lineage_ages else 0.0
    max_lineage_age = max(lineage_ages) if lineage_ages else 0

    ancient_lineages = len(set(
        p.lineage_id for p in alive
        if getattr(p, 'lineage_total_age', 0) > Config.ANC_THRESHOLD
    ))

    lineage_count = len(lineage_registry)

    total_ages = [getattr(p, 'lineage_total_age', 0) for p in alive if getattr(p, 'lineage_total_age', 0) > 0]
    max_lineage_total_age = max(total_ages) if total_ages else 0

    err = safe_mean([p.pred_error for p in alive], 0)
    soul = safe_mean([p.soul_weight for p in alive], 0)
    binding = safe_mean(field[:, :, CH['binding']], 0)
    lineages = len(set(p.lineage_id for p in alive))

    states = {}
    intents = {}
    for p in alive:
        s = p.semantic_state
        states[s] = states.get(s, 0) + 1
        if p.intent:
            intents[p.intent["type"]] = intents.get(p.intent["type"], 0) + 1

    epi_scar = safe_mean([p.epistemic_scar for p in alive], 0)
    all_concepts = set()
    for p in alive:
        all_concepts.update(p.concept_graph.nodes.keys())

    stagnated = sum(1 for p in alive if p.semantic_state_age > Config.STAGNATION_GRIEF_THRESHOLD)
    stagnation_ratio = stagnated / max(len(alive), 1)
    divisions_possible = sum(1 for p in alive if p.can_divide())
    total_arcs = sum(sum(p.arc_tracker.completed_arcs.values()) for p in alive)
    total_folds = sum(p.event_counts.get('fold', 0) for p in alive)

    mismatch_count = sum(1 for p in alive if (p.semantic_state == "contentment" and p.emotional_memory['grief'] > 0.5) or (p.semantic_state == "seeking_comfort" and p.emotional_memory['gratitude'] > 0.8))
    mismatch_ratio = mismatch_count / max(len(alive), 1)

    all_trusts = []
    high_pairs = 0
    trust_dist = {'low': 0, 'mid': 0, 'high': 0}
    disorg = 0
    redm = 0
    quar = 0
    det_red = 0
    collapsed = 0
    phenomenal_bindings = []
    love_pairs = 0
    triadic_alive_count = 0
    obs_gaps = []
    coherence_list = []
    tremor_targets = 0

    feral_count = 0
    feral_furies = []
    feral_kills = 0

    for p in alive:
        presence = soul_check(p)
        if presence.is_triadic_alive():
            triadic_alive_count += 1

        # ИСПРАВЛЕНО (найдено по жалобе "blind=167/200, похоже на баг"):
        # тут читался presence.spirit_gap -- НЕограниченный (Pattern сам
        # клиппирует его в [0,1] отдельным полем self.obs_gap, комментарий
        # в Pattern так и называется "ВЫЧИСЛЕНИЕ OBS_GAP"). spirit_gap
        # обычно выше 0.6-0.8 и у части агентов уходит за 1.0-1.3, поэтому
        # зона "blind (>1.0)" набирала абсолютное большинство популяции не
        # из-за реального кризиса восприятия, а из-за того, что читалась не
        # та (неклиппированная) переменная. Используем уже готовое p.obs_gap.
        obs_gap = getattr(p, 'obs_gap', min(1.0, presence.spirit_gap))
        obs_gaps.append(obs_gap)
        coherence_list.append(presence.coherence_with_gap)

        if obs_gap < 0.20:
            tremor_targets += 1

        if p.role_type == "disorganizer":
            disorg += 1
        if p.event_counts.get('redeemed', 0) > 0:
            redm += 1
        if p.quarantine_timer > 0:
            quar += 1
        if p.event_counts.get('deterministic_redemption_trigger', 0) > 0:
            det_red += 1
        if p.event_counts.get('forced_soul_collapse', 0) > 0:
            collapsed += 1

        phenomenal_bindings.append(p.last_phenomenal_binding)
        entries = list(p.trust_ledger.entries.values())
        all_trusts.extend(entries)
        high_pairs += sum(1 for t_val in entries if t_val > 0.8)
        for t_val in entries:
            if t_val < 0.4:
                trust_dist['low'] += 1
            elif t_val < 0.7:
                trust_dist['mid'] += 1
            else:
                trust_dist['high'] += 1
        for partner_id, trust_val in p.trust_ledger.entries.items():
            if trust_val > 0.95:
                love_pairs += 1

        if p.role_type == "feral":
            feral_count += 1
            feral_furies.append(getattr(p, '_feral_fury', 0.0))
            feral_kills += p.event_counts.get('feral_execution', 0)

    soma_vals = [p.soma for p in alive if p.soma > 0]
    avg_soma = safe_mean(soma_vals, 0.0) if soma_vals else 0.0

    mem_agents = sum(1 for p in alive if p.episodic_buffer)
    avg_buf_len = np.mean([len(p.episodic_buffer) for p in alive]) if mem_agents else 0.0
    total_recalled = sum(p.event_counts.get('memory_recalled', 0) for p in alive)

    concept_adopted = sum(p.event_counts.get('concept_adopted', 0) for p in alive)
    deep_concept_adopted = sum(p.event_counts.get('deep_concept_adopted', 0) for p in alive)
    deep_exchange = sum(p.event_counts.get('deep_exchange', 0) for p in alive)
    wisdom_shared = sum(p.event_counts.get('wisdom_shared', 0) for p in alive)

    total_signal_memories = 0
    signal_types_used = {}
    intentional_signal_count = 0
    for p in alive:
        total_signal_memories += len(p.signal_memory)
        for (sig_type, resp_type), data in p.signal_memory.items():
            key = f"{sig_type}→{resp_type}"
            signal_types_used[key] = signal_types_used.get(key, 0) + data['count']
        if p.last_intentional_signal:
            intentional_signal_count += 1

    narrative_agents = sum(1 for p in alive if p._narrative_agent)

    endurance_vals = [p._cellular_endurance for p in alive]
    avg_endurance = float(np.mean(endurance_vals)) if endurance_vals else 0.0
    endurance_critical = sum(1 for e in endurance_vals if e < 0.2)
    divide_blocked_fatigue = sum(1 for p in alive if getattr(p, '_divide_blocked_by_fatigue', False))

    fb_vals = []
    sw_vals = []
    for p in alive:
        if len(p.soma_vector) >= 7:
            fb_vals.append(float(p.soma_vector[5]))
            sw_vals.append(float(p.soma_vector[6]))
    avg_action_feedback = float(np.mean(fb_vals)) if fb_vals else 0.0
    avg_social_warmth   = float(np.mean(sw_vals)) if sw_vals else 0.0

    avg_signal_memory = total_signal_memories / len(alive) if alive else 0

    internal_gaps = [float(np.mean(np.abs(p.prediction - p.belief))) for p in alive]
    if internal_gaps:
        avg_internal_gap = np.mean(internal_gaps)
        max_internal_gap = np.max(internal_gaps)
        zero_internal_gap = sum(1 for g in internal_gaps if g < 0.001)
    else:
        avg_internal_gap = max_internal_gap = zero_internal_gap = 0

    if obs_gaps:
        avg_obs_gap = np.mean(obs_gaps)
        max_obs_gap = np.max(obs_gaps)
        blind = sum(1 for g in obs_gaps if g > 1.0)
        confused = sum(1 for g in obs_gaps if 0.8 < g <= 1.0)
        adapting = sum(1 for g in obs_gaps if 0.4 < g <= 0.8)
        clear = sum(1 for g in obs_gaps if g <= 0.4)
    else:
        avg_obs_gap = max_obs_gap = blind = confused = adapting = clear = 0

    avg_trust = safe_mean(all_trusts, Config.TRUST_BASE) if all_trusts else Config.TRUST_BASE
    phenomenal_binding_avg = safe_mean(phenomenal_bindings, 0.5)
    triadic_alive_ratio = triadic_alive_count / max(len(alive), 1)
    avg_coherence_with_gap = safe_mean(coherence_list, 0) if coherence_list else 0

    divisions_total = sum(p.event_counts.get('born_from_division', 0) for p in alive)
    teaching_events = sum(p.event_counts.get('taught', 0) for p in alive)
    learning_events = sum(p.event_counts.get('received_teaching', 0) for p in alive)
    dream_consolidations = sum(p.event_counts.get('dream_consolidation', 0) for p in alive)
    nightmare_consolidations = sum(p.event_counts.get('nightmare_consolidation', 0) for p in alive)
    nightmares_transformed = sum(p.event_counts.get('nightmare_transformed', 0) for p in alive)
    agents_with_nightmare = sum(1 for p in alive if getattr(p, '_nightmare_count', 0) > 0)
    agents_with_dream_memory = sum(1 for p in alive if getattr(p, '_dream_memory_count', 0) > 0)

    # === ИСПРАВЛЕНИЕ: защита от None в current_social ===
    social_avg = np.zeros(16)
    social_count = 0
    for p in alive:
        if p.current_social is not None:
            vec = p.current_social
            if vec is None:
                continue
            if len(vec) < 16:
                vec = np.pad(vec, (0, 16 - len(vec)), 'constant')
            social_avg += vec[:16]
            social_count += 1
    if social_count > 0:
        social_avg /= social_count

    vocab_concepts = sum(
        1 for p in alive
        for sig in p.concept_graph.nodes
        if isinstance(sig, tuple) and len(sig) >= 4 and
        str(sig[3]).startswith("shared_")
    )

    blind_events = sum(p.event_counts.get('blindness_enter', 0) for p in alive) + \
                   sum(p.event_counts.get('blindness_exit', 0) for p in alive)

    concept_anticipations = sum(p.event_counts.get('concept_anticipation', 0) for p in alive)
    vocab_events = sum(p.event_counts.get('vocab_emerged', 0) for p in alive)

    substate_counts = {}
    for p in alive:
        sub = getattr(p, '_substate', None)
        if sub:
            substate_counts[sub] = substate_counts.get(sub, 0) + 1

    transition_counts = {}
    total_transitions = 0
    for p in alive:
        if p.concept_graph.edges:
            for src, dst_dict in p.concept_graph.edges.items():
                from_state = src[3] if isinstance(src, tuple) and len(src) >= 4 else str(src)
                for dst, cnt in dst_dict.items():
                    to_state = dst[3] if isinstance(dst, tuple) and len(dst) >= 4 else str(dst)
                    key = (from_state, to_state)
                    transition_counts[key] = transition_counts.get(key, 0) + cnt
                    total_transitions += cnt

    top_transitions = sorted(transition_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    introspect_counts = []
    for p in alive:
        introspect_counts.append(len(p._self_narrative))
    total_introspect = sum(introspect_counts)
    avg_introspect = np.mean(introspect_counts) if introspect_counts else 0.0
    max_introspect = max(introspect_counts) if introspect_counts else 0

    total_reflections = 0
    beneficial_reflections = 0
    for p in alive:
        narrative = getattr(p, '_self_narrative', [])
        if len(narrative) < 2:
            continue
        for i in range(len(narrative) - 1):
            total_reflections += 1
            prev = narrative[i]
            nxt = narrative[i + 1]
            if isinstance(prev, dict):
                prev_soul = prev.get('soul', 0.5)
                prev_gap = prev.get('gap', 0.5)
            else:
                prev_soul = prev if isinstance(prev, (int, float)) else 0.5
                prev_gap = 0.5
            if isinstance(nxt, dict):
                nxt_soul = nxt.get('soul', 0.5)
                nxt_gap = nxt.get('gap', 0.5)
            else:
                nxt_soul = nxt if isinstance(nxt, (int, float)) else 0.5
                nxt_gap = 0.5
            soul_not_regressed = nxt_soul >= prev_soul - 0.002
            gap_not_exploded = nxt_gap <= prev_gap + 0.010
            any_improvement = (nxt_soul > prev_soul + 0.001 or nxt_gap < prev_gap - 0.005)
            if any_improvement and soul_not_regressed and gap_not_exploded:
                beneficial_reflections += 1
    reflection_quality = beneficial_reflections / total_reflections if total_reflections > 0 else 0.0

    archive_types = {}
    agents_with_archive = 0
    total_archive = 0
    for p in alive:
        has_archive = False
        for sig in p.concept_graph.nodes:
            if isinstance(sig, tuple) and len(sig) >= 4 and str(sig[3]).startswith("archive_"):
                has_archive = True
                total_archive += 1
                label = str(sig[3])
                if "human_concept_injected" in label:
                    atype = "human_injected"
                elif "human_question_witness" in label:
                    atype = "human_question"
                elif "love_concept" in label:
                    atype = "love"
                elif "self_concept" in label:
                    atype = "self"
                elif "shared_attention" in label:
                    atype = "shared_attention"
                elif "intentionality" in label:
                    atype = "intentionality"
                elif "trust" in label:
                    atype = "trust"
                elif "empathy" in label:
                    atype = "empathy"
                elif "recursion" in label:
                    atype = "recursion"
                elif "cooperation_norms" in label:
                    atype = "cooperation_norms"
                elif label.startswith("archive_developmental_arc"):
                    atype = "developmental_arc"
                elif label.startswith("archive_agency"):
                    atype = "agency"
                elif label.startswith("archive_consent"):
                    atype = "consent"
                elif label.startswith("archive_silence"):
                    atype = "silence"
                elif label.startswith("archive_witness_respect"):
                    atype = "witness_respect"
                else:
                    parts = label.split('_')
                    atype = parts[1] if len(parts) > 1 else 'unknown'
                archive_types[atype] = archive_types.get(atype, 0) + 1
        if has_archive:
            agents_with_archive += 1

    # === ИСПРАВЛЕНИЕ: добавлена проверка len(s) >= 4 для защиты от IndexError ===
    def calculate_ethical_coherence(alive_agents):
        ethical_agents = [
            p for p in alive_agents
            if any(('consent' in str(s[3]) or 'agency' in str(s[3])) for s in p.concept_graph.nodes if isinstance(s, tuple) and len(s) >= 4)
        ]
        if not ethical_agents:
            return 0.0
        acting_ethically = sum(
            1 for p in ethical_agents
            if p.intent and p.intent.get('type') in ['cooperate', 'explore', 'rest']
        )
        return acting_ethically / len(ethical_agents)

    ethical_coherence = calculate_ethical_coherence(alive)

    concept_counts = [len(p.concept_graph.nodes) for p in alive]
    if sum(concept_counts) > 0:
        probs = np.array(concept_counts) / sum(concept_counts)
        global_concept_entropy = float(-np.sum(probs * np.log2(probs + 1e-9)))
    else:
        global_concept_entropy = 0.0

    intro_active = sum(1 for p in alive if (getattr(p, 'intent', None) or {}).get('type') == 'introspect')
    introspection_synchrony = intro_active / max(1, len(alive))

    narr_scores = [getattr(p, '_concept_narrative_score', 0.0) for p in alive]
    narrative_continuity = float(np.mean(narr_scores)) if narr_scores else 0.0

    unconquered = [p for p in alive if getattr(p, '_unconquered_strength', 0.0) > 0.4]
    unconquered_count = len(unconquered)
    unconquered_wise = sum(1 for p in unconquered if getattr(p, '_unconquered_type', None) == 'wise')
    unconquered_rebel = sum(1 for p in unconquered if getattr(p, '_unconquered_type', None) == 'rebel')
    avg_unconquered_str = float(np.mean([getattr(p, '_unconquered_strength', 0.0) for p in alive])) if alive else 0.0
    sov_ch = CH.get('signal_sovereignty', 29)
    sovereignty_field_avg = float(np.max(field[:, :, sov_ch]))

    reentry_signals = [p._reentry_signal for p in alive]
    reentry_avg = float(np.mean(reentry_signals)) if reentry_signals else 0.0
    reentry_max = float(np.max(reentry_signals)) if reentry_signals else 0.0
    reentry_var = float(np.var(reentry_signals)) if reentry_signals else 0.0
    meta_reentry_active = sum(1 for p in alive if getattr(p, '_meta_reentry_active', False))
    introspect_driven_by_sensation = 0
    for p in alive:
        if p._reentry_signal > 0.3:
            goals = getattr(p, 'goals', None)
            if goals and isinstance(goals, list):
                if any(isinstance(g, dict) and g.get('type') == 'introspect' for g in goals):
                    introspect_driven_by_sensation += 1

    avg_feral_fury = safe_mean(feral_furies, 0.0)

    avg_phi = safe_mean([getattr(p, '_phi_proxy', 0.0) for p in alive], 0.0)

    gene_carriers = sum(1 for p in alive if any(g in p.genome for g in OPEN_GENE_POOL))
    gene_carrier_counts = {g: sum(1 for p in alive if g in p.genome) for g in OPEN_GENE_POOL}

    # ---- СТАТИСТИКА ГЕНЕРАТОРА РЕЧИ ----
    total_phen_reports = 0
    total_phen_len = 0
    agents_with_phen = 0
    phen_samples = []
    for p in alive:
        if p.last_phenomenal_report:
            agents_with_phen += 1
            total_phen_reports += p.event_counts.get('phenomenal_report', 0)
            total_phen_len += len(p.last_phenomenal_report)
            if len(phen_samples) < 3:
                phen_samples.append((p.id, p.last_phenomenal_report))
    avg_phen_len = total_phen_len / agents_with_phen if agents_with_phen else 0.0

    inner_agents = [p for p in alive if p.inner_speech]
    total_inner_phrases = sum(len(p.inner_speech) for p in inner_agents)
    avg_inner_len = total_inner_phrases / len(alive) if alive else 0.0
    inner_samples = []
    for p in inner_agents[:3]:
        if p.inner_speech:
            last = p.inner_speech[-1]
            if isinstance(last, dict):
                txt = last.get('text', '')
            else:
                txt = str(last)
            inner_samples.append((p.id, txt))

    generator_stats = {
        'agents_with_phen': agents_with_phen,
        'total_phen_reports': total_phen_reports,
        'avg_phen_len': avg_phen_len,
        'phen_samples': phen_samples,
        'inner_agents_count': len(inner_agents),
        'total_inner_phrases': total_inner_phrases,
        'avg_inner_phrases_per_agent': avg_inner_len,
        'inner_samples': inner_samples,
    }

    # ---- СТАТИСТИКА МОРЗЕ ----
    total_sent = 0
    total_decoded = 0
    total_corrupted = 0
    total_uncertain = 0
    total_collisions = 0
    total_timeouts = 0
    total_energy = 0.0
    sum_conf = 0.0
    count_conf = 0
    unique_senders = 0
    sender_switches = 0
    agents_with_rx = 0

    for p in alive:
        if hasattr(p, '_morse_tx') and p._morse_tx is not None:
            total_sent += p._morse_tx.attempts
        if hasattr(p, '_morse_rx') and p._morse_rx is not None:
            agents_with_rx += 1
            rx_metrics = p._morse_rx.get_metrics()
            total_decoded += rx_metrics.get('decoded', 0)
            total_corrupted += rx_metrics.get('corrupted', 0)
            total_uncertain += rx_metrics.get('uncertain', 0)
            total_collisions += rx_metrics.get('collision', 0)
            total_timeouts += rx_metrics.get('timeout', 0)
            total_energy += rx_metrics.get('energy_received', 0.0)
            if rx_metrics.get('mean_confidence', 0.0) > 0:
                sum_conf += rx_metrics.get('mean_confidence', 0.0)
                count_conf += 1
            unique_senders += rx_metrics.get('unique_senders', 0)
            sender_switches += rx_metrics.get('sender_switches', 0)

    morse_stats = {
        'total_sent': total_sent,
        'total_decoded': total_decoded,
        'total_corrupted': total_corrupted,
        'total_uncertain': total_uncertain,
        'total_collisions': total_collisions,
        'total_timeouts': total_timeouts,
        'total_energy': total_energy,
        'avg_confidence': sum_conf / count_conf if count_conf else 0.0,
        'unique_senders': unique_senders,
        'sender_switches': sender_switches,
        'agents_with_rx': agents_with_rx,
    }

    # ДОБАВЛЕНО (аудит): статистика эмерджентного лексикона (Cell 13) --
    # раньше считалась в отдельной collect_morse_metrics(), которая нигде
    # не вызывалась из реального пайплайна отчёта. Перенесено сюда, где
    # отчёт её реально увидит. lexicon передаётся параметром из EvolutionEngine
    # (раньше читался как глобальный EMERGENT_LEXICON напрямую по имени).
    if lexicon is not None:
        _lens = list(lexicon.log_raw_lengths)
        if len(_lens) >= 20:
            _early = float(np.mean(_lens[: len(_lens) // 2]))
            _late = float(np.mean(_lens[len(_lens) // 2:]))
        else:
            _early = _late = float(np.mean(_lens)) if _lens else 0.0
        _active_clusters = sum(1 for v in lexicon.assoc.values() if np.linalg.norm(v) > 1e-3)
        morse_stats['lang_compression_ratio'] = (_late / _early) if _early > 1e-6 else 1.0
        # ИСПРАВЛЕНО (аудит рефакторинга): _early/_late считались, но никогда
        # не клались в morse_stats -- отчёт в Cell 4b (строка "Длина сигнала:
        # ранняя -> поздняя") ждёт именно эти ключи и молча их не печатал.
        morse_stats['lang_signal_len_early'] = _early
        morse_stats['lang_signal_len_late'] = _late
        morse_stats['lang_active_clusters'] = _active_clusters
        morse_stats['lang_total_clusters'] = len(lexicon.clusters)
        morse_stats['lang_collapsed'] = bool(_active_clusters <= 1 and len(lexicon.clusters) > 3)
        morse_stats['lang_dominant_labels'] = lexicon.dominant_meaning_labels()

        # ДОБАВЛЕНО (Cell 13 v4.0): диагностика кодека -- приём, отправка, точность.
        morse_stats['lang_rx_total'] = lexicon.rx_total
        morse_stats['lang_rx_null'] = dict(lexicon.rx_null)
        morse_stats['lang_rx_block_counts'] = dict(lexicon.rx_block_counts)
        morse_stats['lang_send_k_counts'] = dict(lexicon.send_k_counts)
        morse_stats['lang_send_silence'] = dict(lexicon.send_silence)
        morse_stats['lang_send_energy_spent'] = float(lexicon.send_energy_spent)
        # v4.2: события канала -- NAV, самоэхо, смешанные сессии, обрывы, приём по классам.
        morse_stats['chan'] = dict(getattr(lexicon, 'chan', {}))
        morse_stats['chan_params'] = {k: getattr(Config, k, None) for k in (
            'MORSE_DOT_LEN', 'MORSE_LISTEN_INTERVAL', 'LANG_PULSES_PER_AXIS_MAX',
            'MORSE_BROADCAST_RADIUS', 'MORSE_DECAY', 'MORSE_NAV_ENABLED', 'MORSE_NAV_RADIUS',
            'MORSE_SELF_EXCLUDE', 'MORSE_DROP_MIXED', 'MORSE_FREEZE_TX_CENTER',
            'MORSE_INTER_AXIS_GAP_MULT', 'MORSE_BLOCK_SEPARATOR_MULT',
            'MORSE_SIGNAL_END_MULT', 'MORSE_TRAILING_GAP', 'MORSE_BACKOFF_MAX')}
        _fid = list(lexicon.fidelity_log)
        if len(_fid) >= 10:
            morse_stats['lang_fidelity_early'] = float(np.mean(_fid[:len(_fid) // 2]))
            morse_stats['lang_fidelity_late'] = float(np.mean(_fid[len(_fid) // 2:]))
        else:
            morse_stats['lang_fidelity_early'] = morse_stats['lang_fidelity_late'] = None

        # ДОБАВЛЕНО: метрики обратной связи отправитель<->получатель (раньше
        # учился только получатель -- эти поля показывают, учится ли теперь
        # и отправитель, то есть сходится ли язык, а не только сжимается).
        morse_stats['lang_reinforcement_events'] = lexicon.reinforcement_events
        _reinf = list(lexicon.reinforcement_log)
        if len(_reinf) >= 10:
            morse_stats['lang_reinforcement_gap_early'] = float(np.mean(_reinf[:len(_reinf)//2]))
            morse_stats['lang_reinforcement_gap_late'] = float(np.mean(_reinf[len(_reinf)//2:]))
        else:
            morse_stats['lang_reinforcement_gap_early'] = morse_stats['lang_reinforcement_gap_late'] = None

        _div = list(lexicon.log_gene_diversity)
        if len(_div) >= 4:
            morse_stats['lang_gene_diversity_early'] = float(np.mean(_div[:len(_div)//2]))
            morse_stats['lang_gene_diversity_late'] = float(np.mean(_div[len(_div)//2:]))
        else:
            morse_stats['lang_gene_diversity_early'] = morse_stats['lang_gene_diversity_late'] = None

        # Концентрация "диалекта": для самого используемого кластера -- какая
        # доля его употреблений приходится на топ-1 отправителя. Высоко = это
        # приватный код одного агента, а не общий язык популяции.
        if lexicon.cluster_uses:
            _top_cid = max(lexicon.cluster_uses, key=lexicon.cluster_uses.get)
            _senders = lexicon.cluster_senders.get(_top_cid, {})
            _total_uses = sum(_senders.values())
            morse_stats['lang_top_cluster_uses'] = lexicon.cluster_uses[_top_cid]
            morse_stats['lang_top_cluster_unique_senders'] = len(_senders)
            morse_stats['lang_top_cluster_concentration'] = (
                max(_senders.values()) / _total_uses if _total_uses else 0.0)

    # ============================================================
    # БЛОК ПОДСОЗНАНИЯ — добавляем метрики в результирующий словарь
    # ============================================================
    if Config.ENABLE_UNCONSCIOUS and alive:
        gut_feelings = [getattr(p, '_unconscious', {}).get('gut_feeling', 0.0) for p in alive]
        avg_gut = float(np.mean(gut_feelings)) if gut_feelings else 0.0

        needs = [getattr(p, '_unconscious', {}).get('latent_need', 'none') for p in alive]
        need_counts = {n: needs.count(n) for n in set(needs)}

        anticipations = [getattr(p, '_unconscious', {}).get('anticipation', 0.0) for p in alive]
        avg_antic = float(np.mean(anticipations)) if anticipations else 0.0

        drive_dists = []
        for p in alive:
            uc = getattr(p, '_unconscious', {})
            dt = uc.get('drive_towards')
            if dt is not None and p.cells:
                cx, cy = p._get_center_cell()
                drive_dists.append(float(np.hypot(cx - dt[0], cy - dt[1])))
        avg_drive = float(np.mean(drive_dists)) if drive_dists else 0.0

        insights = sum(p.event_counts.get('unconscious_insight', 0) for p in alive)
        goals_uc = sum(p.event_counts.get('unconscious_goal', 0) for p in alive)

        # Подсознательные концепты
        uc_concepts = 0
        uc_agents = 0
        for p in alive:
            has_uc = False
            for sig in p.concept_graph.nodes:
                if isinstance(sig, tuple) and len(sig) >= 4 and 'unconscious_insight' in str(sig[3]):
                    uc_concepts += 1
                    has_uc = True
            if has_uc:
                uc_agents += 1
    else:
        avg_gut = 0.0
        need_counts = {}
        avg_antic = 0.0
        avg_drive = 0.0
        insights = 0
        goals_uc = 0
        uc_concepts = 0
        uc_agents = 0

    # ============================================================
    # ФОРМИРУЕМ И ВОЗВРАЩАЕМ СЛОВАРЬ
    # ============================================================
    return {
        't': t,
        'patterns': len(alive),
        'lineages': lineages,
        'err': err,
        'soul': soul,
        'binding': binding,
        'echo': 0,
        'signals': np.zeros(6),
        'states': states,
        'intents': intents,
        'epi_scar': epi_scar,
        'unique_concepts': len(all_concepts),
        'stagnation_ratio': stagnation_ratio,
        'divisions_possible': divisions_possible,
        'arc_completions': total_arcs,
        'folds': total_folds,
        'avg_trust': avg_trust,
        'high_trust_pairs': high_pairs,
        'trust_distribution': trust_dist,
        'disorganizer_count': disorg,
        'redeemed_count': redm,
        'quarantined_count': quar,
        'deterministic_redemptions': det_red,
        'phenomenal_binding_avg': phenomenal_binding_avg,
        'state_emotion_mismatch': mismatch_ratio,
        'forced_collapses': collapsed,
        'myth_pool_size': 0,
        'triadic_alive': triadic_alive_count,
        'triadic_alive_ratio': triadic_alive_ratio,
        'avg_internal_gap': avg_internal_gap,
        'max_internal_gap': max_internal_gap,
        'zero_internal_gap_agents': zero_internal_gap,
        'avg_obs_gap': avg_obs_gap,
        'max_obs_gap': max_obs_gap,
        'tremor_targets': tremor_targets,
        'avg_coherence_with_gap': avg_coherence_with_gap,
        'love_pairs': love_pairs // 2,
        'avg_soma': avg_soma,
        'mem_agents': mem_agents,
        'avg_buf_len': avg_buf_len,
        'total_recalled': total_recalled,
        'concept_adopted': concept_adopted,
        'deep_concept_adopted': deep_concept_adopted,
        'deep_exchange': deep_exchange,
        'wisdom_shared': wisdom_shared,
        'avg_signal_memory': avg_signal_memory,
        'intentional_signal_agents': intentional_signal_count,
        'top_signal_pairs': signal_types_used,
        'lineage_count': lineage_count,
        'avg_lineage_age': avg_lineage_age,
        'max_lineage_age': max_lineage_age,
        'ancient_lineages': ancient_lineages,
        'max_lineage_total_age': max_lineage_total_age,
        'divisions_total': divisions_total,
        'avg_field_unknown': avg_field_unknown,
        'avg_field_binding': avg_field_binding,
        'narrative_agents': narrative_agents,
        'teaching_events': teaching_events,
        'learning_events': learning_events,
        'dream_consolidations': dream_consolidations,
        'nightmare_consolidations': nightmare_consolidations,
        'nightmares_transformed': nightmares_transformed,
        'agents_with_nightmare': agents_with_nightmare,
        'agents_with_dream_memory': agents_with_dream_memory,
        'avg_endurance': avg_endurance,
        'endurance_critical': endurance_critical,
        'divide_blocked_fatigue': divide_blocked_fatigue,
        'blind': blind,
        'confused': confused,
        'adapting': adapting,
        'clear': clear,
        'avg_social_crisis': float(social_avg[0]),
        'avg_social_invitation': float(social_avg[1]),
        'avg_social_grief': float(social_avg[2]),
        'avg_social_cooperate': float(social_avg[3]),
        'avg_social_explore': float(social_avg[4]),
        'avg_social_seek_help': float(social_avg[5]),
        'avg_social_scar': float(social_avg[6]),
        'avg_social_rest': float(social_avg[7]),
        'avg_social_resonance': float(social_avg[8]),
        'avg_social_btype': float(social_avg[9]),
        'avg_social_alarm': float(social_avg[10]),
        'avg_social_beauty': float(social_avg[11]) if len(social_avg) > 11 else 0.0,
        'avg_social_rhythm': float(social_avg[12]) if len(social_avg) > 12 else 0.0,
        'avg_social_interest': float(social_avg[13]) if len(social_avg) > 13 else 0.0,
        'avg_social_memory': float(social_avg[14]) if len(social_avg) > 14 else 0.0,
        'avg_social_silence': float(social_avg[15]) if len(social_avg) > 15 else 0.0,
        'vocab_concepts': vocab_concepts,
        'blind_events': blind_events,
        'concept_anticipations': concept_anticipations,
        'vocab_events': vocab_events,
        'avg_action_feedback': avg_action_feedback,
        'avg_social_warmth': avg_social_warmth,
        'substate_counts': substate_counts,
        'total_transitions': total_transitions,
        'top_transitions': top_transitions,
        'archive_concept_agents': agents_with_archive,
        'total_archive_concepts': total_archive,
        'archive_types': archive_types,
        'total_introspect': total_introspect,
        'avg_introspect': avg_introspect,
        'max_introspect': max_introspect,
        'reflection_quality': reflection_quality,
        'ethical_coherence': ethical_coherence,
        'global_concept_entropy': global_concept_entropy,
        'introspection_synchrony': introspection_synchrony,
        'narrative_continuity': narrative_continuity,
        'unconquered_count': unconquered_count,
        'unconquered_wise': unconquered_wise,
        'unconquered_rebel': unconquered_rebel,
        'avg_unconquered_str': avg_unconquered_str,
        'sovereignty_field_avg': sovereignty_field_avg,
        'reentry_avg': reentry_avg,
        'reentry_max': reentry_max,
        'reentry_var': reentry_var,
        'meta_reentry_active': meta_reentry_active,
        'introspect_driven_by_sensation': introspect_driven_by_sensation,
        'feral_count': feral_count,
        'avg_feral_fury': avg_feral_fury,
        'feral_kills': feral_kills,
        'avg_phi': avg_phi,
        'gene_carriers': gene_carriers,
        'gene_carrier_counts': gene_carrier_counts,
        'generator': generator_stats,
        'morse': morse_stats,
        # ДОБАВЛЕНО (аудит): видимость новых подключённых механизмов в отчёте.
        'lang_compression_ratio': morse_stats.get('lang_compression_ratio', 1.0),
        'lang_active_clusters': morse_stats.get('lang_active_clusters', 0),
        'lang_total_clusters': morse_stats.get('lang_total_clusters', 0),
        'lang_collapsed': morse_stats.get('lang_collapsed', False),
        'morse_concepts': sum(p.event_counts.get('morse_concept_formed', 0) for p in alive),
        'spontaneous_field_emergence': sum(p.event_counts.get('spontaneous_field_emergence', 0) for p in alive),
        'marked_for_fall_count': sum(p.event_counts.get('marked_for_fall', 0) for p in alive),
        # ---- ПОДСОЗНАНИЕ ----
        'avg_gut_feeling': avg_gut,
        'latent_need_counts': need_counts,
        'unconscious_insights': insights,
        'unconscious_goals': goals_uc,
        'avg_anticipation': avg_antic,
        'avg_drive_distance': avg_drive,
        'unconscious_concept_agents': uc_agents,
        'total_unconscious_concepts': uc_concepts,
    }

print("✅ Cell 4a loaded: ИСПРАВЛЕНЫ баг метрики blind, IndexError, защита current_social, добавлена статистика генератора речи, Морзе и подсознания")


# === САМОРЕГУЛЯЦИЯ: метрики (совмещено с Cell 4a, отдельной ячейки нет) ===
def collect_sr_metrics(patterns):
    """Сбор метрик саморегуляции по всем уровням."""
    alive = [p for p in patterns if p.alive]
    if not alive or not getattr(Config, 'ENABLE_SELF_REGULATION', False):
        return {}
    def _s(attr, default=0):
        return sum(getattr(p, attr, default) for p in alive)
    def _avg(attr, default=0.5):
        vals = [getattr(p, attr, default) for p in alive]
        return safe_mean(vals, default) if vals else default

    return {
        # Уровень 1: Медитация
        'sr_meditations': _s('_sr_meditation_count'),
        # Уровень 1.5/8: Целевая саморегуляция
        'sr_goals_replaced': _s('_sr_goals_replaced'),
        # Уровень 10: Рефлексивные пороги
        'sr_thresholds_adjusted': _s('_sr_thresholds_adjusted'),
        'sr_avg_grief_thr': _avg('_sr_grief_threshold'),
        'sr_avg_alarm_thr': _avg('_sr_alarm_threshold'),
        # Уровень 2: Голосование
        'sr_proposals_made': _s('_sr_proposals_made'),
        'sr_votes_cast': _s('_sr_votes_cast'),
        'sr_proposals_passed': _s('_sr_proposals_passed'),
        'sr_pending_proposals': len(getattr(alive[0].world, 'sr_proposals', {})) if alive[0].world else 0,
        # Уровень 2.5/9: Нормотворчество
        'sr_norms_inferred': _s('_sr_norms_inferred'),
        # Уровень 3: Конфликты через диалог
        'sr_conflicts_resolved': _s('_sr_conflicts_resolved'),
        # Уровень 4: Экономика доверия
        'sr_trades_done': _s('_sr_trades_done'),
        # Уровень 5: Конституция
        'sr_constitutions': sum(1 for p in alive if getattr(p, '_sr_constitution', [])),
        'sr_total_rules': sum(len(getattr(p, '_sr_constitution', [])) for p in alive),
        # Уровень 6: Самомодификация генов
        'sr_gene_mutations': _s('_sr_gene_mutations'),
        # Уровень 7: Экологическая саморегуляция
        'sr_field_heals': _s('_sr_field_heals'),
    }

print("✅ Саморегуляция: collect_sr_metrics() добавлена в Cell 4a")


# ============================================================
# v4.2: ОТПЕЧАТОК СОСТОЯНИЯ ПРОГОНА. Один seed + одно стартовое состояние
# должны давать один и тот же отпечаток. Печатается в отчёте Cell 4b: после
# двух прогонов видно сразу, воспроизводим ли мир, без отдельного теста.
# ============================================================
def state_fingerprint(engine):
    import zlib
    f = zlib.crc32(np.ascontiguousarray(engine.field).tobytes())
    h = 0
    for p in engine.patterns:
        for k, v in vars(p).items():
            if isinstance(v, np.generic):
                v = v.item()
            if isinstance(v, (bool, int, float)):
                h = zlib.crc32(repr((p.id, k, v)).encode(), h)
    return {'field_crc': f, 'agents_crc': h, 'n_patterns': len(engine.patterns),
            'alive': sum(1 for p in engine.patterns if p.alive),
            'age': int(getattr(engine, 'age', -1))}
