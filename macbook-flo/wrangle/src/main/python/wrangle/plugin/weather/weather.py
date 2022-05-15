import datetime

import pandas as pd

from .. import library

DAILY_START_MONTH = 1
DAILY_START_YEAR = 2009
DAILY_URL = "ftp://ftp.bom.gov.au/anon/gen/clim_data//IDCKWCDEA0/tables/wa/perth_airport/perth_airport-{}{:02d}.csv"

# TODO: These are no longer used?
DAILY_HISTORIC_RAIN_FILE = "IDCJAC0009_009021_1800_Data.csv"
DAILY_HISTORIC_SOLAR_FILE = "IDCJAC0016_009021_1800_Data.csv"
DAILY_HISTORIC_MAXTEMP_FILE = "IDCJAC0010_009021_1800_Data.csv"

MONTHLY_STATS_URL = "http://www.bom.gov.au/clim_data/cdio/tables/text/IDCJCM0039_009021.csv"

WEEKLY_FORECAST_URL = "ftp://ftp.bom.gov.au/anon/gen/fwo/IDW12300.xml"


class Weather(library.Library):

    def _run(self):
        weather_df = pd.DataFrame()
        weather_delta_df = pd.DataFrame()
        if not library.is_true(library.WRANGLE_DISABLE_DOWNLOAD_FILES):
            new_data = False
            now = datetime.datetime.now()

            # TODO: Fails on first day of the month
            # for year in range(DAILY_START_YEAR, now.year + 1):
            #     for month in range(DAILY_START_MONTH if year == DAILY_START_YEAR else 1, (now.month + 1) if year == now.year else 13):
            #         daily_url = DAILY_URL.format(year, month)
            #         daily_file = os.path.join(self.input, daily_url.split("/")[-1])
            #         file_status = self.ftp_download(daily_url, daily_file, check=year == now.year and month == now.month)
            #         if file_status[0]:
            #             if library.is_true(library.ENV_REPROCESS_ALL_FILES) or file_status[1]:
            #                 try:
            #                     new_data = True
            #
            #                     # TODO: Provide Implementation
            #
            #                     self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
            #                 except Exception as exception:
            #                     self.print_log("Unexpected error processing file [{}]".format(daily_file), exception)
            #                     self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
            #             else:
            #                 self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
            #         else:
            #             self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)

            # TODO: HTTP now fails, convert to FTP
            # monthly_stats_file = os.path.join(self.input, MONTHLY_STATS_URL.split("/")[-1])
            # file_status = self.http_download(MONTHLY_STATS_URL, monthly_stats_file)
            # if file_status[0]:
            #     if library.is_true(library.ENV_REPROCESS_ALL_FILES) or file_status[1]:
            #         try:
            #             new_data = True
            #
            #             # TODO: Provide Implementation
            #
            #             self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
            #         except Exception as exception:
            #             self.print_log("Unexpected error processing file [{}]".format(monthly_stats_file), exception)
            #             self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
            #     else:
            #         self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
            # else:
            #     self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)

            # TODO: FTP site seems to be down now too?
            # weekly_forecast_file = os.path.join(self.input, WEEKLY_FORECAST_URL.split("/")[-1])
            # file_status = self.ftp_download(WEEKLY_FORECAST_URL, weekly_forecast_file)
            # if file_status[0]:
            #     if library.is_true(library.ENV_REPROCESS_ALL_FILES) or file_status[1]:
            #         try:
            #             new_data = True
            #
            #             # TODO: Provide Implementation
            #
            #             self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
            #         except Exception as exception:
            #             self.print_log("Unexpected error processing file [{}]".format(weekly_forecast_file), exception)
            #             self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
            #     else:
            #         self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
            # else:
            #     self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)

            try:

                # TODO: Provide Implementation
                None

            except Exception as exception:
                self.print_log("Unexpected error processing weather dataframe", exception)
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        try:
            weather_delta_df, weather_current_df, _ = self.state_cache(pd.DataFrame({"some_dummy_data": [1.0]}),
                                                                       only_load=library.is_true(library.WRANGLE_DISABLE_DOWNLOAD_FILES))
            self.state_write()
        except Exception as exception:
            self.print_log("Unexpected error processing weather data", exception)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        if not len(weather_delta_df):
            self.print_log("No new data found")
        self.counter_write()

    def __init__(self):
        super(Weather, self).__init__("Weather", "1SiOrwMf-DgNQ19wRNbE7itzd4RWT829v")
