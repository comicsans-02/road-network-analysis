"""Task 6: robust map matching with LeuvenMapMatching on data/processed/porto_drive.graphml.

Baseline (the team's settings, equals P2's routes):
    python task6_robust_matching.py
Fix for the failure found in Task 6:
    python task6_robust_matching.py --robust --tag _robust

Failure: Leuven stops at the first GPS point it cannot continue from (no road within max_dist,
or the lattice dies after a GPS jump) and silently returns only the matched prefix of the trip.
--robust skips the failing point, restarts matching from the next one and joins the pieces with
a shortest-path bridge (at most --max-gap-m), so the rest of the trip is not lost.

Output: data/processed/leuven_<n><tag>.csv with trip_id (row in train-1500.csv), n_points,
n_matched (leading points matched) and nodes (node ids along the matched path).
"""
import argparse
import json
from pathlib import Path

import networkx as nx
import osmnx as ox
import pandas as pd
from leuvenmapmatching.map.inmem import InMemMap
from leuvenmapmatching.matcher.distance import DistanceMatcher

DATA = Path("data/processed")

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=1500, help="number of trips (first n)")
ap.add_argument("--max-dist", type=float, default=200)
ap.add_argument("--obs-noise", type=float, default=25)
ap.add_argument("--dist-noise", type=float, default=25)
ap.add_argument("--lattice-width", type=int, default=5)
ap.add_argument("--robust", action="store_true", help="restart after a failed point and join pieces")
ap.add_argument("--max-gap-m", type=float, default=2000, help="longest shortest-path bridge between pieces")
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


def bridge(x, y):
    """Intermediate nodes of the shortest path x -> y within max_gap_m, else None."""
    try:
        _, path = nx.single_source_dijkstra(G, x, y, cutoff=a.max_gap_m, weight="length")
        return path[1:-1]
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def match_robust(pts):
    pieces, matched, pos = [], 0, 0
    while len(pts) - pos >= 2:
        nodes, k = match_once(pts[pos:])
        if len(nodes) >= 2:
            pieces.append(nodes)
            matched += k
        pos += max(k, 1) + 1  # skip the point the matcher failed on
    path = []
    for piece in pieces:
        if path and path[-1] != piece[0]:
            mid = bridge(path[-1], piece[0])
            if mid:
                path += mid
        path += piece if not path or path[-1] != piece[0] else piece[1:]
    return path, matched


trips = pd.read_csv(DATA / "train-1500.csv", nrows=a.n, dtype=str)
rows = []
for i, polyline in enumerate(trips.POLYLINE):
    pts = [(lat, lon) for lon, lat in json.loads(polyline)]
    nodes, k = [], 0
    if len(pts) >= 2:
        nodes, k = match_robust(pts) if a.robust else match_once(pts)
    rows.append({"trip_id": i, "n_points": len(pts), "n_matched": k if len(nodes) >= 2 else 0,
                 "nodes": ",".join(map(str, nodes))})
out = DATA / f"leuven_{a.n}{a.tag}.csv"
pd.DataFrame(rows).to_csv(out, index=False)
print("saved", out)
