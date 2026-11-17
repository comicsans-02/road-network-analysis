import json
import math
from pathlib import Path
import osmnx as ox
import pandas as pd
import matplotlib.pyplot as plt

graph = ox.load_graphml("data/processed/porto_drive.graphml")
edges = ox.graph_to_gdfs(graph, nodes=False).reset_index()

data_dir = Path("data/processed")
edges = edges.sort_values("length").drop_duplicates(["u", "v"])
geometry = dict(zip(zip(edges.u, edges.v), edges.geometry))   # (u, v) -> line

id_map = pd.read_csv(data_dir /'segment_id_map.csv')
id_to_uv = dict(zip(id_map.id, zip(id_map.u, id_map.v)))

routes= pd.read_csv(data_dir /'matched_15.csv').fillna("")
# print(routes.shape)

# gps_tracks = matched_15["POLYLINE"].map(json.loads)
# points = [sample for track in gps_tracks for sample in track]
# all_long, all_lat = zip(*points)

# map_padding = 0.01
# bbox = (min(all_long) - map_padding, min(all_lat) - map_padding, max(all_long) + map_padding, max(all_lat) + map_padding)

fig, ax = ox.plot_graph(graph, figsize=(12, 8), bgcolor="white", node_size=0, edge_color="#bbbbbb", edge_linewidth=0.5, show=False, close=False)
fig.patch.set_facecolor("white")
fig.patch.set_alpha(1)

colors = plt.colormaps["tab20"].colors
all_x, all_y = [], []
for n, ids in enumerate(routes.road_segment_ids):
    for k, seg in enumerate(ids.split()):
        line = geometry[id_to_uv[int(seg)]]
        x, y = line.xy
        all_x.extend(x)
        all_y.extend(y)
        ax.plot(x, y, color=colors[n], linewidth=2.5, zorder=3,
                label=f"Trip {n + 1}" if k == 0 else None)

# zoom to the routes, with a small margin
pad = 0.01
ax.set_xlim(min(all_x) - pad, max(all_x) + pad)
ax.set_ylim(min(all_y) - pad, max(all_y) + pad)

ax.legend(loc="lower left", ncol=3, fontsize=8)
ax.set_title("Map-Matched Routes of the First 15 Taxi Trips", fontsize=14)
fig.savefig(data_dir / "task4_first_15_routes.png", dpi=300,
            bbox_inches="tight", facecolor="white")
plt.close(fig)



# ---- Figure 2: one small map per trip (3 x 5 grid), so overlapping routes are not hidden ----
trips = pd.read_csv(data_dir / "train-1500.csv", usecols=["TRIP_ID", "POLYLINE"], dtype=str)
gps_by_trip = dict(zip(trips.TRIP_ID, trips.POLYLINE.map(json.loads)))

lat_scale = math.cos(math.radians(41.15))  # 1 degree of longitude is shorter than 1 degree of latitude in Porto

fig, axes = plt.subplots(3, 5, figsize=(20, 13))
fig.patch.set_facecolor("white")

for n, (ax, row) in enumerate(zip(axes.flat, routes.itertuples())):
    lines = [geometry[id_to_uv[int(seg)]] for seg in row.road_segment_ids.split()]
    gps = gps_by_trip[str(row.TRIP_ID)]

    # extent covering both the route and the raw GPS points, made square in metres
    xs = [x for line in lines for x in line.xy[0]] + [lon for lon, lat in gps]
    ys = [y for line in lines for y in line.xy[1]] + [lat for lon, lat in gps]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    half_h = max((max(ys) - min(ys)) / 2, (max(xs) - min(xs)) / 2 * lat_scale) * 1.15 + 0.002
    half_w = half_h / lat_scale

    # grey road network around this trip only (much faster than drawing the whole city 15 times)
    edges.cx[cx - half_w:cx + half_w, cy - half_h:cy + half_h].plot(ax=ax, color="#cccccc", linewidth=0.5, zorder=1)

    for k, line in enumerate(lines):
        ax.plot(*line.xy, color=colors[n], linewidth=3, zorder=3, label="Matched route" if k == 0 else None)
    lon, lat = zip(*gps)
    ax.scatter(lon, lat, s=8, color="black", alpha=0.6, zorder=4, label="Raw GPS point")

    ax.set_xlim(cx - half_w, cx + half_w)
    ax.set_ylim(cy - half_h, cy + half_h)
    ax.set_aspect(1 / lat_scale)
    ax.set_axis_off()
    ax.set_title(f"Trip {n + 1} ({len(lines)} segments, {len(gps)} GPS points)", fontsize=11)

handles, labels = axes.flat[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=2, fontsize=12, frameon=False)
fig.suptitle("Map-Matched Route of Each of the First 15 Taxi Trips", fontsize=16)
fig.tight_layout(rect=(0, 0.03, 1, 0.97))
fig.savefig(data_dir / "task4_routes_per_trip.png", dpi=200, bbox_inches="tight", facecolor="white")
plt.close(fig)
print("saved", data_dir / "task4_routes_per_trip.png")
