# AI6128 Project 2: Porto Taxi Trajectory and Road Network Analysis

Map matching and route analysis of the first 1,500 trips of the ECML/PKDD 2015 Porto taxi dataset
(Kaggle `train.csv`) on the OpenStreetMap driving network of Porto.

## Setup

```powershell
uv sync
uv add leuvenmapmatching rtree tqdm folium
```

Place Kaggle's `train.csv` in the repository root (it is not committed). All scripts run from the
repository root and read and write `data/processed/`, which already contains every input and output
listed below, so any task can be run without rerunning the earlier ones.

## Files

| Task | Code | Output in `data/processed/` |
| --- | --- | --- |
| 1 Data preparation | `task1_data_preparation.py` | `train-1500.csv`, `porto_drive.graphml` |
| 2 GPS points | `task2_gps_visualization.py` | `task2_first_15_trips.png` |
| 3 Map matching | `task3_map_matching.ipynb` | `matched_1500.csv`, `matched_15.csv`, `segment_id_map_p2.csv` |
| 4 Matched routes | `task4_route_visualization.py` | `task4_first_15_routes.png`, `task4_routes_per_trip.png` |
| 5(1) Most traversed segments | `task5_1_most_traversed.py` | `task5_1_top10_traversed.csv` |
| 5(2), 5(3) Travel time and figures | `task5_travel_time_analysis.py` | `task5_top10_avgtime.csv`, `task5_all_avgtime.csv`, `task5_top10_traversed.csv`, `task5_3_top10_avgtime.png`, `task5_3_top10_traversed.png` |
| 6 Partial matches | `task6_robust_matching.py`, `task6_compare.py` | `leuven_1500.csv`, `leuven_1500_robust.csv`, `leuven_1500_robust_look1.csv`, `task6_summary.csv`, `task6_compare_per_trip.csv`, `task6_before_after.png` |
| 6 GPS jumps | `task6_gps_jump_fix_task.ipynb` | `task6_gps_jump.png` |

## Run order

```powershell
uv run python task1_data_preparation.py
uv run python task2_gps_visualization.py
# Task 3: run task3_map_matching.ipynb (see below)
uv run python task4_route_visualization.py
uv run python task5_1_most_traversed.py
uv run python task5_travel_time_analysis.py
uv run python task6_robust_matching.py                                        # reproduction of Task 3 -> leuven_1500.csv
uv run python task6_robust_matching.py --robust --tag _robust                 # Task 6 fix            -> leuven_1500_robust.csv
uv run python task6_robust_matching.py --robust --look 1 --tag _robust_look1  # direct bridges only   -> leuven_1500_robust_look1.csv
uv run python task6_compare.py
# Task 6 GPS jumps: run task6_gps_jump_fix_task.ipynb
```

The three `task6_robust_matching.py` runs take several minutes each and can run in parallel. The two
notebooks read and write files in their working directory, so start them with `data/processed/` as the
working directory and set `CSV_PATH` in `task3_map_matching.ipynb` to `train-1500.csv`.

## Task 1: data preparation

`train-1500.csv` holds the first 1,500 rows of `train.csv` in their original order. The road network is
the OSMnx `drive` network inside the bounding box of all GPS points, padded by 0.05 degrees on every
side, simplified and saved as `porto_drive.graphml` (53,903 nodes, 124,814 directed edges).

## Task 2: GPS points

The raw GPS points of the first 15 trips are plotted over the road network, one colour per trip.

## Task 3: map matching

Library: `leuvenmapmatching` (`DistanceMatcher`, a hidden Markov model matcher after Newson and Krumm
2009, solved with the Viterbi algorithm). Trips with fewer than two GPS points (19 of 1,500) are skipped,
so 1,481 trips are matched.

| Parameter | Value | What it controls |
| --- | --- | --- |
| `max_dist` | 300 m | Maximum distance from a GPS point to a candidate road segment |
| `obs_noise` | 50 m | Expected GPS error (width of the emission probability) |
| `dist_noise` | 50 m | Allowed difference between route length and GPS distance in a transition |
| `non_emitting_states` | True | Lets the route pass nodes that have no nearby GPS point |
| `non_emitting_length_factor` | 0.75 | Penalty for such transitions |
| `max_lattice_width` | 10 | Maximum number of candidates kept per GPS point |

Output format: `matched_1500.csv` has one row per matched trip with `trip_index` (position among the
trips with at least two points), `TRIP_ID`, `road_segment_ids` (space-separated) and `num_segments`. A
segment ID is the position of the directed edge in `ox.graph_to_gdfs(G, nodes=False).reset_index()`, which
is the same order as `list(G.edges(keys=True))`; `segment_id_map_p2.csv` lists the start and end node
(`id`, `u`, `v`) of every ID. A segment that is matched more than once in a trip is listed only once.
`matched_15.csv` holds the first 15 trips.

## Task 4: matched routes

Each segment ID of the first 15 routes is looked up in `segment_id_map_p2.csv` and drawn with its road
geometry from the network: all routes on one map, and one map per trip with its raw GPS points.

## Task 5: route analysis

**5(1)** counts how often each segment ID occurs in `matched_1500.csv` and how many trips use it, and
lists the ten most traversed segments with their OpenStreetMap name, type and length.

**5(2)** estimates the average travel time per segment from the Task 3 routes:
- each GPS point within 50 m of its route is projected onto the route, giving its distance along the
  route (points farther away are ignored, `--max-dist`); a point is only placed after the previous one
  and within the next 40 edges, so time never runs backwards;
- points are 15 s apart, so the time at any position is interpolated, and a segment's travel time is
  the time between entering and leaving it (only segments crossed completely between the first and
  last GPS point count);
- a 15 s step that advances less than 10 m counts as 0 s, so pick-ups, drop-offs and red lights do not
  inflate the average (the average including stops is kept as `avg_time_incl_wait_s`);
- a segment is ranked only with at least 10 timed traversals.

Travel time grows with length, so `avg_speed_kmh` is also reported. With `--routes leuven` the script
times the reproduced routes in `leuven_1500.csv` instead of `matched_1500.csv`.

**5(3)** draws both top-10 sets on the network: a city overview with the segments numbered by rank,
above zoomed panels of the segments that lie close together.

## Task 6: failure cases of map matching

### Partial matches

Failure: when no candidate of the next GPS point can be reached, LeuvenMapMatching stops without an
error and returns only the route up to the last matched point.

`task6_robust_matching.py` uses the Task 3 settings above. Without `--robust` it reproduces Task 3
(`leuven_1500.csv`). With `--robust`, when the matcher stops it skips the failing point and restarts
from the next one (if nothing can be matched from a point, only that point is skipped), and joins the
pieces with the shortest road path of at most 2 km (`--max-gap-m`). At each join up to 6 nodes may be
trimmed off the end of the route and the start of the next piece (`--look`), choosing the join with the
smallest bridge length plus dropped matched length; this removes the overlap when a restarted piece
begins slightly behind the previous one. If no bridge exists the pieces are joined with a gap. Trips
that are matched completely are not changed. The output records `n_matched` (points matched, summed
over all pieces) and `matched_pts` (the matched point ranges, e.g. `0-11;13-40`).

LeuvenMapMatching breaks ties in an order that depends on Python's randomised string hashing, so the
script re-launches itself with `PYTHONHASHSEED=0` and its results are reproducible. With the same
settings, the reproduction gives the same route as `matched_1500.csv` for 1,266 of 1,481 trips and the
same summary figures.

`task6_compare.py` compares the routes with the GPS points (there is no ground truth), using only the
route geometry, so `matched_1500.csv` is measured in the same way as the other runs: coverage (share of
GPS points within 50 m of the route), route length over GPS path length (a gap adds its straight-line
length), the distance from the GPS points to the route, and the share of the route farther than 100 m
from the GPS trace.

| 1,481 trips with at least 2 points | Task 3 (`matched_1500.csv`) | Reproduction | After the fix | After, `--look 1` |
| --- | --- | --- | --- | --- |
| Trips with coverage < 0.7 | 216 | 216 | 37 | 27 |
| Mean coverage | 0.878 | 0.878 | 0.956 | 0.959 |
| Routes under 0.7x / over 1.5x GPS path length | 184 / 31 | 183 / 37 | 14 / 79 | 3 / 90 |
| Median GPS-to-route distance (m) | 6.1 | 6.1 | 5.9 | 5.9 |
| Trips with mean GPS-to-route distance > 50 m | 252 | 252 | 47 | 26 |
| Trips with > 20% of the route over 100 m from the GPS trace | 102 | 100 | 111 | 108 |
| Gaps (trips with a gap) | 57 (43) | 0 (0) | 108 (68) | 182 (118) |
| Total straight-line gap length (km) | 18.4 | 0 | 414.8 | 591.2 |

Compared with Task 3, 242 trips gain more than 5 percentage points of coverage and none loses that
much. Limits: the fix adds some over-long routes (detours in dense, noisy areas) and leaves a gap where
no road path of at most 2 km exists; it only repairs matches that stop, not wrong matches that continue.
`task6_before_after.png` shows the trips with the largest gain (black points lie within 50 m of the
route, a dotted line is a gap).

### GPS coordinate jumps

`task6_gps_jump_fix_task.ipynb` finds trips with a jump of more than 500 m between consecutive GPS
points, removes such points in one forward pass (`filter_jumps()`, each point is compared with the
previous accepted point), re-matches the cleaned trips and compares the number of matched segments
before and after. `task6_gps_jump.png` shows an example trip.
