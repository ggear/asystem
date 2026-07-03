from homeassistant.generate import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    write_bootstrap()
    write_healthcheck()

    # Build metadata publish JSON
    metadata_zeroth_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Zeroth") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["state_topic"].str.len() > 0)
        ]
    write_entity_metadata("zeroth", join(DIR_ROOT, "src/main/resources/image/mqtt"), metadata_zeroth_df,
                          "homeassistant/+/zeroth_${SUPERVISOR_HOST}/+/config",
                          "zeroth/${SUPERVISOR_HOST}/data/+/+/+", "zeroth_${SUPERVISOR_HOST}")
