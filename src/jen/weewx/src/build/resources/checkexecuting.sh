/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  [ -f "/data/html/loopdata/loop-data.txt" ] &&
  [ $(($(date +%s) - $(stat -c %Y "/data/html/loopdata/loop-data.txt"))) -le 5 ] &&
  [ $(($(date +%s) - $(jq -r '."current.dateTime.raw"' "/data/html/loopdata/loop-data.txt"))) -le 5 ]
