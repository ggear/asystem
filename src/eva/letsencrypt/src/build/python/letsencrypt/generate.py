import glob
import os
import sys
from os.path import *
from pathlib import Path

import pandas as pd

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
for dir_module in glob.glob(join(DIR_ROOT, "../../*/*")):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, join(dir_module, "src/build/python"))

from homeassistant.generate import load_env

pd.options.mode.chained_assignment = None

if __name__ == "__main__":
    env = load_env(DIR_ROOT)

    hosts_path = join(DIR_ROOT, "src/main/resources/pushcerts-hosts.txt")
    os.makedirs(os.path.dirname(hosts_path), exist_ok=True)

    hosts_lookup = {line.split("=")[0]: line.split("=")[-1].split(",")
                    for line in Path(join(DIR_ROOT, "../../../.hosts")).read_text().strip().split("\n")}
    host_pull = os.path.basename(os.path.dirname(DIR_ROOT))
    with (open(hosts_path, "w") as hosts_file):
        for certificates_path in Path(os.path.join(DIR_ROOT, "../..")).rglob('certificates.sh'):
            certificates_path = os.path.abspath(certificates_path)
            certificates_path_tokens = certificates_path.split("/src/")
            if "/target/" not in certificates_path and \
                    len(certificates_path_tokens) > 2:
                module_tokens = certificates_path_tokens[1].split("/")
                if len(module_tokens) > 1:
                    hosts_file.write("""
{}-{} {}-{}
                    """.format(
                        hosts_lookup[host_pull][0],
                        host_pull,
                        hosts_lookup[module_tokens[0]][0],
                        module_tokens[0],
                    ).strip() + "\n")
    print("Build generate script [letsencrypt] entity metadata persisted to [{}]".format(hosts_path))
