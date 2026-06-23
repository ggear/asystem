#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT_DIR/refresh_lib.bash"

if [ -n "$(git -C "$ROOT_DIR" status --porcelain -- . 2>/dev/null | grep -E '^.[MD]|\?\?' || true)" ]; then
  refresh_log_error "dirty files present, commit or stash before refreshing"
  exit 1
fi

while IFS= read -r script; do
  echo "==> $script"
  bash "$script"
done < <(find "$ROOT_DIR" -mindepth 2 -name "refresh.sh" | sort -r)

ALL_CHANGED=$(printf '%s\n%s' \
  "$(git -C "$ROOT_DIR" diff --name-only -- '*.csv' 2>/dev/null || true)" \
  "$(git -C "$ROOT_DIR" ls-files --others --exclude-standard -- '*.csv' 2>/dev/null || true)" | grep . || true)
REMOVED=$(git -C "$ROOT_DIR" diff --unified=0 -- '*.csv' 2>/dev/null | grep '^-[^-]' || true)

echo ""
refresh_log_sep
if [ -z "$ALL_CHANGED" ]; then
  refresh_log_success "Data is unchanged"
elif [ -n "$REMOVED" ]; then
  refresh_log_warning "Data changes include CSV row reductions, Yahoo stock API is unreliable and drops days sometimes, suggest retry"
  printf 'git diff\ngit restore %s\n\n%s\n' "$ROOT_DIR" "$ALL_CHANGED"
else
  refresh_log_success "Data changes includes CSV row additions only, likely correct but run full test suite to confirm"
  printf '\n%s\n' "$ALL_CHANGED"
fi
refresh_log_sep
echo ""
