from pathlib import Path
import osmnx as ox
import pandas as pd

graph = ox.load_graphml("data/processed/porto_drive.graphml")
edges = ox.graph_to_gdfs(graph, nodes=False).reset_index()

data_dir = Path("data/processed")
edges = edges.sort_values("length").drop_duplicates(["u", "v"])

routes= pd.read_csv(data_dir /'matched_1500.csv').fillna("")
routes = routes[routes['num_segments']!=0]

routes['road_segment_ids'] = routes['road_segment_ids'].str.split(' ')
routes_explode = routes.explode('road_segment_ids', ignore_index=True)
print(routes_explode['road_segment_ids'].value_counts().head(10))

routes_explode["segment_id"] = routes_explode["road_segment_ids"].astype(int)
counts = (routes_explode.groupby("segment_id")
          .agg(traversals=("TRIP_ID", "size"),          # every pass counts
               distinct_trips=("TRIP_ID", "nunique"))   # each trip counts once
          .reset_index())
top10 = counts.sort_values("traversals", ascending=False).head(10)

id_map = pd.read_csv(data_dir / "segment_id_map.csv")          # id, u, v
top10 = top10.merge(id_map, left_on="segment_id", right_on="id", how="left")
top10 = top10.merge(edges[["u", "v", "name", "highway", "length"]],
                    on=["u", "v"], how="left")

top10 = top10[["segment_id", "traversals", "distinct_trips",
               "name", "highway", "length", "u", "v"]]
top10["length"] = top10["length"].round(1)
top10.insert(0, "rank", range(1, 11))

print(top10.to_string(index=False))
top10.to_csv(data_dir / "task5_1_top10_traversed.csv", index=False)
