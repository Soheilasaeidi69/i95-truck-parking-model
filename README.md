#  I-95 Truck Parking Reservation Model

An academic research model developed at Florida Atlantic University, with a case study of northbound I-95 in FDOT District 4 and adjacent corridor areas (142.6 miles, 21 truck parking facilities). The input data are not included in this repository.

Author: Soheila Saeidi, Florida Atlantic University

## What the model does

This research develops a two-stage stochastic mixed-integer optimization model to improve truck parking management along Florida's I-95 corridor.

The model considers uncertain parking occupancy, traffic congestion, facility capacity, and drivers' Hours-of-Service requirements. It evaluates parking reservations, allocation decisions, and potential infrastructure improvements.

The objective is to provide a data-driven decision-support framework for safer freight operations and truck parking infrastructure planning.

## Main results

Per night, for 100 trucks that need parking (146 in 2045). Trucks are generated, so these are model estimates.

| | Today (walk-in) | With reservations |
|---|---|---|
| HOS violation hours, 2024 | 17.3 | 9.0 |
| Search hours, 2024 | 23.3 | 0 |
| Unauthorized stops, 2024 | 6.8 | 6.8 |
| Unauthorized stops, 2045 | 9.2 | 6.1 |

These findings represent simulated outcomes for the I-95 corridor case study under the specified assumptions and should not be interpreted as measured improvements from field implementation.

- Reservations cut violation hours by about half and remove search time.
- Reservations do not remove unauthorized stops: about 70% of them fall in a 55-mile stretch of I-95, mostly in
  Palm Beach County, with one 13-space facility.
- In 2045, one new site at I-95 mile 47 lowers unauthorized stops from 6.1 to 1.1 per night, and three gap sites
  (miles 33, 47, 69) remove nearly all of them.
- Planning on average conditions costs 7.8% more than the stochastic plan in 2045; the difference is negligible in 2024.
 
## Corridor Profile
![I-95 Corridor Analysis](fig_corridor.png)

## Optimization Results
![I-95 Optimization Results](fig_results.png)

## Repository layout

```
fdot_model.py       Main stochastic optimization model
run_all.py          Baseline scenario experiments
run_cand.py         Candidate parking site analysis
run_review.py       Sensitivity analysis
make_validation.py  Comparison of modeled and observed parking patterns
figures.py          Research figures
build_data.py       Prepares model input data
fig_corridor.png    I-95 corridor analysis
fig_results.png     Optimization results
```

## Running the model

The model needs the input file `corridor.json`, prepared by `build_data.py`. The input data are not included.

With the input file in place:

```
pip install -r requirements.txt
python run_all.py
python run_cand.py
python run_review.py
python figures.py
```

```python
from fdot_model import make_case, solve, report

d = make_case(N=100, seed=11)                       # 2024, 100 trucks needing parking
print(report(d, solve(d, 'status_quo')))            # today's walk-in system
print(report(d, solve(d, 'reservation')))           # reservation system
```

The solver is HiGHS through PuLP (`solver='cbc'` also works). Main settings (speed, search-time curve, congestion
range, costs) are in the dictionary `P` at the top of `fdot_model.py`.

## Limits

- Trucks (positions and duty status) are generated; no truck-level data were available.
- The congestion range is an assumption (one-to-two-hour trips), not measured speeds.
- The search-time curve is an assumption, and the benefit of reservations rests mainly on it.
- The number of unauthorized stops depends on how far beyond their limit drivers are assumed to drive to reach a
  facility (30 minutes in the base case).
- Cost coefficients are illustrative; results are compared in hours and stops, not dollars.

## Contact

Soheila Saeidi, Department of Civil, Environmental and Geomatics Engineering, Florida Atlantic University.
