from homeassistant.generate import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    write_healthcheck()

    # Build MQTT schema
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
    write_entity_metadata(metadata_digitemp_df,
                          topic_glob_discovery="homeassistant/+/digitemp/#",
                          topic_glob_data="telegraf/+/digitemp/#")

    metadata_digitemp_dicts = []
    for _, row in metadata_digitemp_df.iterrows():
        metadata_digitemp_dicts.append(row[[
            "unique_id",
            "connection_mac",
        ]].dropna().to_dict())
    metadata_digitemp_path = abspath(join(DIR_ROOT, "src/main/resources/image/sensors.json"))
    with open(metadata_digitemp_path, 'w') as metadata_digitemp_file:
        metadata_digitemp_file.write(json.dumps(metadata_digitemp_dicts, indent=2))
    print("Build generate script [digitemp] sensor metadata persisted to [{}]".format(metadata_digitemp_path))
