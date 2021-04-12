from __future__ import print_function

import json
import os

import pandas as pd

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
        if new_data:
            data_df = pd.DataFrame()
            for file_name in files:
                if files[file_name][0] and files[file_name][1]:
                    sleep_df = pd.DataFrame()
                    health_df = pd.DataFrame()
                    workout_df = pd.DataFrame()

                    def normalise(df):
                        df['Date'] = pd.to_datetime(df['Date'])
                        df = df.set_index('Date')
                        return df

                    if os.path.basename(file_name).startswith("_Sleep"):
                        with open(file_name) as data_file:
                            file_objs = json.load(data_file).items()
                            if len(file_objs) > 0:
                                file_df = pd.DataFrame([[
                                    file_objs[3][1],
                                    file_objs[3][1],
                                    file_objs[6][1],
                                    file_objs[4][1],
                                    file_objs[1][1],
                                    file_objs[2][1],
                                    file_objs[0][1],
                                    file_objs[5][1],
                                ]], columns=[
                                    'Date',
                                    'Sleep Start (dt)',
                                    'Sleep Until (dt)',
                                    'Sleep Duration (hr)',
                                    'Sleep Recharge (%)',
                                    'Sleep Debt (%)',
                                    'Sleep Credit (%)',
                                    'Sleep Balance (hr)',
                                ])
                                sleep_df = pd.concat([sleep_df, normalise(file_df)])
                    elif os.path.basename(file_name).startswith("Sleep"):
                        file_df = pd.read_csv(file_name)
                    elif os.path.basename(file_name).startswith("_Sleep"):
                        None
                    # else:
                    #     raise Exception("Unknown file type [{}]".format(file_name))



                    #     file_df = pd.read_csv(file_name)
                    #     if os.path.basename(file_name).startswith("_Health"):
                    #         None
                    #     elif os.path.basename(file_name).startswith("_Workout"):
                    #         file_df = file_df.add_prefix("Workout ")
                    #         file_df['Date'] = file_df['Workout Start']
                    # file_df['Date'] = pd.to_datetime(file_df['Date'])
                    # file_df = file_df.set_index('Date')
                    #
                    # # health_df = pd.concat([health_df, file_df], axis=1)
                    # # health_df = pd.merge(health_df, file_df, how='outer', left_index=True, right_index=True) if len(health_df) > 0 else file_df
                    # data_df = data_df.join(file_df, how='left')


            data_df = pd.concat([
                sleep_df[~sleep_df.index.duplicated()],
                health_df[~health_df.index.duplicated()],
                workout_df[~workout_df.index.duplicated()]
            ], axis=1).dropna(how='all', thresh=2).dropna(axis=1, how='all')
            data_delta_df = self.delta_cache(data_df, "health")
        else:
            self.print_log("No new data found")

    def __init__(self, profile_path=".profile"):
        super(Health, self).__init__("Health", "1oI-jGTGsaYJgvj--v0q0B4Q_42OR21E2", "161A72NTU5CZWiGCDkrCCTl3fjG2N4E6S", profile_path)
