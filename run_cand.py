"""Candidate sites and budget plans (2045, two truck samples) and the mile-47 site in 2024; updates results.json."""
import sys, os, json, time, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdot_model import make_case, solve, report, D
out = json.load(open('results.json'))
out = {k: v for k, v in out.items() if '_cand_' not in k and '_bundle_' not in k}
def run(key, d, modes):
    for mode in modes:
        s = solve(d, mode); r = report(d, s); out[f'{key}|{mode}'] = r
        print(time.strftime('%H:%M:%S'), key, mode, r['status'], round(r['unauthorized'], 2), round(r['violation_h'], 2), round(r['time'], 1), flush=True)
        json.dump(out, open('results.json', 'w'), indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
N45 = out['meta']['N2045']; C = D['candidates']
bund = {'Low ($175M)': [], 'Medium ($350M)': [], 'High ($650M)': []}
for c in C:
    for b in c['budgets']: bund[b].append(c)
for seed in (11, 22):
    for c in C: run(f"2045_s{seed}_cand_{c['mile']:.1f}", make_case(N=N45, seed=seed, year=2045, kd_weight=True, cand=[c]), ('reservation',))
    for b, cs in bund.items(): run(f'2045_s{seed}_bundle_{b}', make_case(N=N45, seed=seed, year=2045, kd_weight=True, cand=cs), ('status_quo', 'reservation'))
run('2024_s11_cand_47.2', make_case(N=100, seed=11, cand=[c for c in C if abs(c['mile'] - 47.23) < 0.1]), ('status_quo', 'reservation'))
print('DONE')
