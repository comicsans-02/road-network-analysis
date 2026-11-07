import json
from pathlib import Path

import osmnx as ox
import pandas as pd


train_file = Path("train.csv")
data_dir = Path("data/processed")
margin = 0.05

data_dir.mkdir(parents=True, exist_ok=True)

trips = pd.read_csv(train_file, nrows=1500, dtype=str, keep_default_na=False)
trips.to_csv(data_dir / "train-1500.csv", index=False)

tracks = trips["POLYLINE"].map(json.loads)
points = [point for track in tracks for point in track]
all_long, all_lat = zip(*points)

bbox = (min(all_long) - margin, min(all_lat) - margin, max(all_long) + margin, max(all_lat) + margin)

print(f"Trips: {len(trips)}")
print(f"GPS points: {len(points)}")
print(f"Bounding box (W, S, E, N): {bbox}")

ox.settings.use_cache = True
ox.settings.cache_folder = Path("data/cache")
graph = ox.graph_from_bbox(bbox=bbox, network_type="drive", simplify=True, retain_all=True, truncate_by_edge=True)
ox.save_graphml(graph, data_dir / "porto_drive.graphml")

print(f"Road network: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
