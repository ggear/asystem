import os
from os.path import *
from pathlib import Path

import pandas as pd

from homeassistant.generate import load_env

pd.options.mode.chained_assignment = None

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    env = load_env(DIR_ROOT)

    hosts_path = join(DIR_ROOT, "src/main/resources/pushcerts-hosts.sh")
    os.makedirs(os.path.dirname(hosts_path), exist_ok=True)
    hosts_labels = {line.split("=")[0]: line.split("=")[-1].split(",")
                    for line in Path(join(DIR_ROOT, "../../../.hosts")).read_text().strip().split("\n")}
    host_pull_label = os.path.basename(os.path.dirname(DIR_ROOT))
    with (open(hosts_path, "w") as hosts_file):
        hosts_file.write("#!/bin/sh\n\n")
        for certificates_path in Path(os.path.join(DIR_ROOT, "../..")).rglob('certificates.sh'):
            certificates_path = os.path.abspath(certificates_path)
            certificates_path_tokens = certificates_path.split("/src/")
            if "/target/" not in certificates_path and \
                    len(certificates_path_tokens) > 2:
                module_tokens = certificates_path_tokens[1].split("/")
                if len(module_tokens) > 1:
                    service_name = module_tokens[1]
                    host_pull = "{}-{}".format(hosts_labels[host_pull_label][0], host_pull_label)
                    host_push = "{}-{}".format(hosts_labels[module_tokens[0]][0], module_tokens[0])
                    hosts_file.write(f"""
ssh -n -q -o "StrictHostKeyChecking=no" root@{host_push} "find /var/lib/asystem/install/{service_name}/latest/config -name certificates.sh -exec {{}} pull {host_pull} {host_push} \\;"
ssh -n -q -o "StrictHostKeyChecking=no" root@{host_push} "find /var/lib/asystem/install/{service_name}/latest/config -name certificates.sh -exec {{}} push {host_pull} {host_push} \\;"
logger -t pushcerts "Pushed new certificates to [{host_push}]"
                    """.strip() + "\n")
    print("Build generate script [letsencrypt] entity metadata persisted to [{}]".format(hosts_path))
