import sys, json, time, numpy as np
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import fdot_model as fm
from fdot_model import make_case, solve, report, D, P
out = {}
def run(key, d, modes=('status_quo', 'reservation')):
    for mode in modes:
        s = solve(d, mode); r = report(d, s); out[f'{key}|{mode}'] = r
        print(time.strftime('%H:%M:%S'), key, mode, {k: (round(float(v), 2) if isinstance(v, (float, np.floating)) else v) for k, v in r.items()
              if k in ('obj', 'status', 'time', 'reservations', 'honor_rate', 'temp_spaces', 'unauthorized', 'violation_h', 'search_h', 'walk_in')}, flush=True)
        json.dump(out, open('results.json', 'w'), indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
# truck demand growth 2025->2045: county growth weighted by truck flow along I-95
segs = D['segs']; cg = D['county_growth']
wsum = sum(s['TruckAADT'] * (s['mi1'] - s['mi0']) for s in segs)
G = sum(s['TruckAADT'] * (s['mi1'] - s['mi0']) * (1 + cg[s['COUNTY']]) for s in segs) / wsum
N45 = int(round(100 * G)); out['meta'] = dict(N2024=100, N2045=N45, growth=G)
print('2045 growth', round(G, 3), 'trucks', N45)
for seed in (11, 22, 33): run(f'2024_cong_s{seed}', make_case(N=100, seed=seed))
run('2024_freeflow_s11', make_case(N=100, seed=11, cong=False))
fm.P['s0'], fm.P['s1'] = 1.0, 0.0                       # FHWA national average search of one hour, independent of occupancy
run('2024_search1h_s11', make_case(N=100, seed=11), modes=('status_quo',))
fm.P['s0'], fm.P['s1'] = 0.25, 0.75
for seed in (11, 22): run(f'2045_s{seed}', make_case(N=N45, seed=seed, year=2045, kd_weight=True))
C = D['candidates']
for c in C: run(f"2045_s11_cand_{c['mile']:.1f}", make_case(N=N45, seed=11, year=2045, kd_weight=True, cand=[c]), modes=('reservation',))
bund = {'Low ($175M)': [], 'Medium ($350M)': [], 'High ($650M)': []}
for c in C:
    for b in c['budgets']: bund[b].append(c)
for b, cs in bund.items(): run(f'2045_s11_bundle_{b}', make_case(N=N45, seed=11, year=2045, kd_weight=True, cand=cs), modes=('status_quo', 'reservation'))
run('2024_s11_cand_47.2', make_case(N=100, seed=11, cand=[c for c in C if abs(c['mile'] - 47.23) < 0.1]), modes=('status_quo', 'reservation'))
print('DONE')
