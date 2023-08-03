import glob
import os.path
import shutil
import string
import subprocess
import sys
from datetime import datetime

import osxphotos
import pandas as pd
import urllib3
from osxphotos import ExportOptions
from osxphotos import PhotoExporter
from pathvalidate import sanitize_filepath

urllib3.disable_warnings()
pd.options.mode.chained_assignment = None

DIR_ROOT = os.path.abspath("{}/../../../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/../../*/*".format(DIR_ROOT)):
    if dir_module.endswith("homeassistant"):
        sys.path.insert(0, os.path.join(dir_module, "src/build/python"))

from homeassistant.generate import load_env

DIR_PHOTOS_DB = "/Users/graham/Pictures/Photos Library.photoslibrary"

if __name__ == "__main__":
    env = load_env(DIR_ROOT)

    export_root_path = os.path.join(DIR_ROOT, "../../../../../Backup/photos/photo_album_draft")
    shutil.rmtree(export_root_path, ignore_errors=True)
    os.mkdir(export_root_path)
    photos_db = osxphotos.PhotosDB(os.path.expanduser(DIR_PHOTOS_DB))
    for folder in photos_db.folder_info:
        if folder.title == "Draft":
            for album in folder.album_info:
                index = 1
                export_date = None
                for photo in album.photos:
                    if not photo.ismissing:
                        album_name = sanitize_filepath(album.title, platform="auto") \
                            .translate(str.maketrans('', '', string.punctuation)).replace(" ", "_") \
                            .encode('ascii', 'ignore').decode('UTF-8')
                        export_path = os.path.abspath(os.path.join(export_root_path, album_name))
                        if not os.path.isdir(export_path):
                            os.makedirs(export_path)
                        photo_type = photo.filename.split(".")[-1]
                        photo_name = "{}_{:03d}.jpg".format(album_name, index)
                        export_info = PhotoExporter(photo).export(export_path, photo_name, ExportOptions(
                            update=True,
                            location=True,
                            persons=True,
                            jpeg_quality=0.0,
                            convert_to_jpeg=True,
                            edited=photo.hasadjustments
                        ))
                        if export_date is None:
                            try:
                                export_date = datetime.strptime(
                                    subprocess.run(["exiftool", "-T", "-DateTimeOriginal", export_info.exported[0]],
                                                   capture_output=True)
                                    .stdout.decode("utf-8").strip().split(" ")[0], "%Y:%m:%d")
                            except (Exception,):
                                raise Exception("Could not parse original date time on file [{}] from album [{}]"
                                                .format(photo.original_filename, album.title))
                        subprocess.run(
                            ["exiftool", "-q", "-wm", "w", "-m", "-overwrite_original", "-AllDates={} {:02d}:{:02d}:{:02d}".format(
                                export_date.strftime("%Y:%m:%d"),
                                12 + int(index / 60),
                                index % 60,
                                0
                            ), export_info.exported[0]])
                        index += 1
                        print("Build generate script [photos] image [{}] from album [{}] exported to {}"
                              .format(photo.original_filename, album.title, export_info.exported))
                        sys.stdout.flush()

                        # TODO: Add document manual process -
                        #  if DLSR: pause iCloud,
                        #  import, create albums, delete unwanted photos, empty trash, export
                        #  if DLSR: delete last import, empty trash, import new albums, unpause iCloud
                        #  upload new albums to Google
                        #  if DSLR or Janes Phone delete photos on device

                    else:
                        print("Build generate script [photos] image [{}] from album [{}] has unsupported type [{}]"
                              .format(photo.original_filename, album.title, photo_type), file=sys.stderr)
    subprocess.run(["open", export_root_path])
