#!/bin/bash

SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/latest

# shellcheck disable=SC1091
. "${SERVICE_INSTALL}/.env"

chmod +x "${SERVICE_INSTALL}/supervisor"
rm -f /usr/local/bin/atop
cat >/usr/local/bin/atop <<EOF
#!/bin/bash

exec ${SERVICE_INSTALL}/supervisor watch -m local -F 1 "\$@"

EOF
chmod +x /usr/local/bin/atop
rm -f /usr/local/bin/atops
cat >/usr/local/bin/atops <<EOF
#!/bin/bash

exec ${SERVICE_INSTALL}/supervisor watch -m remote "\$@"

EOF
chmod +x /usr/local/bin/atops
if [[ "${SERVICE_FORM_FACTOR:-}" == "edge" || "${SERVICE_FORM_FACTOR:-}" == "server" ]]; then
  rm -f /usr/local/bin/abackup
  cat >/usr/local/bin/abackup <<EOF
#!/bin/bash

set -a
[ -f "${SERVICE_INSTALL}/.env" ] && . "${SERVICE_INSTALL}/.env"
set +a
exec ${SERVICE_INSTALL}/supervisor backup "\$@"

EOF
  chmod +x /usr/local/bin/abackup
fi
chmod +x "${SERVICE_INSTALL}/image/backups.sh"
rm -f /usr/local/bin/abackups
cat >/usr/local/bin/abackups <<EOF
#!/bin/bash

exec ${SERVICE_INSTALL}/image/backups.sh "\$@"

EOF
chmod +x /usr/local/bin/abackups
if [ -d /etc/bash_completion.d ]; then
  completion="$(mktemp)"
  {
    "${SERVICE_INSTALL}/supervisor" completion &&
      "${SERVICE_INSTALL}/image/backups.sh" completion
  } >"${completion}" && install -m 644 "${completion}" /etc/bash_completion.d/supervisor
  rm -f "${completion}"
fi
