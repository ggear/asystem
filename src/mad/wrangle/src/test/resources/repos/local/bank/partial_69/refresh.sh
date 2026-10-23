#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, closed month totals described: a category by its Classifier description, blank without one, a bucket by its categories and a month by its buckets, an all-caps word kept, a pattern row description a warning
refresh_write_fixture 0 0 "" 0 -1
