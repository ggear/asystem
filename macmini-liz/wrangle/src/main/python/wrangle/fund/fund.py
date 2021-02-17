from __future__ import print_function

import datetime
import glob
import os

import pandas as pd
import pdftotext

from .. import script

DIR_DRIVE = "1TQ6Ky5sB_5Xn1lp8W6Us-OFfvEct6g4x"

STATUS_FAILURE = "failure"
STATUS_SKIPPED = "skipped"
STATUS_SUCCESS = "success"

CURRENCIES = ["GBP", "USD", "SGD"]
ATTRIBUTES = ("Date", "Type", "Owner", "Currency", "Rate", "Units", "Value")
PERIODS = {'Monthly': 1, 'Quarterly': 3, 'Yearly': 12, 'Five-Yearly': 5 * 12, 'Decennially': 10 * 12}


class Fund(script.Script):

    def run(self):
        if len(self.drive_sync(DIR_DRIVE, self.input)) > 0:
            statement_data = {}
            for statement_file_name in glob.glob("{}/*.pdf".format(self.input)):
                with open(statement_file_name, "rb") as statement_file:
                    statement_date = None
                    statement_type = None
                    statement_owner = None
                    statement_data[statement_file_name] = {}
                    statement_data[statement_file_name]['Status'] = STATUS_FAILURE
                    statement_data[statement_file_name]["Errors"] = []
                    statement_data[statement_file_name]["Positions"] = {}
                    statement_data[statement_file_name]['Parse'] = ""
                    statement_pages = pdftotext.PDF(statement_file)
                    page_index = 0
                    while page_index < len(statement_pages):
                        line_index = 0
                        statement_lines = statement_pages[page_index].split("\n")
                        if page_index == 0:
                            if len(statement_lines) > 1 and statement_lines[0].startswith("Consolidated Statement"):
                                statement_data[statement_file_name]['Status'] = STATUS_SUCCESS
                            elif len(statement_lines) > 1 and "Administration Services" in statement_lines[0]:
                                statement_data[statement_file_name]['Status'] = STATUS_SKIPPED
                            else:
                                statement_data[statement_file_name]["Errors"].append("File did not begin with required heading")
                        while line_index < len(statement_lines):
                            statement_data[statement_file_name]['Parse'] += "File [{}]: Page [{:02d}]: Line [{:02d}]:  " \
                                .format(os.path.basename(statement_file_name), page_index, line_index)
                            statement_line = statement_lines[line_index]
                            statement_tokens = statement_line.split()
                            token_index = 0
                            while token_index < len(statement_tokens):
                                statement_data[statement_file_name]['Parse'] += u"{:02d}:{} " \
                                    .format(token_index, statement_tokens[token_index])
                                token_index += 1
                            statement_data[statement_file_name]['Parse'] += "\n"
                            try:
                                if statement_data[statement_file_name]['Status'] == STATUS_SUCCESS:
                                    if page_index == 0:
                                        if statement_line.startswith("Account name"):
                                            if "Jane" in statement_line and "Graham" in statement_line:
                                                statement_type = "Fund "
                                                statement_owner = "Joint"
                                            elif "Jane" in statement_line and not "Graham" in statement_line:
                                                statement_type = "Equity "
                                                statement_owner = "Jane"
                                            else:
                                                statement_data[statement_file_name]['Status'] = STATUS_FAILURE
                                                statement_data[statement_file_name]["Errors"] \
                                                    .append("Could not determine statement type or owner from line [{}]"
                                                            .format(statement_line))
                                        if statement_line.startswith("Statement date"):
                                            statement_date = datetime.datetime.strptime(statement_line.split()[2], '%d-%b-%y')
                                        if statement_type:
                                            for currency in CURRENCIES:
                                                if statement_line.startswith(currency):
                                                    statement_data[statement_file_name]["Positions"][statement_type + currency] = {}
                                                    file_name = statement_data[statement_file_name]["Positions"][statement_type + currency]
                                                    file_name["Date"] = statement_date
                                                    file_name["Type"] = statement_type.strip()
                                                    file_name["Owner"] = statement_owner
                                                    file_name["Currency"] = currency
                                                    file_name["Rate"] = \
                                                        float(statement_line.split()[4].replace(',', ''))
                                    if statement_type:
                                        for indexes in [
                                            (2, "Special Situations", CURRENCIES, 5, 10),
                                            (3, "Special Situations", CURRENCIES, 5, 9),
                                            (2, "Required Shares", ["USD"], 2, 7),
                                            (3, "Required Shares", ["USD"], 2, 6),
                                        ]:
                                            if page_index == indexes[0] and indexes[1] in statement_line:
                                                for currency in indexes[2]:
                                                    if currency == "USD" or currency in statement_line:
                                                        try:
                                                            file_name = \
                                                                statement_data[statement_file_name]["Positions"][statement_type + currency]
                                                            file_name["Units"] = float(statement_line.split()[indexes[3]].replace(',', ''))
                                                            file_name["Value"] = float(statement_line.split()[indexes[4]].replace(',', ''))
                                                        except Exception:
                                                            None
                            except Exception as exception:
                                statement_data[statement_file_name]['Status'] = STATUS_FAILURE
                                statement_data[statement_file_name]["Errors"].append(
                                    "Statement parse failed with exception [{}: {}]".format(type(exception).__name__, exception))
                            line_index += 1
                        page_index += 1
                if statement_data[statement_file_name]['Status'] == STATUS_SUCCESS:
                    statement_positions = statement_data[statement_file_name]["Positions"]
                    for statement_position in statement_positions.values():
                        if len(statement_positions) == 0 or not all(key in statement_position for key in ATTRIBUTES):
                            statement_data[statement_file_name]['Status'] = STATUS_FAILURE
                            statement_data[statement_file_name]["Errors"] \
                                .append("Statement parse failed to resolve all keys {} in {}".format(ATTRIBUTES, statement_position))

            statements_success = 0
            statements_skipped = 0
            statements_postions = []
            for file_name in statement_data:
                if statement_data[file_name]['Status'] == STATUS_SUCCESS:
                    statement_postion = statement_data[file_name]["Positions"]
                    statements_postions.extend(statement_postion.values())
                    self.print_log("File [{}] processed as [{}] with positions {}"
                                   .format(os.path.basename(file_name), STATUS_SUCCESS, statement_postion.keys()))
                    self.add_counter(script.CTR_SRC_FILES, script.CTR_ACT_PROCESSED)
                elif statement_data[file_name]['Status'] == STATUS_SKIPPED:
                    self.print_log("File [{}] processed as [{}]".format(os.path.basename(file_name), STATUS_SKIPPED))
                    self.add_counter(script.CTR_SRC_FILES, script.CTR_ACT_SKIPPED)
                else:
                    self.print_log("File [{}] processed as [{}] at parsing point:"
                                   .format(os.path.basename(file_name), STATUS_FAILURE))
                    self.print_log(statement_data[file_name]["Parse"].split("\n"))
                    self.print_log("File [{}] processed as [{}] with errors:".format(os.path.basename(file_name), STATUS_FAILURE))
                    if not statement_data[file_name]["Errors"]:
                        statement_data[file_name]["Errors"] = ["<NONE>"]
                    error_index = 0;
                    while error_index < len(statement_data[file_name]["Errors"]):
                        self.print_log(" {:2d}: {}".format(error_index, statement_data[file_name]["Errors"][error_index]))
                        error_index += 1
            self.add_counter(script.CTR_SRC_FILES, script.CTR_ACT_ERRORED, len(statement_data)
                             - self.get_counter(script.CTR_SRC_FILES, script.CTR_ACT_PROCESSED)
                             - self.get_counter(script.CTR_SRC_FILES, script.CTR_ACT_SKIPPED))

            statement_df = pd.DataFrame(statements_postions)
            if len(statement_df) > 0:
                statement_df["Price (Reporting)"] = statement_df["Value"] / statement_df["Units"]
                statement_df["Value (Original)"] = statement_df["Value"] / statement_df["Rate"]
                statement_df["Price (Original)"] = statement_df["Value"] / statement_df["Units"] / statement_df["Rate"]
                statement_df = statement_df.rename(columns={'Value': 'Value (Reporting)'})
                statement_df = statement_df.sort_values(['Date']).reset_index(drop=True)
                for key in ["Price (Reporting)", "Price (Original)"]:
                    for period in PERIODS:
                        statement_df['{} {}'.format(key, period)] = \
                            statement_df.groupby(['Type', 'Currency'],
                                                 sort=False)[key].apply(lambda x: x.pct_change(PERIODS[period]) * 100)
                statement_df = statement_df.set_index('Date').sort_index(ascending=False)
            self.fs_write(statement_df, "{}/58861_consolidated.csv".format(self.output))

    def __init__(self):
        super(Fund, self).__init__("Fund")
