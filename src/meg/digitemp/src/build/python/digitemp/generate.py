import json
from os.path import *

from homeassistant.generate import load_entity_metadata
from homeassistant.generate import write_entity_metadata

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    # Build metadata publish JSON
    metadata_digitemp_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "DigiTemp") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["state_topic"].str.len() > 0) &
        (metadata_df["connection_mac"].str.len() > 0)
        ]
    write_entity_metadata("digitemp", join(DIR_ROOT, "src/main/resources/config/mqtt"), metadata_digitemp_df,
                          "homeassistant/+/digitemp/#", "telegraf/+/digitemp/#", )

    metadata_digitemp_dicts = []
    for _, row in metadata_digitemp_df.iterrows():
        metadata_digitemp_dicts.append(row[[
            "unique_id",
            "connection_mac",
        ]].dropna().to_dict())
    metadata_digitemp_path = abspath(join(DIR_ROOT, "src/main/resources/config/sensors.json"))
    with open(metadata_digitemp_path, 'w') as metadata_digitemp_file:
        metadata_digitemp_file.write(json.dumps(metadata_digitemp_dicts, indent=2))
    print("Build generate script [digitemp] sensor metadata persisted to [{}]".format(metadata_digitemp_path))

    metadata_digitemp_dicts = [row.dropna().to_dict() for index, row in metadata_digitemp_df.iterrows()]
    metadata_digitemp_health_path = abspath(join(DIR_ROOT, "src/main/resources/config/healthcheck.sh"))
    with open(metadata_digitemp_health_path, 'w') as metadata_digitemp_health_file:
        metadata_digitemp_health_file.write("""
#!/bin/bash

telegraf --once >/dev/null 2>&1 &&
        """.strip() + "\n")
        for metadata_digitemp_state_topic in metadata_digitemp_df["state_topic"].unique():
            metadata_digitemp_health_file.write("  " + """
  [ $(mosquitto_sub -h ${{VERNEMQ_SERVICE}} -p ${{VERNEMQ_PORT}} -t '{}' -W 1 2>/dev/null | jq -r .tags.run_code) -eq 0 ] &&
  [ $(mosquitto_sub -h ${{VERNEMQ_SERVICE}} -p ${{VERNEMQ_PORT}} -t '{}' -W 1 2>/dev/null | jq -r .fields.metrics_failed) -eq 0 ] &&
  [ $(mosquitto_sub -h ${{VERNEMQ_SERVICE}} -p ${{VERNEMQ_PORT}} -t '{}' -W 1 2>/dev/null | jq -r .fields.metrics_succeeded) -eq {} ]
            """.format(
                metadata_digitemp_state_topic,
                metadata_digitemp_state_topic,
                metadata_digitemp_state_topic,
                len(metadata_digitemp_dicts),
            ).strip() + "\n")
    print("Build generate script [digitemp] health script persisted to [{}]".format(metadata_digitemp_health_path))
