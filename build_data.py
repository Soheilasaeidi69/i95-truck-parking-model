"""Build the I-95 northbound corridor data set (FDOT District 4) from all FDOT files.
Sources
  Data_for_Table.xlsx        site capacity, hourly expanded occupancy (Mar/Jun/Nov/Dec 2024 x weekday x hour), county growth to 2045
  Existing Truck Parking Inventory (shp)   33 sites with coordinates and spaces (adds 3 Broward sites)
  Truck AADT 2024 (shp)      I-95 segments: mileposts, AADT, truck AADT, K, D, T factors  -> distances, congestion propensity, truck flows
  Hex8_External_Hourly (shp) informal (unauthorized) truck parking by zone and hour        -> validation of unauthorized-parking outcome
  Spatial Distribution 2045 (raster) kernel density of 2045 parking demand                  -> 2045 location of parking requests
  Finaldataclean.xls         candidate new sites (author's site-selection model)             -> candidate facilities
  currentTrucklocations.xlsx statewide inventory                                             -> cross-check of capacities
  crash.xlsx                 truck-involved crashes                                          -> context along the corridor
"""
import json, math, os, numpy as np, pandas as pd, rasterio

# folder with the prepared FDOT study files (not public); set FDOT_DATA to change it
RAW = os.environ.get('FDOT_DATA', 'fdot_data')
from pyproj import Transformer
V = np.load(RAW + '/i95_vertices.npy')                     # lat, lon, I-95 mile (0 = Miami-Dade/Broward line)
seg = pd.read_pickle(RAW + '/i95_segments.pkl')


def snap(lat, lon):
    dx = (V[:, 1] - lon) * np.cos(np.radians(lat)) * 111.32; dy = (V[:, 0] - lat) * 110.57
    d = np.hypot(dx, dy); k = d.argmin(); return float(V[k, 2]), float(d[k])


# ------------------------------------------------------------------ facilities usable by northbound I-95 trucks
FAC = [  # name in inventory, short label, public?
    ('Safe Truck Parking - Hallandale Beach', 'Safe Truck Parking Hallandale'), ('Discount Truck Parking (Hollywood)', 'Discount TP Hollywood'),
    ('Better Truck Parking', 'Better Truck Parking'), ("Tim's Truck Parking", "Tim's Truck Parking"), ('Florida 595 Truck Stop', 'Florida 595 Truck Stop'),
    ('Mobil Fuel', 'Mobil Fuel Pompano'), ('Discount Truck Parking (Andrews Ave)', 'Discount TP Andrews Ave'),
    ('Discount Truck Parking (Powerline Rd)', 'Discount TP Powerline Rd'), ('Discount Truck Parking (16th Terrace)', 'Discount TP 16th Terrace'),
    ('Marathon #18958', 'Marathon Riviera Beach'), ('Martin Co I-95 Weigh Station (WIM) Northbound', 'Martin WIM NB'),
    ('Martin Co Northbound Rest Area #40401', 'Martin Rest Area NB'), ('Marathon Truck Stop #149369', 'Marathon Truck Stop Ft Pierce'),
    ('Bell Avenue Storage and Parking', 'Bell Ave Parking'), ("Love's Travel Stop #415", "Love's #415"), ('Pilot Travel Center #90', 'Pilot #90'),
    ("Love's Travel Stop #467", "Love's #467"), ('Flying J Travel Plaza #622', 'Flying J #622'),
    ('St. Lucie Co Northbound Rest Area #40391', 'St. Lucie Rest Area NB'), ('TA Travel Center #197', 'TA #197'), ('RaceTrac #2586', 'RaceTrac Vero')]
PUBLIC_XY = {'Martin Co I-95 Weigh Station (WIM) Northbound': (27.0049, -80.2054), 'Martin Co Northbound Rest Area #40401': (27.128885, -80.332894),
             'St. Lucie Co Northbound Rest Area #40391': (27.4663, -80.4176)}
inv = pd.read_pickle(RAW + '/inventory.pkl')
su = pd.read_pickle(f'{RAW}/su_clean.pkl'); su['ZoneDescription'] = su.ZoneDescription.str.strip()
sd = pd.read_pickle(f'{RAW}/Site-data.pkl'); sd.columns = [str(c) for c in sd.iloc[1]]; sd = sd.iloc[2:32, :11]
sd['Existing Truck Parking Sites'] = sd['Existing Truck Parking Sites'].str.strip()
county_growth = sd.groupby('County')['Growth (%)'].first().astype(float).to_dict()      # study's county growth 2025->2045
spaces_wb = su.drop_duplicates('ZoneDescription').set_index('ZoneDescription').Parking_Spots.to_dict()

rows = []
for name, label in FAC:
    if name in PUBLIC_XY: lat, lon = PUBLIC_XY[name]; county = 'Martin' if 'Martin' in name else 'St. Lucie'; owner = 'Public'
    else:
        r = inv[inv.Location_N.astype(str).str.strip() == name].iloc[0]; lat, lon, county, owner = r.y, r.x, r.County, r.PublicPriv
    mile, off = snap(lat, lon)
    spaces = int(spaces_wb.get(name, 0)) or int(inv[inv.Location_N.astype(str).str.strip() == name].Truck_Park.iloc[0])
    rows.append(dict(name=name, label=label, lat=lat, lon=lon, county=county, owner=owner, mile=round(mile, 2), offset_km=round(off, 2),
                     spaces=spaces, observed=name in spaces_wb, growth2045=1 + county_growth[county]))
fac = pd.DataFrame(rows).sort_values('mile').reset_index(drop=True)

# ------------------------------------------------------------------ hourly occupancy scenarios (28 day types)
MONTHS = ['March', 'June', 'November', 'December']; DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
S = [(m, d) for m in MONTHS for d in DAYS]
occ = su.groupby(['ZoneDescription', 'Month', 'DayOfWeek', 'Hour'])['new_exp_count'].mean()
avg = su.groupby(['ZoneDescription', 'DayOfWeek', 'Hour'])['new_exp_count'].mean()
# utilization profile used for sites without observations: Broward daily-pay truck parking lots
proxy = ['Discount Truck Parking (Hollywood)', "Tim's Truck Parking", 'Discount Truck Parking (Andrews Ave)', 'Discount Truck Parking (16th Terrace)']
pu = su[su.ZoneDescription.isin(proxy)].assign(u=lambda x: x.new_exp_count / x.Parking_Spots)
proxy_u = pu.groupby(['Month', 'DayOfWeek', 'Hour']).u.mean(); proxy_ua = pu.groupby(['DayOfWeek', 'Hour']).u.mean()
eta = np.zeros((len(fac), 24, len(S))); imputed = np.zeros(len(fac))
for j, f in fac.iterrows():
    for s, (m, d) in enumerate(S):
        nxt = DAYS[(DAYS.index(d) + 1) % 7]
        for t in range(24):
            day, hr = (d, 16 + t) if t < 8 else (nxt, t - 8)
            if f.observed:
                k = (f['name'], m, day, hr)
                if k in occ.index: v = occ[k]
                else: v = avg[(f['name'], day, hr)]; imputed[j] += 1
            else:
                v = f.spaces * (proxy_u[(m, day, hr)] if (m, day, hr) in proxy_u.index else proxy_ua[(day, hr)]); imputed[j] += 1
            eta[j, t, s] = v
fac['imputed_share'] = imputed / (24 * len(S))

# ------------------------------------------------------------------ I-95 segments: truck flow and congestion propensity
segs = seg[['COUNTY', 'mi0', 'mi1', 'AADT', 'TruckAADT', 'KFCTR', 'DFCTR', 'TFCTR', 'DESC_FRM', 'DESC_TO']].reset_index(drop=True)
lo, hi = 50000.0, float(segs.AADT.max())
segs['congestion_propensity'] = ((segs.AADT - lo) / (hi - lo)).clip(0, 1)              # 0 rural (<=50k AADT) .. 1 busiest Broward segment

# ------------------------------------------------------------------ informal (unauthorized) parking along I-95 at 23:00 (validation)
hx = pd.read_csv(RAW + '/hex.csv', dtype={'exclude': str})
z = hx.drop_duplicates('ZoneId')[['ZoneId', 'lat', 'lon']]
z[['mile', 'km']] = [snap(a, b) for a, b in zip(z.lat, z.lon)]
hx = hx.merge(z[['ZoneId', 'mile', 'km']], on='ZoneId')
f23 = hx[(hx.F2_Mile_Bu == 'include') & (hx.exclude == '0') & (hx.km <= 3.3) & (hx.Hour == 23)]
ndays = hx.DataFrom_T.nunique()
bins = np.arange(0, 150, 5.0)
informal = (f23.groupby(pd.cut(f23.mile, bins), observed=False)['Count_expa'].sum() / ndays).reindex(pd.IntervalIndex.from_breaks(bins), fill_value=0).values

# ------------------------------------------------------------------ 2045 demand density along I-95 (raster)
tr = Transformer.from_crs(4326, 26917, always_xy=True)
with rasterio.open(RAW + '/demand2045.tif') as r:
    xs, ys = tr.transform(V[:, 1], V[:, 0]); kd = np.array([v[0] for v in r.sample(zip(xs, ys))])
kd = np.where(kd > 1e30, np.nan, kd)
kd2045 = pd.Series(kd).groupby(pd.cut(V[:, 2], bins), observed=False).mean().reindex(pd.IntervalIndex.from_breaks(bins)).fillna(0).values

# ------------------------------------------------------------------ candidate new sites from the site-selection model
c = pd.read_excel(RAW + '/final.xls', sheet_name='Sheet1')
c = c[(c.Latitude > 25.95) & (c.Latitude < 27.86) & (c.Longitude > -80.95)].drop_duplicates('PARCEL_ID')
cand = []
for _, r in c.iterrows():
    mile, off = snap(r.Latitude, r.Longitude)
    if off <= 5 and 20.4 < mile < 75.4:             # inside the Palm Beach gap
        scen = sorted(set(pd.read_excel(RAW + '/final.xls', sheet_name='Sheet1').query('PARCEL_ID == @r.PARCEL_ID').Scenario))
        cand.append(dict(parcel=str(r.PARCEL_ID), lat=r.Latitude, lon=r.Longitude, mile=round(mile, 2), offset_km=round(off, 2),
                         spaces=int(r.Estimated_Capacity_spaces), cost_M=float(r['Estimated_Cost_M$']), score=float(r.DynamicScore),
                         budgets=scen, county='Palm Beach' if mile > 25.3 else 'Broward'))
ded = {}
for x in cand:
    k = (round(x['lat'], 4), round(x['lon'], 4))
    if k in ded: ded[k]['budgets'] = sorted(set(ded[k]['budgets']) | set(x['budgets']))
    else: ded[k] = x
cand = sorted(ded.values(), key=lambda x: x['mile'])

# ------------------------------------------------------------------ cross-checks: statewide inventory and crashes
t = pd.read_excel(RAW + '/trucks.xlsx'); t = t[t.FDOT_DIST == 4]
cross = []
for _, r in t.iterrows():
    mile, off = snap(r.LAT, r.LONG)
    dd = np.hypot(fac.lat - r.LAT, fac.lon - r.LONG); near = fac[dd == dd.min()]
    if dd.min() < 0.002: cross.append(dict(statewide_name=str(r.Location_N), site=near.label.iloc[0], study_spaces=int(near.spaces.iloc[0]), statewide_spaces=int(r.TRUCK_SPAC)))
cr = pd.read_excel(RAW + '/crash.xlsx'); cr = cr[cr.latitude != 0]
cr = cr[(cr.latitude > 25.95) & (cr.latitude < 27.86) & (cr.longitude > -80.95)]
cr[['mile', 'km']] = [snap(a, b) for a, b in zip(cr.latitude, cr.longitude)]
cr = cr[cr.km <= 1.0]
crash = cr.groupby(pd.cut(cr.mile, [0, 25.3, 71.4, 96.2, 123.4, 142.6])).agg(n=('fatalities', 'size'), fatalities=('fatalities', 'sum'), injured=('injured', 'sum'))

out = dict(fac=fac.to_dict('records'), scenarios=S, eta=eta.tolist(), segs=segs.to_dict('records'),
           bins=bins.tolist(), informal23=[float(x) for x in informal], kd2045=[float(x) for x in kd2045], candidates=cand,
           cross=cross, crash={str(k): v for k, v in crash.to_dict('index').items()}, county_growth=county_growth,
           corridor_miles=float(seg.mi1.max()))
json.dump(out, open('corridor.json', 'w'), indent=1, default=float)
print(fac[['label', 'county', 'owner', 'mile', 'offset_km', 'spaces', 'observed', 'imputed_share', 'growth2045']].to_string())
print('candidates', [(c['mile'], c['spaces'], c['budgets']) for c in cand])
print('cross-check', cross); print(crash)
print('informal at 23h total', round(sum(informal)), 'kd2045 max', round(np.nanmax(kd2045), 1))
