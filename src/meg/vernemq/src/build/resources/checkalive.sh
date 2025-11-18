vmq-admin node status | awk -F '|' '/version/ {gsub(/ /,"",$3); exit ($3=="")?1:0}'
