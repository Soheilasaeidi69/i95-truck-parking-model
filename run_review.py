
import sys, os, json, time, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fdot_model as fm
from fdot_model import make_case, solve, report, make_ev, rule_plan, D
out = json.load(open('sensitivity.json')) if os.path.exists('sensitivity.json') else {}
def save(): json.dump(out, open('sensitivity.json', 'w'), indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)
def slim(r): return {k: r[k] for k in ('obj', 'reservations', 'temp_spaces', 'unauthorized', 'violation_h', 'search_h', 'honor_rate', 'time', 'status')}
N45 = json.load(open('results.json'))['meta']['N2045']
cases = {'2024': dict(N=100, seed=11), '2045': dict(N=N45, seed=11, year=2045, kd_weight=True)}
# ---------------- .4 value of the stochastic solution, perfect information, rule benchmark
for yr, kw in cases.items():
    if f'vss_{yr}' in out: continue
    d = make_case(**kw)
    rp = solve(d, 'reservation'); rr = report(d, rp)
    ev = make_ev(d); se = solve(ev, 'reservation')
    ee = solve(d, 'reservation', fix_y=se['y'], fix_e=se['e']); re_ = report(d, ee)
    ws = [solve(d, 'reservation', scen=[s])['obj'] for s in d['S']]
    yr_, er_ = rule_plan(d); ru = solve(d, 'reservation', fix_y=yr_, fix_e=er_); rru = report(d, ru)
    sq = report(d, solve(d, 'status_quo'))
    out[f'vss_{yr}'] = dict(RP=rp['obj'], EV=se['obj'], EEV=ee['obj'], WS=float(np.mean(ws)), VSS=ee['obj'] - rp['obj'], EVPI=rp['obj'] - float(np.mean(ws)),
                           RULE=ru['obj'], SQ=sq['obj'], rp=slim(rr), eev=slim(re_), rule=slim(rru), sq=slim(sq),
                           ev_res=sum(se['y'].values()), ev_temp=sum(se['e'].values()), rule_res=sum(yr_.values()))
    log('vss', yr, {k: round(v, 1) for k, v in out[f'vss_{yr}'].items() if isinstance(v, float)}); save()
# ----------------  cost sensitivity (2024; temporary-space cost in 2045)
base = dict(fm.P)
grid = [('phi_U', 1500.0, '2024'), ('phi_hat', 500.0, '2024'), ('phi_s', 25.0, '2024'), ('phi1', 10.0, '2024'), ('sigma', 500.0, '2045')]
for par, bv, yr in grid:
    for f in (0.25, 0.5, 2.0, 4.0):
        key = f'cost_{par}_{f}'
        if key in out: continue
        fm.P.update(base); fm.P[par] = bv * f
        d = make_case(**cases[yr])
        r = {'res': slim(report(d, solve(d, 'reservation')))}
        if par in ('phi_U', 'phi_hat', 'phi_s'): r['sq'] = slim(report(d, solve(d, 'status_quo')))
        out[key] = dict(par=par, factor=f, value=bv * f, year=yr, **r); fm.P.update(base)
        log('cost', par, f, round(r['res']['unauthorized'], 2), round(r['res']['violation_h'], 2)); save()
# ----------------  lexicographic: (1) unauthorized stops, (2) violation hours, (3) cost
for yr, kw in cases.items():
    key = f'lex_{yr}'
    if key in out: continue
    d = make_case(**kw)
    s = solve(d, 'reservation', lex=['unauth', 'viol']); r = report(d, s)
    out[key] = dict(lexvals=s['lexvals'], **slim(r)); log('lex', yr, s['lexvals'], round(r['obj'], 1)); save()
log('DONE')
