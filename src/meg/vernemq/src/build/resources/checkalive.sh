(vmq-admin node status >/dev/null 2>&1) | awk -F '|' '/version/ {gsub(/ /,"",$3); exit ($3=="")?1:0}'
