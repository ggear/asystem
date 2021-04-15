from __future__ import print_function

import json
import os
from datetime import datetime

import numpy as np
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
            sleep_df = pd.DataFrame()
            health_df = pd.DataFrame()
            workout_df = pd.DataFrame()
            sleep_yesterday_df = pd.DataFrame()
            for file_name in files:
                if files[file_name][0] and files[file_name][1]:

                    def normalise(df):
                        df['Date'] = pd.to_datetime(df['Date'])
                        df = df.set_index('Date')
                        return df

                    if os.path.basename(file_name).startswith("_Sleep-"):
                        if len(sleep_yesterday_df) == 0:
                            with open(file_name) as data_file:
                                file_objs = json.load(data_file).items()
                                if len(file_objs) > 0:
                                    file_df = pd.DataFrame([[
                                        datetime.strptime(file_objs[6][1], '%a, %d/%m/%y, %I:%M %p'),
                                        datetime.strptime(file_objs[3][1], '%a, %d/%m/%y, %I:%M %p'),
                                        datetime.strptime(file_objs[6][1], '%a, %d/%m/%y, %I:%M %p'),
                                        file_objs[1][1],
                                        file_objs[2][1],
                                        file_objs[0][1],
                                        file_objs[5][1],
                                    ]], columns=[
                                        'Date',
                                        'Sleep Start (dt)',
                                        'Sleep Finish (dt)',
                                        'Sleep Recharge (%)',
                                        'Sleep Debt (%)',
                                        'Sleep Credit (%)',
                                        'Sleep Balance (hr)',
                                    ])
                                    sleep_yesterday_df = file_df
                    elif os.path.basename(file_name).startswith("_SleepReadiness-"):
                        if len(sleep_yesterday_df) == 1 and len(sleep_yesterday_df.columns) == 7:
                            with open(file_name) as data_file:
                                file_objs = json.load(data_file).items()
                                if len(file_objs) > 0:
                                    file_df = pd.DataFrame([[
                                        file_objs[1][1],
                                        file_objs[0][1],
                                        file_objs[2][1],
                                        file_objs[3][1],
                                        float(file_objs[4][1]) / 5 * 100,
                                    ]], columns=[
                                        'Sleep Heart Rate Variability (ms)',
                                        'Sleep Heart Rate Variability Baseline (ms)',
                                        'Sleep Heart Rate Waking',
                                        'Sleep Heart Rate Waking Baseline',
                                        'Sleep Readiness Rating',
                                    ])
                                    sleep_yesterday_df = pd.concat([sleep_yesterday_df, file_df], axis=1)
                    elif os.path.basename(file_name).startswith("_SleepRings-"):
                        if len(sleep_yesterday_df) == 1 and len(sleep_yesterday_df.columns) == 12:
                            with open(file_name) as data_file:
                                file_objs = json.load(data_file).items()
                                if len(file_objs) > 0:
                                    awake = float(sleep_yesterday_df['Sleep Finish (dt)'].values[-1] -
                                                  sleep_yesterday_df['Sleep Start (dt)'].values[-1]) / (60 * 60 * 1000000000) - \
                                            float(file_objs[5][1])
                                    efficiency = (1 - awake / float(file_objs[5][1])) * 100
                                    file_df = pd.DataFrame([[
                                        file_objs[5][1],
                                        awake if awake >= 0 else None,
                                        file_objs[7][1],
                                        file_objs[3][1],
                                        efficiency if awake >= 0 else None,
                                        file_objs[0][1],
                                        file_objs[4][1],
                                        file_objs[1][1],
                                        file_objs[8][1],
                                        file_objs[6][1],
                                    ]], columns=[
                                        'Sleep Duration (hr)',
                                        'Sleep Awake (hr)',
                                        'Sleep Quality (hr)',
                                        'Sleep Deep (hr)',
                                        'Sleep Efficiency (%)',
                                        'Sleep Heart Rate (bpm)',
                                        'Sleep Duration Goal (%)',
                                        'Sleep Quality Goal (%)',
                                        'Sleep Deep Goal (%)',
                                        'Sleep Rating (%)',
                                    ])
                                    sleep_df = pd.concat([sleep_df, normalise(pd.concat([sleep_yesterday_df, file_df], axis=1))])
                    elif os.path.basename(file_name).startswith("Sleep-"):

                        def duration_normalise(df, column):
                            df[column] = df[column].replace('--', 0)
                            df[column] = file_df[column].apply(lambda x: x if ':' in str(x) else "0:{}".format(x))
                            return df[column]

                        def duration_decimalise(df, column, scale=1.0 / (60 * 60)):
                            df[column] = duration_normalise(df, column)
                            df[column] = file_df[column].apply(lambda x: datetime.strptime(x, '%M:%S'))
                            df[column] = df[column] - datetime.strptime('00:00', '%M:%S')
                            df[column] = df[column].apply(lambda x: x / np.timedelta64(1, 's') * 60 * scale)
                            return df[column]

                        sleep_history_df = pd.DataFrame()
                        file_df = pd.read_csv(file_name)
                        file_df['Start'] = file_df['Fell asleep in'].replace('--', 0)
                        file_df['Start'] = duration_decimalise(file_df, 'Start', 1)
                        file_df['Start'] = pd.to_timedelta(file_df['Start'], 's')
                        sleep_history_df['Date'] = pd.to_datetime(file_df['Until'], format='%Y-%m-%d %H:%M:%S')
                        sleep_history_df['Sleep Start (dt)'] = pd.to_datetime(file_df['In bed at'], format='%Y-%m-%d %H:%M:%S') + file_df['Start']
                        sleep_history_df['Sleep Finish (dt)'] = sleep_history_df['Date']
                        sleep_history_df['Sleep Recharge (%)'] = np.NaN
                        sleep_history_df['Sleep Debt (%)'] = np.NaN
                        sleep_history_df['Sleep Credit (%)'] = np.NaN
                        sleep_history_df['Sleep Balance (hr)'] = np.NaN
                        sleep_history_df['Sleep Heart Rate Variability (ms)'] = np.NaN
                        sleep_history_df['Sleep Heart Rate Variability Baseline (ms)'] = np.NaN
                        sleep_history_df['Sleep Heart Rate Waking'] = np.NaN
                        sleep_history_df['Sleep Heart Rate Waking Baseline'] = np.NaN
                        sleep_history_df['Sleep Readiness Rating'] = np.NaN
                        sleep_history_df['Sleep Duration (hr)'] = duration_decimalise(file_df, 'Asleep')
                        sleep_history_df['Sleep Awake (hr)'] = (sleep_history_df['Sleep Finish (dt)'] -
                                                                sleep_history_df['Sleep Start (dt)']
                                                                ).astype('timedelta64[s]') / (60 * 60) - \
                                                               sleep_history_df['Sleep Duration (hr)']
                        sleep_history_df['Sleep Awake (hr)'] = sleep_history_df['Sleep Awake (hr)'] \
                            .mask(sleep_history_df['Sleep Awake (hr)'] < 0, np.NaN)
                        sleep_history_df['Sleep Quality (hr)'] = duration_decimalise(file_df, 'Quality sleep')
                        sleep_history_df['Sleep Deep (hr)'] = duration_decimalise(file_df, 'Deep sleep')
                        sleep_history_df['Sleep Efficiency (%)'] = (1 - sleep_history_df['Sleep Awake (hr)'] /
                                                                    sleep_history_df['Sleep Duration (hr)']) * 100
                        sleep_history_df['Sleep Efficiency (%)'] = sleep_history_df['Sleep Efficiency (%)'] \
                            .mask(sleep_history_df['Sleep Efficiency (%)'] > 100, np.NaN)
                        sleep_history_df['Sleep Heart Rate (bpm)'] = file_df['Heartrate']
                        sleep_history_df['Sleep Duration Goal (%)'] = sleep_history_df['Sleep Duration (hr)'] / 0.08
                        sleep_history_df['Sleep Quality Goal (%)'] = sleep_history_df['Sleep Quality (hr)'] / 0.06
                        sleep_history_df['Sleep Deep Goal (%)'] = sleep_history_df['Sleep Deep (hr)'] / 0.024
                        sleep_history_df['Sleep Rating (%)'] = np.NaN
                        sleep_df = pd.concat([sleep_df, normalise(sleep_history_df)])
            data_df = pd.concat([
                sleep_df[~sleep_df.index.duplicated(keep='last')],
                health_df[~health_df.index.duplicated(keep='last')],
                workout_df[~workout_df.index.duplicated(keep='last')]
            ], axis=1).dropna(how='all', thresh=2).dropna(axis=1, how='all')
            data_delta_df = self.delta_cache(data_df, "health")
        else:
            self.print_log("No new data found")

    def __init__(self, profile_path=".profile"):
        super(Health, self).__init__("Health", "1oI-jGTGsaYJgvj--v0q0B4Q_42OR21E2", "161A72NTU5CZWiGCDkrCCTl3fjG2N4E6S", profile_path)
