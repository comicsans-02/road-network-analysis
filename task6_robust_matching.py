"""Task 6: robust map matching with LeuvenMapMatching on data/processed/porto_drive.graphml.

Baseline (our seeded reproduction of Task 3, with the settings task3_map_matching.ipynb actually
used: max_dist 300 m, obs_noise 50 m, dist_noise 50 m, max_lattice_width 10):
    python task6_robust_matching.py
Fix for the failure found in Task 6:
    python task6_robust_matching.py --robust --tag _robust

Failure: Leuven stops at the first GPS point it cannot continue from (no road within max_dist,
or the lattice dies after a GPS jump) and silently returns only the matched prefix of the trip.
--robust skips the failing point, restarts matching from the next one and joins the pieces with
a shortest-path bridge (at most --max-gap-m), so the rest of the trip is not lost.

Output: data/processed/leuven_<n><tag>.csv with trip_id (row in train-1500.csv), n_points,
n_matched (number of GPS points matched, summed over all pieces), matched_pts (the matched point
indices as ranges, e.g. "0-11;13-40") and nodes (node ids along the matched path).
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# LeuvenMapMatching breaks ties in an order that depends on Python's string hashing, which is
# randomised per process, so the same trip can get a different route in each run. Fixing the
# seed makes the output reproducible: re-launch this script with PYTHONHASHSEED=0.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    sys.exit(subprocess.call([sys.executable] + sys.argv))

import networkx as nx
import osmnx as ox
import pandas as pd
from leuvenmapmatching.map.inmem import InMemMap
from leuvenmapmatching.matcher.distance import DistanceMatcher

DATA = Path("data/processed")

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=1500, help="number of trips (first n)")
# defaults = the values match_trip() in task3_map_matching.ipynb used for matched_1500.csv
ap.add_argument("--max-dist", type=float, default=300)
ap.add_argument("--obs-noise", type=float, default=50)
ap.add_argument("--dist-noise", type=float, default=50)
ap.add_argument("--lattice-width", type=int, default=10)
ap.add_argument("--robust", action="store_true", help="restart after a failed point and join pieces")
ap.add_argument("--max-gap-m", type=float, default=2000, help="longest shortest-path bridge between pieces")
ap.add_argument("--look", type=int, default=6,
                help="nodes that may be trimmed at a join (1 = only bridge end of path -> start of piece)")
ap.add_argument("--tag", default="")
a = ap.parse_args()

G = ox.load_graphml(DATA / "porto_drive.graphml")
mp = InMemMap("porto", use_latlon=True, use_rtree=True, index_edges=True)
for n, d in G.nodes(data=True):
    mp.add_node(n, (d["y"], d["x"]))
for u, v in G.edges():
    mp.add_edge(u, v)


def match_once(pts):
    """Match pts; return (node path, number of leading points matched)."""
    m = DistanceMatcher(mp, max_dist=a.max_dist, obs_noise=a.obs_noise, dist_noise=a.dist_noise,
                        non_emitting_states=True, non_emitting_length_factor=0.75,
                        max_lattice_width=a.lattice_width)
    try:
        _, last = m.match(pts)
    except Exception:
        return [], 0
    return list(m.path_pred_onlynodes), last + 1


def edge_len(u, v):
    """Length of the shortest edge u -> v (0 if there is none, e.g. an earlier gap)."""
    return min((d["length"] for d in G.get_edge_data(u, v, default={}).values()), default=0.0)


def join(path, piece, look=None):
    """Append piece to path through the shortest bridge of at most max_gap_m; return (path, bridged).

    A restarted piece often begins a little behind where the previous one ended (the matcher picks
    the edge under the next GPS point), so the direct bridge end -> start can need a long detour on
    one-way streets. We therefore also try trimming up to `look` nodes off the end of the path and
    off the start of the piece. Cost = bridge length + length of the matched road that is dropped,
    so trimming only wins when it saves more detour than the matched road it removes.
    Compared with the direct bridge only (--look 1), this leaves 108 instead of 182 gaps and fewer
    over-long routes, but drops some matched road (trips with GPS points over 50 m from the route:
    47 instead of 26).
    If no bridge exists the pieces are joined without a road between them (a gap, counted by
    task6_compare.py)."""
    look = look or a.look
    best = None
    drop_end = 0.0  # length of path[i:] being dropped
    for i in range(len(path) - 1, max(len(path) - 1 - look, 0) - 1, -1):
        if i < len(path) - 1:
            drop_end += edge_len(path[i], path[i + 1])
        try:
            dist, sp = nx.single_source_dijkstra(G, path[i], cutoff=a.max_gap_m, weight="length")
        except nx.NodeNotFound:
            continue
        drop_start = 0.0  # length of piece[:j] being dropped
        for j, y in enumerate(piece[:look]):
            if j > 0:
                drop_start += edge_len(piece[j - 1], y)
            if y in dist:
                cost = dist[y] + drop_end + drop_start
                if best is None or cost < best[0]:
                    best = (cost, i, j, sp[y])
    if best is None:
        return path + piece, False
    _, i, j, sp = best
    return path[:i + 1] + sp[1:] + piece[j + 1:], True


def match_robust(pts):
    """Return (node path, number of points matched, matched point ranges [(first, last), ...])."""
    pieces, ranges, pos = [], [], 0
    while len(pts) - pos >= 2:
        nodes, k = match_once(pts[pos:])
        if len(nodes) >= 2 and k >= 1:
            pieces.append(nodes)
            ranges.append((pos, pos + k - 1))
            pos += k + 1  # points pos .. pos+k-1 are matched; skip only the point it failed on (pos+k)
        else:
            pos += 1  # nothing usable was matched from pos: skip only point pos
    path = []
    for piece in pieces:
        path = list(piece) if not path else join(path, piece)[0]
    return path, sum(b - a + 1 for a, b in ranges), ranges


trips = pd.read_csv(DATA / "train-1500.csv", nrows=a.n, dtype=str)
rows = []
for i, polyline in enumerate(trips.POLYLINE):
    pts = [(lat, lon) for lon, lat in json.loads(polyline)]
    nodes, k, ranges = [], 0, []
    if len(pts) >= 2:
        if a.robust:
            nodes, k, ranges = match_robust(pts)
        else:
            nodes, k = match_once(pts)
            ranges = [(0, k - 1)] if len(nodes) >= 2 and k >= 1 else []
    if len(nodes) < 2:
        k, ranges = 0, []
    rows.append({"trip_id": i, "n_points": len(pts), "n_matched": k,
                 "matched_pts": ";".join(f"{x}-{y}" for x, y in ranges), "nodes": ",".join(map(str, nodes))})
out = DATA / f"leuven_{a.n}{a.tag}.csv"
pd.DataFrame(rows).to_csv(out, index=False)
print("saved", out)
