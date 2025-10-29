[ $(ps aux | grep tini | grep /app/index.js | grep -v grep | wc -l) -gt 0 ]
