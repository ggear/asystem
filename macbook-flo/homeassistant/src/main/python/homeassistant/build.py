from __future__ import print_function

import datetime
import os
import sys
import time

import pandas as pd
from requests import get

DIR_MODULE_ROOT = os.path.abspath("{}/..".format(os.path.dirname(os.path.realpath(__file__))))
DIR_ROOT = os.path.abspath("{}/../../../../".format(DIR_MODULE_ROOT))
sys.path.insert(0, DIR_MODULE_ROOT)


def load_env(root_dir=None):
    env = {}
    env_path = os.path.abspath(os.path.join(DIR_MODULE_ROOT if root_dir is None else root_dir, "../../../.env"))
    with open(env_path, 'r') as env_file:
        for env_line in env_file:
            env_line = env_line.replace("export ", "").rstrip()
            if "=" not in env_line:
                continue
            if env_line.startswith("#"):
                continue
            env_key, env_value = env_line.split("=", 1)
            env[env_key] = env_value
    print("Build script [homeassistant] environment loaded from [{}]".format(env_path))
    return env


def load_entity_metadata():
    metadata_path = os.path.abspath(os.path.join(DIR_MODULE_ROOT, "../resources/entity_metadata.xlsx"))
    metadata_df = pd.read_excel(metadata_path, header=2, dtype=unicode)
    metadata_df = metadata_df.set_index(metadata_df["index"]).sort_index()
    print("Build script [homeassistant] entity metadata loaded from [{}]".format(metadata_path))
    return metadata_df


if __name__ == "__main__":
    env = load_env()
    metadata_df = load_entity_metadata()

    # Verify entity IDs
    metadata_verify_df = metadata_df[
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["index"] > 0) &
        (metadata_df["entity_namespace"].str.len() > 0) &
        (metadata_df["unique_id"].str.len() > 0)
        ]
    metadata_verify_dicts = [row.dropna().to_dict() for index, row in metadata_verify_df.iterrows()]
    for metadata_verify_dict in metadata_verify_dicts:
        state_response = get(
            "http://{}:{}/api/states/{}.{}".format(
                env["HOMEASSISTANT_HOST_PROD"],
                env["HOMEASSISTANT_PORT"],
                metadata_verify_dict["entity_namespace"],
                metadata_verify_dict["unique_id"]
            ), headers={"Authorization": "Bearer {}".format(env["HOMEASSISTANT_API_TOKEN"]), "content-type": "application/json", })
        if state_response.status_code == 200:
            hours_since_update = (time.time() - (time.mktime(datetime.datetime.strptime(
                state_response.json()["last_updated"].split('+')[0], '%Y-%m-%dT%H:%M:%S.%f').timetuple()) + 8 * 60 * 60)) / (60 * 60)
            if hours_since_update > 1:
                print("Build script [homeassistant] entity metadata [{}.{}] not recently updated"
                      .format(metadata_verify_dict["entity_namespace"], metadata_verify_dict["unique_id"]),
                      file=sys.stderr if "display_mode" in metadata_verify_dict else sys.stdout)
            else:
                print("Build script [homeassistant] entity metadata [{}.{}] verified"
                      .format(metadata_verify_dict["entity_namespace"], metadata_verify_dict["unique_id"]))
        else:
            print("Build script [homeassistant] entity metadata [{}.{}] not found"
                  .format(metadata_verify_dict["entity_namespace"], metadata_verify_dict["unique_id"]), file=sys.stderr)

    sys.exit()

    # Build customise YAML
    metadata_customise_df = metadata_df[
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["index"] > 0) &
        (metadata_df["entity_namespace"].str.len() > 0) &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["friendly_name"].str.len() > 0) &
        (metadata_df["entity_domain"].str.len() > 0)
        ]
    metadata_customise_dicts = [row.dropna().to_dict() for index, row in metadata_customise_df.iterrows()]
    metadata_customise_path = os.path.join(DIR_MODULE_ROOT, "../resources/config/customise.yaml")
    with open(metadata_customise_path, 'w') as metadata_customise_file:
        metadata_customise_file.write("#######################################################################################\n")
        metadata_customise_file.write("# WARNING: This file is written to by the build process, any manual edits will be lost!\n")
        metadata_customise_file.write("#######################################################################################\n")
        last_domain = None
        for metadata_customise_dict in metadata_customise_dicts:
            domain_spacer = ""
            if last_domain is None or last_domain != metadata_customise_dict["entity_domain"]:
                last_domain = metadata_customise_dict["entity_domain"]
                domain_spacer = "\n#######################################################################################\n" \
                                "# {}\n#######################################################################################\n" \
                    .format(last_domain)
            metadata_customise_str = "{}{}.{}:\n  friendly_name: {}\n".format(
                domain_spacer,
                metadata_customise_dict["entity_namespace"],
                metadata_customise_dict["unique_id"],
                metadata_customise_dict["friendly_name"],
            )
            metadata_customise_file.write(metadata_customise_str)
        print("Build script [homeassistant] entity metadata persisted to [{}]".format(metadata_customise_path))

    # Build lovelace YAML
    metadata_lovelace_df = metadata_df[
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["index"] > 0) &
        (metadata_df["entity_namespace"].str.len() > 0) &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["friendly_name"].str.len() > 0) &
        (metadata_df["entity_domain"].str.len() > 0) &
        (metadata_df["entity_group"].str.len() > 0) &
        (metadata_df["display_mode"].str.len() > 0)
        ]
    metadata_lovelace_dicts = [row.dropna().to_dict() for index, row in metadata_lovelace_df.iterrows()]
    metadata_lovelace_group_domain_dicts = OrderedDict()
    for metadata_lovelace_dict in metadata_lovelace_dicts:
        group = metadata_lovelace_dict["entity_group"]
        domain = metadata_lovelace_dict["entity_domain"]
        if group not in metadata_lovelace_group_domain_dicts:
            metadata_lovelace_group_domain_dicts[group] = OrderedDict()
        if domain not in metadata_lovelace_group_domain_dicts[group]:
            metadata_lovelace_group_domain_dicts[group][domain] = []
        metadata_lovelace_group_domain_dicts[group][domain].append(metadata_lovelace_dict)
    for group in metadata_lovelace_group_domain_dicts:
        for domain in metadata_lovelace_group_domain_dicts[group]:
            for metadata_lovelace_dict in metadata_lovelace_group_domain_dicts[group][domain]:
                # TODO: Provide implementation
                print("{} : {} : {}".format(group, domain, metadata_lovelace_dict["friendly_name"]))

    # Build metadata publish JSON
    metadata_publish_df = metadata_df[
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["index"] > 0) &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0)
        ]
    metadata_publish_dicts = [row.dropna().to_dict() for index, row in metadata_publish_df[[
        "unique_id",
        "name",
        "state_class",
        "unit_of_measurement",
        "device_class",
        "icon",
        "force_update",
        "state_topic",
        "value_template",
        "qos",
    ]].iterrows()]
    metadata_device_columns = [column for column in metadata_publish_df.columns
                               if (column.startswith("device_") and column != "device_class")]
    metadata_device_columns_rename = {column: column.replace("device_", "") for column in metadata_device_columns}
    metadata_device_pub_dicts = [row.dropna().to_dict() for index, row in
                                 metadata_publish_df[metadata_device_columns]
                                     .rename(columns=metadata_device_columns_rename).iterrows()]
    metadata_publish_dir = os.path.join(DIR_MODULE_ROOT, "../resources/entity_metadata")
    if os.path.exists(metadata_publish_dir):
        shutil.rmtree(metadata_publish_dir)
    os.makedirs(metadata_publish_dir)
    for index, metadata_publish_dict in enumerate(metadata_publish_dicts):
        metadata_publish_dict["device"] = metadata_device_pub_dicts[index]
        metadata_publish_str = json.dumps(metadata_publish_dict, ensure_ascii=False).encode('utf8')
        metadata_publish_path = os.path.abspath(os.path.join(metadata_publish_dir, metadata_publish_dict["unique_id"] + ".json"))
        with open(metadata_publish_path, 'a') as metadata_customise_file:
            metadata_customise_file.write(metadata_publish_str)
            print("Build script [homeassistant] entity metadata [sensor.{}] persisted to [{}]"
                  .format(metadata_publish_dict["unique_id"], metadata_publish_path))

    # Publish metadata JSON
    subprocess.call(['bash', os.path.join(DIR_MODULE_ROOT, '../resources/entity_metadata_publish.sh')])
