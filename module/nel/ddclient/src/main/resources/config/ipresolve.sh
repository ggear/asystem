ssh -q root@udm-net ifconfig eth8 | grep 'inet addr' | cut -d ':' -f2 | cut -d ' ' -f1 | awk '{print $1}'
