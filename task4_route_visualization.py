import json
import math
from pathlib import Path
import osmnx as ox
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

graph = ox.load_graphml("data/processed/porto_drive.graphml")
edges = ox.graph_to_gdfs(graph, nodes=False).reset_index()

data_dir = Path("data/processed")
edges = edges.sort_values("length").drop_duplicates(["u", "v"])
geometry = dict(zip(zip(edges.u, edges.v), edges.geometry))   # (u, v) -> line

id_map = pd.read_csv(data_dir /'segment_id_map_p2.csv')
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



# ---- Figure 2: one map per trip, all 15 on a single A4 portrait page (5 rows x 3 columns) ----
trips = pd.read_csv(data_dir / "train-1500.csv", usecols=["TRIP_ID", "POLYLINE"], dtype=str)
gps_by_trip = dict(zip(trips.TRIP_ID, trips.POLYLINE.map(json.loads)))

lat_scale = math.cos(math.radians(41.15))  # 1 degree of longitude is shorter than 1 degree of latitude in Porto
a4_portrait = (8.27, 11.69)                 # inches
n_rows, n_cols = 5, 3
panel_ratio = 1.2                           # width / height of each map, in metres on the ground


def draw_trip(ax, n, row):
    """Draw trip n: grey streets, matched route, raw GPS points, start and end markers."""
    lines = [geometry[id_to_uv[int(seg)]] for seg in row.road_segment_ids.split()]
    gps = gps_by_trip[str(row.TRIP_ID)]

    # extent covering both the route and the GPS points, stretched to the panel shape
    xs = [x for line in lines for x in line.xy[0]] + [lon for lon, lat in gps]
    ys = [y for line in lines for y in line.xy[1]] + [lat for lon, lat in gps]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    half_h = max((max(ys) - min(ys)) / 2, (max(xs) - min(xs)) / 2 * lat_scale / panel_ratio) * 1.12 + 0.0015
    half_w = half_h * panel_ratio / lat_scale

    edges.cx[cx - half_w:cx + half_w, cy - half_h:cy + half_h].plot(ax=ax, color="#c8c8c8", linewidth=0.6, zorder=1)

    for line in lines:
        ax.plot(*line.xy, color=colors[n], linewidth=2.5, solid_capstyle="round", zorder=3)
    lon, lat = zip(*gps)
    ax.scatter(lon, lat, s=5, color="black", alpha=0.65, zorder=4)
    ax.scatter(*lines[0].coords[0], s=40, marker="^", color="#1a9850", edgecolor="white", linewidth=0.5, zorder=5)
    ax.scatter(*lines[-1].coords[-1], s=32, marker="s", color="#d73027", edgecolor="white", linewidth=0.5, zorder=5)

    ax.set_xlim(cx - half_w, cx + half_w)
    ax.set_ylim(cy - half_h, cy + half_h)
    ax.set_aspect(1 / lat_scale)
    ax.set_xticks([])
    ax.set_yticks([])
    for side in ax.spines.values():
        side.set_color("#999999")
    ax.set_title(f"Trip {n + 1}: {len(lines)} segments, {len(gps)} GPS points", fontsize=8)


per_page = n_rows * n_cols
pages = [routes.iloc[i:i + per_page] for i in range(0, len(routes), per_page)]
for page_number, page in enumerate(pages, start=1):
    fig, axes = plt.subplots(n_rows, n_cols, figsize=a4_portrait)
    fig.patch.set_facecolor("white")
    for ax, (n, row) in zip(axes.flat, page.iterrows()):
        draw_trip(ax, n, row)
    for ax in axes.flat[len(page):]:
        ax.set_visible(False)

    # route colour differs per trip, so the legend shows it in neutral grey
    legend_items = [
        Line2D([], [], color="#555555", linewidth=2.5, label="Matched route"),
        Line2D([], [], marker="o", linestyle="", markersize=3, color="black", alpha=0.65),
        Line2D([], [], marker="^", linestyle="", markersize=6, color="#1a9850"),
        Line2D([], [], marker="s", linestyle="", markersize=5, color="#d73027"),
    ]
    fig.legend(handles=legend_items, loc="lower center", ncol=4, fontsize=8, frameon=False)
    fig.suptitle("Map-Matched Route of Each of the First 15 Trips", fontsize=12)
    fig.tight_layout(rect=(0, 0.02, 1, 0.98), h_pad=0.6, w_pad=0.4)
    output = data_dir / "task4_routes_per_trip.png"
    fig.savefig(output, dpi=300, facecolor="white")
    plt.close(fig)
    print("saved", output)
