
Model features
  F1 search time: a truck without a confirmed space searches; search time grows with facility occupancy at arrival
     (FHWA: about one hour on average) and counts against the remaining legal driving time
  F2 congestion: travel times are scenario- and time-of-day dependent, by I-95 segment (AADT-based propensity)
  F3 unauthorized parking: when no legal space can be reached within the remaining legal time the truck stops
     where its hours run out (shoulder, ramp, side road) - a counted, penalized outcome
  F4 strict HOS: no tolerance; any driving beyond the remaining legal driving time is a violation (u)
  F5 real data: facilities, capacities, hourly occupancy, mileposts, truck flows, 2045 growth, candidate sites
"""
import json, math, os, time, numpy as np, pulp

D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'corridor.json')))
P = dict(speed=60.0, local_kmh=40.0, R=10, zeta=0.5, band=0.6, K_next=6,
         w=[10.0, 3.0, 1.0], phi=2.0, phi_hat=500.0, phi_U=1500.0, phi1=10.0, phi2=15.0, phi_bar=5.0, phi_s=25.0, sigma=500.0,
         s0=0.25, s1=0.75, u0=0.60, e_frac_public=0.25,
         g_weekday=(1.3, 2.5), g_weekend=(1.0, 1.5))
HPROF = {15: 1.0, 16: 1.0, 17: 1.0, 18: 1.0, 19: 0.6, 20: 0.3, 21: 0.1, 22: 0.05, 23: 0.05, 0: 0.05, 1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05,
         5: 0.2, 6: 0.5, 7: 1.0, 8: 1.0, 9: 0.8, 10: 0.4, 11: 0.4, 12: 0.4, 13: 0.4, 14: 0.6}


def segments():
    sg = D['segs']
    return np.array([s['mi0'] for s in sg]), np.array([s['mi1'] for s in sg]), np.array([s['congestion_propensity'] for s in sg]), \
           np.array([s['TruckAADT'] for s in sg])


MI0, MI1, PROP, TRK = segments()
LMAX = D['corridor_miles']


def travel(a, b, clock, g, cong=True):
    """hours to drive northbound from mile a to mile b leaving at clock hour (0-24); segments beyond the corridor at free flow"""
    if b <= a: return 0.0
    t = 0.0
    for m0, m1, p in zip(MI0, MI1, PROP):
        lo, hi = max(a, m0), min(b, m1)
        if hi <= lo: continue
        ff = (hi - lo) / P['speed']
        mult = 1 + (g - 1) * p * HPROF[int((clock + t) % 24)] if cong else 1.0
        t += ff * mult
    if b > LMAX: t += (b - max(a, LMAX)) / P['speed']
    return t


def make_case(N=100, seed=11, year=2024, cand=None, cong=True, kd_weight=False, occ_mult=1.0):
    """cand: list of candidate-site dicts to add (from corridor.json)"""
    g = np.random.default_rng(seed)
    fac = [dict(f) for f in D['fac']]
    eta = np.array(D['eta'])                                               # [j, t, s]
    prof = (eta / np.array([f['spaces'] for f in fac])[:, None, None]).mean(axis=0)       # 2024 corridor-average utilization profile
    if year == 2045:
        eta = eta * np.array([f['growth2045'] for f in fac])[:, None, None]
    if cand:
        for c in cand:
            fac.append(dict(label=f"NEW mile {c['mile']:.1f} ({c['spaces']} sp.)", mile=c['mile'], offset_km=c['offset_km'], spaces=c['spaces'],
                            owner='Candidate', county=c['county'], growth2045=1 + D['county_growth'][c['county']]))
            add = prof * c['spaces'] * (fac[-1]['growth2045'] if year == 2045 else 1.0)
            eta = np.concatenate([eta, add[None]], axis=0)
        order = np.argsort([f['mile'] for f in fac]); fac = [fac[k] for k in order]; eta = eta[order]
    kap = np.array([f['spaces'] for f in fac])
    eta = np.minimum(kap[:, None, None], np.rint(eta * occ_mult)).astype(int)
    J, T = range(len(fac)), range(24)
    S = range(len(D['scenarios']))
    gs = [g.uniform(*P['g_weekend']) if d in ('Saturday', 'Sunday') else g.uniform(*P['g_weekday']) for (m, d) in D['scenarios']]
    if not cong: gs = [1.0] * len(gs)
    # where trucks ask for parking: proportional to truck flow (2024) or to 2045 demand density x truck flow (2045)
    bins = np.array(D['bins']); centers = (bins[:-1] + bins[1:]) / 2
    flow = np.array([TRK[(MI0 <= c) & (MI1 > c)].mean() if ((MI0 <= c) & (MI1 > c)).any() else 0 for c in centers])
    wgt = flow * (np.array(D['kd2045']) if kd_weight else 1.0); wgt[centers > LMAX - 10] = 0; wgt = wgt / wgt.sum()
    trucks = []
    while len(trucks) < N:
        b = g.choice(len(centers), p=wgt); pos = float(g.uniform(bins[b], bins[b + 1]))
        tau = g.uniform(8, 11.5); om = tau + g.uniform(0.5, 3.0); c = g.uniform(0, 8)            # requests 16:00-24:00
        brk = g.uniform(5.0, 7.5); beta = min(8.0, max(0.0, tau - min(brk, tau))); q = g.uniform(30, 50) + om
        dest = pos + g.uniform(75, 150)
        rho = min(11 - tau, 14 - om, 70 - q)
        if travel(pos, dest, 16 + c, 1.0, cong=False) <= rho: continue                 # can finish the trip legally: no request
        trucks.append(dict(pos=pos, tau=tau, omega=om, c=c, beta=beta, q=q, dest=dest, rho=rho))
    I = range(len(trucks))
    th = np.zeros((len(trucks), len(fac), len(S))); tp = np.zeros((len(trucks), len(S)))
    for i, tk in enumerate(trucks):
        for s in S:
            for j, f in enumerate(fac):
                th[i, j, s] = travel(tk['pos'], f['mile'], 16 + tk['c'], gs[s], cong) + f['offset_km'] / P['local_kmh'] if f['mile'] >= tk['pos'] else 99
            tp[i, s] = travel(tk['pos'], tk['dest'], 16 + tk['c'], gs[s], cong)
    thm = np.median(th, axis=2)
    rho = [t['rho'] for t in trucks]
    theta = [int(r <= 0) for r in rho]; theta_h = [int(0 < r <= P['band']) for r in rho]
    w = [P['w'][0] if theta[i] else P['w'][1] if theta_h[i] else P['w'][2] for i in I]
    def rho_trip(i, hours):
        tk = trucks[i]; b = int(tk['beta'] + hours > 8.0)
        return min(11 - tk['tau'], 14 - tk['omega'] - 0.5 * b, 70 - tk['q']), b
    lam = np.zeros((len(trucks), len(fac)), dtype=int)
    for i, tk in enumerate(trucks):
        ok = [j for j, f in enumerate(fac) if tk['pos'] <= f['mile'] <= tk['dest'] and thm[i, j] <= max(rho_trip(i, thm[i, j])[0], 0) + P['zeta']]
        for j in sorted(ok, key=lambda j: fac[j]['mile'])[:P['K_next']]: lam[i, j] = 1
    # search time for walk-ins (no confirmed space), from occupancy at arrival
    srch = np.zeros_like(th); rho_j = np.zeros_like(th); bj = np.zeros_like(th)
    occ_r = {}; occ_w = {}
    for i, tk in enumerate(trucks):
        for j in J:
            if not lam[i, j]: continue
            for s in S:
                rj, b = rho_trip(i, th[i, j, s]); rho_j[i, j, s] = rj; bj[i, j, s] = b
                a = tk['c'] + th[i, j, s] + 0.5 * b
                t0 = min(23, int(a)); u = eta[j, t0, s] / kap[j]
                srch[i, j, s] = P['s0'] + P['s1'] * min(1.0, max(0.0, (u - P['u0']) / (1 - P['u0'])))
                occ_r[i, j, s] = (int(a), int(a) + P['R']); aw = a + srch[i, j, s]; occ_w[i, j, s] = (int(aw), int(aw) + P['R'])
            am = tk['c'] + thm[i, j]; occ_r[i, j, 'typ'] = (int(am), int(am) + P['R'])
    rho_d = np.array([[rho_trip(i, tp[i, s])[0] for s in S] for i in I])
    e_max = [math.ceil(P['e_frac_public'] * f['spaces']) if f['owner'] == 'Public' else 0 for f in fac]
    return dict(fac=fac, trucks=trucks, I=I, J=J, T=T, S=S, eta=eta, kap=kap, gs=gs, th=th, tp=tp, lam=lam, srch=srch, rho_j=rho_j,
                rho_d=rho_d, occ_r=occ_r, occ_w=occ_w, theta=theta, theta_h=theta_h, w=w, rho=rho, e_max=e_max, year=year, cong=cong)


def solve(d, mode='reservation', solver='highs', tl=1800, msg=False, scen=None, fix_y=None, fix_e=None, lex=None):
    """mode 'reservation' (proposed system) or 'status_quo' (no reservations: walk-in, continue, or unauthorized stop)"""
    I, J, T = d['I'], d['J'], d['T']; S = list(d['S']) if scen is None else list(scen); lam = d['lam']; nS = len(S); pi = 1.0 / nS
    V = pulp.LpVariable; L = pulp.lpSum; m = pulp.LpProblem('fdot', pulp.LpMinimize)
    pairs = [(i, j) for i in I for j in J if lam[i, j]]
    res = mode == 'reservation'
    y = {(i, j): V(f'y_{i}_{j}', cat='Binary') for (i, j) in pairs} if res else {}
    e = {j: V(f'e_{j}', lowBound=0, upBound=d['e_max'][j], cat='Integer') for j in J if d['e_max'][j] > 0} if res else {}
    h = {(i, j, s): V(f'h_{i}_{j}_{s}', cat='Binary') for (i, j) in pairs for s in S} if res else {}
    r = {(i, j, s): V(f'r_{i}_{j}_{s}', cat='Binary') for (i, j) in pairs for s in S} if res else {}
    wv = {(i, j, s): V(f'w_{i}_{j}_{s}', cat='Binary') for (i, j) in pairs for s in S}
    z1 = {(i, s): V(f'z1_{i}_{s}', cat='Binary') for i in I for s in S}
    z2 = {(i, s): V(f'z2_{i}_{s}', cat='Binary') for i in I for s in S}
    u = {(i, s): V(f'u_{i}_{s}', lowBound=0) for i in I for s in S}
    E = lambda j: e.get(j, 0)
    Y = lambda i: L(y[i, j] for j in J if (i, j) in y)
    for i in I:
        if res: m += Y(i) <= 1                                                                            # (2),(3)
    for j in J:                                                                                            # (4)
        if not res: break
        for t in T:
            tm = [y[i, j] for i in I if (i, j) in y and d['occ_r'][i, j, 'typ'][0] <= t < d['occ_r'][i, j, 'typ'][1]]
            if tm: m += L(tm) <= int(d['kap'][j]) + E(j)
    for (i, j) in pairs:
        for s in S:
            if res:
                m += h[i, j, s] <= y[i, j]                                                                 # (5)
                m += r[i, j, s] <= 1 - y[i, j]                                                             # (7)
    for j in J:                                                                                            # (8) hourly capacity
        for s in S:
            for t in T:
                tm = [h[i, j, s] for i in I if (i, j, s) in h and d['occ_r'][i, j, s][0] <= t < d['occ_r'][i, j, s][1]] + \
                     [r[i, j, s] for i in I if (i, j, s) in r and d['occ_r'][i, j, s][0] <= t < d['occ_r'][i, j, s][1]] + \
                     [wv[i, j, s] for i in I if (i, j, s) in wv and d['occ_w'][i, j, s][0] <= t < d['occ_w'][i, j, s][1]]
                if tm: m += int(d['eta'][j, t, s]) + L(tm) <= int(d['kap'][j]) + E(j)
    th, sr, rj, tp, rd = d['th'], d['srch'], d['rho_j'], d['tp'], d['rho_d']
    for i in I:
        for s in S:
            H = L(h[i, j, s] for j in J if (i, j, s) in h); Rr = L(r[i, j, s] for j in J if (i, j, s) in r)
            W = L(wv[i, j, s] for j in J if (i, j, s) in wv)
            if res:
                m += Rr <= Y(i) - H                                                                        # (9)
                m += W <= 1 - Y(i)                                                                         # (9b) walk-in only without reservation
            m += H + Rr + W + z1[i, s] + z2[i, s] == 1                                                     # (10)-(11)
            # (13) strict HOS: driving (+ search for walk-ins) beyond the remaining legal time is a violation
            m += (L((th[i, j, s] - rj[i, j, s]) * h[i, j, s] for j in J if (i, j, s) in h)
                  + L((th[i, j, s] - rj[i, j, s]) * r[i, j, s] for j in J if (i, j, s) in r)
                  + L((th[i, j, s] + sr[i, j, s] - rj[i, j, s]) * wv[i, j, s] for j in J if (i, j, s) in wv)
                  + (tp[i, s] - rd[i, s]) * z1[i, s] <= u[i, s])
            # (14) a violation is possible only when parking at a facility beyond the remaining legal time
            Om = {j: max(0.0, th[i, j, s] + sr[i, j, s] - rj[i, j, s]) for j in J if lam[i, j]}
            m += u[i, s] <= L(Om[j] * (h.get((i, j, s), 0) + r.get((i, j, s), 0) + wv[i, j, s]) for j in Om)
    if fix_y is not None:
        for k, v in y.items(): m += v == fix_y.get(k, 0)
    if fix_e is not None:
        for j, v in e.items(): m += v == fix_e.get(j, 0)
    first = P['phi'] * L(y.values()) + P['sigma'] * L(e.values())
    rec = []
    for s in S:
        for i in I:
            wi = d['w'][i]
            rec += [wi * P['phi_hat'] * u[i, s], wi * P['phi_U'] * z2[i, s], P['phi2'] * d['theta_h'][i] * z1[i, s]]
            if res: rec += [wi * P['phi1'] * (Y(i) - L(h[i, j, s] for j in J if (i, j, s) in h))]
            rec += [P['phi_bar'] * th[i, j, s] * (h.get((i, j, s), 0) + r.get((i, j, s), 0) + wv[i, j, s]) for j in J if lam[i, j]]
            rec += [P['phi_s'] * sr[i, j, s] * wv[i, j, s] for j in J if lam[i, j]]
    t0 = time.time()
    mk = lambda: pulp.HiGHS(msg=msg, timeLimit=tl) if solver == 'highs' else pulp.PULP_CBC_CMD(msg=msg, timeLimit=tl)
    lexvals = []
    if lex:
        # lexicographic priority (# lexicographic priority: each level): each level is minimized and then held at its optimum
        levels = {'unauth': pi * L(z2.values()), 'viol': pi * L(u.values()),
                  'search': pi * L(d['srch'][i, j, s] * wv[i, j, s] for (i, j, s) in wv)}
        for lv in lex:
            m.setObjective(levels[lv]); m.solve(mk()); v = pulp.value(m.objective) or 0.0
            lexvals.append(v); m += levels[lv] <= v + 1e-6
    m.setObjective(first + pi * L(rec))
    m.solve(mk())
    vv = lambda x: x.value() or 0.0
    return dict(status=pulp.LpStatus[m.status], obj=pulp.value(m.objective), time=time.time() - t0, lexvals=lexvals, S=S, nvars=len(m.variables()), ncons=len(m.constraints),
                y={k: round(vv(v)) for k, v in y.items()}, e={j: round(vv(v)) for j, v in e.items()},
                h={k: round(vv(v)) for k, v in h.items()}, r={k: round(vv(v)) for k, v in r.items()}, w={k: round(vv(v)) for k, v in wv.items()},
                z1={k: round(vv(v)) for k, v in z1.items()}, z2={k: round(vv(v)) for k, v in z2.items()}, u={k: vv(v) for k, v in u.items()}, mode=mode)


def report(d, sol):
    I, J = d['I'], d['J']; S = sol.get('S', list(d['S'])); nS = len(S)
    tot = lambda dct: sum(dct.values()) / nS
    search = sum(d['srch'][i, j, s] * v for (i, j, s), v in sol['w'].items() if v) / nS
    walk = tot(sol['w']); hon = tot(sol['h']); rea = tot(sol['r'])
    unauth = tot(sol['z2']); cont = tot(sol['z1']); viol = sum(sol['u'].values()) / nS
    tier = lambda i: 'mandatory' if d['theta'][i] else 'advised' if d['theta_h'][i] else 'safe'
    un_t = {k: sum(sol['z2'][i, s] for i in I for s in S if tier(i) == k) / nS for k in ('mandatory', 'advised', 'safe')}
    vi_t = {k: sum(sol['u'][i, s] for i in I for s in S if tier(i) == k) / nS for k in ('mandatory', 'advised', 'safe')}
    # where unauthorized stops happen: mile where hours run out
    um = []
    for (i, s), v in sol['z2'].items():
        if v: tk = d['trucks'][i]; um.append(tk['pos'] + max(0.0, tk['rho']) * P['speed'] / 1.3)
    nres = sum(sol['y'].values())
    return dict(obj=sol['obj'], status=sol['status'], time=sol['time'], trucks=len(I), reservations=nres, temp_spaces=sum(sol['e'].values()),
                honored=hon, reallocated=rea, walk_in=walk, continue_legal=cont, unauthorized=unauth, violation_h=viol, search_h=search,
                honor_rate=hon / nres if nres else None, unauth_by_tier=un_t, viol_by_tier=vi_t, unauth_miles=um,
                tiers=[sum(d['theta']), sum(d['theta_h']), len(I) - sum(d['theta']) - sum(d['theta_h'])], nvars=sol['nvars'], ncons=sol['ncons'],
                e={d['fac'][j]['label']: v for j, v in sol['e'].items() if v})


def make_ev(d):
    """expected-value problem: one scenario with mean occupancy, mean travel times and mean search times"""
    import copy
    e = dict(d); nS = len(d['S'])
    e['eta'] = np.rint(d['eta'].mean(axis=2, keepdims=True)).astype(int)
    for k in ('th', 'srch', 'rho_j'): e[k] = d[k].mean(axis=2, keepdims=True)
    e['tp'] = d['tp'].mean(axis=1, keepdims=True); e['rho_d'] = d['rho_d'].mean(axis=1, keepdims=True)
    occ_r, occ_w = {}, {}
    for (i, j, s), v in d['occ_r'].items():
        if s == 'typ': occ_r[i, j, 'typ'] = v
    for i in d['I']:
        for j in d['J']:
            if not d['lam'][i, j]: continue
            a = d['trucks'][i]['c'] + e['th'][i, j, 0]
            occ_r[i, j, 0] = (int(a), int(a) + P['R']); aw = a + e['srch'][i, j, 0]; occ_w[i, j, 0] = (int(aw), int(aw) + P['R'])
    e['occ_r'], e['occ_w'], e['S'] = occ_r, occ_w, range(1)
    return e


def rule_plan(d):
    """urgency-first nearest-facility rule: most urgent truck first; reserve the nearest reachable facility with at least
       one space of expected free capacity in every hour of the stay (no temporary spaces)"""
    Eeta = d['eta'].mean(axis=2); used = np.zeros_like(Eeta, dtype=float)
    y = {(i, j): 0 for i in d['I'] for j in d['J'] if d['lam'][i, j]}
    for i in sorted(d['I'], key=lambda i: d['rho'][i]):
        for j in sorted([j for j in d['J'] if d['lam'][i, j]], key=lambda j: d['fac'][j]['mile']):
            t0, t1 = d['occ_r'][i, j, 'typ']; ts = [t for t in d['T'] if t0 <= t < t1]
            if all(d['kap'][j] - Eeta[j, t] - used[j, t] >= 1 for t in ts):
                y[i, j] = 1
                for t in ts: used[j, t] += 1
                break
    return y, {j: 0 for j in d['J'] if d['e_max'][j] > 0}
