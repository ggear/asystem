import mailbox
import os.path
import shutil
import subprocess
from datetime import datetime
from subprocess import check_output

import dateutil.parser
import pandas as pd
import urllib3
from os.path import *

urllib3.disable_warnings()
pd.options.mode.chained_assignment = None

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

TIME_FORMAT_FILE = "%Y-%m-%d_%H-%M-%S"
TIME_FORMAT_COMMAND = "%Y:%m:%d %H:%M:%S"
IMAGE_TYPES = ["JPG", "PNG", "GIF", "WEBP", "TIFF", "PSD", "RAW", "BMP", "HEIF", "HEIC", "INDD", "JPEG"]

if __name__ == "__main__":
    export_root_path = join(DIR_ROOT, "../../../../../Backup/photos/mbox")
    shutil.rmtree(export_root_path, ignore_errors=True)
    os.mkdir(export_root_path)
    mbox_db = mailbox.mbox(expanduser(join(DIR_ROOT, "src/build/resources/Jane-26-08-22.mbox")))
    for email in mbox_db:
        if email.get_content_maintype() == 'multipart':
            for part in email.walk():
                if part.get_content_maintype() != 'multipart' and part.get('Content-Disposition') is not None:
                    email_subject = email["Subject"].strip().replace("\n", "").replace("\r", "") if email["Subject"] is not None else ""
                    image_name = part.get_filename().split("/")[-1] if part.get_filename() is not None else None
                    image_type = image_name.split(".")[-1].lower() if image_name is not None else None
                    if email['From'].lower().startswith("jane") and \
                            image_name is not None and image_type is not None and image_type.upper() in IMAGE_TYPES:
                        try:
                            email_date = dateutil.parser.parse(email['Date'])
                        except Exception as exception:
                            print("Error: Could not parse date [{}]".format(email['Date']))
                            email_date = datetime(9999, 1, 1)
                        image_path = normpath("{}/{}_{}".format(
                            export_root_path,
                            email_date.strftime(TIME_FORMAT_FILE),
                            image_name
                        ).lower())
                        while exists(image_path):
                            image_path = image_path.replace(".{}".format(image_type), "_.{}".format(image_type))
                        with open(image_path, 'wb') as image_file:
                            image_payload = part.get_payload(decode=True)
                            if image_payload is not None:
                                image_file.write(image_payload)
                        image_date_str = check_output(["exiftool", "-DateTimeOriginal", "-s", "-s", "-s", image_path]) \
                            .decode('ascii').replace("+00:00", "").strip()
                        image_date = email_date if len(image_date_str) == 0 else datetime.strptime(image_date_str, TIME_FORMAT_COMMAND)
                        subprocess.run(["exiftool", "-q", "-overwrite_original",
                                        "-AllDates=\"{}\"".format(image_date.strftime(TIME_FORMAT_COMMAND)),
                                        "-DateTimeOriginal=\"{}\"".format(image_date.strftime(TIME_FORMAT_COMMAND)), image_path])
                        subprocess.run(["touch", "-t", image_date.strftime("%Y%m%d%H%M.%S"), image_path])
                        print("Build generate script [photos] image [{}] from email [{}] with creation date [{}] exported to [{}]"
                              .format(part.get_filename(), email_subject, image_date.strftime(TIME_FORMAT_FILE), image_path))
    subprocess.run(["open", export_root_path])
