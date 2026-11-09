import json
import os

import matplotlib.pyplot as plt
import numpy as np
import polars as pl


def explore_plot(label, data_pl, data_x, data_y, type="-", overlay=False):
    if not overlay:
        plt.figure(figsize=(16, 8))
    plt.plot(data_pl.select(data_x), data_pl.select(data_y), type, label=label)
    plt.xlabel(data_x)
    plt.ylabel(data_y)
    plt.legend(loc="upper right")


def evaluate_error_plot(label, data_pl, data_x, data_error, limit):
    x = data_pl[data_x].to_numpy()
    error = data_pl[data_error].to_numpy()
    within = np.abs(error) <= limit
    rmse = float(np.sqrt(np.mean(error**2)))
    bias = float(np.mean(error))
    passed = rmse <= limit
    plt.figure(figsize=(16, 8))
    plt.axhspan(-limit, limit, color="tab:green" if passed else "tab:red", alpha=0.12, label=f"Limit of {limit:g} either way, rmse {rmse:.2f}, {'PASS' if passed else 'FAIL'}")
    plt.axhline(0, color="black", linewidth=1, label="No error")
    plt.axhline(bias, color="tab:blue", linestyle="--", linewidth=1.5, label=f"Bias {bias:+.2f}, mean error")
    points, counts = np.unique(np.column_stack([x, error]), axis=0, return_counts=True)
    inside = np.abs(points[:, 1]) <= limit
    sizes = 20 + 12 * np.sqrt(counts)
    plt.scatter(
        points[inside, 0],
        points[inside, 1],
        color="tab:green",
        alpha=0.7,
        s=sizes[inside],
        label=f"Within the limit, {int(within.sum())} readings ({100 * within.mean():.0f}%), a larger marker is more readings",
    )
    plt.scatter(
        points[~inside, 0], points[~inside, 1], color="tab:red", alpha=0.7, marker="X", s=sizes[~inside], label=f"Outside the limit, {int((~within).sum())} readings ({100 * (~within).mean():.0f}%)"
    )
    plt.xlabel(data_x)
    plt.ylabel(f"{label}, above 0 reads high and below 0 reads low")
    plt.legend(loc="upper right")
    return {"rmse": rmse, "bias": bias, "within_pct": float(100 * within.mean()), "passed": passed}


def evaluate_curves(curves, x_label, y_label, band=None, band_label=None):
    plt.figure(figsize=(16, 8))
    if band is not None:
        plt.axvspan(band[0], band[1], color="tab:orange", alpha=0.12, label=band_label)
    for label, x, y, style in curves:
        plt.plot(x, y, label=label, **style)
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.grid(alpha=0.3)
    plt.legend(loc="best")


def data_plot(*paths, column=None, align=None):
    plt.figure(figsize=(16, 8))
    time_names = set()
    plotted = None
    for path in paths:
        stem = path[: -len(".csv")]
        meta = {}
        if os.path.isfile(f"{stem}.json"):
            with open(f"{stem}.json") as meta_file:
                meta = json.load(meta_file)
        label = f"{meta.get('split', '?')} run {meta.get('run', '?')}, {meta.get('name', os.path.basename(stem))}"
        with open(path, "rb") as data_file:
            empty = not data_file.read().strip()
        frame = pl.DataFrame() if empty else pl.read_csv(path, try_parse_dates=True)
        time_name = next((name for name, dtype in frame.schema.items() if dtype == pl.Datetime), None)
        value_names = [name for name, dtype in frame.schema.items() if dtype.is_numeric() and name != time_name]
        chosen = column if column is not None else (value_names[0] if value_names else None)
        if frame.height == 0 or chosen not in value_names:
            plt.plot([], [], label=f"{label}, no readings")
            continue
        plotted = chosen
        if time_name is None:
            x = np.arange(frame.height)
        elif align == "start":
            x = ((frame[time_name] - frame[time_name].min()).dt.total_seconds() / 86400).to_numpy()
            time_names.add(time_name)
        else:
            x = frame[time_name].to_numpy()
            time_names.add(time_name)
        plt.plot(x, frame[chosen].to_numpy(), label=label, drawstyle="steps-post" if meta.get("source") == "influxdb3" else "default")
    plt.xlabel("Days since the start of each run" if align == "start" else (next(iter(time_names)) if len(time_names) == 1 else "Reading"))
    plt.ylabel(column or plotted or "Value")
    plt.grid(alpha=0.3)
    plt.legend(loc="best")
