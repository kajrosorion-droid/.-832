# MASTER OBSERVATORY v0.1.6
# ============================================================================
# READ-ONLY: читает rich_log + ledger, симуляцию НЕ запускает и НЕ меняет.
#
# Основные правки относительно v0.1.2:
# - .prev теперь реально валидируется (valid / malformed / missing), без падения.
# - A: input_fp/input fingerprint показываются явно, если присутствуют.
# - D: добавлены Shannon H(utterance), H(emotion), H(intent) по окнам.
# - E1: убран термин "verbatim response"; это association window.
# - E2/E8: явно разделены observed / eligible / matched / analysed;
#        разрешение state-response = SNAPSHOT_EVERY, а не 1 тик.
# - E2/E8: не создают видимость causal proof.
# - E6: neighbor correlations считаются global и по окнам.
# - E7: counter coverage + monotonicity + per-agent maxima.
# - K: сохраняется coverage проверенных events и ограничения.
# - сохранение master JSON атомарное.
# ============================================================================

import json
import os
import math
import time
from collections import Counter, defaultdict

import numpy as np


MASTER_VERSION = "0.1.6"
SNAPSHOT_EVERY = 10
RECORD_CAP = 400_000
W_MAX = 15
W = 100
DIR = "/content/drive/MyDrive/832_ledgers"
def _master_json_for(log_path):
    base = os.path.basename(log_path)
    if base.endswith(".json"):
        base = base[:-5]
    return f"{DIR}/master_{base}.json"


# ----------------------------------------------------------------------------
# SERIALIZATION / BASIC STATS
# ----------------------------------------------------------------------------
def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, set):
        return list(o)
    if isinstance(o, tuple):
        return list(o)
    if isinstance(o, defaultdict):
        return dict(o)
    raise TypeError(f"несериализуемо: {type(o).__name__}")


def _sanitize_json(obj):
    """Convert non-finite floats to None so JSON remains strict-valid."""
    if isinstance(obj, dict):
        return {k: _sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_json(v) for v in obj]
    if isinstance(obj, (float, np.floating)):
        return float(obj) if np.isfinite(float(obj)) else None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, set):
        return [_sanitize_json(v) for v in obj]
    if isinstance(obj, defaultdict):
        return _sanitize_json(dict(obj))
    return obj


def _safe_load(path):
    if not path or not os.path.exists(path):
        return None, {"error": "missing", "path": path}
    size = os.path.getsize(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), {"size": size, "ok": True}
    except json.JSONDecodeError as e:
        return None, {
            "error": "decode",
            "size": size,
            "pos": e.pos,
            "msg": str(e)[:180],
        }
    except Exception as e:
        return None, {"error": "io", "size": size, "msg": str(e)[:180]}


def _stat(vals):
    v = []
    for x in vals:
        if x is None:
            continue
        if not isinstance(x, (int, float, np.integer, np.floating)):
            continue
        if not np.isfinite(float(x)):
            continue
        v.append(float(x))
    if not v:
        return {"n": 0, "value": None}
    a = np.asarray(v, dtype=float)
    return {
        "n": int(len(a)),
        "value": float(a.mean()),
        "p10": float(np.percentile(a, 10)),
        "p50": float(np.percentile(a, 50)),
        "p90": float(np.percentile(a, 90)),
        "min": float(a.min()),
        "max": float(a.max()),
        "mean": float(a.mean()),
    }


def _frac(bools):
    v = [bool(b) for b in bools if b is not None]
    if not v:
        return {"n": 0, "value": None}
    return {
        "n": len(v),
        "value": sum(v) / len(v),
    }


def _ss(st):
    if not st or st.get("n", 0) == 0:
        return "n/a"
    if "p50" in st and st.get("p50") is not None:
        return (
            f"p10={st['p10']:.3f} "
            f"p50={st['p50']:.3f} "
            f"p90={st['p90']:.3f} "
            f"(n={st['n']})"
        )
    if st.get("value") is not None:
        return f"{st['value']:.3f} (n={st['n']})"
    return f"n={st['n']}"


def _pm(v, n=None):
    if v is None:
        return "n/a"
    try:
        s = f"{float(v):.3f}"
    except Exception:
        return str(v)
    return s + (f" (n={n})" if n is not None else "")


def _corr(a, b):
    pairs = []
    for x, y in zip(a, b):
        if not isinstance(x, (int, float, np.integer, np.floating)):
            continue
        if not isinstance(y, (int, float, np.integer, np.floating)):
            continue
        x = float(x)
        y = float(y)
        if not np.isfinite(x) or not np.isfinite(y):
            continue
        pairs.append((x, y))
    if len(pairs) < 5:
        return {"n": len(pairs), "r": None}
    xa = np.asarray([p[0] for p in pairs], dtype=float)
    ya = np.asarray([p[1] for p in pairs], dtype=float)
    if xa.std() < 1e-9 or ya.std() < 1e-9:
        return {"n": len(pairs), "r": None}
    return {"n": len(pairs), "r": float(np.corrcoef(xa, ya)[0, 1])}


def _entropy(counter):
    n = sum(counter.values())
    if n <= 0:
        return None
    return float(
        -sum((c / n) * math.log2(c / n) for c in counter.values() if c > 0)
    )


def _window_index(t):
    return int(t) // W


# ----------------------------------------------------------------------------
# MATCHING
# ----------------------------------------------------------------------------
def _match_pairs(speaks, w_max=W_MAX):
    """
    Association only:
    A->B followed by B->A within <= w_max ticks.
    This is NOT proof that B's utterance is a direct causal response to A.
    """
    sp = [
        s for s in speaks
        if s.get("to") not in (None, -1) and s.get("utt")
    ]
    by_pair = defaultdict(list)
    for s in sp:
        by_pair[(s["pid"], s["to"])].append(s)

    pairs = []
    used = defaultdict(set)

    for (A, B), a_list in by_pair.items():
        b_list = sorted(
            by_pair.get((B, A), []),
            key=lambda s: s.get("t", 0),
        )
        for a_s in sorted(a_list, key=lambda s: s.get("t", 0)):
            tA = a_s.get("t", 0)
            for b_s in b_list:
                tB = b_s.get("t", 0)
                if tB <= tA:
                    continue
                if tB - tA > w_max:
                    break
                if tB in used[(B, A)]:
                    continue
                used[(B, A)].add(tB)
                pairs.append({
                    "tA": tA,
                    "A": a_s["pid"],
                    "B": b_s["pid"],
                    "tB": tB,
                    "dt": tB - tA,
                    "utt_A": list(a_s["utt"]),
                    "utt_B": list(b_s["utt"]),
                    "st_A": a_s.get("st"),
                    "st_B": b_s.get("st"),
                })
                break
    return pairs


# ----------------------------------------------------------------------------
# DIALOGUE COUNTER DEDUP
# ----------------------------------------------------------------------------
def _dedup_dlg_stats(snaps):
    """
    Existing dlg_stats are treated as cumulative counters.
    We retain max-per-agent, but explicitly report:
      - agents seen per field
      - snapshot observations per field
      - non-monotonic decreases
    """
    best = defaultdict(lambda: defaultdict(float))
    last = defaultdict(dict)
    coverage = defaultdict(lambda: {
        "agents": set(),
        "observations": 0,
        "non_monotonic": 0,
    })

    for s in snaps:
        ds = s.get("dlg_stats")
        if not isinstance(ds, dict):
            continue
        pid = s.get("id")
        if pid is None:
            continue

        for k, v in ds.items():
            if not isinstance(v, (int, float, np.integer, np.floating)):
                continue
            v = float(v)
            coverage[k]["agents"].add(pid)
            coverage[k]["observations"] += 1

            if k in last[pid] and v < last[pid][k]:
                coverage[k]["non_monotonic"] += 1
            last[pid][k] = v

            if v > best[pid][k]:
                best[pid][k] = v

    out_cov = {}
    for k, c in coverage.items():
        out_cov[k] = {
            "agents": len(c["agents"]),
            "observations": c["observations"],
            "non_monotonic": c["non_monotonic"],
        }
    return best, out_cov


# ----------------------------------------------------------------------------
# RAW INVENTORY
# ----------------------------------------------------------------------------
def raw_inventory(log_raw, ledger_raw):
    inv = {}
    inv["log_header_keys"] = sorted(log_raw.get("header", {}).keys())
    inv["log_top_keys"] = sorted(log_raw.keys())

    for coll in (
        "tick_rows",
        "agent_snaps",
        "events",
        "speaks",
        "dialogues",
        "cluster_births",
    ):
        arr = log_raw.get(coll, [])
        inv[f"{coll}_len"] = len(arr)
        if arr:
            first = arr[0]
            if isinstance(first, dict):
                inv[f"{coll}_keys"] = sorted(first.keys())
            else:
                inv[f"{coll}_type"] = type(first).__name__

    snaps = log_raw.get("agent_snaps", [])
    if snaps:
        nested = set()
        for s in snaps[:100]:
            if isinstance(s.get("dlg_stats"), dict):
                nested.update(s["dlg_stats"].keys())
        inv["agent_snaps_dlg_stats_keys"] = sorted(nested)

    if ledger_raw:
        inv["ledger_header_keys"] = sorted(ledger_raw.get("header", {}).keys())
        inv["ledger_top_keys"] = sorted(ledger_raw.keys())
        lrows = ledger_raw.get("rows", [])
        if lrows and isinstance(lrows[0], dict):
            inv["ledger_rows_keys"] = sorted(lrows[0].keys())
            ev_keys = set()
            for r in lrows[:100]:
                if isinstance(r.get("ev"), dict):
                    ev_keys.update(r["ev"].keys())
            inv["ledger_rows_ev_keys"] = sorted(ev_keys)
        llife = ledger_raw.get("lifecycle", {})
        if isinstance(llife, dict):
            first = next(iter(llife.values()), None)
        elif isinstance(llife, list):
            first = llife[0] if llife else None
        else:
            first = None
        inv["ledger_lifecycle_type"] = (
            "dict" if isinstance(llife, dict)
            else "list" if isinstance(llife, list)
            else type(llife).__name__
        )
        inv["ledger_lifecycle_keys"] = (
            sorted(first.keys()) if isinstance(first, dict) else []
        )
    return inv


def print_inventory(inv):
    print("\n" + "-" * 78)
    print("[RAW INVENTORY]")
    for k, v in inv.items():
        if isinstance(v, list) and len(v) > 30:
            print(f"  {k}: [{len(v)} keys] {v[:30]}...")
        else:
            print(f"  {k}: {v}")


# ----------------------------------------------------------------------------
# A — IDENTITY
# ----------------------------------------------------------------------------
def _first_present(*dicts, keys):
    for d in dicts:
        if not isinstance(d, dict):
            continue
        for k in keys:
            if d.get(k) is not None:
                return d.get(k)
    return None


def sec_A_identity(log_raw, ledger_raw, cov):
    h = log_raw.get("header", {})
    lh = ledger_raw.get("header", {}) if ledger_raw else {}
    lrows = ledger_raw.get("rows", []) if ledger_raw else []

    tag = h.get("tag")
    if tag is None and h.get("seed") is not None:
        tag = f"seed{h['seed']}_steps{h.get('steps')}"

    input_fp = _first_present(
        h, lh,
        keys=("input_fp", "input_fingerprint", "input_hash", "world_input_fp"),
    )

    return {
        "tag": tag,
        "seed": h.get("seed"),
        "steps": h.get("steps"),
        "mult": h.get("mult"),
        "wall_seconds": h.get("wall_seconds"),
        "complete": h.get("complete"),
        "empathy_pull_override": h.get("empathy_pull_override"),
        "neighbor_sync_override": h.get("neighbor_sync_override"),
        "content_response_enabled": h.get("content_response_enabled", "n/a"),
        "config_hash": lh.get("config_hash", h.get("config_hash")),
        "input_fp": input_fp if input_fp is not None else "MISSING",
        "overrides": lh.get("overrides", h.get("overrides")),
        "chain_first": lrows[0].get("chain") if lrows else None,
        "chain_last": lrows[-1].get("chain") if lrows else None,
        "final_n": lrows[-1].get("n") if lrows else None,
        "ledger_found": ledger_raw is not None,
        "log_size": cov.get("size"),
    }


# ----------------------------------------------------------------------------
# B — COVERAGE
# ----------------------------------------------------------------------------
def sec_B_coverage(log_raw, ledger_raw, prev_path):
    snaps = log_raw.get("agent_snaps", [])
    events = log_raw.get("events", [])
    speaks = log_raw.get("speaks", [])
    dialogues = log_raw.get("dialogues", [])
    rows_log = log_raw.get("tick_rows", [])
    rows_led = ledger_raw.get("rows", []) if ledger_raw else []

    ticks_expected = log_raw.get("header", {}).get("steps", 0)
    ticks_log = len(rows_log)
    ticks_led = len(rows_led)

    snap_ticks_expected = set(range(0, ticks_expected, SNAPSHOT_EVERY))
    snap_ticks_actual = {
        s.get("t") for s in snaps if s.get("t") is not None
    }
    snaps_expected = sum(
        r.get("n", 0)
        for r in rows_led
        if r.get("t") in snap_ticks_expected
    )
    snaps_missing = sorted(
        snap_ticks_expected - snap_ticks_actual
    )[:20]

    nan_fields = [
        "uc", "drag", "tension", "scar", "grief", "grat", "gap",
        "nbr", "nbrN", "feral_near", "bind_loc", "body_mem",
    ]
    nan_frac = {}
    for f in nan_fields:
        vals = [s.get(f) for s in snaps if f in s]
        if not vals:
            continue
        nn = sum(
            1 for v in vals
            if v is None or (
                isinstance(v, float) and not np.isfinite(v)
            )
        )
        nan_frac[f] = round(nn / len(vals), 4)

    sp_dir = sum(
        1 for s in speaks if s.get("to") not in (None, -1)
    )
    dir_frac = sp_dir / max(len(speaks), 1)

    capped = {
        k: len(log_raw.get(k, [])) >= RECORD_CAP
        for k in ("events", "dialogues", "speaks")
    }

    prev_info = {
        "path": prev_path,
        "exists": bool(prev_path and os.path.exists(prev_path)),
    }
    if prev_info["exists"]:
        prev_raw, prev_load = _safe_load(prev_path)
        prev_info.update({
            "size": prev_load.get("size"),
            "status": "valid" if prev_raw is not None else prev_load.get("error"),
            "decode_pos": prev_load.get("pos"),
            "message": prev_load.get("msg"),
        })

    return {
        "ticks_expected": ticks_expected,
        "ticks_log": ticks_log,
        "ticks_ledger": ticks_led,
        "snaps_recorded": len(snaps),
        "snap_ticks_expected": len(snap_ticks_expected),
        "snap_ticks_actual": len(snap_ticks_actual),
        "snaps_expected_approx": snaps_expected,
        "snap_ticks_missing": snaps_missing,
        "events": len(events),
        "speaks": len(speaks),
        "dialogues": len(dialogues),
        "directed_speaks_frac": round(dir_frac, 4),
        "nan_frac_by_field": nan_frac,
        "capped": capped,
        "log_errors": log_raw.get("errors", {}),
        "prev": prev_info,
    }


# ----------------------------------------------------------------------------
# C — POPULATION
# ----------------------------------------------------------------------------
def sec_C_population(ledger_raw):
    if not ledger_raw:
        return {"n/a": "ledger не найден"}

    rows = ledger_raw.get("rows", [])
    life = ledger_raw.get("lifecycle", {})
    if not rows:
        return {"n/a": "rows пусто"}

    # lifecycle может быть dict {pid: rec} или list[rec] -- нормализуем
    if isinstance(life, dict):
        life_records = list(life.values())
    elif isinstance(life, list):
        life_records = life
    else:
        life_records = []

    ns = [r.get("n", 0) for r in rows]
    deaths = [
        r for r in life_records
        if isinstance(r, dict) and r.get("death_t") is not None
    ]
    births_tot = sum(r.get("births", 0) for r in rows)
    deaths_tot = sum(r.get("deaths", 0) for r in rows)
    divs_tot = sum(r.get("divisions", 0) for r in rows)

    causes = Counter(r.get("death_cause") for r in deaths)
    ages = [
        r.get("age_at_death")
        for r in deaths
        if r.get("age_at_death") is not None
    ]
    agent_ticks = sum(ns)

    return {
        "n_start": ns[0],
        "n_min": min(ns),
        "n_max": max(ns),
        "n_end": ns[-1],
        "births": births_tot,
        "deaths": deaths_tot,
        "divisions": divs_tot,
        "agent_ticks": agent_ticks,
        "deaths_per_1000_at": round(
            1000 * deaths_tot / max(agent_ticks, 1), 2
        ),
        "divisions_per_1000_at": round(
            1000 * divs_tot / max(agent_ticks, 1), 2
        ),
        "causes_top": dict(causes.most_common(10)),
        "age_at_death": _stat(ages),
        "was_subject": sum(1 for r in deaths if r.get("was_subject")),
        "was_narrative": sum(1 for r in deaths if r.get("was_narrative")),
        "protection_above_thr_at_death": sum(
            1 for r in deaths
            if (r.get("protection_before_tick") or 0) > 0.2
        ),
    }


# ----------------------------------------------------------------------------
# D — COMMUNICATION + ENTROPY
# ----------------------------------------------------------------------------
def sec_D_communication(log_raw):
    speaks = log_raw.get("speaks", [])
    dialogues = log_raw.get("dialogues", [])
    births = log_raw.get("cluster_births", [])
    tick_rows = log_raw.get("tick_rows", [])

    uniq = Counter(
        tuple(s.get("utt") or [])
        for s in speaks
        if s.get("utt")
    )
    top10 = uniq.most_common(10)

    recipients = {
        s.get("to")
        for s in speaks
        if s.get("to") not in (None, -1)
    }
    senders = {
        s["pid"]
        for s in speaks
        if s.get("utt")
    }

    nw = (
        (tick_rows[-1]["t"] // W + 1)
        if tick_rows else
        (
            max((s.get("t", 0) for s in speaks), default=-1) // W + 1
            if speaks else 0
        )
    )

    by_window = []
    for w in range(nw):
        sw = [
            s for s in speaks
            if w * W <= s.get("t", -1) < (w + 1) * W
            and s.get("utt")
        ]
        dw = [
            d for d in dialogues
            if w * W <= d.get("t", -1) < (w + 1) * W
        ]

        emo = Counter(
            s["utt"][1]
            for s in sw
            if len(s["utt"]) > 1
        )
        intn = Counter(
            s["utt"][2]
            for s in sw
            if len(s["utt"]) > 2
        )
        utt_counter = Counter(tuple(s["utt"]) for s in sw)
        ext = Counter(
            s["utt"][3] if len(s["utt"]) > 3 else None
            for s in sw
        )

        by_window.append({
            "w": w,
            "speaks": len(sw),
            "speakers": len({s["pid"] for s in sw}),
            "dialogues": len(dw),
            "GRIEF": emo.get("GRIEF", 0),
            "JOY": emo.get("JOY", 0),
            "CALM": emo.get("CALM", 0),
            "SEEK": intn.get("SEEK", 0),
            "HELP": intn.get("HELP", 0),
            "ANSWER": sum(
                1 for s in sw if "ANSWER" in s["utt"]
            ),
            "KNOT": ext.get("KNOT", 0),
            "GAP": ext.get("GAP", 0),
            "DRAG": ext.get("DRAG", 0),
            "unique_utterances": len(utt_counter),
            "H_utterance": _entropy(utt_counter),
            "H_emotion": _entropy(emo),
            "H_intent": _entropy(intn),
        })

    fid_by_w = {}
    for r in tick_rows:
        w = r["t"] // W
        fid_by_w.setdefault(w, []).append(r.get("fidelity"))

    fid = {}
    for w, v in fid_by_w.items():
        vv = [
            float(x) for x in v
            if isinstance(x, (int, float)) and np.isfinite(float(x))
        ]
        fid[w] = sum(vv) / len(vv) if vv else None

    return {
        "speaks": len(speaks),
        "dialogues": len(dialogues),
        "unique_utterances": len(uniq),
        "top10_utt": top10,
        "speakers": len(senders),
        "recipients": len(recipients),
        "only_speak": len(senders - recipients),
        "only_listen": len(recipients - senders),
        "clusters": len(births),
        "by_window": by_window,
        "fidelity_by_window": fid,
        "n_windows": nw,
    }


# ----------------------------------------------------------------------------
# E1 — ASSOCIATION WINDOW, NOT "VERBATIM RESPONSE"
# ----------------------------------------------------------------------------
def sec_E1_grief_response(pairs, log_raw):
    speaks = log_raw.get("speaks", [])
    nw = (
        max((s.get("t", 0) for s in speaks), default=-1) // W + 1
        if speaks else 0
    )

    def _calc(pp):
        if not pp:
            return {
                "n": 0,
                "calm": 0,
                "grief": 0,
                "rate_calm": None,
                "rate_grief": None,
            }
        n_calm = sum(
            1 for p in pp
            if len(p["utt_B"]) > 1 and p["utt_B"][1] == "CALM"
        )
        n_grief = sum(
            1 for p in pp
            if len(p["utt_B"]) > 1 and p["utt_B"][1] == "GRIEF"
        )
        return {
            "n": len(pp),
            "calm": n_calm,
            "grief": n_grief,
            "rate_calm": n_calm / len(pp),
            "rate_grief": n_grief / len(pp),
        }

    with_grief_a = [
        p for p in pairs
        if len(p["utt_A"]) > 1 and p["utt_A"][1] == "GRIEF"
    ]
    without_grief_a = [
        p for p in pairs
        if len(p["utt_A"]) > 1 and p["utt_A"][1] != "GRIEF"
    ]

    by_w = []
    for w in range(nw):
        wp = [
            p for p in pairs
            if w * W <= p["tA"] < (w + 1) * W
        ]
        wg = [
            p for p in wp
            if len(p["utt_A"]) > 1 and p["utt_A"][1] == "GRIEF"
        ]
        wo = [
            p for p in wp
            if len(p["utt_A"]) > 1 and p["utt_A"][1] != "GRIEF"
        ]
        by_w.append({
            "w": w,
            "grief": _calc(wg),
            "other": _calc(wo),
        })

    dt = [p["dt"] for p in with_grief_a]
    return {
        "definition": "A->B followed by B->A within W_MAX ticks; association only",
        "w_max": W_MAX,
        "global": {
            "grief_a": _calc(with_grief_a),
            "other_a": _calc(without_grief_a),
        },
        "grief_response_delay": _stat(dt),
        "by_window": by_w,
        "n_windows": nw,
    }


# ----------------------------------------------------------------------------
# E2 / E8 — STATE RESPONSE DIAGNOSTIC
# ----------------------------------------------------------------------------
def sec_E_state_response(log_raw, horizons=(10, 20), only_grief_a=False):
    """
    Diagnostic only.

    IMPORTANT:
      - state resolution is SNAPSHOT_EVERY ticks;
      - this cannot establish a 1-5 tick response;
      - treatment/control are matched observationally;
      - control is nearest in state at t_snap among agents with no directed
        communication in the future diagnostic window;
      - one recipient is counted once per snapshot bin.
    """
    snaps = log_raw.get("agent_snaps", [])
    speaks = log_raw.get("speaks", [])

    meta = {
        "state_resolution_ticks": SNAPSHOT_EVERY,
        "exact_1_5_tick_response_available": False,
        "causal_claim": False,
        "control_rule": (
            "nearest same-t_snap state; candidate has no directed communication "
            "in [t_snap, t_snap+max_h]; pool size is reported"
        ),
        "selection_unit": "(t_snap, recipient)",
    }

    if not snaps or not speaks:
        return {"meta": meta, "n/a": "нет снапшотов или speaks"}

    by_t = defaultdict(dict)
    for s in snaps:
        if all(k in s for k in ("grief", "grat", "uc")):
            by_t[s["t"]][s["id"]] = (
                s["grief"], s["grat"], s["uc"]
            )

    directed_at = defaultdict(set)
    for s in speaks:
        if s.get("to") not in (None, -1):
            directed_at[s["t"]].add(s["pid"])
            directed_at[s["t"]].add(s["to"])

    def has_dir(pid, t0, t1):
        return any(
            pid in directed_at.get(t, set())
            for t in range(t0, t1 + 1)
        )

    max_h = max(horizons)
    treat = {
        h: {"grief": [], "grat": [], "uc": []}
        for h in horizons
    }
    ctrl = {
        h: {"grief": [], "grat": [], "uc": []}
        for h in horizons
    }

    observed = 0
    eligible = 0
    matched = 0
    duplicates = 0
    no_control = 0
    control_pool_sizes = []
    analysed_by_h = Counter()
    seen = set()

    for s in speaks:
        if s.get("to") in (None, -1):
            continue

        if only_grief_a:
            if not s.get("utt") or len(s["utt"]) < 2:
                continue
            if s["utt"][1] != "GRIEF":
                continue

        observed += 1
        rec = s["to"]
        t_ev = s["t"]
        t_snap = (t_ev // SNAPSHOT_EVERY) * SNAPSHOT_EVERY

        if t_snap not in by_t or rec not in by_t[t_snap]:
            continue
        eligible += 1

        key = (t_snap, rec)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)

        pre = np.asarray(by_t[t_snap][rec], dtype=float)

        candidates = []
        for cand, vec in by_t[t_snap].items():
            if cand == rec:
                continue
            if has_dir(cand, t_snap, t_snap + max_h):
                continue
            candidates.append((cand, vec))

        control_pool_sizes.append(len(candidates))

        best_d = float("inf")
        best_id = None
        for cand, vec in candidates:
            d = float(np.linalg.norm(
                pre - np.asarray(vec, dtype=float)
            ))
            if d < best_d:
                best_d = d
                best_id = cand

        if best_id is None:
            no_control += 1
            continue

        matched += 1

        for h in horizons:
            tp = t_snap + h
            if tp not in by_t:
                continue
            if rec not in by_t[tp] or best_id not in by_t[tp]:
                continue

            dt = (
                np.asarray(by_t[tp][rec], dtype=float)
                - np.asarray(by_t[t_snap][rec], dtype=float)
            )
            dc = (
                np.asarray(by_t[tp][best_id], dtype=float)
                - np.asarray(by_t[t_snap][best_id], dtype=float)
            )

            analysed_by_h[h] += 1
            for i, k in enumerate(("grief", "grat", "uc")):
                treat[h][k].append(float(dt[i]))
                ctrl[h][k].append(float(dc[i]))

    out = {
        "meta": meta,
        "observed_events": observed,
        "eligible_events": eligible,
        "matched_recipients": matched,
        "duplicates": duplicates,
        "no_control": no_control,
        "duplicate_selection_suppressed": duplicates,
        "unmatched_total": no_control,
        "control_pool_size_at_snap_avg": (
            float(np.mean(control_pool_sizes))
            if control_pool_sizes else None
        ),
        "control_pool_empty_frac": (
            float(np.mean([n == 0 for n in control_pool_sizes]))
            if control_pool_sizes else None
        ),
        "control_pool_size_at_snap_min": (
            int(min(control_pool_sizes))
            if control_pool_sizes else None
        ),
        "control_pool_size_at_snap_max": (
            int(max(control_pool_sizes))
            if control_pool_sizes else None
        ),
        "analysed_cases_by_horizon": dict(analysed_by_h),
        "by_horizon": {},
    }

    for h in horizons:
        out["by_horizon"][f"h={h}"] = {}
        for k in ("grief", "grat", "uc"):
            t = treat[h][k]
            c = ctrl[h][k]
            out["by_horizon"][f"h={h}"][k] = {
                "treat": _stat(t),
                "ctrl": _stat(c),
                "diff_mean": (
                    float(np.mean(t) - np.mean(c))
                    if t and c else None
                ),
            }
    return out


# ----------------------------------------------------------------------------
# E3 — SEEK / ANSWER
# ----------------------------------------------------------------------------
def sec_E3_seek(ledger_raw):
    if not ledger_raw:
        return {"n/a": "ledger не найден"}

    ev = Counter()
    for r in ledger_raw.get("rows", []):
        for k, v in (r.get("ev") or {}).items():
            ev[k] += v

    return {
        k: ev.get(k, 0)
        for k in (
            "sr_conflict_resolved",
            "req_heard",
            "req_registered",
            "answers_said",
            "answers_heard",
            "relief",
        )
    }


# ----------------------------------------------------------------------------
# E6 — NEIGHBOR EFFECT
# ----------------------------------------------------------------------------
def sec_E6_neighbors(log_raw):
    snaps = log_raw.get("agent_snaps", [])
    if not snaps:
        return {}

    nw = max((s.get("t", 0) for s in snaps), default=-1) // W + 1

    def calc(ss):
        nbr = [s.get("neighbor_grief_own_excl") for s in ss]
        nbr_raw = [s.get("neighbor_grief") for s in ss]
        out = {}
        for f in ("grief", "grat", "uc", "gap", "drag"):
            out[f"nbrN~{f}"] = _corr(
                nbr, [s.get(f) for s in ss]
            )
        for f in ("grief", "uc"):
            out[f"nbr_raw~{f}"] = _corr(
                nbr_raw, [s.get(f) for s in ss]
            )
        return out

    out = {"global": calc(snaps), "by_window": []}
    for w in range(nw):
        ss = [
            s for s in snaps
            if w * W <= s.get("t", -1) < (w + 1) * W
        ]
        out["by_window"].append({
            "w": w,
            "n": len(ss),
            **calc(ss),
        })
    return out


# ----------------------------------------------------------------------------
# E7 — GAMMA
# ----------------------------------------------------------------------------
def sec_E7_gamma(snaps):
    best, coverage = _dedup_dlg_stats(snaps)

    tot = Counter()
    for pid, ds in best.items():
        for k, v in ds.items():
            tot[k] += v

    out = dict(tot)
    out["_dedup_method"] = "max_per_agent"
    out["_assumption"] = "cumulative_monotonic"
    out["_coverage"] = coverage

    non_mono = {
        k: v["non_monotonic"]
        for k, v in coverage.items()
        if v["non_monotonic"] > 0
    }
    out["_non_monotonic_warnings"] = non_mono

    # Explicit coverage flags for the gamma experiment.
    for k in (
        "content_response_heard",
        "content_response_applied",
        "content_response_source_mismatch",
        "fb_shifts",
    ):
        c = coverage.get(k)
        out[f"{k}_coverage"] = c if c else {
            "agents": 0,
            "observations": 0,
            "non_monotonic": 0,
            "status": "NOT_RECORDED",
        }

    return out


# ----------------------------------------------------------------------------
# F — FEELINGS
# ----------------------------------------------------------------------------
def sec_F_feelings(log_raw):
    snaps = log_raw.get("agent_snaps", [])
    if not snaps:
        return {}

    keys = [
        "grief", "grat", "uc", "gap", "drag",
        "tension", "soul", "nci", "scar",
    ]
    out = {k: _stat([s.get(k) for s in snaps]) for k in keys}

    for f in ("fear", "fury"):
        vals = [s.get(f) for s in snaps if f in s]
        if vals:
            out[f] = _stat(vals)

    # Explicitly named as snapshot fractions; these are not fractions of unique agents.
    out["frac_snaps_uc_gt_0.6"] = _frac([
        s.get("uc", 0) > 0.6
        for s in snaps
        if "uc" in s
    ])
    out["frac_snaps_gap_gt_0.8"] = _frac([
        s.get("gap", 0) > 0.8
        for s in snaps
        if "gap" in s
    ])
    out["frac_snaps_drag_lt_0.5"] = _frac([
        s.get("drag", 1) < 0.5
        for s in snaps
        if "drag" in s
    ])
    out["frac_snaps_tension_gt_1"] = _frac([
        s.get("tension", 0) > 1.0
        for s in snaps
        if "tension" in s
    ])
    out["frac_snaps_tension_at_cap"] = _frac([
        s.get("tension", 0) >= 1.9
        for s in snaps
        if "tension" in s
    ])

    def _agent_ever(predicate, key):
        by_agent = defaultdict(list)
        for snap in snaps:
            if "id" in snap and key in snap:
                by_agent[snap["id"]].append(snap[key])
        if not by_agent:
            return None
        return _frac([
            any(predicate(v) for v in vals)
            for vals in by_agent.values()
        ])

    out["frac_agents_ever_uc_gt_0.6"] = _agent_ever(lambda v: v > 0.6, "uc")
    out["frac_agents_ever_gap_gt_0.8"] = _agent_ever(lambda v: v > 0.8, "gap")
    out["frac_agents_ever_drag_lt_0.5"] = _agent_ever(lambda v: v < 0.5, "drag")
    out["frac_agents_ever_tension_gt_1"] = _agent_ever(lambda v: v > 1.0, "tension")
    out["frac_agents_ever_tension_at_cap"] = _agent_ever(lambda v: v >= 1.9, "tension")
    return out


# ----------------------------------------------------------------------------
# G — CONCEPTS
# ----------------------------------------------------------------------------
def sec_G_concepts(log_raw, ledger_raw):
    snaps = log_raw.get("agent_snaps", [])
    if not snaps:
        return {}

    out = {
        "n_conc": _stat([s.get("n_conc") for s in snaps]),
        "n_edge": _stat([s.get("n_edge") for s in snaps]),
        "cns": _stat([s.get("cns") for s in snaps]),
    }
    out["frac_cns_gt_0.55"] = _frac([
        s.get("cns", 0) > 0.55
        for s in snaps
        if "cns" in s
    ])
    out["frac_narrative"] = _frac([
        s.get("narrative") for s in snaps
    ])
    out["frac_subject"] = _frac([
        s.get("subject") for s in snaps
    ])
    out["frac_root_q"] = _frac([
        s.get("root_q") for s in snaps
    ])
    out["frac_meta_gt_0"] = _frac([
        s.get("meta_s", 0) > 0
        for s in snaps
        if "meta_s" in s
    ])
    return out


# ----------------------------------------------------------------------------
# I — MECHANISMS
# ----------------------------------------------------------------------------
def sec_I_mechanisms(ledger_raw):
    if not ledger_raw:
        return {"n/a": "ledger не найден"}

    rows = ledger_raw.get("rows", [])
    if not rows:
        return {"n/a": "rows пусто"}

    ev = Counter()
    for r in rows:
        for k, v in (r.get("ev") or {}).items():
            ev[k] += v

    at = sum(r.get("n", 0) for r in rows)
    out = {}

    for k in (
        "feral_execution",
        "spore_emitted",
        "fold",
        "identity_crisis_transformation",
        "redeemed",
        "dream_consolidation",
        "nightmare_consolidation",
        "redemption_complete",
        "became_feral",
        "feral_redemption_complete",
        "sr_meditation",
        "fb_shifts",
        "intent_switch",
    ):
        c = ev.get(k, 0)
        out[k] = {
            "count": c,
            "rate_per_1000_at": round(
                1000 * c / max(at, 1), 3
            ),
        }
    return out


# ----------------------------------------------------------------------------
# J — TEMPORAL
# ----------------------------------------------------------------------------
def sec_J_temporal(log_raw, ledger_raw):
    snaps = log_raw.get("agent_snaps", [])
    speaks = log_raw.get("speaks", [])
    rows_led = ledger_raw.get("rows", []) if ledger_raw else []

    if not rows_led:
        return {"n/a": "нет ledger rows"}

    nw = rows_led[-1]["t"] // W + 1
    out = []

    for w in range(nw):
        sw = [
            s for s in speaks
            if w * W <= s.get("t", -1) < (w + 1) * W
            and s.get("utt")
        ]
        sn = [
            s for s in snaps
            if w * W <= s.get("t", -1) < (w + 1) * W
        ]
        emo = Counter(
            s["utt"][1]
            for s in sw
            if len(s["utt"]) > 1
        )
        lw = rows_led[w * W:(w + 1) * W]

        out.append({
            "w": w,
            "n_mean": (
                sum(r.get("n", 0) for r in lw) / len(lw)
                if lw else None
            ),
            "speaks": len(sw),
            "GRIEF": emo.get("GRIEF", 0),
            "JOY": emo.get("JOY", 0),
            "CALM": emo.get("CALM", 0),
            "p50_grief": _stat([
                s.get("grief") for s in sn
            ]).get("p50"),
            "p50_uc": _stat([
                s.get("uc") for s in sn
            ]).get("p50"),
            "p50_gap": _stat([
                s.get("gap") for s in sn
            ]).get("p50"),
            "p50_drag": _stat([
                s.get("drag") for s in sn
            ]).get("p50"),
            "p50_tension": _stat([
                s.get("tension") for s in sn
            ]).get("p50"),
        })

    return {"windows": out}


# ----------------------------------------------------------------------------
# K — ANOMALIES
# ----------------------------------------------------------------------------
def sec_K_anomalies(log_raw, ledger_raw):
    an = []
    snaps = log_raw.get("agent_snaps", [])
    events = log_raw.get("events", [])
    seen = set()
    last_t_per_id = {}

    rows_log = log_raw.get("tick_rows", [])
    rows_led = ledger_raw.get("rows", []) if ledger_raw else []

    bounded_01 = (
        "uc", "grief", "grat", "gap",
        "drag", "soul", "scar",
    )

    for s in snaps:
        key = (s.get("t"), s.get("id"))
        if key in seen:
            an.append(("dup_snap", s.get("t"), s.get("id")))
        seen.add(key)

        pid = s.get("id")
        t = s.get("t")

        if pid in last_t_per_id and t < last_t_per_id[pid]:
            an.append(("time_backwards", t, pid))
        last_t_per_id[pid] = t

        for f in bounded_01:
            v = s.get(f)
            if v is None:
                continue
            if not isinstance(v, (int, float, np.integer, np.floating)):
                continue
            v = float(v)
            if not np.isfinite(v):
                an.append(("nan_or_inf", t, pid, f, v))
                continue
            if not (-1e-6 <= v <= 1 + 1e-6):
                an.append(("out_of_range", t, pid, f, round(v, 4)))

        t_v = s.get("tension")
        if isinstance(t_v, (int, float)) and np.isfinite(float(t_v)):
            if float(t_v) < -1e-6:
                an.append(("out_of_range", t, pid, "tension", t_v))

    events_checked = min(len(events), 100_000)
    for e in events[:events_checked]:
        if e.get("type") == "trust_change" and e.get("deltas"):
            for pid, _p, new_v, _d in e["deltas"]:
                if isinstance(new_v, (int, float)):
                    if new_v < -1e-6 or new_v > 1 + 1e-6:
                        an.append((
                            "trust_out_of_range",
                            e.get("t"),
                            e.get("pid"),
                            pid,
                            new_v,
                        ))

    if rows_log and rows_led:
        common = min(len(rows_log), len(rows_led))
        for i in range(common):
            if rows_log[i].get("n") != rows_led[i].get("n"):
                an.append((
                    "pop_mismatch",
                    i,
                    rows_log[i].get("n"),
                    rows_led[i].get("n"),
                ))
                break

    for k in ("events", "speaks", "dialogues"):
        if len(log_raw.get(k, [])) >= RECORD_CAP:
            an.append((
                "record_cap_reached",
                k,
                len(log_raw.get(k, [])),
            ))

    return {
        "count": len(an),
        "first_50": an[:50],
        "events_checked": events_checked,
        "events_total": len(events),
    }


# ----------------------------------------------------------------------------
# PRINTING
# ----------------------------------------------------------------------------
def _P(k, v):
    print(f"  {k}: {v}")


def _print_state_response(name, section):
    print("\n" + "-" * 78)
    print(name)
    meta = section.get("meta", {})
    for k in (
        "state_resolution_ticks",
        "exact_1_5_tick_response_available",
        "causal_claim",
        "selection_unit",
    ):
        if k in meta:
            _P(k, meta[k])

    for k in (
        "observed_events",
        "eligible_events",
        "matched_recipients",
        "duplicates",
        "no_control",
        "duplicate_selection_suppressed",
        "analysed_cases_by_horizon",
    ):
        if k in section:
            _P(k, section[k])

    for hk, hv in (section.get("by_horizon") or {}).items():
        print(f"  {hk}:")
        for k in ("grief", "grat", "uc"):
            v = hv.get(k, {})
            print(
                f"    {k}: "
                f"Δtreat={_ss(v.get('treat'))} "
                f"Δctrl={_ss(v.get('ctrl'))} "
                f"diff={_pm(v.get('diff_mean'))}"
            )


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def run_master(LOG_PATH, LEDGER_PATH=None, PREV_PATH=None):
    t0 = time.time()

    print("=" * 78)
    print(f"MASTER OBSERVATORY v{MASTER_VERSION}")
    print("READ-ONLY: simulation is not executed")
    print("=" * 78)

    print(f"log: {LOG_PATH}")
    log_raw, log_info = _safe_load(LOG_PATH)
    if log_raw is None:
        print(f"  [!] log: {log_info}")
        return None

    print(f"  ok, size={log_info['size'] / 1e6:.1f} MB")

    ledger_raw = None
    if LEDGER_PATH:
        ledger_raw, led_info = _safe_load(LEDGER_PATH)
        print(f"ledger: {LEDGER_PATH}")
        if ledger_raw is None:
            print(f"  [!] ledger: {led_info}")
        else:
            print(f"  ok, size={led_info['size'] / 1e6:.1f} MB")

    if PREV_PATH:
        print(f".prev: {PREV_PATH}")

    inventory = raw_inventory(log_raw, ledger_raw)
    print_inventory(inventory)

    sections = {"raw": inventory}
    failed = []

    section_fns = (
        ("A", lambda: sec_A_identity(log_raw, ledger_raw, log_info)),
        ("B", lambda: sec_B_coverage(log_raw, ledger_raw, PREV_PATH)),
        ("C", lambda: sec_C_population(ledger_raw)),
        ("D", lambda: sec_D_communication(log_raw)),
        ("F", lambda: sec_F_feelings(log_raw)),
        ("G", lambda: sec_G_concepts(log_raw, ledger_raw)),
        ("I", lambda: sec_I_mechanisms(ledger_raw)),
        ("J", lambda: sec_J_temporal(log_raw, ledger_raw)),
        ("K", lambda: sec_K_anomalies(log_raw, ledger_raw)),
    )

    for name, fn in section_fns:
        try:
            sections[name] = fn()
        except Exception as e:
            failed.append((name, f"{type(e).__name__}: {e}"))
            sections[name] = {
                "_error": f"{type(e).__name__}: {e}"
            }

    pairs = _match_pairs(log_raw.get("speaks", []))
    print(f"\nA->B->A association pairs: {len(pairs)}")

    extra_fns = (
        ("E1", lambda: sec_E1_grief_response(pairs, log_raw)),
        ("E2", lambda: sec_E_state_response(
            log_raw, horizons=(10, 20), only_grief_a=True
        )),
        ("E3", lambda: sec_E3_seek(ledger_raw)),
        ("E6", lambda: sec_E6_neighbors(log_raw)),
        ("E7", lambda: sec_E7_gamma(log_raw.get("agent_snaps", []))),
        ("E8", lambda: sec_E_state_response(
            log_raw, horizons=(10, 20, 30), only_grief_a=False
        )),
    )

    for name, fn in extra_fns:
        try:
            sections[name] = fn()
        except Exception as e:
            failed.append((name, f"{type(e).__name__}: {e}"))
            sections[name] = {
                "_error": f"{type(e).__name__}: {e}"
            }

    # A
    print("\n" + "-" * 78)
    print("[A] IDENTITY")
    for k, v in sections["A"].items():
        _P(k, v)

    # B
    print("\n" + "-" * 78)
    print("[B] COVERAGE")
    B = sections["B"]
    for k in (
        "ticks_expected",
        "ticks_log",
        "ticks_ledger",
        "snaps_recorded",
        "snap_ticks_expected",
        "snap_ticks_actual",
        "snaps_expected_approx",
        "events",
        "speaks",
        "dialogues",
        "directed_speaks_frac",
    ):
        _P(k, B.get(k))
    _P("snap_ticks_missing_first20", B.get("snap_ticks_missing"))
    _P("nan_frac_by_field", B.get("nan_frac_by_field"))
    _P("capped", B.get("capped"))
    _P("log_errors", B.get("log_errors"))
    _P("prev", B.get("prev"))

    # C
    print("\n" + "-" * 78)
    print("[C] POPULATION")
    C = sections.get("C", {})
    for k in (
        "n_start", "n_min", "n_max", "n_end",
        "births", "deaths", "divisions",
        "agent_ticks", "deaths_per_1000_at",
        "divisions_per_1000_at", "was_subject",
        "was_narrative", "protection_above_thr_at_death",
    ):
        _P(k, C.get(k))
    _P("causes_top", C.get("causes_top"))
    if isinstance(C.get("age_at_death"), dict):
        _P("age_at_death", _ss(C["age_at_death"]))

    # D
    print("\n" + "-" * 78)
    print("[D] COMMUNICATION")
    D = sections.get("D", {})
    for k in (
        "speaks", "dialogues", "unique_utterances",
        "speakers", "recipients", "only_speak",
        "only_listen", "clusters", "n_windows",
    ):
        _P(k, D.get(k))

    print("  top-10 utterances:")
    for utt, n in (D.get("top10_utt") or []):
        print(f"    {n:>6}  {utt}")

    print("  by_window:")
    print(
        "    "
        f"{'w':<5}{'spk':>7}{'uniq':>7}"
        f"{'Hutt':>8}{'Hem':>8}{'Hint':>8}"
        f"{'GRF':>6}{'JOY':>6}{'CALM':>6}"
        f"{'KNOT':>6}{'GAP':>6}{'DRAG':>6}{'fid':>8}"
    )

    fid_w = D.get("fidelity_by_window", {})
    for r in (D.get("by_window") or []):
        print(
            f"    {r['w']:<5}"
            f"{r['speaks']:>7}"
            f"{r['unique_utterances']:>7}"
            f"{(r['H_utterance'] if r['H_utterance'] is not None else float('nan')):>8.3f}"
            f"{(r['H_emotion'] if r['H_emotion'] is not None else float('nan')):>8.3f}"
            f"{(r['H_intent'] if r['H_intent'] is not None else float('nan')):>8.3f}"
            f"{r['GRIEF']:>6}"
            f"{r['JOY']:>6}"
            f"{r['CALM']:>6}"
            f"{r['KNOT']:>6}"
            f"{r['GAP']:>6}"
            f"{r['DRAG']:>6}"
            f"{(fid_w.get(r['w']) if fid_w.get(r['w']) is not None else float('nan')):>8.4f}"
        )

    # E1
    print("\n" + "-" * 78)
    print("[E1] GRIEF A -> subsequent B->A association window")
    E1 = sections.get("E1", {})
    gg = E1.get("global", {}).get("grief_a", {})
    go = E1.get("global", {}).get("other_a", {})

    print(
        f"  global GRIEF A: n={gg.get('n', 0)} "
        f"rate_calm={gg.get('rate_calm')}"
    )
    print(
        f"  global non-GRIEF A: n={go.get('n', 0)} "
        f"rate_calm={go.get('rate_calm')}"
    )
    if gg.get("n") and go.get("n"):
        print(
            "  Δ rate_calm "
            f"(GRIEF − other) = "
            f"{gg['rate_calm'] - go['rate_calm']:+.3f}"
        )
    _P("response_delay", _ss(E1.get("grief_response_delay")))

    # E2
    _print_state_response(
        "[E2] GRIEF A -> state B (+10/+20) | diagnostic",
        sections.get("E2", {}),
    )

    # E3
    print("\n" + "-" * 78)
    print("[E3] SEEK / ANSWER (ledger events)")
    for k, v in (sections.get("E3") or {}).items():
        _P(k, v)

    # E6
    print("\n" + "-" * 78)
    print("[E6] NEIGHBORS — global + per window")
    E6 = sections.get("E6") or {}
    print("  global:")
    for k, v in (E6.get("global") or {}).items():
        if isinstance(v, dict):
            print(f"    {k}: r={v.get('r')} (n={v.get('n')})")
    for row in E6.get("by_window") or []:
        print(f"  window {row['w']} (n={row['n']}):")
        for k, v in row.items():
            if k in ("w", "n"):
                continue
            if isinstance(v, dict):
                print(f"    {k}: r={v.get('r')} (n={v.get('n')})")

    # E7
    print("\n" + "-" * 78)
    print("[E7] γ — dedup=max_per_agent")
    E7 = sections.get("E7") or {}
    for k in (
        "content_response_heard",
        "content_response_applied",
        "content_response_source_mismatch",
        "fb_shifts",
        "req_heard",
        "req_registered",
        "answers_said",
        "answers_heard",
        "relief",
        "knot_said",
        "utt_total",
    ):
        if k in E7:
            _P(k, E7[k])

    print(f"  _dedup_method: {E7.get('_dedup_method')}")
    print(f"  _assumption: {E7.get('_assumption')}")
    print("  counter coverage:")
    for k, v in (E7.get("_coverage") or {}).items():
        print(f"    {k}: {v}")

    nw_warn = E7.get("_non_monotonic_warnings") or {}
    if nw_warn:
        print(f"  [!] non-monotonic counters: {nw_warn}")
    else:
        print("  monotonicity: no decreases observed")

    # E8
    _print_state_response(
        "[E8] delayed state — all directed | diagnostic, not causality",
        sections.get("E8", {}),
    )

    # F
    print("\n" + "-" * 78)
    print("[F] FEELINGS")
    F = sections.get("F") or {}
    for k in (
        "grief", "grat", "uc", "gap", "drag",
        "tension", "soul", "nci", "scar", "fear", "fury",
    ):
        v = F.get(k)
        if v:
            print(f"  {k}: {_ss(v)}")
    for k in (
        "frac_snaps_uc_gt_0.6",
        "frac_snaps_gap_gt_0.8",
        "frac_snaps_drag_lt_0.5",
        "frac_snaps_tension_gt_1",
        "frac_snaps_tension_at_cap",
        "frac_agents_ever_uc_gt_0.6",
        "frac_agents_ever_gap_gt_0.8",
        "frac_agents_ever_drag_lt_0.5",
        "frac_agents_ever_tension_gt_1",
        "frac_agents_ever_tension_at_cap",
    ):
        v = F.get(k)
        if v:
            print(f"  {k}: {_ss(v)}")

    # G
    print("\n" + "-" * 78)
    print("[G] CONCEPTS")
    for k, v in (sections.get("G") or {}).items():
        if isinstance(v, dict):
            print(f"  {k}: {_ss(v)}")

    # I
    print("\n" + "-" * 78)
    print("[I] MECHANISMS")
    for k, v in (sections.get("I") or {}).items():
        if isinstance(v, dict):
            print(
                f"  {k}: {v.get('count')} "
                f"({v.get('rate_per_1000_at')}/1000at)"
            )

    # J
    print("\n" + "-" * 78)
    print("[J] TEMPORAL")
    J = sections.get("J") or {}
    if "windows" in J:
        print(
            f"  {'w':<5}{'n_mean':>8}{'speaks':>8}"
            f"{'GRF':>6}{'JOY':>6}{'CALM':>6}"
            f"{'p50_grief':>11}{'p50_uc':>9}"
            f"{'p50_gap':>9}{'p50_drag':>10}"
            f"{'p50_tension':>13}"
        )
        for r in J["windows"]:
            def _g(k):
                v = r.get(k)
                return f"{v:.3f}" if isinstance(v, (int, float)) else "n/a"

            print(
                f"  {r['w']:<5}"
                f"{(r.get('n_mean') or 0):>8.1f}"
                f"{r['speaks']:>8}"
                f"{r['GRIEF']:>6}"
                f"{r['JOY']:>6}"
                f"{r['CALM']:>6}"
                f"{_g('p50_grief'):>11}"
                f"{_g('p50_uc'):>9}"
                f"{_g('p50_gap'):>9}"
                f"{_g('p50_drag'):>10}"
                f"{_g('p50_tension'):>13}"
            )

    # K
    print("\n" + "-" * 78)
    print("[K] ANOMALIES")
    K = sections.get("K") or {}
    print(f"  count: {K.get('count', 0)}")
    print(
        f"  events_checked: {K.get('events_checked', 0)} "
        f"из {K.get('events_total', 0)}"
    )
    for a in K.get("first_50", []):
        print(f"    {a}")

    # Final
    print("\n" + "-" * 78)
    ok_cnt = sum(
        1 for s in sections.values()
        if not (isinstance(s, dict) and "_error" in s)
    )
    print(f"секции: OK={ok_cnt} failed={len(failed)}")
    for f in failed:
        print(f"  [!] {f[0]}: {f[1]}")
    print(f"wall={time.time() - t0:.1f}s")

    out = {
        "master_version": MASTER_VERSION,
        "log_path": LOG_PATH,
        "ledger_path": LEDGER_PATH,
        "prev_path": PREV_PATH,
        "sections": sections,
        "failed": failed,
        "pairs": len(pairs),
        "pair_definition": (
            f"A->B followed by B->A within <= {W_MAX} ticks; "
            "association only"
        ),
    }

    MASTER_JSON = _master_json_for(LOG_PATH)

    try:
        os.makedirs(os.path.dirname(MASTER_JSON), exist_ok=True)
        tmp = MASTER_JSON + ".tmp"
        clean_out = _sanitize_json(out)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                clean_out,
                f,
                ensure_ascii=False,
                allow_nan=False,
                default=_json_default,
            )
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, MASTER_JSON)
        print(
            f"JSON: {MASTER_JSON} "
            f"({os.path.getsize(MASTER_JSON) / 1e6:.1f} MB)"
        )
    except Exception as e:
        print(f"[!] JSON save: {e}")

    return out


# ----------------------------------------------------------------------------
# RUN CONFIG
# ----------------------------------------------------------------------------
# This is the ONLY execution point.
# It reads the existing run; it does NOT start a simulation.
_TAG = "rich_dlgV2_pull0.0_normTrue_seed118951255_steps300_mult0.15"
_LOG = f"{DIR}/rich_log_{_TAG}.json"
_LED = f"{DIR}/rich_ledger_{_TAG}.json"
_PREV = f"{DIR}/rich_log_{_TAG}.json.prev"

# Execution point: run after mounting Drive in Colab.
RUN_NOW = True
if RUN_NOW:
    run_master(_LOG, _LED, _PREV)
