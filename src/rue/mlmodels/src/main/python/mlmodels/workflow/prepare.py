import polars as pl

from mlmodels._constants import FOLD_SCHEMES, PROJECT_SPLITS
from mlmodels._errors import GateError
from mlmodels._prepare import Fold, Split
from mlmodels._selection import Selection


def prepare_split(ws, *, overlap=(), **splits):
    unknown = sorted(set(splits) - set(PROJECT_SPLITS))
    if unknown:
        raise ValueError(f"unknown splits {unknown} not in {list(PROJECT_SPLITS)}")
    allowed = {frozenset(pair) for pair in overlap}
    defined, claimed = {}, {}
    for name, given in splits.items():
        members = list(given) if isinstance(given, (list, tuple)) else [given]
        if not members or not any(member.rows for member in members):
            raise GateError("Prepare", "empty", f"split [{name}] holds no rows")
        for member in members:
            if ws.runs[(member.run, member.name)].live and name != "monitoring":
                raise GateError("Prepare", "live", f"run [{member.run}] is refreshed live so it may only be the monitoring split not [{name}]")
        defined[name] = Split(name, pl.concat([member.frame for member in members], how="vertical_relaxed"), members)
        claimed[name] = {(member.run, member.name, row) for member in members for row in member.rows}
    names = list(defined)
    for position, first in enumerate(names):
        for second in names[position + 1 :]:
            shared = claimed[first] & claimed[second]
            pair = frozenset((first, second))
            if shared and "backtest" in pair and pair & {"training", "validation"}:
                raise GateError("Prepare", "backtest", f"split [backtest] shares [{len(shared)}] rows with [{next(iter(pair - {'backtest'}))}], and a backtest must be rows no decision has used")
            if shared and pair not in allowed:
                raise GateError("Prepare", "overlap", f"splits [{first}] and [{second}] share [{len(shared)}] rows, declare the pair in overlap or separate them")
    ws.splits = defined
    return defined


def prepare_folds(ws, selection, *, k, gap=0, scheme="blocked"):
    if scheme not in FOLD_SCHEMES:
        raise ValueError(f"unknown fold scheme [{scheme}] not in {list(FOLD_SCHEMES)}")
    if isinstance(k, bool) or not isinstance(k, int) or k < 2:
        raise ValueError(f"k must be an integer of at least 2 [{k}]")
    if isinstance(gap, bool) or gap < 0:
        raise ValueError(f"gap must be an integer of at least 0 [{gap}]")
    rows = selection.rows
    if len(rows) < k:
        raise GateError("Prepare", "folds", f"[{len(rows)}] rows cannot make [{k}] folds")
    base, extra = divmod(len(rows), k)
    bounds, start = [], 0
    for index in range(k):
        stop = start + base + (1 if index < extra else 0)
        bounds.append((start, stop))
        start = stop
    ws.folds = []
    for index in range(1 if scheme == "forward" else 0, k):
        first, last = bounds[index]
        before = rows[: max(first - gap, 0)]
        after = () if scheme == "forward" else rows[last + gap :]
        training = Selection(ws, selection.run, selection.name, tuple(before) + tuple(after))
        validation = Selection(ws, selection.run, selection.name, tuple(rows[first:last]))
        if not training.rows:
            raise GateError("Prepare", "folds", f"fold [{len(ws.folds)}] has no training rows, use fewer folds or a smaller gap")
        prepare_split(ws, training=training, validation=validation)
        ws.folds.append({"fold": len(ws.folds), "scheme": scheme, "gap": gap, "training": len(training.rows), "validation": len(validation.rows)})
        yield Fold(ws, len(ws.folds) - 1)


def prepare_plot(ws, *, column=None, align=None, title=None):
    import matplotlib.pyplot as plt
    import numpy as np

    plt.figure(figsize=(16, 8))
    plotted = None
    time_names = set()
    for name, split in ws.splits.items():
        frame = split.frame
        time_name = next((entry for entry, dtype in frame.schema.items() if dtype == pl.Datetime), None)
        values = [entry for entry, dtype in frame.schema.items() if dtype.is_numeric() and entry != time_name]
        chosen = column if column is not None else (values[0] if values else None)
        label = f"{name} " + ", ".join(f"run {member.run}" for member in split.members)
        if frame.height == 0 or chosen not in values:
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
        plt.plot(x, frame[chosen].to_numpy(), label=label)
    plt.xlabel("Days since the start of each split" if align == "start" else (next(iter(time_names)) if len(time_names) == 1 else "Row"))
    plt.ylabel(column or plotted or "Value")
    if title is not None:
        plt.title(title)
    plt.grid(alpha=0.3)
    plt.legend(loc="best")
