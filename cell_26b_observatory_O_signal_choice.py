# ============================================================
# OBSERVATORY ADD-ON [O] — СИГНАЛ → ВЫБОР → ОБУЧЕНИЕ (читает summary['signal_choice'] из audit JSON)
# READ-ONLY. Ставится ПОСЛЕ MASTER OBSERVATORY (ячейка 26). Подцепляется к run_master через _print_N:
# после раздела [N] ФОРМЫ печатается раздел [O]. Динамику прогона не трогает.
# ============================================================
import os, json
import numpy as np

for _need in ("_print_N", "_audit_path_for"):
    if _need not in globals():
        raise RuntimeError(f"{_need} не найден: сначала выполни ячейку MASTER OBSERVATORY.")


def _o_share(a, b):
    return round(a / b, 4) if b else None


def sec_O_signal_choice(audit_path):
    if not audit_path or not os.path.exists(audit_path):
        return {"n/a": f"нет файла аудита: {audit_path}"}
    with open(audit_path, "r", encoding="utf-8") as f:
        A = json.load(f)
    S = (A.get("summary") or {}).get("signal_choice")
    if not S:
        return {"n/a": "в аудите нет summary['signal_choice']: слой SIGNAL→CHOICE не подключён или аудит старый"}
    st = S.get("stats", {})
    g = lambda k: int(st.get(k, 0))
    rows = A.get("rows", [])
    half = len(rows) // 2
    first, last = rows[:half] or rows, rows[half:]

    def rs(rr, k):
        return sum((r.get("sc_" + k) or 0) for r in rr)

    rec_keys = ("recognized", "partial", "doubt", "concept", "none", "stress_missed")
    rec_tot = sum(g("rec_" + k) for k in rec_keys)
    prov_tot = sum(g("prov_" + k) for k in ("foreign", "mixed", "own", "unknown"))
    cs = g("choice_signal")
    ch_tot = g("choice_noflip") + g("choice_influenced") + g("choice_reinforced") + g("choice_blocked")
    snap = S.get("snapshot", {})
    cpt = S.get("concepts", {})
    out = {
        "version": S.get("version"),
        "ticks": (A.get("summary") or {}).get("ticks"),
        "recognition": {k: {"n": g("rec_" + k), "share": _o_share(g("rec_" + k), rec_tot)} for k in rec_keys},
        "provenance": {k: {"n": g("prov_" + k), "share": _o_share(g("prov_" + k), prov_tot)}
                       for k in ("foreign", "mixed", "own", "unknown")},
        "provenance_geo_unconfirmed": g("prov_geo_unconfirmed"),
        "choice": {"signal_calls": cs, "noflip": g("choice_noflip"), "influenced": g("choice_influenced"),
                   "reinforced": g("choice_reinforced"), "blocked": g("choice_blocked"),
                   "influenced_share": _o_share(g("choice_influenced") + g("choice_reinforced"), ch_tot),
                   "blocked_share": _o_share(g("choice_blocked"), ch_tot),
                   "mean_abs_bias": (round(g("choice_bias_abs_x1000") / 1000.0 / cs, 4) if cs else None)},
        "choice_trend": {
            "influenced_share_first": _o_share(rs(first, "choice_influenced") + rs(first, "choice_reinforced"),
                                               sum(rs(first, k) for k in ("choice_noflip", "choice_influenced", "choice_reinforced", "choice_blocked"))),
            "influenced_share_last": _o_share(rs(last, "choice_influenced") + rs(last, "choice_reinforced"),
                                              sum(rs(last, k) for k in ("choice_noflip", "choice_influenced", "choice_reinforced", "choice_blocked"))),
            "recognized_share_first": _o_share(rs(first, "rec_recognized"), sum(rs(first, "rec_" + k) for k in rec_keys)),
            "recognized_share_last": _o_share(rs(last, "rec_recognized"), sum(rs(last, "rec_" + k) for k in rec_keys))},
        "learning": {"emitter": g("exp_upd_emitter"), "listener": g("exp_upd_listener"), "observed": g("exp_upd_observed"),
                     "warmup": g("exp_warmup"), "listener_no_credit": g("listener_no_credit")},
        "witness": {"deaths_seen": g("deaths_seen"), "events": g("wit_events"), "credits": g("wit_credits"),
                    "forms_born": g("wit_forms_born"), "no_context": g("wit_no_context"), "no_room": g("wit_no_room"),
                    "feral_deaths_ignored": g("wit_feral_death_ignored")},
        "concepts": {"born": g("concepts_born"), "born_harm": g("concepts_born_harm"), "born_help": g("concepts_born_help"),
                     "merged": g("concepts_merged"), "dropped": g("concepts_dropped"),
                     "alive": snap.get("concepts_alive"), "agents_with_concept": snap.get("agents_with_concept"),
                     "mean_n": cpt.get("mean_n"), "mean_exp": cpt.get("mean_exp")},
        "expectation_model": {"forms_with_exp": snap.get("forms_with_exp"), "forms": snap.get("forms"),
                              "mean_exp_vector": snap.get("exp")},
        "echo": {"mode": (S.get("config") or {}).get("SC_ECHO_MODE"), "heard": g("echo_heard"),
                 "recognized": g("echo_recognized"), "adopted": g("echo_adopted"),
                 "ignored": max(0, g("echo_heard") - g("echo_recognized") - g("echo_adopted")),
                 "forms_alive_series": S.get("echo_series")},
        "errors": sum(v for k, v in st.items() if k.startswith("err_")), "last_err": S.get("last_err"),
    }
    warn = []
    if rec_tot == 0:
        warn.append("ничего не распознаётся: проверь, что SPECTRUM слушает и формы есть")
    if g("rec_recognized") + g("rec_partial") + g("rec_concept") > 0 and cs == 0:
        warn.append("сигнал распознаётся, но до выбора не доходит: нет ожиданий с n>=SC_MIN_N (идёт разогрев?)")
    if out["errors"]:
        warn.append("есть ошибки слоя, см. last_err")
    out["warn"] = warn or None
    return out


def _print_O(log_path):
    print("\n" + "-" * 78)
    print("[O] СИГНАЛ → ВЫБОР → ОБУЧЕНИЕ (SIGNAL→CHOICE v1.0)")
    O = sec_O_signal_choice(_audit_path_for(log_path))
    for k, v in O.items():
        if isinstance(v, float):
            v = round(v, 4)
        print(f"  {k}: {v}")
    return O


if not getattr(_print_N, "_o_wrapped", False):
    _orig_print_N = _print_N

    def _print_N(log_path):
        N = _orig_print_N(log_path)
        try:
            _print_O(log_path)
        except Exception as e:
            print(f"[O] ⚠️ раздел не построен: {e!r}")
        return N

    _print_N._o_wrapped = True

print("✅ OBSERVATORY ADD-ON [O]: после [N] ФОРМЫ печатается [O] СИГНАЛ → ВЫБОР → ОБУЧЕНИЕ (run_master подхватит сам).")
