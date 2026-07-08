from homeassistant.generate import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    write_healthcheck()

    # Build metadata publish JSON
    metadata_tempstat_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "TempStat") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["state_topic"].str.len() > 0)
        ].copy()
    metadata_tempstat_df["availability_topic"] = "tempstat/macmini-max/status"
    write_entity_metadata("tempstat", join(DIR_ROOT, "src/main/resources/image/mqtt"), metadata_tempstat_df,
                          "homeassistant/+/tempstat/+/config",
                          "tempstat/+/data", "tempstat")
