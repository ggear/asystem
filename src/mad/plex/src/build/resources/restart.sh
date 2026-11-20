# The engine (`supervisor`) owns the watch and the restart, this snippet owns what must hold first, as hooks each in its
# own bash. A module enrols with <MODULE>_RESTART=on in .env. Optional hooks: restart_policy, restart_ready.
# No hook relies on a variable another set.
#
# restart_policy prints key=value lines:
#   requires=mount:<path> | mounts:all-cifs | tcp:<host>:<port> | mqtt:<host>:<port> | healthy:<service>
#   requires_stable=<n>s   how long every requirement must have held, default 60s
#   settle_min=<n>s        when set, the least wait before a late-prerequisite restart in place of the health window, and the least settle after any restart
# restart_ready returns zero when what requires cannot say holds, called once every requirement has held.
#
# RESTART_MODULE_NAME     this module's name
# RESTART_ENABLED         on when .env switches the restart on

restart_policy() {
  echo "requires=mounts:all-cifs"
}

restart_ready() {
  [ "$(find /share -mindepth 1 -maxdepth 1 | wc -l)" -eq "$(find /share -mindepth 2 -maxdepth 2 -name media -type d | wc -l)" ]
}
