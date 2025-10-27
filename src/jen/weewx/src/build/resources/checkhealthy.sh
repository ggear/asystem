/asystem/etc/checkready.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(jq -r '."current.outTemp"? | sub("°C";"")' "/data/html/loopdata/loop-data.txt" | awk '{print ($1>-25 && $1<60)?"true":"false"}')" = "true" ]
