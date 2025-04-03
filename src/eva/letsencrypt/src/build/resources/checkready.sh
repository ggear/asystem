[ $(ps uax | grep dnsrobocert | grep -v grep | wc -l) -eq 1 ] &&
  [ $(grep ERROR /etc/letsencrypt/logs/letsencrypt.log | wc -l) -eq 0 ] &&
  [ $((($(date +%s) - $(stat /etc/letsencrypt/logs/letsencrypt.log -c %Y)) / 3600)) -le 25 ]
