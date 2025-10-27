/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" && 
  [ -f "/data/html/loopdata/loop-data.txt" ] &&
  [ $(($(date +%s) - $(stat "/data/html/loopdata/loop-data.txt" -c %Y))) -le 2 ] &&
  [ $(($(date +%s) - $(jq -r '."current.dateTime.raw"' "/data/html/loopdata/loop-data.txt"))) -le 2 ]
