from __future__ import print_function

from .. import library

LINE_PROTOCOL = "health,source={},type={},period={} {}="


# Health metrics that seem to have values:
# active_energy
# apple_exercise_time
# apple_stand_hour
# apple_stand_time
# basal_energy_burned
# flights_climbed
# headphone_audio_exposure
# heart_rate
# heart_rate_variability
# resting_heart_rate
# stair_speed:_up
# stair_speed:_down
# walking_running_distance
# walking_double_support_percentage
# walking_speed
# walking_step_length


class Health(library.Library):

    def run(self):
        new_data = False

        files = self.dropbox_download("/Data/Health", self.input)
        new_data = new_data or all([status[0] for status in files.values()]) and any([status[1] for status in files.values()])

        if not new_data:
            self.print_log("No new data found")

    def __init__(self, profile_path=".profile"):
        super(Health, self).__init__("Health", "1oI-jGTGsaYJgvj--v0q0B4Q_42OR21E2", "161A72NTU5CZWiGCDkrCCTl3fjG2N4E6S", profile_path)
