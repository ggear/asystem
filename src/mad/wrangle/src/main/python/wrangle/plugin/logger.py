import traceback
from datetime import datetime

import polars as pl

from .config import config, PL_PRINT_ROWS

LOG_LEVELS = {"debug": 10, "info": 20, "warning": 30, "error": 40, "fatal": 50}


def log_enabled(level):
    return LOG_LEVELS.get(level, 20) >= LOG_LEVELS.get(config.log_level, 20)


def print_log(process, messages, exception=None, level="info"):
    effective_level = "error" if exception is not None else level
    if not log_enabled(effective_level):
        return
    prefix = f"{effective_level.upper()} [{process}] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}]: "
    if type(messages) is not list:
        messages = [messages]
    for line in messages:
        line_text = "" if line is None else str(line)
        if len(line_text) > 0:
            print(f"{prefix}{line_text}")
    if exception is not None:
        traceback_lines = traceback.format_exception(type(exception), exception, exception.__traceback__)
        print(f"{prefix}{(chr(10) + prefix).join(''.join(traceback_lines).splitlines())}", flush=True)


def dataframe_print(process, data_df, messages=None, compact=False,
                    print_prefix="DataFrame", print_label=None, print_verb="created",
                    print_suffix=None, print_rows=PL_PRINT_ROWS, started=None, level="debug"):
    import time
    if print_rows < 0:
        return data_df
    if messages is None:
        label = f" [{print_label}]" if print_label else ""
        suffix = f" {print_suffix}" if print_suffix else ""
        messages = (
            f"{print_prefix}{label} {print_verb} "
            f"with [{len(data_df.columns):,}] columns "
            f"and [{len(data_df):,}] rows{suffix}"
        )
    if not isinstance(messages, list):
        messages = [messages]
    if started is not None:
        messages[-1] = messages[-1] + f" in [{time.time() - started:.3f}] sec"
    if print_rows != 0:
        if compact:
            data_str = "[" + ", ".join(f"{c}({t})" for c, t in zip(data_df.columns, data_df.dtypes)) + "]"
            messages[-1] = messages[-1] + ": "
            messages.append(data_str)
        else:
            with pl.Config(
                    tbl_rows=print_rows,
                    tbl_cols=-1,
                    fmt_str_lengths=50,
                    set_tbl_width_chars=30000,
                    set_fmt_float="full",
                    set_ascii_tables=True,
                    tbl_formatting="ASCII_FULL_CONDENSED",
                    set_tbl_hide_dataframe_shape=True,
            ):
                messages[-1] = messages[-1] + ": "
                messages.extend(str(data_df).split('\n'))
    print_log(process, messages, level=level)
    return data_df

