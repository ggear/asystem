import glob
import sys
from os.path import *

import pandas as pd
from pathlib2 import Path

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

# Shared library excluded from module discovery. Not a deployable module, lacks generated .env file.
SHARED_MODULE_NAME = basename(DIR_ROOT)


def load_bootstrap_root() -> str:
    return abspath(join(dirname(realpath(sys.argv[0])), "../../../.."))


def load_bootstrap_env(root_dir=None):
    env_load = {}
    if root_dir is None:
        root_dir = load_bootstrap_root()
    env_load_path = abspath(join(root_dir, ".env"))
    env_load_path_dev = env_load_path
    if not isfile(env_load_path):
        env_load_path = abspath(join(root_dir, "target/release/.env"))
    if not isfile(env_load_path):
        raise Exception("Could not find dev [{}] or prod [{}] env file".format(env_load_path_dev, env_load_path))
    with open(env_load_path, 'r') as env_file:
        for env_load_line in env_file:
            env_load_line = env_load_line.replace("export ", "").rstrip()
            if "=" not in env_load_line:
                continue
            if env_load_line.startswith("#"):
                continue
            env_load_key, env_load_value = env_load_line.split("=", 1)
            env_load[env_load_key] = env_load_value
    print("Build generate script environment loaded from [{}]".format(env_load_path))
    sys.stdout.flush()
    return env_load


def load_bootstrap_env_value(name, default="", filename=".env_prod", module_root=None):
    if module_root is None:
        module_root = load_bootstrap_root()
    env_path = join(module_root, filename)
    if not isfile(env_path):
        return default
    for line in open(env_path, 'r'):
        line = line.replace("export ", "").rstrip()
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        if key == name:
            return value
    return default


def load_bootstrap_modules(load_disabled=True, load_infrastructure=True):
    modules = {}
    hosts_path = Path(join(dirname(abspath(join(DIR_ROOT, "../.."))), ".hosts"))
    host_labels_names = {
        line.split("=")[0]: line.split("=")[-1].split(",")
        for line in hosts_path.read_text().strip().split("\n")
        if line.strip() and not line.strip().startswith("#")
    }
    for module in glob.glob(abspath(join(DIR_ROOT, "../../*/*"))):
        group_path = Path(join(module, ".group"))
        if basename(module) != SHARED_MODULE_NAME and \
                (load_disabled or (isfile(group_path) and group_path.read_text().strip().isdigit() and
                                   int(group_path.read_text().strip()) >= 0)) and \
                (load_infrastructure or not basename(module).startswith("_")):
            env = load_bootstrap_env(module)
            name = basename(module)
            host_labels = basename(dirname(module)).split("_")
            if host_labels == ["all"]:
                host_labels = sorted(
                    label for label, metadata in host_labels_names.items()
                    if len(metadata) > 4 and metadata[4] != "ignore"
                )
            unknown_labels = [host_label for host_label in host_labels if host_label not in host_labels_names]
            if unknown_labels:
                raise KeyError(
                    "Unknown host label(s) [{}] for module [{}]. Check [{}]".format(
                        ",".join(unknown_labels),
                        module,
                        hosts_path,
                    )
                )
            hosts = ["{}-{}".format(host_labels_names[host_label][0], host_label) for host_label in host_labels]
            modules[name] = [hosts, env]
    return modules


def load_bootstrap_entities():
    metadata_path = abspath(join(DIR_ROOT, "src/build/resources/entity_metadata.xlsx"))
    metadata_df = pd.read_excel(metadata_path, header=2, dtype=str)
    metadata_df["index"] = metadata_df["index"].astype(int)
    metadata_df = metadata_df.set_index(metadata_df["index"]).sort_index()
    print("Build generate script entity metadata loaded from [{}]".format(metadata_path))
    sys.stdout.flush()
    return metadata_df
