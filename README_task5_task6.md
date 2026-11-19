# Task 5(2), Task 5(3) and Task 6 (map matching with LeuvenMapMatching)

Add the dependencies once: `uv add leuvenmapmatching rtree` (osmnx already brings geopandas and shapely).
All scripts run from the repository root and read/write `data/processed/`. Inputs already in the repo (in `data/processed/`):
`train-1500.csv`, `porto_drive.graphml`, `matched_1500.csv` (P2).

## Run order
```powershell
uv run python task5_travel_time_analysis.py                         # Task 5(2) + 5(3), on P2's matched_1500.csv
uv run python task6_robust_matching.py                              # our reproduction of Task 3 -> leuven_1500.csv
uv run python task6_robust_matching.py --robust --tag _robust       # Task 6 fix                 -> leuven_1500_robust.csv
uv run python task6_robust_matching.py --robust --look 1 --tag _robust_look1   # ablation: direct bridge only
uv run python task6_compare.py                                      # Task 6: Task 3 CSV vs fix, plus the other runs
```
The matcher runs take several minutes each and can run in parallel.

## Task 5(2): average travel time per segment
Each GPS point is placed on its matched route (distance along the route). Points are 15 s apart, so the time at any position is interpolated and a segment's travel time is the time between entering and leaving it (only segments fully crossed count). Taxis standing still (advance under 10 m per 15 s) are excluded from the "moving" clock, because pick-ups and red lights otherwise inflate the average; the plain clock is kept in the CSV (`avg_time_incl_wait_s`). Segments need at least 10 timed traversals. Travel time grows with length, so long roads rank high; `avg_speed_kmh` is in the CSV.
Outputs: `task5_top10_avgtime.csv`, `task5_all_avgtime.csv`, `task5_top10_traversed.csv` (Task 5(1), counted from P2's ids), `task5_3_top10_avgtime.png`, `task5_3_top10_traversed.png` (5(3)).

## Task 6: partial matches
Failure: Leuven stops at the first GPS point it cannot continue from and silently returns only the matched prefix (e.g. trip 1226 in the Task 3 CSV: 2 of 70 points near the route). Fix (`--robust`): skip the failing point, restart matching from the next point (if nothing could be matched from a point, only that point is skipped) and join the pieces with a shortest-path bridge of at most 2 km. At each join up to 6 nodes may be trimmed off the route end and the next piece start (`--look`), minimising bridge length + dropped matched road; this removes the overlap when a restarted piece begins behind the previous one. If no bridge exists the pieces are joined with a gap. The output records `n_matched` (summed over pieces) and `matched_pts` (the matched point ranges, e.g. `0-11;13-40`).

Settings: the defaults of `task6_robust_matching.py` are the ones `match_trip()` in `task3_map_matching.ipynb` actually used for `matched_1500.csv` (`max_dist` 300 m, `obs_noise` 50 m, `dist_noise` 50 m, `max_lattice_width` 10, non-emitting states with length factor 0.75). With these, our baseline gives the same route as the Task 3 CSV for 1266 of 1481 trips (after removing repeated segment IDs as the notebook does) and the same summary figures.

Reproducibility: Leuven's tie-breaking depends on Python's randomised string hashing, so routes change between runs. `task6_robust_matching.py` re-launches itself with `PYTHONHASHSEED=0`; all numbers below are reproducible. P2's notebook does not fix the seed, which is why 215 trips differ.

Diagnosis of the baseline: 255 trips stop early (193 with under 70% of points matched). At the first failing point no point is farther than 300 m from a road; 63 are GPS jumps of more than 500 m in 15 s, the other 192 lie on a road (median 3.5 m) a normal 137 m from the previous point, i.e. the transition model fails.

Metrics (`task6_compare.py`) use only the route geometry and the GPS points, so the Task 3 CSV (no matched-point count) is measured like our runs: coverage = share of GPS points within 50 m of the route; route length adds the straight-line length of each gap, so a disconnected route is not shorter than the ground it claims to cover.

| (1481 trips with at least 2 points) | Task 3 CSV (before) | our reproduction | after | after, `--look 1` |
|---|---|---|---|---|
| trips with coverage < 0.7 | 216 | 216 | 37 | 27 |
| mean coverage | 0.878 | 0.878 | 0.956 | 0.959 |
| routes under 0.7x / over 1.5x GPS path length | 184 / 31 | 183 / 37 | 14 / 79 | 3 / 90 |
| median GPS-to-route distance (m) | 6.1 | 6.1 | 5.9 | 5.9 |
| trips with mean GPS-to-route distance > 50 m | 252 | 252 | 47 | 26 |
| trips with > 20% of route over 100 m from the GPS trace | 102 | 100 | 111 | 108 |
| gaps (trips with a gap) | 57 (43) | 0 (0) | 108 (68) | 182 (118) |
| total straight-line gap length (km) | 18.4 | 0 | 414.8 | 591.2 |

Compared with the Task 3 CSV, 242 trips gain more than 5 percentage points of coverage and none loses that much.
Limits: the fix adds some over-long routes (detours in dense, noisy areas) and leaves gaps where no bridge is found within 2 km; it only catches matches that stop, not wrong matches that don't; there is no ground truth.
Outputs: `task6_summary.csv`, `task6_compare_per_trip.csv` (Task 3 CSV vs fix), `task6_before_after.png` (black points within 50 m of the route, dotted line = gap).

## Segment ids
P2's `road_segment_ids` are the 0-based position of the edge in `list(G.edges(keys=True))` of `porto_drive.graphml`, and `trip_index` is the position among the trips with at least two GPS points. Task 5(2) times P2's routes directly; the CSV has no matched-point count, so GPS points farther than 50 m from the route are ignored (`--max-dist`). `--routes leuven` times our reproduced routes instead. `build_segment_id_map.py` is no longer needed.
