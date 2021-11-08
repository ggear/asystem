# -*- coding: utf-8 -*-

from __future__ import print_function

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from .. import library


class Health(library.Library):

    def _run(self):
        data_df = pd.DataFrame()
        data_delta_df = pd.DataFrame()
        if not library.is_true(library.ENV_DISABLE_DOWNLOAD_FILES):
            sleep_df = pd.DataFrame()
            health_df = pd.DataFrame()
            workout_df = pd.DataFrame()
            files = self.dropbox_download("/Data/Health", self.input)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED, 0 if library.is_true(library.ENV_REPROCESS_ALL_FILES) else \
                sum([not status[1] for status in files.values()]))
            new_data = library.is_true(library.ENV_REPROCESS_ALL_FILES) or \
                       all([status[0] for status in files.values()]) and any([status[1] for status in files.values()])
            if new_data:
                sleep_yesterday_df = pd.DataFrame()
                for file_name in files:
                    if files[file_name][0] and (library.is_true(library.ENV_REPROCESS_ALL_FILES) or files[file_name][1]):

                        def normalise(df):
                            df['Date'] = pd.to_datetime(df['Date'])
                            df = df.set_index('Date')
                            return df

                        def get(list, label):
                            for item in list:
                                if item[0] == label:
                                    return item[1]
                            raise Exception("Health label [{}] not found in list {}".format(label, list))

                        if os.path.basename(file_name).startswith("_Sleep-"):
                            if len(sleep_yesterday_df) == 0:
                                with open(file_name) as data_file:
                                    file_objs = json.load(data_file).items()
                                    if len(file_objs) > 0:
                                        try:
                                            file_df = pd.DataFrame([[
                                                datetime.strptime(get(file_objs, 'Until'), '%a, %d/%m/%y, %I:%M %p'),
                                                datetime.strptime(get(file_objs, 'Start'), '%a, %d/%m/%y, %I:%M %p'),
                                                datetime.strptime(get(file_objs, 'Until'), '%a, %d/%m/%y, %I:%M %p'),
                                                get(file_objs, 'Recharge%'),
                                                get(file_objs, 'Debt%'),
                                                get(file_objs, 'Credit%'),
                                                get(file_objs, 'Balance'),
                                            ]], columns=[
                                                'Date',
                                                'Sleep Start (dt)',
                                                'Sleep Finish (dt)',
                                                'Sleep Recharge (%)',
                                                'Sleep Debt (%)',
                                                'Sleep Credit (%)',
                                                'Sleep Balance (hr)',
                                            ])
                                            if float(get(file_objs, 'Sleep')) > 0:
                                                sleep_yesterday_df = file_df
                                                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                                        except Exception as exception:
                                            self.print_log("Unexpected error processing file [{}]".format(file_name), exception)
                                            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
                        elif os.path.basename(file_name).startswith("_SleepReadiness-"):
                            if len(sleep_yesterday_df) == 1 and len(sleep_yesterday_df.columns) == 7:
                                with open(file_name) as data_file:
                                    file_objs = json.load(data_file).items()
                                    if len(file_objs) > 0:
                                        try:
                                            file_df = pd.DataFrame([[
                                                get(file_objs, 'HRV'),
                                                get(file_objs, 'BaselineHRV'),
                                                get(file_objs, 'bpm'),
                                                get(file_objs, 'BaselineWakingBPM'),
                                                float(get(file_objs, 'Stars')) / 5 * 100,
                                            ]], columns=[
                                                'Sleep Heart Rate Variability (ms)',
                                                'Sleep Heart Rate Variability Baseline (ms)',
                                                'Sleep Heart Rate Waking (bpm)',
                                                'Sleep Heart Rate Waking Baseline (bpm)',
                                                'Sleep Readiness Rating (%)',
                                            ])
                                            sleep_yesterday_df = pd.concat([sleep_yesterday_df, file_df], axis=1, sort=True)
                                            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                                        except Exception as exception:
                                            self.print_log("Unexpected error processing file [{}]".format(file_name), exception)
                                            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
                        elif os.path.basename(file_name).startswith("_SleepRings-"):
                            if len(sleep_yesterday_df) == 1 and len(sleep_yesterday_df.columns) == 12:
                                with open(file_name) as data_file:
                                    file_objs = json.load(data_file).items()
                                    if len(file_objs) > 0:
                                        try:
                                            awake = float(
                                                sleep_yesterday_df['Sleep Finish (dt)'].values[-1] -
                                                sleep_yesterday_df['Sleep Start (dt)'].values[-1]) / \
                                                    (60 * 60 * 1000000000) - float(get(file_objs, 'Sleep'))
                                            efficiency = (1 - awake / float(get(file_objs, 'Sleep'))) * 100
                                            file_df = pd.DataFrame([[
                                                get(file_objs, 'Sleep'),
                                                awake if awake >= 0 else None,
                                                get(file_objs, 'Quality'),
                                                get(file_objs, 'Deep'),
                                                efficiency if awake >= 0 else None,
                                                get(file_objs, 'bpm'),
                                                get(file_objs, 'Sleep%'),
                                                get(file_objs, 'Quality%'),
                                                get(file_objs, 'Deep%'),
                                                get(file_objs, 'SleepRating'),
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
                                            sleep_df = pd.concat([sleep_df, normalise(
                                                pd.concat([sleep_yesterday_df, file_df], axis=1, sort=True))], sort=True)
                                            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                                        except Exception as exception:
                                            self.print_log("Unexpected error processing file [{}]".format(file_name), exception)
                                            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
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

                            try:
                                sleep_history_df = pd.DataFrame()
                                file_df = pd.read_csv(file_name, skipinitialspace=True)
                                file_df['Start'] = file_df['Fell asleep in'].replace('--', 0)
                                file_df['Start'] = duration_decimalise(file_df, 'Start', 1)
                                file_df['Start'] = pd.to_timedelta(file_df['Start'], 's')
                                sleep_history_df['Date'] = pd.to_datetime(file_df['Until'], format='%Y-%m-%d %H:%M:%S')
                                sleep_history_df['Sleep Start (dt)'] = pd.to_datetime(file_df['In bed at'],
                                                                                      format='%Y-%m-%d %H:%M:%S') + file_df['Start']
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
                                sleep_history_df['Sleep Awake (hr)'] = \
                                    (sleep_history_df['Sleep Finish (dt)'] - sleep_history_df['Sleep Start (dt)']) \
                                        .astype('timedelta64[s]') / (60 * 60) - sleep_history_df['Sleep Duration (hr)']
                                sleep_history_df['Sleep Awake (hr)'] = \
                                    sleep_history_df['Sleep Awake (hr)'].mask(sleep_history_df['Sleep Awake (hr)'] < 0, np.NaN)
                                sleep_history_df['Sleep Quality (hr)'] = duration_decimalise(file_df, 'Quality sleep')
                                sleep_history_df['Sleep Deep (hr)'] = duration_decimalise(file_df, 'Deep sleep')
                                sleep_history_df['Sleep Efficiency (%)'] = \
                                    (1 - sleep_history_df['Sleep Awake (hr)'] / sleep_history_df['Sleep Duration (hr)']) * 100
                                sleep_history_df['Sleep Efficiency (%)'] = \
                                    sleep_history_df['Sleep Efficiency (%)'].mask(sleep_history_df['Sleep Efficiency (%)'] > 100, np.NaN)
                                sleep_history_df['Sleep Heart Rate (bpm)'] = file_df['Heartrate']
                                sleep_history_df['Sleep Duration Goal (%)'] = sleep_history_df['Sleep Duration (hr)'] / 0.08
                                sleep_history_df['Sleep Quality Goal (%)'] = sleep_history_df['Sleep Quality (hr)'] / 0.06
                                sleep_history_df['Sleep Deep Goal (%)'] = sleep_history_df['Sleep Deep (hr)'] / 0.024
                                sleep_history_df['Sleep Rating (%)'] = np.NaN
                                sleep_df = pd.concat([sleep_df, normalise(sleep_history_df)], sort=True)
                                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                            except Exception as exception:
                                self.print_log("Unexpected error processing file [{}]".format(file_name), exception)
                                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
                        elif os.path.basename(file_name).startswith("_Health-") or os.path.basename(file_name).startswith("Health-"):
                            try:
                                file_df = pd.read_csv(file_name, skipinitialspace=True)
                                file_df = file_df.dropna(how='all', thresh=2).dropna(axis=1, how='all')
                                if 'Sleep Analysis [Asleep] (hours)' in file_df:
                                    del file_df['Sleep Analysis [Asleep] (hours)']
                                if 'Sleep Analysis [Asleep] (hr)' in file_df:
                                    del file_df['Sleep Analysis [Asleep] (hr)']
                                if 'Sleep Analysis [In Bed] (hours)' in file_df:
                                    del file_df['Sleep Analysis [In Bed] (hours)']
                                if 'Sleep Analysis [In Bed] (hr)' in file_df:
                                    del file_df['Sleep Analysis [In Bed] (hr)']
                                file_df = file_df.rename(columns={
                                    'Apple Stand Time (min)': 'Stand Duration (min)',
                                    'Apple Stand Hour (count)': 'Stand Sessions (count)',
                                    'Active Energy (kJ)': 'Energy Active Burned (kJ)',
                                    'Basal Energy Burned (kJ)': 'Energy Basal Burned (kJ)',
                                    'Mindful Minutes (min)': 'Breathing Duration (min)',
                                    'Headphone Audio Exposure (dBASPL)': 'Hearing Headphone Exposure (dBSPL)',
                                    'Heart Rate Variability (ms)': 'Heart Rate Variability (ms)',
                                    'Heart Rate [Avg] (count/min)': 'Heart Rate Average (bpm)',
                                    'Heart Rate [Max] (count/min)': 'Heart Rate Maximum (bpm)',
                                    'Heart Rate [Min] (count/min)': 'Heart Rate Minimum (bpm)',
                                    'Resting Heart Rate (count/min)': 'Heart Rate Resting (bpm)',
                                    'Apple Exercise Time (min)': 'Exercise Duration (min)',
                                    'Step Count (count)': 'Exercise Steps Taken (count)',
                                    'Flights Climbed (count)': 'Exercise Flights Climbed (count)',
                                    'VO2 Max (ml/(kg·min))': 'Exercise VO2 Max (mL/kg/min)',
                                    'Walking + Running Distance (km)': 'Walking Distance (km)',
                                    'Walking Asymmetry Percentage (%)': 'Walking Asymmetry (%)',
                                    'Walking Double Support Percentage (%)': 'Walking Double Support Percentage (%)',
                                    'Walking Heart Rate Average (count/min)': 'Walking Heart Rate Average (bpm)',
                                    'Walking Speed (km/hr)': 'Walking Speed (km/hr)',
                                })
                                health_df = pd.concat([health_df, normalise(file_df)], sort=True)
                                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                            except Exception as exception:
                                self.print_log("Unexpected error processing file [{}]".format(file_name), exception)
                                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
                        elif os.path.basename(file_name).startswith("_Workout-") or os.path.basename(file_name).startswith("Workout-"):
                            try:
                                file_df = pd.read_csv(file_name, skipinitialspace=True)
                                file_df['Start'] = pd.to_datetime(file_df['Start'], format='%Y-%m-%d %H:%M')
                                file_df['End'] = pd.to_datetime(file_df['End'], format='%Y-%m-%d %H:%M')
                                file_df['Duration'] = file_df['Duration'].apply(lambda x: datetime.strptime(x, '%H:%M:%S'))
                                file_df['Duration'] = file_df['Duration'] - datetime.strptime('00:00', '%M:%S')
                                file_df['Duration'] = file_df['Duration'].apply(lambda x: x / np.timedelta64(1, 's') * 60)
                                file_df = pd.concat([
                                    file_df.pivot(columns='Type', values='Start')
                                        .add_prefix('Workout-').add_suffix(' Start (dt)'),
                                    file_df.pivot(columns='Type', values='End')
                                        .add_prefix('Workout-').add_suffix(' Finish (dt)'),
                                    file_df.pivot(columns='Type', values='Duration')
                                        .add_prefix('Workout-').add_suffix(' Duration (sec)'),
                                    file_df.pivot(columns='Type', values='Total Energy (kJ)')
                                        .add_prefix('Workout-').add_suffix(' Energy Total (kJ)'),
                                    file_df.pivot(columns='Type', values='Active Energy (kJ)')
                                        .add_prefix('Workout-').add_suffix(' Energy Active (kJ)'),
                                    file_df.pivot(columns='Type', values='Avg Speed(km/hr)')
                                        .add_prefix('Workout-').add_suffix(' Speed Average (km/hr)'),
                                    file_df.pivot(columns='Type', values='Avg Heart Rate (bpm)')
                                        .add_prefix('Workout-').add_suffix(' Heart Rate Average (bpm)'),
                                    file_df.pivot(columns='Type', values='Max Heart Rate (bpm)')
                                        .add_prefix('Workout-').add_suffix(' Heart Rate Maximum (bpm)'),
                                ], axis=1)
                                start_columns = ['Date']
                                for start_column in file_df.columns.get_values().tolist():
                                    if start_column.endswith('Start (dt)'):
                                        start_columns.append(start_column)
                                file_df['Date'] = np.NaN
                                file_df = file_df.assign(Date=file_df[start_columns].bfill(axis=1)['Date'])
                                file_df['Date'] = pd.to_datetime(file_df['Date'], format='%Y-%m-%d %H:%M')
                                file_df = file_df.reindex(sorted(file_df.columns), axis=1)
                                workout_df = pd.concat([workout_df, normalise(file_df)], sort=True)
                                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                            except Exception as exception:
                                self.print_log("Unexpected error processing file [{}]".format(file_name), exception)
                                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
                        else:
                            self.print_log("Error: Unknown file format [{}]".format(file_name))
                            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
            try:
                if len(sleep_df) > 0:
                    sleep_df = sleep_df[[
                        'Sleep Start (dt)',
                        'Sleep Finish (dt)',
                        'Sleep Balance (hr)',
                        'Sleep Recharge (%)',
                        'Sleep Debt (%)',
                        'Sleep Credit (%)',
                        'Sleep Duration (hr)',
                        'Sleep Duration Goal (%)',
                        'Sleep Quality (hr)',
                        'Sleep Quality Goal (%)',
                        'Sleep Deep (hr)',
                        'Sleep Deep Goal (%)',
                        'Sleep Awake (hr)',
                        'Sleep Efficiency (%)',
                        'Sleep Readiness Rating (%)',
                        'Sleep Rating (%)',
                        'Sleep Heart Rate (bpm)',
                        'Sleep Heart Rate Variability (ms)',
                        'Sleep Heart Rate Variability Baseline (ms)',
                        'Sleep Heart Rate Waking (bpm)',
                        'Sleep Heart Rate Waking Baseline (bpm)',
                    ]]
                    sleep_df = sleep_df[~sleep_df.index.duplicated(keep='last')]
                if len(health_df) > 0:
                    health_df = health_df[[
                        'Energy Basal Burned (kJ)',
                        'Energy Active Burned (kJ)',
                        'Stand Duration (min)',
                        'Stand Sessions (count)',
                        'Exercise Duration (min)',
                        'Exercise Steps Taken (count)',
                        'Exercise Flights Climbed (count)',
                        'Walking Asymmetry (%)',
                        'Walking Distance (km)',
                        'Walking Double Support Percentage (%)',
                        'Walking Heart Rate Average (bpm)',
                        'Walking Speed (km/hr)',
                        'Breathing Duration (min)',
                        'Hearing Headphone Exposure (dBSPL)',
                        'Heart Rate Average (bpm)',
                        'Heart Rate Maximum (bpm)',
                        'Heart Rate Minimum (bpm)',
                        'Heart Rate Resting (bpm)',
                        'Heart Rate Variability (ms)',
                    ]]
                    health_df = health_df[~health_df.index.duplicated(keep='last')]
                if len(workout_df) > 0:
                    workout_columns = []
                    workout_types = set()
                    for workout_column in workout_df.columns.get_values().tolist():
                        workout_types.add(workout_column.split(' ')[0].split('-')[1])
                    for workout_type in workout_types:
                        for workout_dimension in [
                            'Start (dt)',
                            'Finish (dt)',
                            'Duration (sec)',
                            'Energy Total (kJ)',
                            'Energy Active (kJ)',
                            'Speed Average (km/hr)',
                            'Heart Rate Average (bpm)',
                            'Heart Rate Maximum (bpm)',
                        ]:
                            workout_columns.append("Workout-{} {}".format(workout_type, workout_dimension))
                    workout_df = workout_df[workout_columns]
                    workout_df = workout_df[~workout_df.index.duplicated(keep='last')]
                data_df = pd.concat([health_df, workout_df, sleep_df], axis=1, sort=True)
                data_df.index.name = 'Date'
            except Exception as exception:
                self.print_log("Unexpected error processing health dataframe", exception)
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        try:
            data_delta_df, _, _ = self.state_cache(data_df, library.is_true(library.ENV_DISABLE_DOWNLOAD_FILES))
            if len(data_delta_df):
                buckets = {}
                for column in data_delta_df.columns.tolist():
                    column_rename = {column: ' '.join(column.split('(')[0].split(' ')[1:])}
                    type = column.split(' ')[0].lower()
                    unit = column.split('(')[-1].replace(')', '').strip()
                    if (type, unit) not in buckets:
                        buckets[(type, unit)] = ([], {})
                    buckets[(type, unit)][0].append(column)
                    buckets[(type, unit)][1].update(column_rename)
                for bucket in buckets:
                    data_df = data_delta_df[buckets[bucket][0]].dropna(axis=0, how='all')
                    for column in data_df.columns.tolist():
                        if column.endswith("(dt)"):
                            data_df[column] = pd.to_datetime(data_df[data_df[column].notna()][column]).astype('int64') // 10 ** 9
                        else:
                            data_df[column] = pd.to_numeric(data_df[column])
                    self.database_write(data_df.rename(columns=buckets[bucket][1]), global_tags={
                        "type": bucket[0],
                        "period": "1d",
                        "unit": bucket[1]
                    })
                self.state_write()
        except Exception as exception:
            self.print_log("Unexpected error processing health data", exception)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        if not len(data_delta_df):
            self.print_log("No new data found")
        self.counter_write()

    def __init__(self):
        super(Health, self).__init__("Health", "1oI-jGTGsaYJgvj--v0q0B4Q_42OR21E2")
