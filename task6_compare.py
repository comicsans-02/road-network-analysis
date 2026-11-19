"""Task 6: compare the Task 3 routes with the robust matching and plot before / after.

Failure case: Leuven silently stops at the first GPS point it cannot continue from, so a trip is
only matched for its first k points. All metrics are computed from the route geometry and the GPS
points only, so they treat every run the same way (P2's CSV has no matched-point count):
  coverage  = share of the trip's GPS points within --near-m of the route
  len_ratio = route length / raw GPS path length (about 1 when the whole trip is matched);
              a gap (two consecutive route nodes with no road between them) adds its straight-line
              length, so a disconnected route is not shorter than the ground it claims to cover
  gps_dist  = mean distance from every GPS point of the trip to the route (m)
  off_route = share of the route length farther than --off-m from the GPS trace (detours, loops)
  gaps      = consecutive route nodes with no road between them (a failed bridge), and their
              total straight-line length
For our own Leuven runs the share of points the matcher itself matched is also reported.

Runs (--runs, first two are compared per trip and plotted):
  p2            data/processed/matched_1500.csv, the Task 3 deliverable (segment id = row of the
                edge GeoDataFrame after reset_index(), trip_index = position among trips with >= 2 points)
  base          data/processed/leuven_1500.csv, our reproduction of Task 3 with PYTHONHASHSEED=0
  _robust, ...  data/processed/leuven_1500<tag>.csv from task6_robust_matching.py --robust --tag <tag>

Run first: python task6_robust_matching.py
           python task6_robust_matching.py --robust --tag _robust
           python task6_robust_matching.py --robust --look 1 --tag _robust_look1
Usage: python task6_compare.py [--runs p2 _robust base _robust_look1] [--plot trip ids ...]

Outputs in data/processed/: task6_summary.csv, task6_compare_per_trip.csv, task6_before_after.png
"""
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
import pandas as pd
import shapely
from shapely.geometry import LineString, MultiLineString

DATA = Path("data/processed")
N = 1500

ap = argparse.ArgumentParser()
ap.add_argument("--runs", nargs="+", default=["p2", "_robust", "base", "_robust_look1"])
ap.add_argument("--plot", type=int, nargs="*", default=None)
ap.add_argument("--low", type=float, default=0.7, help="coverage below this counts as a failure")
ap.add_argument("--near-m", type=float, default=50, help="a GPS point within this of the route is covered")
ap.add_argument("--off-m", type=float, default=100, help="route farther than this from the GPS trace is off-route")
a = ap.parse_args()


def haversine_m(p, q):
    lon1, lat1, lon2, lat2 = map(np.radians, (p[:, 0], p[:, 1], q[:, 0], q[:, 1]))
    h = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * np.arcsin(np.sqrt(h))


G = ox.load_graphml(DATA / "porto_drive.graphml")
EDGES = ox.graph_to_gdfs(G, nodes=False).reset_index()  # P2's segment id = row of this table
e = EDGES.sort_values("length").drop_duplicates(["u", "v"])
LEN = dict(zip(zip(e.u, e.v), e["length"]))
GEOM = dict(zip(zip(e.u, e.v), e.geometry))
XY = {n: (d["x"], d["y"]) for n, d in G.nodes(data=True)}

trips = pd.read_csv(DATA / "train-1500.csv", nrows=N, dtype=str)
gps = [np.array(json.loads(s), dtype=float).reshape(-1, 2) for s in trips.POLYLINE]
gps_len = [haversine_m(p[:-1], p[1:]).sum() if len(p) > 1 else 0.0 for p in gps]
VALID = [i for i, p in enumerate(gps) if len(p) >= 2]

LON0, LAT0 = -8.61, 41.15
KX, KY = 111320 * np.cos(np.radians(LAT0)), 110540  # metres per degree (local projection)


def to_m(xy):
    xy = np.asarray(xy, dtype=float)
    return np.column_stack([(xy[:, 0] - LON0) * KX, (xy[:, 1] - LAT0) * KY])


def metrics(tid, path):
    """coverage, near mask, route length, gps_dist, off_route, gaps, gap length of one trip."""
    p = gps[tid]
    pairs = list(zip(path, path[1:]))
    edges = [uv for uv in pairs if uv in GEOM]
    gap_pairs = [uv for uv in pairs if uv not in GEOM and uv[0] != uv[1]]
    gap_m = float(sum(haversine_m(np.array([XY[u]]), np.array([XY[v]]))[0] for u, v in gap_pairs))
    route_len = sum(LEN[uv] for uv in edges) + gap_m
    if not edges or len(p) < 2:
        return 0.0, np.zeros(len(p), bool), route_len, np.nan, np.nan, len(gap_pairs), gap_m
    route = MultiLineString([to_m(GEOM[uv].coords) for uv in edges])
    d = shapely.distance(shapely.points(to_m(p)), route)
    near = d <= a.near_m
    # sample the route every 10 m and measure each sample's distance to the GPS polyline
    trace = LineString(to_m(p))
    samples = [shapely.line_interpolate_point(g, np.arange(0, g.length, 10.0)) for g in route.geoms if g.length > 0]
    samples = np.concatenate(samples) if samples else np.array([])
    off = float((shapely.distance(samples, trace) > a.off_m).mean()) if len(samples) else np.nan
    return float(near.mean()), near, route_len, float(d.mean()), off, len(gap_pairs), gap_m


def load(run):
    """Per-trip table (index = row in train-1500.csv) with the route as a node path."""
    if run == "p2":
        p2 = pd.read_csv(DATA / "matched_1500.csv", dtype=str).fillna("")
        paths = {}
        for r in p2.itertuples():
            nodes = []
            for i in (int(x) for x in r.road_segment_ids.split()):
                u, v = int(EDGES.u.iat[i]), int(EDGES.v.iat[i])
                if not nodes or nodes[-1] != u:
                    nodes.append(u)
                nodes.append(v)
            paths[VALID[int(r.trip_index)]] = nodes
        d = pd.DataFrame({"path": [paths.get(t, []) for t in range(N)]})
        d["n_matched"] = np.nan  # not recorded in the Task 3 CSV
    else:
        f = DATA / f"leuven_{N}{'' if run == 'base' else run}.csv"
        d = pd.read_csv(f).fillna("").set_index("trip_id")
        d["path"] = d.nodes.apply(lambda s: [int(x) for x in str(s).split(",") if x])
    d["n_points"] = [len(p) for p in gps]
    m = [metrics(t, p) for t, p in zip(d.index, d.path)]
    d["coverage"], d["near"], d["route_len"], d["gps_dist"], d["off_route"], d["gaps"], d["gap_m"] = zip(*m)
    d["len_ratio"] = d.route_len / pd.Series(gps_len, index=d.index).replace(0, np.nan)
    d["matched_share"] = d.n_matched.astype(float) / d.n_points.clip(lower=1)
    return d


runs = {r: load(r) for r in a.runs}
valid = runs[a.runs[0]].n_points >= 2
rows = []
for name, d in runs.items():
    x = d[valid]
    rows.append({
        "run": name,
        "trips >=2 pts": len(x),
        "no route": int((x.path.apply(len) < 2).sum()),
        f"coverage<{a.low}": int((x.coverage < a.low).sum()),
        "mean coverage": round(x.coverage.mean(), 3),
        f"matched points<{a.low}": int((x.matched_share < a.low).sum()) if x.n_matched.notna().any() else np.nan,
        "median len_ratio": round(x.len_ratio.median(), 3),
        "len_ratio<0.7": int((x.len_ratio < 0.7).sum()),
        "len_ratio>1.5": int((x.len_ratio > 1.5).sum()),
        "median gps_dist m": round(x.gps_dist.median(), 1),
        "gps_dist>50m": int((x.gps_dist > 50).sum()),
        "mean off_route": round(x.off_route.mean(), 3),
        "off_route>0.2": int((x.off_route > 0.2).sum()),
        "trips with gaps": int((x.gaps > 0).sum()),
        "gaps": int(x.gaps.sum()),
        "gap length km": round(x.gap_m.sum() / 1000, 1),
    })
summary = pd.DataFrame(rows)
print(summary.set_index("run").T.to_string())
summary.to_csv(DATA / "task6_summary.csv", index=False)

b, f = runs[a.runs[0]], runs[a.runs[1]]
cols = ["coverage", "len_ratio", "gps_dist", "off_route", "gaps", "gap_m"]
cmp = pd.concat([b[cols].add_suffix("_before"), f[cols].add_suffix("_after")], axis=1)
cmp.insert(0, "n_points", b.n_points)
cmp.to_csv(DATA / "task6_compare_per_trip.csv")

ids = a.plot or cmp[valid].assign(gain=cmp.coverage_after - cmp.coverage_before) \
    .sort_values("gain", ascending=False).head(4).index.tolist()
fig, axes = plt.subplots(len(ids), 2, figsize=(11, 5 * len(ids)), squeeze=False)
labels = {"p2": "Task 3 CSV", "base": "our baseline"}
for row, tid in zip(axes, ids):
    p = gps[tid]
    pad = 0.003
    for ax, d, name in zip(row, (b, f), a.runs[:2]):
        e.cx[p[:, 0].min() - pad:p[:, 0].max() + pad, p[:, 1].min() - pad:p[:, 1].max() + pad].plot(
            ax=ax, color="#cccccc", linewidth=0.5, zorder=1)
        path = d.loc[tid, "path"]
        for uv in zip(path, path[1:]):
            if uv in GEOM:
                ax.plot(*GEOM[uv].xy, color="crimson", linewidth=2, zorder=2)
            elif uv[0] != uv[1]:  # gap: no road between the two nodes
                ax.plot(*zip(XY[uv[0]], XY[uv[1]]), color="crimson", linewidth=1, linestyle=":", zorder=2)
        near = d.loc[tid, "near"]
        ax.scatter(p[near, 0], p[near, 1], s=7, c="black", zorder=3, label=f"within {a.near_m:g} m of route")
        ax.scatter(p[~near, 0], p[~near, 1], s=7, c="#999999", zorder=3, label="farther")
        ax.set_xlim(p[:, 0].min() - pad, p[:, 0].max() + pad)
        ax.set_ylim(p[:, 1].min() - pad, p[:, 1].max() + pad)
        ax.set_title(f"trip {tid} - {labels.get(name, 'robust' if name == '_robust' else name)}: "
                     f"{int(near.sum())}/{len(p)} points within {a.near_m:g} m", fontsize=9)
        ax.set_aspect("equal")
        ax.legend(fontsize=7, loc="lower left")
fig.savefig(DATA / "task6_before_after.png", dpi=150, bbox_inches="tight")
print("plotted trips", ids, "->", DATA / "task6_before_after.png")
