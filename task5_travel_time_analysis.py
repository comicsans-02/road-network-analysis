"""Task 5(2) and 5(3): average travel time per road segment, and the top-10 plots.

Each GPS point of a trip is placed on its matched route (projection onto the route polyline,
moving forward only), giving its distance along the route. Points are 15 s apart, so the time
at any position on the route is interpolated; the travel time of a segment is the time between
entering and leaving it. Only segments fully crossed between the first and last matched point
count (the partly crossed first and last ones are skipped).

Routes: by default P2's Task 3 CSV (data/processed/matched_1500.csv). Its segment ids are the 0-based
position of the edge in list(G.edges(keys=True)) of porto_drive.graphml, and trip_index is the row in
train-1500.csv (trips with fewer than two GPS points have an empty route and are skipped). The CSV does not say which GPS points were matched, so a
point is used only if it lies within --max-dist metres of the route (points past the end of a route
that stopped early are dropped). --routes leuven uses our reproduced routes (leuven_1500.csv) with the
matcher's matched-point count instead.

Waiting: a taxi standing still (pick-up, drop-off, red light) inflates the average. Two clocks
are kept: "with waiting" (plain timestamps) and "moving" (steps where the taxi advanced less than
--dwell-m metres count as 0 s). The ranking uses the moving clock unless --rank wait.
Travel time grows with segment length, so long roads rank high; average speed is in the CSV.

Usage: python task5_travel_time_analysis.py [--routes p2|leuven] [--min-obs 10] [--dwell-m 10]
       [--max-dist 50] [--rank move|wait]   (--routes leuven needs task6_robust_matching.py first)

Outputs in data/processed/: task5_top10_avgtime.csv, task5_all_avgtime.csv, task5_top10_traversed.csv,
task5_3_top10_avgtime.png, task5_3_top10_traversed.png.
The traversed top 10 (Task 5(1), used for 5(3)) is counted from P2's matched_1500.csv (total traversals).
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
import pandas as pd
from shapely.geometry import LineString, Point

DATA = Path("data/processed")
STEP_S = 15  # Porto taxi GPS sampling interval
LON0, LAT0 = -8.61, 41.15
KX, KY = 111320 * np.cos(np.radians(LAT0)), 110540  # metres per degree

G = ox.load_graphml(DATA / "porto_drive.graphml")
EDGES = list(G.edges(keys=True, data="length"))  # P2's segment id = position in this list
E = ox.graph_to_gdfs(G, nodes=False).reset_index().sort_values("length").drop_duplicates(["u", "v"])
GEOM = dict(zip(zip(E.u, E.v), E.geometry))
_MGEOM = {}


def edge_m(uv):
    if uv not in _MGEOM:
        c = np.array(GEOM[uv].coords)
        _MGEOM[uv] = LineString(np.column_stack([(c[:, 0] - LON0) * KX, (c[:, 1] - LAT0) * KY]))
    return _MGEOM[uv]


def place_points(path, pts, max_dist=np.inf):
    """Return (edges, chainage at each edge start, [(edge index, chainage)] per point)."""
    edges = [e for e in zip(path, path[1:]) if e in GEOM]
    geoms = [edge_m(e) for e in edges]
    start = np.concatenate([[0.0], np.cumsum([g.length for g in geoms])])
    out, j = [], 0
    for lon, lat in pts:
        p = Point((lon - LON0) * KX, (lat - LAT0) * KY)
        best = None
        for k in range(j, min(len(geoms), j + 40)):
            if start[k] > (out[-1][1] if out else 0) + 2500:
                break
            d = geoms[k].distance(p)
            if best is None or d < best[0] - 1e-6:
                best = (d, k, start[k] + geoms[k].project(p))
        if best is None:
            break
        if best[0] > max_dist:  # point not explained by the route (outlier, or past its end)
            continue
        j = best[1]
        out.append((j, max(best[2], out[-1][1]) if out else best[2]))
    return edges, start, out


def trip_segment_times(path, pts, dwell_m, max_dist=np.inf):
    """List of (edge, time with waiting, time moving) for every segment fully crossed, or None."""
    edges, start, placed = place_points(path, pts, max_dist)
    if len(placed) < 3:
        return None
    s = np.array([p[1] for p in placed])
    t_wait = np.arange(len(s)) * float(STEP_S)
    moving = np.concatenate([[False], np.diff(s) >= dwell_m])
    t_move = np.cumsum(np.where(moving, float(STEP_S), 0.0))
    keep = np.concatenate([[True], np.diff(s) > 1e-6])  # a repeated position keeps its earliest time
    su, tw, tm = s[keep], t_wait[keep], t_move[keep]
    if len(su) < 2:
        return None
    out = []
    for j, e in enumerate(edges):
        if start[j] >= su[0] and start[j + 1] <= su[-1]:
            a, b = start[j], start[j + 1]
            out.append((e, float(np.interp(b, su, tw) - np.interp(a, su, tw)),
                        float(np.interp(b, su, tm) - np.interp(a, su, tm))))
    return out


def plot_top(uvs, title, fname, color):
    """City overview on top, one zoomed panel per cluster of nearby segments below."""
    geoms = [GEOM[uv] for uv in uvs]
    cent = [g.centroid for g in geoms]
    clusters = []
    for r, c in enumerate(cent):
        for cl in clusters:
            if abs(cent[cl[0]].x - c.x) < 0.02 and abs(cent[cl[0]].y - c.y) < 0.02:
                cl.append(r)
                break
        else:
            clusters.append([r])
    ncol = len(clusters)
    fig = plt.figure(figsize=(max(4.5 * ncol, 9), 10))
    gs = fig.add_gridspec(2, ncol, height_ratios=[1.1, 1])
    ov = fig.add_subplot(gs[0, :])
    E.plot(ax=ov, color="#cccccc", linewidth=0.3)
    for g in geoms:
        ov.plot(*g.xy, color=color, linewidth=6, zorder=3)
    for r, c in enumerate(cent):
        ov.annotate(str(r + 1), (c.x, c.y), xytext=(6, 6), textcoords="offset points", fontsize=8, weight="bold", color=color)
    ov.set_aspect("equal"); ov.set_axis_off(); ov.set_title(title)
    for k, cl in enumerate(clusters):
        ax = fig.add_subplot(gs[1, k])
        xs = np.concatenate([np.array(geoms[r].coords)[:, 0] for r in cl])
        ys = np.concatenate([np.array(geoms[r].coords)[:, 1] for r in cl])
        pad = max(0.0015, 0.3 * max(np.ptp(xs), np.ptp(ys)))
        E.cx[xs.min() - pad:xs.max() + pad, ys.min() - pad:ys.max() + pad].plot(ax=ax, color="#cccccc", linewidth=0.6)
        for n, r in enumerate(cl):
            ax.plot(*geoms[r].xy, color=color, linewidth=4, zorder=3)
            ax.annotate(str(r + 1), (cent[r].x, cent[r].y), xytext=(8, 8 + 12 * (n % 3)), textcoords="offset points",
                        fontsize=10, weight="bold", bbox=dict(boxstyle="circle,pad=0.2", fc="white", ec=color),
                        arrowprops=dict(arrowstyle="-", color=color))
        ax.set_xlim(xs.min() - pad, xs.max() + pad); ax.set_ylim(ys.min() - pad, ys.max() + pad)
        ax.set_aspect("equal"); ax.set_axis_off()
    fig.savefig(DATA / fname, dpi=170, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-obs", type=int, default=10, help="min timed traversals for a segment to be ranked")
    ap.add_argument("--dwell-m", type=float, default=10.0, help="advance per 15 s step below this counts as standing still")
    ap.add_argument("--rank", choices=["move", "wait"], default="move")
    ap.add_argument("--routes", choices=["p2", "leuven"], default="p2")
    ap.add_argument("--max-dist", type=float, default=50.0, help="p2 routes: ignore GPS points farther from the route")
    a = ap.parse_args()

    trips = pd.read_csv(DATA / "train-1500.csv", dtype=str)
    polylines = [json.loads(s) for s in trips.POLYLINE]
    p2 = pd.read_csv(DATA / "matched_1500.csv", dtype=str).fillna("")
    jobs = []  # (node path, GPS points, max distance)
    if a.routes == "p2":
        for r in p2.itertuples():
            if not r.road_segment_ids.strip():
                continue  # trip with fewer than two GPS points: no route
            nodes = []
            for i in (int(x) for x in r.road_segment_ids.split()):
                u, v = EDGES[i][:2]
                if not nodes or nodes[-1] != u:
                    nodes.append(u)
                nodes.append(v)
            jobs.append((nodes, polylines[int(r.trip_index)], a.max_dist))
    else:
        routes = pd.read_csv(DATA / "leuven_1500.csv").fillna("")
        for pts, r in zip(polylines, routes.itertuples()):
            jobs.append(([int(x) for x in r.nodes.split(",") if x], pts[:int(r.n_matched)], np.inf))
    tw, tm = defaultdict(list), defaultdict(list)
    n_used = 0
    for path, pts, md in jobs:
        if len(path) < 3 or len(pts) < 3:
            continue
        res = trip_segment_times(path, pts, a.dwell_m, md)
        if res is None:
            continue
        n_used += 1
        for e, w, m in res:
            tw[e].append(w)
            tm[e].append(m)
    print(f"trips used: {n_used}; segments with a timed traversal: {len(tw)}")

    uv2id = {}  # (u, v) -> id of its shortest parallel edge, the one whose geometry is used
    for i, (u, v, _, length) in enumerate(EDGES):
        if (u, v) not in uv2id or length < EDGES[uv2id[(u, v)]][3]:
            uv2id[(u, v)] = i
    info = E.set_index(["u", "v"])
    rows = []
    for uv, w in tw.items():
        if len(w) >= a.min_obs:
            m = tm[uv]
            rows.append((uv2id.get(uv), uv[0], uv[1], np.mean(m), np.median(m), np.mean(w), np.median(w), len(w),
                         info.loc[uv, "length"], info.loc[uv, "name"], info.loc[uv, "highway"]))
    allt = pd.DataFrame(rows, columns=["segment_id", "u", "v", "avg_time_s", "median_time_s", "avg_time_incl_wait_s",
                                       "median_incl_wait_s", "n_obs", "length_m", "name", "highway"])
    allt["avg_speed_kmh"] = (allt.length_m / allt.avg_time_s.clip(lower=1e-6) * 3.6).round(1)
    allt.to_csv(DATA / "task5_all_avgtime.csv", index=False)
    key = "avg_time_s" if a.rank == "move" else "avg_time_incl_wait_s"
    top_time = allt.sort_values(key, ascending=False).head(10).reset_index(drop=True)
    top_time.to_csv(DATA / "task5_top10_avgtime.csv", index=False)
    pd.set_option("display.width", 220)
    print(f"top 10 by {key} (dwell threshold {a.dwell_m} m per step):")
    print(top_time.drop(columns=["u", "v"]).round(1).to_string())

    # 5(1): most traversed segments (P2's ids); 5(3): plot both sets
    traversals = Counter(int(x) for s in p2.road_segment_ids for x in s.split())
    trips_with = Counter(i for s in p2.road_segment_ids for i in {int(x) for x in s.split()})
    top_ids = [i for i, _ in traversals.most_common(10)]
    trav = pd.DataFrame([(i, traversals[i], trips_with[i], EDGES[i][0], EDGES[i][1], info.loc[EDGES[i][:2], "length"],
                          info.loc[EDGES[i][:2], "name"], info.loc[EDGES[i][:2], "highway"]) for i in top_ids],
                        columns=["segment_id", "traversals", "trips", "u", "v", "length_m", "name", "highway"])
    trav.to_csv(DATA / "task5_top10_traversed.csv", index=False)
    print("top 10 most traversed (P2 ids):")
    print(trav.drop(columns=["u", "v"]).round(1).to_string())
    print("next counts:", [c for _, c in traversals.most_common(14)][10:])
    plot_top([EDGES[i][:2] for i in top_ids], "5(1) Top 10 most traversed segments",
             "task5_3_top10_traversed.png", "crimson")
    kind = "excluding stops" if a.rank == "move" else "including waiting"
    plot_top(list(zip(top_time.u, top_time.v)), f"5(2) Top 10 segments by average travel time, {kind}",
             "task5_3_top10_avgtime.png", "royalblue")
    print("saved figures to", DATA)


if __name__ == "__main__":
    main()
