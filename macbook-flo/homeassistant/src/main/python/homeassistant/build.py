import json
import os
import shutil
import subprocess
import sys
from collections import OrderedDict

import pandas as pd

DIR_MODULE_ROOT = os.path.abspath("{}/..".format(os.path.dirname(os.path.realpath(__file__))))
DIR_ROOT = os.path.abspath("{}/../../../../".format(DIR_MODULE_ROOT))
sys.path.insert(0, DIR_MODULE_ROOT)


def load_entity_metadata():
    metadata_path = os.path.abspath(os.path.join(DIR_MODULE_ROOT, "../resources/entity_metadata.xlsx"))
    metadata_df = pd.read_excel(metadata_path, header=1)
    metadata_df = metadata_df.set_index(metadata_df["index"]).sort_index()
    print("Build script [homeassistant] entity metadata loaded from [{}]".format(metadata_path))
    return metadata_df


if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    # Build customise YAML
    metadata_customise_df = metadata_df[
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["index"] > 0) &
        (metadata_df["entity_namespace"].str.len() > 0) &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["friendly_name"].str.len() > 0) &
        (metadata_df["entity_domain"].str.len() > 0)
        ]
    metadata_customise_dicts = [row.dropna().to_dict() for index, row in metadata_customise_df[[
        "entity_namespace",
        "unique_id",
        "friendly_name",
        "entity_domain",
    ]].iterrows()]
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
        (metadata_df["entity_domain"].str.len() > 0) &
        (metadata_df["entity_group"].str.len() > 0) &
        (metadata_df["display_mode"].str.len() > 0)
        ]
    metadata_lovelace_dicts = [row.dropna().to_dict() for index, row in metadata_lovelace_df[[
        "entity_namespace",
        "unique_id",
        "entity_domain",
        "entity_group",
        "display_mode",
    ]].iterrows()]
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
                print("{} : {} : {}".format(group, domain, metadata_lovelace_dict["unique_id"]))

    # Build metadata publish JSON
    metadata_publish_df = metadata_df[
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["index"] > 0) &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0)
        ]
    metadata_publish_dicts = [row.dropna().to_dict() for index, row in metadata_publish_df[[
        "unique_id",
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
            print("Build script [homeassistant] entity metadata [{}] persisted to [{}]"
                  .format(metadata_publish_dict["unique_id"], metadata_publish_path))

    # Publish metadata JSON
    subprocess.call(['bash', os.path.join(DIR_MODULE_ROOT, '../resources/entity_metadata_publish.sh')])
