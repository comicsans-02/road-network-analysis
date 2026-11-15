"""Task 6: compare the baseline Leuven matching with the robust version and plot before / after.

Failure case: Leuven silently stops at the first GPS point it cannot continue from, so a trip is
only matched for its first k points. Metrics per trip:
  coverage  = n_matched / n_points   (share of GPS points the route actually explains)
  len_ratio = matched route length / raw GPS path length   (about 1 when the whole trip is matched)

Run first: python task6_robust_matching.py && python task6_robust_matching.py --robust --tag _robust
Usage: python task6_compare.py [--after _robust] [--plot trip ids ...]

Outputs in data/processed/: task6_summary.csv, task6_compare_per_trip.csv, task6_before_after.png
"""
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
import pandas as pd

DATA = Path("data/processed")
N = 1500

ap = argparse.ArgumentParser()
ap.add_argument("--before", default="")
ap.add_argument("--after", default="_robust")
ap.add_argument("--plot", type=int, nargs="*", default=None)
ap.add_argument("--low", type=float, default=0.7, help="coverage below this counts as a failure")
a = ap.parse_args()


def haversine_m(p, q):
    lon1, lat1, lon2, lat2 = map(np.radians, (p[:, 0], p[:, 1], q[:, 0], q[:, 1]))
    h = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * np.arcsin(np.sqrt(h))


G = ox.load_graphml(DATA / "porto_drive.graphml")
e = ox.graph_to_gdfs(G, nodes=False).reset_index().sort_values("length").drop_duplicates(["u", "v"])
LEN = dict(zip(zip(e.u, e.v), e["length"]))
GEOM = dict(zip(zip(e.u, e.v), e.geometry))

trips = pd.read_csv(DATA / "train-1500.csv", nrows=N, dtype=str)
gps = [np.array(json.loads(s), dtype=float) for s in trips.POLYLINE]
gps_len = [haversine_m(p[:-1], p[1:]).sum() if len(p) > 1 else 0.0 for p in gps]


def load(tag):
    d = pd.read_csv(DATA / f"leuven_{N}{tag}.csv").fillna("").set_index("trip_id")
    d["path"] = d.nodes.apply(lambda s: [int(x) for x in s.split(",") if x])
    d["route_len"] = d.path.apply(lambda p: sum(LEN.get(x, 0) for x in zip(p, p[1:])))
    d["coverage"] = np.where(d.n_points >= 2, d.n_matched / d.n_points.clip(lower=1), np.nan)
    d["len_ratio"] = d.route_len / pd.Series(gps_len, index=d.index).replace(0, np.nan)
    return d


b, f = load(a.before), load(a.after)
valid = b.n_points >= 2
rows = []
for name, d in (("before", b), ("after", f)):
    x = d[valid]
    rows.append({
        "run": name,
        "trips >=2 pts": len(x),
        "no route": int((x.nodes == "").sum()),
        f"coverage<{a.low}": int((x.coverage < a.low).sum()),
        "mean coverage": round(x.coverage.mean(), 3),
        "median len_ratio": round(x.len_ratio.median(), 3),
        "len_ratio<0.7": int((x.len_ratio < 0.7).sum()),
        "len_ratio>1.5": int((x.len_ratio > 1.5).sum()),
    })
summary = pd.DataFrame(rows)
print(summary.to_string(index=False))
summary.to_csv(DATA / "task6_summary.csv", index=False)
cmp = pd.DataFrame({"n_points": b.n_points, "cov_before": b.coverage, "cov_after": f.coverage,
                    "ratio_before": b.len_ratio, "ratio_after": f.len_ratio})
cmp.to_csv(DATA / "task6_compare_per_trip.csv")

ids = a.plot or cmp[valid].assign(gain=cmp.cov_after - cmp.cov_before).sort_values("gain", ascending=False).head(4).index.tolist()
fig, axes = plt.subplots(len(ids), 2, figsize=(11, 5 * len(ids)), squeeze=False)
for row, tid in zip(axes, ids):
    p = gps[tid]
    for ax, d, name in zip(row, (b, f), ("before", "after")):
        path = d.loc[tid, "path"]
        pad = 0.003
        e.cx[p[:, 0].min() - pad:p[:, 0].max() + pad, p[:, 1].min() - pad:p[:, 1].max() + pad].plot(
            ax=ax, color="#cccccc", linewidth=0.5, zorder=1)
        for uv in zip(path, path[1:]):
            if uv in GEOM:
                ax.plot(*GEOM[uv].xy, color="crimson", linewidth=2, zorder=2)
        k = int(d.loc[tid, "n_matched"])
        ax.scatter(p[:k, 0], p[:k, 1], s=7, c="black", zorder=3, label="matched points")
        ax.scatter(p[k:, 0], p[k:, 1], s=7, c="#999999", zorder=3, label="not matched")
        pad = 0.003
        ax.set_xlim(p[:, 0].min() - pad, p[:, 0].max() + pad)
        ax.set_ylim(p[:, 1].min() - pad, p[:, 1].max() + pad)
        ax.set_title(f"trip {tid} - {name}: {k}/{len(p)} points matched", fontsize=9)
        ax.set_aspect("equal")
        ax.legend(fontsize=7, loc="lower left")
fig.savefig(DATA / "task6_before_after.png", dpi=150, bbox_inches="tight")
print("saved", DATA / "task6_before_after.png")
