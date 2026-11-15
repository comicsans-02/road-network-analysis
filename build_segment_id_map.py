"""Recover what P2's road_segment_ids are: map each id to a road segment (u, v) of porto_drive.graphml.

P2's matched_1500.csv lists segment ids, but the id definition is not in the repo. We re-run
Leuven with the team's settings (task6_robust_matching.py, baseline) which reproduces P2's routes
closely, then align our node paths with P2's id lists position by position (only trips whose
segment counts agree) and take the majority vote for every id.

Usage: python task6_robust_matching.py && python build_segment_id_map.py
Output: data/processed/segment_id_map.csv (id, u, v)
"""
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

DATA = Path("data/processed")

leu = pd.read_csv(DATA / "leuven_1500.csv").fillna("")
trips = pd.read_csv(DATA / "train-1500.csv", usecols=["TRIP_ID"], dtype=str)
team = pd.read_csv(DATA / "matched_1500.csv", dtype=str).fillna("")

row_of = {t: i for i, t in enumerate(trips.TRIP_ID)}  # P2's trip_index skips trips with < 2 points
ids_of_row = {row_of[t]: [int(x) for x in s.split()] for t, s in zip(team.TRIP_ID, team.road_segment_ids)}

votes = defaultdict(Counter)
used = 0
for row, r in enumerate(leu.itertuples()):
    ids = ids_of_row.get(row, [])
    nodes = [int(x) for x in r.nodes.split(",") if x]
    if len(nodes) < 2 or len(nodes) - 1 != len(ids):
        continue
    used += 1
    for i, uv in zip(ids, zip(nodes, nodes[1:])):
        votes[i][uv] += 1

rows = [(i, *c.most_common(1)[0][0]) for i, c in votes.items()]
pd.DataFrame(rows, columns=["id", "u", "v"]).sort_values("id").to_csv(DATA / "segment_id_map.csv", index=False)

total = Counter(i for ids in ids_of_row.values() for i in ids)
covered = sum(n for i, n in total.items() if i in votes) / sum(total.values())
print(f"trips aligned: {used}; ids mapped: {len(rows)} of {len(total)}; traversal coverage: {covered:.1%}")
