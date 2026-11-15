# Task 5(2), Task 5(3) and Task 6 (map matching with LeuvenMapMatching)

Add the dependencies once: `uv add leuvenmapmatching rtree` (osmnx already brings geopandas and shapely).
All scripts run from the repository root and read/write `data/processed/`. Inputs already in the repo:
`train-1500.csv`, `porto_drive.graphml`, `matched_1500.csv` (P2).

## Run order
```powershell
uv run python task6_robust_matching.py                              # baseline = P2's settings -> leuven_1500.csv
uv run python task6_robust_matching.py --robust --tag _robust       # Task 6 fix            -> leuven_1500_robust.csv
uv run python build_segment_id_map.py                               # P2's segment ids -> (u, v)  -> segment_id_map.csv
uv run python task5_travel_time_analysis.py                         # Task 5(2) + 5(3)
uv run python task6_compare.py                                      # Task 6 before/after
```
The two matcher runs take several minutes each.

## Task 5(2): average travel time per segment
Each GPS point is placed on its matched route (distance along the route). Points are 15 s apart, so the time at any position is interpolated and a segment's travel time is the time between entering and leaving it (only segments fully crossed count). Taxis standing still (advance under 10 m per 15 s) are excluded from the "moving" clock, because pick-ups and red lights otherwise inflate the average; the plain clock is kept in the CSV (`avg_time_incl_wait_s`). Segments need at least 10 timed traversals. Travel time grows with length, so long roads rank high; `avg_speed_kmh` is in the CSV.
Outputs: `task5_top10_avgtime.csv`, `task5_all_avgtime.csv`, `task5_3_top10_avgtime.png`, `task5_3_top10_traversed.png` (5(3), both top-10 sets; the traversed set is counted from P2's ids).

## Task 6: partial matches
Failure: Leuven stops at the first GPS point it cannot continue from and silently returns only the matched prefix (e.g. trip 93: 3 of 141 points). Fix (`--robust`): skip the failing point, restart matching from the next point and join the pieces with a shortest-path bridge of at most 2 km.

| (1481 trips with at least 2 points) | before | after |
|---|---|---|
| trips with under 70% of points matched | 345 | 1 |
| mean share of points matched | 0.84 | 0.99 |
| routes under 0.7x GPS path length | 327 | 48 |
| routes over 1.5x GPS path length | 39 | 104 |

Limits: the fix adds some over-long routes (small detour loops in dense, noisy areas); it only catches matches that stop, not wrong matches that don't; the metrics are coverage and length ratio, not ground truth.
Outputs: `task6_summary.csv`, `task6_compare_per_trip.csv`, `task6_before_after.png`.

## Segment ids
P2's `road_segment_ids` are not defined in the repo. `build_segment_id_map.py` recovers them: our Leuven run reproduces P2's routes closely, so ids are matched position by position on trips with equal segment counts and the majority vote is taken. About 96% of all traversals are covered; unmapped ids cannot be drawn. Replace this step if P2 provides the id table.
