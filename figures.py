import json, numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
D = json.load(open('corridor.json')); R = json.load(open('results.json'))
BLUE, ORANGE, AQUA, GREY, INK, MUTED = '#2a78d6', '#eb6834', '#1baf7a', '#c9c8c2', '#0b0b0b', '#52514e'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK,
                     'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})
bounds = [(0, 25.3, 'Broward'), (25.3, 71.4, 'Palm Beach'), (71.4, 96.2, 'Martin'), (96.2, 123.4, 'St. Lucie'), (123.4, 142.6, 'Indian River')]

# ---------------- Figure 1: corridor profile
fig, ax = plt.subplots(3, 1, figsize=(7.5, 6.2), sharex=True, gridspec_kw=dict(height_ratios=[1, 1.3, 1], hspace=0.42))
for a in ax:
    a.axvspan(20.4, 75.4, color='#f3efe6', zorder=0)
    for b in bounds[1:]: a.axvline(b[0], color=GREY, lw=0.8, zorder=1)
    a.grid(axis='y', color='#ececea', lw=0.6); a.set_axisbelow(True)
sg = D['segs']
x = np.ravel([[s['mi0'], s['mi1']] for s in sg]); y = np.ravel([[s['TruckAADT'], s['TruckAADT']] for s in sg]) / 1000
ax[0].plot(x, y, color=BLUE, lw=2); ax[0].set_ylabel('Trucks per day\n(thousands)')
ax[0].set_title('Truck traffic on I-95 (FDOT Truck AADT)', loc='left', fontsize=9, color=INK)
for (a0, a1, n) in bounds: ax[0].text((a0 + a1) / 2, 31, n, ha='center', fontsize=8, color=MUTED)
ax[0].set_ylim(0, 34)
f = D['fac']
ax[1].bar([q['mile'] for q in f], [q['spaces'] for q in f], width=1.4, color=BLUE, label='Existing facility (spaces)')
c = D['candidates']
ax[1].bar([q['mile'] for q in c], [q['spaces'] for q in c], width=1.4, color='white', edgecolor=ORANGE, lw=1.4, label='Candidate site (site-selection model)')
for q in c: ax[1].text(q['mile'], q['spaces'] + 12, f"{q['mile']:.0f}", ha='center', fontsize=7, color=ORANGE)
ax[1].set_ylabel('Truck parking\nspaces'); ax[1].set_ylim(0, 560); ax[1].legend(frameon=False, fontsize=8, loc='upper right')
ax[1].text(47.9, 240, 'Palm Beach gap:\n55 miles, 13 spaces', ha='center', fontsize=8, color=INK)
ax[1].set_title('Designated truck parking within 5 km of I-95 (northbound use)', loc='left', fontsize=9, color=INK)
bins = np.array(D['bins']); cen = (bins[:-1] + bins[1:]) / 2
ax[2].bar(cen, D['informal23'], width=4.4, color=AQUA)
ax[2].set_ylabel('Trucks parked\ninformally at 23:00'); ax[2].set_xlabel('I-95 milepost (0 = Miami-Dade/Broward line)')
ax[2].set_title('Informal truck parking within 2 miles of I-95 (FDOT hex-zone data, average night)', loc='left', fontsize=9, color=INK)
ax[2].set_xlim(0, 143)
fig.savefig('figs/fig_corridor.png', dpi=300, bbox_inches='tight'); fig.savefig('figs/fig_corridor.pdf', bbox_inches='tight')

# ---------------- Figure 2: results
avg = lambda keys, m: np.mean([R[k][m] for k in keys])
cases = [('2024\nwalk-in today', ['2024_cong_s11|status_quo', '2024_cong_s22|status_quo', '2024_cong_s33|status_quo']),
         ('2024\nreservations', ['2024_cong_s11|reservation', '2024_cong_s22|reservation', '2024_cong_s33|reservation']),
         ('2045\nwalk-in', ['2045_s11|status_quo', '2045_s22|status_quo']),
         ('2045\nreservations', ['2045_s11|reservation', '2045_s22|reservation']),
         ('2045 res. + gap sites\nLow budget (mile 47)', ['2045_s11_bundle_Low ($175M)|reservation', '2045_s22_bundle_Low ($175M)|reservation']),
         ('2045 res. + gap sites\nMedium (33, 47, 69)', ['2045_s11_bundle_Medium ($350M)|reservation', '2045_s22_bundle_Medium ($350M)|reservation']),
         ('2045 res. + gap sites\nHigh (all five)', ['2045_s11_bundle_High ($650M)|reservation', '2045_s22_bundle_High ($650M)|reservation'])]
fig, ax = plt.subplots(1, 3, figsize=(7.5, 3.0), gridspec_kw=dict(wspace=0.55))
mets = [('unauthorized', 'Unauthorized stops per night'), ('violation_h', 'HOS violation hours per night'), ('search_h', 'Search hours per night')]
cols = [GREY, BLUE, GREY, BLUE, ORANGE, ORANGE, ORANGE]
for a, (m, t) in zip(ax, mets):
    v = [avg(k, m) for _, k in cases]
    a.barh(range(len(cases)), v, color=cols, height=0.62)
    for yy, vv in enumerate(v): a.text(vv + max(v) * 0.02, yy, f'{vv:.1f}', va='center', fontsize=7, color=INK)
    a.set_yticks(range(len(cases))); a.set_yticklabels([n for n, _ in cases] if m == 'unauthorized' else [], fontsize=7)
    a.invert_yaxis(); a.set_title(t, fontsize=8.5, loc='left', color=INK); a.set_xlim(0, max(v) * 1.25)
    a.grid(axis='x', color='#ececea', lw=0.6); a.set_axisbelow(True)
fig.savefig('figs/fig_results.png', dpi=300, bbox_inches='tight'); fig.savefig('figs/fig_results.pdf', bbox_inches='tight')
print('ok')
