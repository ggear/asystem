from fabfile import _get_modules_by_hosts, _get_host_label
from homeassistant.generate import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    # Build config
    shares = {}
    for host, module in _get_modules_by_hosts(filter_path="src/main/resources/fstab").items():
        host_label = _get_host_label(host)
        share_host = "macmini-{}".format(host_label)
        fstab_path = abspath(join(DIR_ROOT, "../..", host_label, module[0], "src/main/resources/fstab"))
        share_ids = shares.setdefault(share_host, [])
        with open(fstab_path) as fstab_file:
            for fstab_line in fstab_file:
                if fstab_line.startswith("#"):
                    continue
                if "/share" in fstab_line and "ext4" in fstab_line:
                    fstab_fields = fstab_line.split()
                    if len(fstab_fields) >= 2:
                        share_id = fstab_fields[1].replace("/share/", "", 1)
                        if share_id not in share_ids:
                            share_ids.append(share_id)
    metadata_shares_path = abspath(join(DIR_ROOT, "src/main/resources/shares.csv"))
    with open(metadata_shares_path, 'w') as metadata_supervisor_file:
        for share_host in sorted(shares):
            for share_id in sorted(
                    shares[share_host],
                    key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value)):
                metadata_supervisor_file.write("{},{}\n".format(share_host, share_id))
    print("Build generate script [supervisor] service metadata persisted to [{}]".format(metadata_shares_path))
