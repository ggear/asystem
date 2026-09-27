import re

from asystem import *
from fabfile import HOSTS, _get_host_index

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
REPO_ROOT = abspath(join(DIR_ROOT, "../../.."))

FSTAB_DOMAIN = "dar"
FSTAB_FORM_FACTORS = ("edge", "server")
SHARE_TOKEN = re.compile(r"(share|backup)_\d+")
SHARE_MOUNT = re.compile(r"^/share/\d+$")
EXCLUDED_MOUNT_PREFIXES = ("/boot", "/proc", "/backup")


def parse_fstab(path):
    entries = []
    with open(path) as fstab_file:
        for line in fstab_file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) < 4 or fields[2] == "swap":
                continue
            entries.append({"identifier": fields[0], "mount": fields[1], "fstype": fields[2]})
    return entries


def fstab_path(label):
    matches = glob.glob(join(REPO_ROOT, "src", label, "_*_" + label, "src/main/resources/fstab"))
    return matches[0] if matches else None


def share_label(identifier):
    match = SHARE_TOKEN.search(identifier)
    return match.group(0) if match else ""


if __name__ == "__main__":
    metadata_df = load_bootstrap_entities()

    metadata_storage_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Storage") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["state_topic"].str.len() > 0)
        ]
    write_schema_broker(metadata_storage_df,
                        broker_topic_glob_discovery="homeassistant/+/storage_${STORAGE_HOST}/+/config",
                        broker_topic_glob_data="storage/${STORAGE_HOST}/data/+/+/+")

    labels = sorted(
        label for label, metadata in HOSTS.items()
        if metadata[4] in FSTAB_FORM_FACTORS
    )
    fstabs = {label: parse_fstab(fstab_path(label)) for label in labels if fstab_path(label)}

    share_registry = {}
    for label, entries in fstabs.items():
        machine_host = "{}-{}".format(HOSTS[label][0], label)
        for entry in entries:
            if SHARE_MOUNT.match(entry["mount"]) and entry["fstype"] != "cifs":
                share_registry[entry["mount"]] = {
                    "host": machine_host,
                    "label": share_label(entry["identifier"]),
                }

    schema = []
    for label in labels:
        if HOSTS[label][2] != FSTAB_DOMAIN or label not in fstabs:
            continue
        machine_host = "{}-{}".format(HOSTS[label][0], label)
        entries = fstabs[label]
        system = [
            {"mount": entry["mount"], "identity": entry["identifier"]}
            for entry in entries
            if not entry["mount"].startswith(EXCLUDED_MOUNT_PREFIXES) and not SHARE_MOUNT.match(entry["mount"])
        ]
        shares = []
        for entry in entries:
            if not SHARE_MOUNT.match(entry["mount"]):
                continue
            owner = share_registry.get(entry["mount"], {"host": machine_host, "label": ""})
            shares.append({
                "mount": entry["mount"],
                "label": owner["label"],
                "served_by": owner["host"],
                "smb": "share-" + entry["mount"].rsplit("/", 1)[-1],
            })
        backup = next((
            {"mount": entry["mount"], "label": share_label(entry["identifier"])}
            for entry in entries if entry["mount"] == "/backup"
        ), None)
        host_schema = {}
        host_index = _get_host_index(label)
        if host_index is not None:
            host_schema["index"] = host_index
        host_schema["host"] = machine_host
        host_schema["label"] = label
        host_schema["form_factor"] = HOSTS[label][4]
        host_schema["os"] = HOSTS[label][3]
        host_schema["arch"] = HOSTS[label][1]
        host_schema["system"] = system
        host_schema["shares"] = shares
        if backup is not None:
            host_schema["backup"] = backup
        schema.append(host_schema)

    metadata_storage_path = abspath(join(DIR_ROOT, "src/main/resources/image/config.json"))
    with open(metadata_storage_path, 'w') as metadata_storage_file:
        metadata_storage_file.write(json.dumps({
            "asystem": {
                "version": "$SERVICE_VERSION_ABSOLUTE",
                "host": "$STORAGE_HOST",
                "schema": schema,
            },
        }, indent=2))
    print("Build generate script [storage] service metadata persisted to [{}]".format(metadata_storage_path))
