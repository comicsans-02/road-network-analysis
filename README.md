# AI6128 Project 2: Trajectory and Road Network Analysis

This repository contains Task 1 data preparation and Task 2 GPS-point
visualization. The full Kaggle `train.csv` is extracted in the project root.

## Setup and run

Keep `train.csv` in the repository root, then run:

```powershell
uv sync
uv run python task1_data_preparation.py
uv run python task2_gps_visualization.py
```

Generated files are written to `data/processed/`:

- `train-1500.csv`: the first 1,500 rows of Kaggle's `train.csv`.
- `porto_drive.graphml`: the Porto driving network in OSMnx GraphML format.
- `task2_first_15_trips.png`: the raw GPS points from the first 15 trips over
  the road network, with a different color for each trip.

The network bounds are the minimum and maximum GPS coordinates, padded by a
simple `0.05` degrees on every side.
