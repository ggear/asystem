#!/bin/bash

docker exec monitor /asystem/etc/mqtt.sh

chmod +x /var/lib/asystem/install/supervisor/latest/supervisor
cat >/usr/local/bin/atop <<'EOF'
#!/bin/bash

/var/lib/asystem/install/supervisor/latest/supervisor watch -m local -F 1 "$@"

EOF
chmod +x /usr/local/bin/atop
cat >/usr/local/bin/atops <<'EOF'
#!/bin/bash

/var/lib/asystem/install/supervisor/latest/supervisor watch -m remote "$@"

EOF
chmod +x /usr/local/bin/atops
