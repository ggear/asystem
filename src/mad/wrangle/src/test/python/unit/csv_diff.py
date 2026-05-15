#!/usr/bin/env python3

import csv
import re
import sys
from pathlib import Path

RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"


def _read_csv_rows(path):
    with open(path, newline="") as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = {}
        for row in reader:
            key = row[0]
            if key in rows:
                print(f"{YELLOW}⚠  Duplicate key '{key}' in {path} — last row kept{RESET}")
            rows[key] = row
    return headers, rows


def _fmt_val(v):
    return v if v != "" else "(empty)"


def diff_print(file_a, file_b, exclude=None):
    path_a, path_b = Path(file_a), Path(file_b)
    if not path_a.exists() or not path_b.exists():
        print(f"{RED}Error: one or both files not found{RESET}")
        return

    name_a, name_b = path_a.name, path_b.name
    print(f"\n{BOLD}{'─' * 80}{RESET}")
    print(f"{BOLD}  CSV DIFF{RESET}")
    print(f"  {CYAN}{name_a}:{RESET} {file_a}")
    print(f"  {CYAN}{name_b}:{RESET} {file_b}")
    print(f"{BOLD}{'─' * 80}{RESET}\n")

    headers_a, rows_a = _read_csv_rows(path_a)
    headers_b, rows_b = _read_csv_rows(path_b)

    key_col = headers_a[0] if headers_a else "key"

    if headers_a != headers_b:
        set_a, set_b = set(headers_a), set(headers_b)
        only_a = set_a - set_b
        only_b = set_b - set_a
        print(f"{YELLOW}⚠  Column differences:{RESET}")
        for col in sorted(only_a):
            print(f"  {RED}- {col}{RESET}  (only in {name_a})")
        for col in sorted(only_b):
            print(f"  {GREEN}+ {col}{RESET}  (only in {name_b})")
        print()
    else:
        print(f"{GREEN}✓  Headers identical ({len(headers_a)} columns){RESET}\n")

    shared_cols = [c for c in headers_a if c in set(headers_b)]
    if exclude:
        excluded = [c for c in shared_cols if re.search(exclude, c)]
        shared_cols = [c for c in shared_cols if not re.search(exclude, c)]
        print(f"{DIM}Excluding {len(excluded)} columns matching {YELLOW}/{exclude}/{DIM}: {', '.join(excluded[:5])}{'...' if len(excluded) > 5 else ''}{RESET}\n")
    idx_a = {c: i for i, c in enumerate(headers_a)}
    idx_b = {c: i for i, c in enumerate(headers_b)}

    all_keys = sorted(set(rows_a) | set(rows_b))
    only_in_a = [k for k in all_keys if k not in rows_b]
    only_in_b = [k for k in all_keys if k not in rows_a]
    common = [k for k in all_keys if k in rows_a and k in rows_b]

    if only_in_a:
        print(f"{RED}Rows only in {name_a} ({len(only_in_a)}):{RESET} {', '.join(only_in_a[:5])}{'...' if len(only_in_a) > 5 else ''}\n")
    if only_in_b:
        print(f"{GREEN}Rows only in {name_b} ({len(only_in_b)}):{RESET} {', '.join(only_in_b[:5])}{'...' if len(only_in_b) > 5 else ''}\n")

    diffs_by_col = {}
    diffs_by_row = {}

    for key in common:
        row_a = rows_a[key]
        row_b = rows_b[key]
        for col in shared_cols:
            if col == key_col:
                continue
            va = row_a[idx_a[col]] if idx_a[col] < len(row_a) else ""
            vb = row_b[idx_b[col]] if idx_b[col] < len(row_b) else ""
            if va != vb:
                diffs_by_col[col] = diffs_by_col.get(col, 0) + 1
                diffs_by_row.setdefault(key, []).append((col, va, vb))

    total_diff_rows = len(diffs_by_row)
    total_diff_cells = sum(len(v) for v in diffs_by_row.values())

    print(f"{BOLD}Summary:{RESET}")
    print(f"  Total rows compared  : {len(common):,}")
    print(f"  Rows with differences: {RED}{total_diff_rows:,}{RESET}")
    print(f"  Cells with differences: {RED}{total_diff_cells:,}{RESET}")
    print()

    if not diffs_by_col:
        print(f"{GREEN}✓  All data identical!{RESET}\n")
        return

    print(f"{BOLD}Columns with differences:{RESET}")
    max_count = max(diffs_by_col.values())
    for col, count in sorted(diffs_by_col.items(), key=lambda x: -x[1]):
        bar = "█" * max(1, round(count * 40 / max_count))
        print(f"  {CYAN}{col:<50}{RESET}  {RED}{count:>6} rows{RESET}  {DIM}{bar}{RESET}")
    print()

    print(f"{BOLD}Sample differences (first 10 differing rows):{RESET}")
    key_w = max(14, len(key_col))
    col_a_w = max(15, len(name_a))
    col_b_w = max(15, len(name_b))
    print(f"  {key_col:<{key_w}}  {'Column':<50}  {name_a:>{col_a_w}}  {name_b:>{col_b_w}}  {'Delta':>12}")
    print(f"  {'─' * key_w}  {'─' * 50}  {'─' * col_a_w}  {'─' * col_b_w}  {'─' * 12}")

    shown = 0
    for key in sorted(diffs_by_row):
        if shown >= 10:
            break
        for col, va, vb in diffs_by_row[key]:
            try:
                delta_str = f"{float(vb) - float(va):+.4f}"
            except (ValueError, TypeError):
                delta_str = "n/a"
            print(f"  {key:<{key_w}}  {col:<50}  {_fmt_val(va):>{col_a_w}}  {_fmt_val(vb):>{col_b_w}}  {RED}{delta_str:>12}{RESET}")
        shown += 1
    print()

    remaining = total_diff_rows - 10
    if remaining > 0:
        print(f"  {DIM}... and {remaining:,} more differing rows{RESET}\n")

    print(f"{BOLD}{'─' * 80}{RESET}\n")


def main():
    if len(sys.argv) < 3:
        print(f"{RED}Usage: {sys.argv[0]} FILE_A FILE_B [EXCLUDE_PATTERN]{RESET}")
        print(f"  FILE_A: Path to first CSV file")
        print(f"  FILE_B: Path to second CSV file")
        print(f"  EXCLUDE_PATTERN: Optional regex pattern to exclude columns")
        sys.exit(1)
    diff_print(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)


if __name__ == "__main__":
    main()
