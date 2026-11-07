import json
from pathlib import Path

import matplotlib.pyplot as plt
import osmnx as ox
import pandas as pd


data_dir = Path("data/processed")
trips = pd.read_csv(data_dir / "train-1500.csv", nrows=15)
porto_road_network = ox.load_graphml(data_dir / "porto_drive.graphml")

gps_tracks = trips["POLYLINE"].map(json.loads)
points = [sample for track in gps_tracks for sample in track]
all_long, all_lat = zip(*points)

map_padding = 0.01
bbox = (min(all_long) - map_padding, min(all_lat) - map_padding, max(all_long) + map_padding, max(all_lat) + map_padding)

fig, map_axes = ox.plot_graph(porto_road_network, bbox=bbox, figsize=(12, 8), bgcolor="white", node_size=0, edge_color="#bbbbbb", edge_linewidth=0.5, show=False, close=False)

trip_colors = plt.colormaps["tab20"].colors
for trip_number, gps_track in enumerate(gps_tracks, start=1):
    long, lat = zip(*gps_track)
    map_axes.scatter(
        long,
        lat,
        s=12,
        color=trip_colors[trip_number - 1],
        label=f"Trip {trip_number}",
        zorder=3,
    )

map_axes.set_title("GPS Points of the First 15 Taxi Trips", fontsize=14)
map_axes.legend(loc="lower left", ncol=3, fontsize=8, markerscale=1.5)

output = data_dir / "task2_first_15_trips.png"
fig.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
plt.close(fig)
