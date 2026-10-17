# ============================================================
# SIGNAL → CHOICE → LEARN v1.0 — слой поверх SPECTRUM v1.3.2 и FERAL v3
# По картинкам «Как должны работать механизмы» и «Как агенты общаются».
#
#   Сигнал → Распознавание → Выбор → Последствия → Обучение
#
# Принципы (из картинок):
#   • Никаких готовых реакций. Сигнал не даёт команду, он меняет ОЦЕНКУ целей.
#   • Оценка = ожидаемые последствия (энергия, настроение, доверие), выученные самим агентом:
#       из СВОИХ исходов (личный опыт), из ЧУЖИХ (гибель рядом), из формы-как-культуры (heard_/наследование).
#   • Нет единой «ценности выживания»: три компоненты хранятся раздельно, смерть рядом = «потеряли всё» (энергия, настроение).
#   • Кредит только за свои действия: источник неизвестен → кредит слушателю не приписывается.
#   • Концепт-обобщение рождается только по данным: порог подтверждений + выученное ожидание (не флаг, не готовая сигнатура).
#   • Эхо (структурный паттерн без имени) в поле: SC_ECHO_MODE = 'structure' | 'off' (полное удаление). По умолчанию 'off'.
#
# Порядок: ... → SPECTRUM v1.3.2 → FERAL v3 → ЭТА ячейка → Ledger → RichEngine → ... → прогон.
# После вставки: Runtime -> Restart session и запуск сверху вниз.
#
# Выход (метрики / лог / обсервер):
#   • audit rows sc_* (приращения за тик), summary['signal_choice'], metrics_history sc_* (если есть register_metrics)
#   • строка [SIGNAL-CHOICE t=..] раз в 50 тиков
#   • обсервер: ячейка OBSERVATORY ADD-ON [O] (читает summary['signal_choice'] из audit JSON)
# Выключатели: Config.SC_ENABLE, SC_CHOICE, SC_LISTENER_CREDIT, SC_WIT_ENABLE, SC_CONCEPT_ENABLE, SC_ECHO_MODE.
# ============================================================
import numpy as np
from collections import Counter, deque

for _need in ("Pattern", "EvolutionEngine", "extend_class", "Config", "FORM_STATS", "FORM_PENDING",
              "_form_open", "_form_settle", "_form_ctx", "_form_normalize", "_form_ambient",
              "_form_mood", "_form_trust", "SIGNAL_CHANNELS", "CH", "phi_hash"):
    if _need not in globals():
        raise RuntimeError(f"{_need} не найден: сначала выполни ячейки SPECTRUM v1.3.2 и FERAL v3.")
if not any(k.__name__ == "SpectrumMixin" for k in Pattern.__mro__):
    raise RuntimeError("Слой SPECTRUM не подключён: эта ячейка идёт ПОСЛЕ SPECTRUM v1.3.2.")
if any(k.__name__ == "SignalChoiceMixin" for k in Pattern.__mro__):
    raise RuntimeError("SIGNAL→CHOICE уже подключён в этой сессии. Runtime -> Restart session и запуск сверху вниз.")
for _n in ("LedgerEngine", "RichEngine"):
    _c = globals().get(_n)
    if _c is not None and not any(k.__name__ == "SignalChoiceEngineMixin" for k in _c.__mro__):
        raise RuntimeError(f"{_n} уже определён без слоя SIGNAL→CHOICE. Поставь эту ячейку ВЫШЕ Ledger/RichEngine, "
                           f"потом Runtime -> Restart session.")

_SC_DEFAULTS = {
    'SC_ENABLE': True, 'SC_CHOICE': True,
    'SC_CHOICE_GAIN': 0.15, 'SC_CHOICE_MAX': 0.5,          # сдвиг приоритета цели: gain * Σ(вес_цели * ожидание), не более max
    'SC_RECENT_TICKS': 6, 'SC_RECENT_DECAY': 0.8,           # сколько тиков «живёт» распознанный сигнал и как затухает
    'SC_CONF_K': 3.0, 'SC_MIN_N': 2,                        # уверенность n/(n+K); минимум наблюдений для ожидания
    'SC_PARTIAL_COS': 0.55, 'SC_DOUBT_GAP': 0.05,           # «частично» и «сомнение» (две формы почти равны)
    'SC_STRESS_MISS': 0.5,                                  # при полном стрессе агент не распознаёт с вероятностью до 0.5
    'SC_TX_WINDOW': 5, 'SC_TX_PAD': 3, 'SC_TX_COS': 0.6,    # журнал эмиссий: окно, запас радиуса, спектральное подтверждение
    'SC_LISTENER_CREDIT': True,
    'SC_VERDICT_Z': 0.5, 'SC_Z_CLIP': 3.0,
    'SC_WIT_ENABLE': True, 'SC_WIT_RADIUS': 10, 'SC_WIT_WINDOW': 6,
    'SC_WIT_W': 0.3, 'SC_WIT_EVID': 0.5, 'SC_WIT_BIRTH': True,
    'SC_CONCEPT_ENABLE': True, 'SC_CONCEPT_MIN': 3.0, 'SC_CONCEPT_COS': 0.8, 'SC_CONCEPT_MAX': 8,
    'SC_ECHO_MODE': 'off', 'SC_ECHO_SITES': 3, 'SC_ECHO_PERIOD': 25, 'SC_ECHO_AVAIL': 0.35,
    'SC_ECHO_AMP': 0.25, 'SC_ECHO_RADIUS': 4, 'SC_ECHO_DRIFT': 40, 'SC_ECHO_COS': 0.6,
    'SC_ECHO_CHANNELS': ('signal_beauty', 'signal_memory', 'signal_interest', 'signal_rhythm'),
    # инструментальная ценность: как ожидаемое изменение (настроение m, доверие tr, энергия en)
    # влияет на достижимость цели данного типа. Это ОЦЕНКА, а не команда и не «ценность выживания».
    'SC_GOAL_W': {
        'cooperate': {'m': 0.5, 'tr': 1.0, 'en': 0.2},
        'seek_help': {'m': 0.3, 'tr': 1.0, 'en': 0.2},
        'explore':   {'m': 0.3, 'tr': 0.0, 'en': 1.0},
        'rest':      {'m': 0.2, 'tr': 0.0, 'en': -0.8},
        '*':         {'m': 0.3, 'tr': 0.2, 'en': 0.5},
    },
    'SC_FLOORS': {'m': 0.01, 'tr': 0.005, 'en': 0.02},
}
for _k, _v in _SC_DEFAULTS.items():
    if not hasattr(Config, _k):
        setattr(Config, _k, _v)

COMPS = ('m', 'tr', 'en')
SC = {}
_SC_OFFS = {}


def _sc_reset():
    SC.clear()
    SC.update({
        'stats': Counter(), 'prev': Counter(), 'tx': deque(maxlen=8192),
        'base': {c: {} for c in COMPS}, 'absm': {c: [0.0, 0] for c in COMPS},
        'alive_prev': {}, 'echo_active': [], 'echo_series': [], 'last_err': None,
    })


def _sc_err(tag, e):
    SC['stats']['err_' + tag] += 1
    msg = f"{tag}: {e!r}"
    if SC.get('last_err') is None:
        print(f"[SIGNAL-CHOICE] ⚠️ {msg}", flush=True)
    SC['last_err'] = msg


def _sc_sync(eng):
    if eng is not None and getattr(eng, '_sc_tok', None) is None:
        eng._sc_tok = True
        _sc_reset()


def _sc_dist2(ax, ay, bx, by, W):
    dx = abs(ax - bx); dx = min(dx, W - dx)
    dy = abs(ay - by); dy = min(dy, W - dy)
    return dx * dx + dy * dy


def _sc_cos(a, b):
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    va = np.array([a.get(k, 0.0) for k in keys], dtype=np.float64)
    vb = np.array([b.get(k, 0.0) for k in keys], dtype=np.float64)
    na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def _sc_match(spec, obs):
    """как в базе: косинус по общим каналам + разница норм"""
    common = set(spec) & set(obs)
    if not common:
        return 0.0, float('inf')
    a = np.array([spec[c] for c in common]); b = np.array([obs[c] for c in common])
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na < 1e-6 or nb < 1e-6:
        return 0.0, float('inf')
    return float(np.dot(a, b) / (na * nb)), float(abs(na - nb))


def _sc_offsets(R):
    o = _SC_OFFS.get(R)
    if o is None:
        d = np.arange(-R, R + 1)
        gx, gy = np.meshgrid(d, d, indexing='ij')
        m = (gx * gx + gy * gy) <= R * R
        o = (gx[m].astype(np.int64), gy[m].astype(np.int64))
        _SC_OFFS[R] = o
    return o


def _sc_heard(field, t, cx, cy):
    """что слышно в точке: те же правила порога и фона, что в базе, но векторно"""
    W = Config.WORLD_SIZE
    dx, dy = _sc_offsets(Config.FORM_LISTEN_RADIUS)
    chans = list(SIGNAL_CHANNELS)
    means = field[(cx + dx) % W, (cy + dy) % W][:, chans].mean(axis=0)
    observed = {ch: float(v) for ch, v in zip(chans, means)}
    thr = Config.FORM_SIGNAL_THRESHOLD
    amb = _form_ambient(field, t)
    adj = {ch: (v - amb.get(ch, 0.0) if amb.get(ch, 0.0) >= thr else v) for ch, v in observed.items()}
    adj = {ch: v for ch, v in adj.items() if v >= thr}
    observed = {ch: v for ch, v in observed.items() if v >= thr}
    use = adj if Config.FORM_LISTEN_ABOVE_AMBIENT else observed
    return _form_normalize(use) if use else None


def _sc_stress(p):
    a = float(getattr(p, 'alarm_level', 0.0))
    mx = float(getattr(Config, 'MAX_METRIC', 1.0)) or 1.0
    tn = float(getattr(p, 'cognitive_tension', 0.0)) / mx
    return float(min(1.0, max(0.0, a, tn)))


# ------------------------------------------------------------
# Модель ожиданий: форма / концепт -> выученный вектор последствий (z-единицы относительно базовой линии контекста)
# ------------------------------------------------------------
def _sc_new():
    return {'m': 0.0, 'tr': 0.0, 'en': 0.0, 'n': 0}


def _sc_upd(rec, vec, w=1.0):
    rec['n'] += 1
    a = max(0.1, 1.0 / rec['n']) * w
    for c in COMPS:
        rec[c] += a * (vec[c] - rec[c])


def _sc_exp_of(entity, ctx):
    exp = entity.get('sc_exp') or {}
    rec = exp.get(ctx)
    if rec is None or rec['n'] < Config.SC_MIN_N:
        rec = exp.get('*')
    return rec if (rec is not None and rec['n'] >= Config.SC_MIN_N) else None


def _sc_learn_vec(p, form, ctx, vec, w, kind):
    exp = form.setdefault('sc_exp', {})
    for key in (ctx, '*'):
        _sc_upd(exp.setdefault(key, _sc_new()), vec, w)
    spec = form.get('spectrum', {})
    for cpt in getattr(p, '_sc_concepts', ()):
        if _sc_cos(spec, cpt['spec']) >= Config.SC_CONCEPT_COS:
            _sc_upd(cpt['exp'], vec, w)
    SC['stats']['exp_upd_' + kind] += 1


def _sc_verdict(z):
    v = 0.5 * (z['m'] + z['en'])
    return -1 if v <= -Config.SC_VERDICT_Z else (1 if v >= Config.SC_VERDICT_Z else 0)


def _sc_adv(raw, key):
    """аванс относительно базовой линии контекста, в z-единицах; None пока идёт разогрев"""
    adv, mature = {}, True
    for c in COMPS:
        b = SC['base'][c].setdefault(key, [0.0, 0])
        adv[c] = raw[c] - b[0]
        if b[1] < Config.FORM_CONS_WARMUP:
            mature = False
        b[1] += 1
        b[0] += max(0.02, 1.0 / b[1]) * (raw[c] - b[0])
        am = SC['absm'][c]
        am[1] += 1
        am[0] += max(0.01, 1.0 / am[1]) * (abs(adv[c]) - am[0])
    if not mature:
        return None
    return {c: float(np.clip(adv[c] / max(SC['absm'][c][0], Config.SC_FLOORS[c]),
                             -Config.SC_Z_CLIP, Config.SC_Z_CLIP)) for c in COMPS}


# ------------------------------------------------------------
# Концепт: обобщение по порогу подтверждений, содержимое — из данных
# ------------------------------------------------------------
def _sc_evidence(p, form, kind, verdict, weight=1.0):
    ev = form.setdefault('sc_ev', {'hp': 0.0, 'hh': 0.0, 'ho': 0.0})
    if verdict < 0:
        ev['hp' if kind == 'personal' else 'ho'] += weight
    elif verdict > 0 and kind == 'personal':
        ev['hh'] += weight
    else:
        return
    _sc_try_concept(p, form)


def _sc_try_concept(p, form):
    if not Config.SC_CONCEPT_ENABLE or form.get('sc_cpt'):
        return
    ev = form.get('sc_ev')
    if not ev:
        return
    harm, help_ = ev['hp'] + ev['ho'], ev['hh']
    if max(harm, help_) < Config.SC_CONCEPT_MIN:
        return
    exp = (form.get('sc_exp') or {}).get('*')
    if exp is None or exp['n'] < Config.SC_MIN_N:
        return                                         # «только если есть данные»
    sign = 'harm' if harm >= help_ else 'help'
    cons = getattr(p, '_sc_concepts', None)
    if cons is None:
        p._sc_concepts = cons = []
    spec = form['spectrum']
    form['sc_cpt'] = True
    for cpt in cons:
        if cpt['sign'] == sign and _sc_cos(spec, cpt['spec']) >= Config.SC_CONCEPT_COS:
            merged = _form_normalize({ch: 0.8 * cpt['spec'].get(ch, 0.0) + 0.2 * spec.get(ch, 0.0)
                                      for ch in set(cpt['spec']) | set(spec)})
            if merged:
                cpt['spec'] = merged
            cpt['ev']['p'] += ev['hp'] + ev['hh']; cpt['ev']['o'] += ev['ho']
            SC['stats']['concepts_merged'] += 1
            return
    if len(cons) >= Config.SC_CONCEPT_MAX:
        cons.remove(min(cons, key=lambda c: c['exp']['n']))
        SC['stats']['concepts_dropped'] += 1
    cons.append({'spec': dict(spec), 'sign': sign, 'exp': dict(exp),
                 'ev': {'p': ev['hp'] + ev['hh'], 'o': ev['ho']},
                 'born_t': int(p.age), 'label': 'c_' + str(form.get('label', ''))})
    SC['stats']['concepts_born'] += 1
    SC['stats']['concepts_born_' + sign] += 1
    info = dict(label=str(form.get('label', '')), sign=sign, n=int(exp['n']),
                harm=round(harm, 2), help=round(help_, 2))
    try:
        p._log_event('sc_concept_born', **info)
        w = getattr(p.world, 'witness', None) if p.world is not None else None
        if w is not None and getattr(Config, 'ENABLE_WITNESS', False):
            w.record(p.id, 'sc_concept_born', **info)
    except Exception as e:
        _sc_err('concept_log', e)


# ------------------------------------------------------------
# Обёртки над _form_open / _form_settle: компоненты последствий и кредит слушателю
# ------------------------------------------------------------
_sc_orig_open = _form_open
_sc_orig_settle = _form_settle


def _sc_open(p, other, form, ctx, sim, now):
    _sc_orig_open(p, other, form, ctx, sim, now)
    try:
        key = (id(p.world), p.id, globals()['_FORM_PENDING_SEQ'])
        pend = FORM_PENDING.get(key)
        if pend is None:
            return
        pend['sc_en0'] = float(p.energy)
        pend['sc_eno0'] = float(other.energy)
        ent = None
        for e in reversed(getattr(other, '_sc_recent', ())):
            if now - e[0] > Config.SC_RECENT_TICKS:
                break
            if e[4] == p.id and e[1] is not None and e[6] in ('recognized', 'partial', 'doubt'):
                ent = e
                break
        pend['sc_lent'] = ent
    except Exception as e:
        _sc_err('open', e)


def _sc_comp_raw(p, other, pend):
    ms = _form_mood(p) - pend['ms0']
    ts = _form_trust(p, pend['other_id']) - pend['ts0']
    es = float(p.energy) - pend.get('sc_en0', float(p.energy))
    em, lst = {'m': ms, 'tr': ts, 'en': es}, None
    if other is not None:
        mo = _form_mood(other) - pend['mo0']
        to = _form_trust(other, p.id) - pend['to0']
        eo = float(other.energy) - pend.get('sc_eno0', float(other.energy))
        lst = {'m': mo, 'tr': to, 'en': eo}
        em = {'m': 0.5 * (ms + mo), 'tr': 0.5 * (ts + to), 'en': 0.5 * (es + eo)}
    return em, lst


def _sc_settle(p, other, pend):
    comps = None
    if Config.SC_ENABLE:
        try:
            comps = _sc_comp_raw(p, other, pend)
        except Exception as e:
            _sc_err('comp', e)
    _sc_orig_settle(p, other, pend)
    if comps is None:
        return
    try:
        em, lst = comps
        form, ctx = pend['form'], pend['ctx']
        z = _sc_adv(em, f"{ctx}|s{pend['band']}")
        if z is not None:
            _sc_learn_vec(p, form, ctx, z, 1.0, 'emitter')
            _sc_evidence(p, form, 'personal', _sc_verdict(z))
        else:
            SC['stats']['exp_warmup'] += 1
        if Config.SC_LISTENER_CREDIT and lst is not None and other is not None:
            ent = pend.get('sc_lent')
            if ent is None:
                SC['stats']['listener_no_credit'] += 1       # источник неизвестен/не распознан: кредит не приписываем
            else:
                zl = _sc_adv(lst, f"L|{ent[5]}")
                if zl is not None:
                    _sc_learn_vec(other, ent[1], ent[5], zl, 1.0, 'listener')
                    _sc_evidence(other, ent[1], 'personal', _sc_verdict(zl))
    except Exception as e:
        _sc_err('learn', e)


_form_open = _sc_open
_form_settle = _sc_settle


# ------------------------------------------------------------
# Эхо: структурный паттерн без имени (режим 'structure') или полное удаление ('off')
# ------------------------------------------------------------
def _sc_echo_site(k):
    W = Config.WORLD_SIZE
    return (int(phi_hash(7001, k, 1) * W) % W, int(phi_hash(7001, k, 2) * W) % W)


def _sc_echo_spec(k, t):
    spec = {}
    for i, name in enumerate(Config.SC_ECHO_CHANNELS):
        if name not in CH:
            continue
        base = 0.3 + 0.7 * phi_hash(7002, k, i)
        drift = 1.0 + 0.5 * (phi_hash(7003, k * 31 + i, int(t) // max(1, Config.SC_ECHO_DRIFT)) - 0.5)
        spec[CH[name]] = base * drift
    return _form_normalize(spec) or {}


def _sc_echo_apply(eng, t):
    SC['echo_active'] = []
    if Config.SC_ECHO_MODE != 'structure':
        return
    W, R = Config.WORLD_SIZE, Config.SC_ECHO_RADIUS
    dx, dy = _sc_offsets(R)
    wts = np.exp(-(dx * dx + dy * dy) / (2.0 * (max(R, 1) / 2.0) ** 2))
    for k in range(Config.SC_ECHO_SITES):
        if phi_hash(7004, k, int(t) // max(1, Config.SC_ECHO_PERIOD)) >= Config.SC_ECHO_AVAIL:
            continue                                        # эхо доступно не всегда
        spec = _sc_echo_spec(k, t)
        if not spec:
            continue
        x0, y0 = _sc_echo_site(k)
        xs, ys = (x0 + dx) % W, (y0 + dy) % W
        for ch, v in spec.items():
            eng.field[xs, ys, ch] = np.minimum(1.0, eng.field[xs, ys, ch] + Config.SC_ECHO_AMP * v * wts)
        SC['echo_active'].append((k, x0, y0, spec))
        SC['stats']['echo_site_ticks'] += 1
    if SC['echo_active']:
        SC['stats']['echo_ticks'] += 1


# ------------------------------------------------------------
# PATTERN: распознавание, происхождение, влияние на выбор
# ------------------------------------------------------------
class SignalChoiceMixin:
    def _sc_init(self):
        if not hasattr(self, '_sc_recent'):
            self._sc_recent = deque(maxlen=8)    # (t, form, concept, strength, src, ctx, state, cat)
            self._sc_concepts = []

    def __init__(self, pid, cells, parent=None, world=None):
        super().__init__(pid, cells, parent, world)
        self._sc_init()

    def dump_extra(self):
        extra = super().dump_extra() if hasattr(super(), "dump_extra") else {}
        try:
            def _ser(exp):
                return {str(k): {c: (int(v[c]) if c == 'n' else float(v[c])) for c in COMPS + ('n',)}
                        for k, v in (exp or {}).items()}
            extra["sc_form_exp"] = [_ser(f.get('sc_exp')) for f in getattr(self, "signal_forms", [])[-20:]]
            extra["sc_concepts"] = [
                {"spec": {str(k): float(v) for k, v in c['spec'].items()}, "sign": c['sign'],
                 "exp": {k: (int(v) if k == 'n' else float(v)) for k, v in c['exp'].items()},
                 "ev": {k: float(v) for k, v in c['ev'].items()}, "born_t": int(c['born_t']),
                 "label": str(c['label'])} for c in getattr(self, '_sc_concepts', [])]
        except Exception as e:
            raise RuntimeError(f"SIGNAL→CHOICE: не удалось сериализовать агента {getattr(self, 'id', '?')}") from e
        return extra

    def load_extra(self, data):
        if hasattr(super(), "load_extra"):
            super().load_extra(data)
        try:
            self._sc_init()
            fe = data.get("sc_form_exp") or []
            forms = getattr(self, "signal_forms", [])
            if fe and len(fe) == len(forms):
                for f, ser in zip(forms, fe):
                    if ser:
                        f['sc_exp'] = {k: {**{c: float(v.get(c, 0.0)) for c in COMPS}, 'n': int(v.get('n', 0))}
                                       for k, v in ser.items()}
            self._sc_concepts = []
            for c in data.get("sc_concepts", []):
                spec = {}
                for k, v in (c.get("spec") or {}).items():
                    try:
                        spec[int(k)] = float(v)
                    except (TypeError, ValueError):
                        continue
                if spec:
                    ex = c.get("exp") or {}
                    self._sc_concepts.append({
                        "spec": spec, "sign": str(c.get("sign", "harm")),
                        "exp": {**{k: float(ex.get(k, 0.0)) for k in COMPS}, 'n': int(ex.get('n', 0))},
                        "ev": {"p": float((c.get("ev") or {}).get("p", 0.0)), "o": float((c.get("ev") or {}).get("o", 0.0))},
                        "born_t": int(c.get("born_t", 0)), "label": str(c.get("label", ""))})
        except Exception as e:
            print(f"SIGNAL→CHOICE: ошибка загрузки: {e!r}")

    def _form_emit(self, field, form, t):
        before = getattr(self, "_form_last_emit_t", None)
        super()._form_emit(field, form, t)
        if getattr(self, "_form_last_emit_t", None) != before and self.world is not None and self.cells:
            _sc_sync(self.world)
            cx, cy = self.get_center()
            W = Config.WORLD_SIZE
            SC['tx'].append((int(t), int(cx) % W, int(cy) % W, self.id, dict(form['spectrum'])))

    def _form_listen(self, field, t):
        w = self.world
        a0 = FORM_STATS['adopts']
        super()._form_listen(field, t)
        if w is None or not Config.SC_ENABLE or not Config.ENABLE_FORM_SPECTRUM or not self.cells:
            return
        try:
            _sc_sync(w)
            self._sc_init()
            self._sc_interpret(field, int(t), FORM_STATS['adopts'] > a0)
        except Exception as e:
            _sc_err('interpret', e)

    def _sc_provenance(self, cx, cy, t, obs):
        W = Config.WORLD_SIZE
        r2 = (Config.FORM_LISTEN_RADIUS + Config.SC_TX_PAD) ** 2
        own, foreign, geo_unconf = False, set(), 0
        for (te, ex, ey, pid, spec) in reversed(SC['tx']):
            if t - te > Config.SC_TX_WINDOW:
                break
            if te > t or _sc_dist2(cx, cy, ex, ey, W) > r2:
                continue
            if _sc_cos(spec, obs) < Config.SC_TX_COS:
                geo_unconf += 1                       # близко, но спектр не подтверждает: источник не объявляем
                continue
            if pid == self.id:
                own = True
            else:
                foreign.add(pid)
        if (own and foreign) or len(foreign) > 1:
            cat = 'mixed'
        elif foreign:
            cat = 'foreign'
        elif own:
            cat = 'own'
        else:
            cat = 'unknown'
        return cat, (next(iter(foreign)) if cat == 'foreign' else None), geo_unconf

    def _sc_interpret(self, field, t, adopted):
        W = Config.WORLD_SIZE
        cx, cy = self.get_center()
        cx, cy = int(cx) % W, int(cy) % W
        obs = _sc_heard(field, t, cx, cy)
        if obs is None:
            return
        st = SC['stats']
        cat, src, geo_unconf = self._sc_provenance(cx, cy, t, obs)
        st['prov_' + cat] += 1
        st['prov_geo_unconfirmed'] += geo_unconf
        scored = []
        for f in self.signal_forms:
            cos, nd = _sc_match(f['spectrum'], obs)
            scored.append((cos, nd, f))
        scored.sort(key=lambda x: -x[0])
        best = scored[0] if scored else None
        state, form, cpt, strength = 'none', None, None, 0.0
        if best is not None:
            bcos, bnd, bf = best
            if bcos >= Config.FORM_MATCH_COSINE and bnd <= Config.FORM_MATCH_NORM:
                state, form, strength = 'recognized', bf, bcos
                if len(scored) > 1 and scored[1][0] >= Config.FORM_MATCH_COSINE \
                        and bcos - scored[1][0] <= Config.SC_DOUBT_GAP:
                    state, strength = 'doubt', 0.5 * bcos
            elif bcos >= Config.SC_PARTIAL_COS:
                state, form, strength = 'partial', bf, bcos
        if state in ('none', 'partial'):
            for c in getattr(self, '_sc_concepts', ()):
                cc = _sc_cos(c['spec'], obs)
                if cc >= Config.SC_CONCEPT_COS and cc > strength:
                    state, cpt, strength = 'concept', c, cc          # обобщение работает там, где формы не совпали
        if state in ('recognized', 'partial', 'doubt', 'concept'):
            if phi_hash(self.id, t, 77001) < Config.SC_STRESS_MISS * _sc_stress(self):
                st['rec_stress_missed'] += 1                         # в стрессе: не распознал / не успел
                state, form, cpt = 'stress_missed', None, None
        st['rec_' + state] += 1
        st['rec_' + state + '_' + cat] += 1
        if Config.SC_ECHO_MODE == 'structure':
            r2 = (Config.FORM_LISTEN_RADIUS + Config.SC_ECHO_RADIUS) ** 2
            for (k, x0, y0, spec) in SC['echo_active']:
                if _sc_dist2(cx, cy, x0, y0, W) <= r2 and _sc_cos(spec, obs) >= Config.SC_ECHO_COS:
                    st['echo_heard'] += 1
                    if state in ('recognized', 'partial', 'doubt', 'concept'):
                        st['echo_recognized'] += 1
                    if adopted:
                        st['echo_adopted'] += 1
                    break
        if state in ('recognized', 'partial', 'doubt', 'concept'):
            self._sc_recent.append((t, form, cpt, strength, src, _form_ctx(self), state, cat))

    def _sc_expectation(self, t):
        acc, any_data = {c: 0.0 for c in COMPS}, False
        for (te, form, cpt, strength, src, ctx, state, cat) in self._sc_recent:
            age = t - te
            if age > Config.SC_RECENT_TICKS or age < 0:
                continue
            rec = _sc_exp_of(form, ctx) if form is not None else (cpt['exp'] if cpt is not None else None)
            if rec is None or rec['n'] < Config.SC_MIN_N:
                continue
            conf = rec['n'] / (rec['n'] + Config.SC_CONF_K)
            srcw = 1.0 if src is None else 0.5 + 0.5 * float(np.clip(_form_trust(self, src), 0.0, 1.0))
            w = strength * conf * srcw * (Config.SC_RECENT_DECAY ** age)
            for c in COMPS:
                acc[c] += w * rec[c]
            any_data = True
        if not any_data:
            return None
        return {c: float(np.clip(v, -Config.SC_Z_CLIP, Config.SC_Z_CLIP)) for c, v in acc.items()}

    def update_intent(self):
        if not Config.SC_ENABLE or not Config.SC_CHOICE or not self.goals or self.world is None:
            return super().update_intent()
        try:
            self._sc_init()
            E = self._sc_expectation(int(self.age))
        except Exception as e:
            _sc_err('expect', e)
            E = None
        if E is None:
            return super().update_intent()
        W = Config.SC_GOAL_W
        biased = []
        for g in self.goals:
            wv = W.get(g.get('type'), W['*'])
            d = float(np.clip(Config.SC_CHOICE_GAIN * sum(wv[c] * E[c] for c in COMPS),
                              -Config.SC_CHOICE_MAX, Config.SC_CHOICE_MAX))
            if d != 0.0:
                biased.append((g, d))
        st = SC['stats']
        st['choice_signal'] += 1
        if not biased:
            return super().update_intent()
        bias_of = {id(g): d for g, d in biased}
        best_b = max(self.goals, key=lambda g: (g['priority'] + bias_of.get(id(g), 0.0), -g['age']))
        best_0 = max(self.goals, key=lambda g: (g['priority'], -g['age']))
        prev_intent = self.intent
        for g, d in biased:
            g['priority'] += d
        try:
            super().update_intent()
        finally:
            for g, d in biased:
                g['priority'] -= d
        st['choice_bias_abs_x1000'] += int(1000 * sum(abs(d) for _, d in biased) / len(biased))
        if best_b is best_0:
            st['choice_noflip'] += 1                     # сигнал был, на выбор не повлиял
        elif self.intent is best_b and prev_intent is not best_b:
            st['choice_influenced'] += 1                 # повлиял: намерение сменилось из-за оценки
        elif self.intent is best_b:
            st['choice_reinforced'] += 1                 # повлиял: оценка подтвердила уже выбранное
        else:
            st['choice_blocked'] += 1                    # хотел, но не смог (обязательство/кулдаун)


# ------------------------------------------------------------
# ДВИЖОК: эхо до прослушивания, наблюдение чужих исходов, аудит, лог
# ------------------------------------------------------------
def _sc_observe_outcome(eng, q, x, y, t):
    SC['stats']['wit_events'] += 1
    q._sc_init()
    vec = {'m': -1.0, 'tr': 0.0, 'en': -1.0}              # гибель рядом: потеряли всё доступное (энергию, настроение)
    for e in reversed(q._sc_recent):
        if t - e[0] > Config.SC_WIT_WINDOW:
            break
        if e[1] is not None:
            _sc_learn_vec(q, e[1], e[5], vec, Config.SC_WIT_W, 'observed')
            _sc_evidence(q, e[1], 'observed', -1, Config.SC_WIT_EVID)
            SC['stats']['wit_credits'] += 1
            return
    if not Config.SC_WIT_BIRTH:
        SC['stats']['wit_no_context'] += 1
        return
    obs = _sc_heard(eng.field, t, x, y)
    if obs is None:
        SC['stats']['wit_no_context'] += 1               # события не вижу и сигнала нет: причину не выдумываем
        return
    best, bcos = None, 0.0
    for f in q.signal_forms:
        cos, _ = _sc_match(f['spectrum'], obs)
        if cos > bcos:
            best, bcos = f, cos
    if best is not None and bcos >= Config.SC_PARTIAL_COS:
        _sc_learn_vec(q, best, _form_ctx(q), vec, Config.SC_WIT_W, 'observed')
        _sc_evidence(q, best, 'observed', -1, Config.SC_WIT_EVID)
        SC['stats']['wit_credits'] += 1
    elif len(q.signal_forms) < Config.FORM_MAX:
        nf = {'spectrum': obs, 'uses': 0, 'outcome': 0.0, 'outcome_n': 0,
              'label': f'obs_{q.id}_{len(q.signal_forms)}', 'born_t': int(q.age)}
        q.signal_forms.append(nf)
        _sc_learn_vec(q, nf, _form_ctx(q), vec, Config.SC_WIT_W, 'observed')
        _sc_evidence(q, nf, 'observed', -1, Config.SC_WIT_EVID)
        SC['stats']['wit_forms_born'] += 1
    else:
        SC['stats']['wit_no_room'] += 1


def _sc_witness_deaths(eng, t):
    W = Config.WORLD_SIZE
    alive_now = {}
    for p in eng.patterns:
        if p.alive and p.cells:
            cx, cy = p.get_center()
            alive_now[p.id] = (int(cx) % W, int(cy) % W, getattr(p, 'role_type', None))
    prev = SC['alive_prev']
    deaths = [(pid, v) for pid, v in prev.items() if pid not in alive_now]
    SC['alive_prev'] = alive_now
    if not deaths or not Config.SC_WIT_ENABLE:
        return
    by_id = {p.id: p for p in eng.patterns if p.alive}
    r2 = Config.SC_WIT_RADIUS ** 2
    for pid, (x, y, role) in deaths:
        SC['stats']['deaths_seen'] += 1
        if role == 'feral':
            SC['stats']['wit_feral_death_ignored'] += 1
            continue
        for qid, qv in alive_now.items():
            if qv[2] == 'feral' or _sc_dist2(qv[0], qv[1], x, y, W) > r2:
                continue
            q = by_id.get(qid)
            if q is not None:
                _sc_observe_outcome(eng, q, x, y, t)


_SC_KEYS = ('rec_recognized', 'rec_partial', 'rec_doubt', 'rec_concept', 'rec_none', 'rec_stress_missed',
            'prov_foreign', 'prov_mixed', 'prov_own', 'prov_unknown', 'prov_geo_unconfirmed',
            'choice_signal', 'choice_noflip', 'choice_influenced', 'choice_reinforced', 'choice_blocked',
            'exp_upd_emitter', 'exp_upd_listener', 'exp_upd_observed', 'exp_warmup', 'listener_no_credit',
            'wit_events', 'wit_credits', 'wit_forms_born', 'wit_no_context', 'wit_no_room',
            'deaths_seen', 'wit_feral_death_ignored',
            'concepts_born', 'concepts_born_harm', 'concepts_born_help', 'concepts_merged', 'concepts_dropped',
            'echo_ticks', 'echo_site_ticks', 'echo_heard', 'echo_recognized', 'echo_adopted')


def _sc_snapshot(eng):
    alive = [p for p in eng.patterns if p.alive]
    forms = [f for p in alive for f in getattr(p, 'signal_forms', ())]
    with_exp = [f for f in forms if _sc_exp_of(f, '*') is not None]
    cons = [c for p in alive for c in getattr(p, '_sc_concepts', ())]
    return {'agents': len(alive), 'forms': len(forms), 'forms_with_exp': len(with_exp),
            'concepts_alive': len(cons), 'agents_with_concept': sum(1 for p in alive if getattr(p, '_sc_concepts', None)),
            'exp': {c: (round(float(np.mean([_sc_exp_of(f, '*')[c] for f in with_exp])), 4) if with_exp else None)
                    for c in COMPS}}


def _sc_tick_row(eng):
    row = {}
    for k in _SC_KEYS:
        cur = SC['stats'][k]
        row['sc_' + k] = cur - SC['prev'].get('t_' + k, 0)
        SC['prev']['t_' + k] = cur
    snap = _sc_snapshot(eng)
    row['sc_forms_with_exp'] = snap['forms_with_exp']
    row['sc_concepts_alive'] = snap['concepts_alive']
    return row


def _sc_line(eng, now):
    d = lambda k: SC['stats'][k] - SC['prev'].get('l_' + k, 0)
    cs = d('choice_signal')
    line = (f"[SIGNAL-CHOICE t={now}] rec: recognized={d('rec_recognized')} partial={d('rec_partial')} "
            f"doubt={d('rec_doubt')} concept={d('rec_concept')} none={d('rec_none')} stress_miss={d('rec_stress_missed')} | "
            f"prov: foreign={d('prov_foreign')} mixed={d('prov_mixed')} own={d('prov_own')} unknown={d('prov_unknown')} "
            f"geo_unconf={d('prov_geo_unconfirmed')} | choice: sig={cs} noflip={d('choice_noflip')} "
            f"influenced={d('choice_influenced')} reinforced={d('choice_reinforced')} blocked={d('choice_blocked')} "
            f"|bias|={(d('choice_bias_abs_x1000') / 1000.0 / max(1, cs)):.3f} | "
            f"learn: emitter={d('exp_upd_emitter')} listener={d('exp_upd_listener')} observed={d('exp_upd_observed')} "
            f"no_credit={d('listener_no_credit')} | wit: events={d('wit_events')} credits={d('wit_credits')} "
            f"born={d('wit_forms_born')} no_ctx={d('wit_no_context')} | "
            f"concepts: born={d('concepts_born')} merged={d('concepts_merged')}")
    snap = _sc_snapshot(eng)
    line += f" alive={snap['concepts_alive']} exp_forms={snap['forms_with_exp']}/{snap['forms']}"
    if Config.SC_ECHO_MODE == 'structure':
        line += (f" | echo: heard={d('echo_heard')} recognized={d('echo_recognized')} adopted={d('echo_adopted')}")
    line += f" | err={sum(d(k) for k in SC['stats'] if k.startswith('err_'))}"
    if SC.get('last_err'):
        line += f" last_err={SC['last_err']}"
    for k in list(SC['stats']):
        SC['prev']['l_' + k] = SC['stats'][k]
    return line


def _sc_echo_forms_alive(eng):
    specs = [s for (_, _, _, s) in SC['echo_active']]
    if not specs:
        return None
    n = 0
    for p in eng.patterns:
        if p.alive:
            for f in getattr(p, 'signal_forms', ()):
                if any(_sc_cos(f['spectrum'], s) >= 0.85 for s in specs):
                    n += 1
    return n


def _sc_summary(eng):
    snap = _sc_snapshot(eng)
    cons = [c for p in eng.patterns if p.alive for c in getattr(p, '_sc_concepts', ())]
    return {
        'version': 'signal-choice-1.0',
        'config': {k: (getattr(Config, k) if k != 'SC_GOAL_W' else getattr(Config, k)) for k in _SC_DEFAULTS},
        'stats': {k: int(v) for k, v in SC['stats'].items()},
        'snapshot': snap,
        'concepts': {'harm': sum(1 for c in cons if c['sign'] == 'harm'), 'help': sum(1 for c in cons if c['sign'] == 'help'),
                     'mean_n': (round(float(np.mean([c['exp']['n'] for c in cons])), 2) if cons else None),
                     'mean_exp': {c: (round(float(np.mean([x['exp'][c] for x in cons])), 4) if cons else None) for c in COMPS}},
        'baseline_cells': {c: len(SC['base'][c]) for c in COMPS},
        'abs_mean': {c: round(SC['absm'][c][0], 5) for c in COMPS},
        'echo_series': list(SC['echo_series']),
        'last_err': SC.get('last_err'),
    }


class SignalChoiceEngineMixin:
    def _post_semantic_step(self, t):
        _sc_sync(self)
        try:
            if Config.SC_ENABLE:
                _sc_echo_apply(self, int(self.age))        # эхо кладём ДО прослушивания
        except Exception as e:
            _sc_err('echo', e)
        super()._post_semantic_step(t)
        try:
            if Config.SC_ENABLE:
                _sc_witness_deaths(self, int(self.age))
                if int(self.age) % 50 == 0 and int(self.age) > 0 and Config.SC_ECHO_MODE == 'structure':
                    SC['echo_series'].append([int(self.age), _sc_echo_forms_alive(self)])
        except Exception as e:
            _sc_err('post', e)

    def _audit_close_tick(self, t, de_x1, res_x1, x2_step0):
        super()._audit_close_tick(t, de_x1, res_x1, x2_step0)
        try:
            _sc_sync(self)
            self._audit_rows[-1].update(_sc_tick_row(self))
            if int(self.age) % 50 == 0 and int(self.age) > 0:
                print(_sc_line(self, int(self.age)), flush=True)
        except Exception as e:
            _sc_err('audit', e)

    def audit_summary(self):
        S = super().audit_summary()
        try:
            S['signal_choice'] = _sc_summary(self)
        except Exception as e:
            _sc_err('summary', e)
        return S


def _sc_metrics(patterns, field, t, lexicon=None):
    try:
        return {'sc_' + k: int(SC['stats'][k]) for k in _SC_KEYS}
    except Exception:
        return {}


_sc_reset()
Pattern = extend_class(Pattern, SignalChoiceMixin)
EvolutionEngine = extend_class(EvolutionEngine, SignalChoiceEngineMixin)

if "register_metrics" in globals():
    register_metrics("signal_choice", _sc_metrics)
else:
    print("ℹ️ sc_* в metrics_history не подключены (audit rows и summary['signal_choice'] работают и без неё).")

print("✅ SIGNAL→CHOICE v1.0: распознавание (recognized/partial/doubt/concept/none/stress), выбор через ожидаемые последствия, "
      "обучение (свои исходы + чужие + кредит слушателю), концепт по порогу, эхо.")
print(f"   CHOICE={Config.SC_CHOICE} GAIN={Config.SC_CHOICE_GAIN} MAX={Config.SC_CHOICE_MAX} | WIT={Config.SC_WIT_ENABLE} "
      f"R={Config.SC_WIT_RADIUS} W={Config.SC_WIT_W} | CONCEPT_MIN={Config.SC_CONCEPT_MIN} | ECHO={Config.SC_ECHO_MODE}")
print("   выход: audit rows sc_*, summary['signal_choice'], [SIGNAL-CHOICE] раз в 50 тиков; обсервер — ячейка ADD-ON [O].")
