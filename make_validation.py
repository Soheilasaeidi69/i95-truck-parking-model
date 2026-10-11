import json, numpy as np
r = json.load(open('results.json')); D = json.load(open('corridor.json')); bins = np.array(D['bins'])
bands = [(0, 25.3, 'Broward'), (25.3, 71.4, 'Palm Beach'), (71.4, 96.2, 'Martin'), (96.2, 123.4, 'St. Lucie'), (123.4, 142.6, 'Indian River'), (142.6, 1e9, 'Beyond corridor (Brevard)')]
obs = np.array(D['informal23']); cen = (bins[:-1] + bins[1:]) / 2
um = []
for s in (11, 22, 33): um += [float(x) for x in r[f'2024_cong_s{s}|status_quo']['unauth_miles']]
um = np.array(um); val = []
for a, b, n in bands:
    o = obs[(cen >= a) & (cen < b)].sum() / obs.sum() if b < 1e8 else None
    m = ((um >= a) & (um < b)).sum() / len(um); val.append((n, o, m)); print(n, o, round(m, 3))
json.dump(val, open('validation.json', 'w'))
