declare -a RENAME_DIRS
declare -A RENAME_DIRS_SET
declare -a CHECK_DIRS
declare -A CHECK_DIRS_SET
declare -a MERGE_DIRS
declare -A MERGE_DIRS_SET
declare -a UPSCALE_DIRS
declare -A UPSCALE_DIRS_SET
LOG=$(echo "${LOG}" | grep -E "1. Rename|2. Check|3. Merge|4. Upscale" | grep "/share")
readarray -t LOG_LINES <<<"${LOG}"
for LOG_LINE in "${LOG_LINES[@]}"; do
  RENAME_DIR=$(grep "1. Rename"  <<< "$LOG_LINE" | cut -d'|' -f12 | xargs | sed -e "s/^\/share//")
  if [ -n "${RENAME_DIR}" ]; then
    RENAME_DIRS_SET["${RENAME_DIR}"]=1
  fi
  CHECK_DIR=$(grep "2. Check"  <<< "$LOG_LINE" | cut -d'|' -f12 | xargs | sed -e "s/^\/share//")
  if [ -n "${CHECK_DIR}" ]; then
    CHECK_DIRS_SET["${CHECK_DIR}"]=1
  fi
  MERGE_DIR=$(grep "3. Merge"  <<< "$LOG_LINE" | cut -d'|' -f12 | xargs | sed -e "s/^\/share//")
  if [ -n "${MERGE_DIR}" ]; then
    MERGE_DIRS_SET["${MERGE_DIR}"]=1
  fi
  UPSCALE_DIR=$(grep "4. Upscale"  <<< "$LOG_LINE" | cut -d'|' -f12 | xargs | sed -e "s/^\/share//")
  if [ -n "${UPSCALE_DIR}" ]; then
    UPSCALE_DIRS_SET["${UPSCALE_DIR}"]=1
  fi
done
for RENAME_DIR in "${!RENAME_DIRS_SET[@]}"; do
  RENAME_DIRS+=("'${SHARE_ROOT}${RENAME_DIR}'")
done
IFS=$'\n' RENAME_DIRS=($(sort <<<"${RENAME_DIRS[*]}"))
unset IFS
for CHECK_DIR in "${!CHECK_DIRS_SET[@]}"; do
  CHECK_DIRS+=("'${SHARE_ROOT}${CHECK_DIR}'")
done
IFS=$'\n' CHECK_DIRS=($(sort <<<"${CHECK_DIRS[*]}"))
unset IFS
for MERGE_DIR in "${!MERGE_DIRS_SET[@]}"; do
  MERGE_DIRS+=("'${SHARE_ROOT}${MERGE_DIR}'")
done
IFS=$'\n' MERGE_DIRS=($(sort <<<"${MERGE_DIRS[*]}"))
unset IFS
for UPSCALE_DIR in "${!UPSCALE_DIRS_SET[@]}"; do
  UPSCALE_DIRS+=("'${SHARE_ROOT}${UPSCALE_DIR}'")
done
IFS=$'\n' UPSCALE_DIRS=($(sort <<<"${UPSCALE_DIRS[*]}"))
unset IFS
echo "done"
if [ "${#RENAME_DIRS[@]}" -gt 0 ]; then
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
    echo "Renames to run in directory ... "
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
    for RENAME_DIR in "${RENAME_DIRS[@]}"; do
       echo "cd ${RENAME_DIR}"
    done
fi
if [ "${#CHECK_DIRS[@]}" -gt 0 ]; then
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
    echo "Checks to run in directory ... "
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
    for CHECK_DIR in "${CHECK_DIRS[@]}"; do
       echo "cd ${CHECK_DIR}"
    done
fi
if [ "${#MERGE_DIRS[@]}" -gt 0 ]; then
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
    echo "Merges to run in directory ... "
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
    for MERGE_DIR in "${MERGE_DIRS[@]}"; do
       echo "cd ${MERGE_DIR}"
    done
fi
if [ "${#UPSCALE_DIRS[@]}" -gt 0 ]; then
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
    echo "Upscales to run in directory ... "
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
    for UPSCALE_DIR in "${UPSCALE_DIRS[@]}"; do
       echo "cd ${UPSCALE_DIR}"
    done
fi
if [ "${#RENAME_DIRS[@]}" -gt 0 ] || [ "${#CHECK_DIRS[@]}" -gt 0 ] || [ "${#MERGE_DIRS[@]}" -gt 0 ] || [ "${#UPSCALE_DIRS[@]}" -gt 0 ]; then
    echo "+----------------------------------------------------------------------------------------------------------------------------+"
fi