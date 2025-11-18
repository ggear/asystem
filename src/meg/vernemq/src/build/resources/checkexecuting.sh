/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  { /asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" >/dev/null 2>&1 && vmq-admin node status | awk -F '|' '/num_offline/ {gsub(/ /,"",$3); offline=$3} /num_online/ {gsub(/ /,"",$3); online=$3} END {exit (offline>0 || online==0)?1:0}'; } >/dev/null 2>&1
