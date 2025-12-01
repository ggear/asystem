import csv
import os

ROOT_DIR = '/Users/graham/Code/asystem/src/meg_may_max_mad/media/src/main/python/sync'

if __name__ == "__main__":
    # media = set()
    # with open(os.path.join(ROOT_DIR, "media_raw.csv"), 'r') as file:
    #     csv_reader = csv.reader(file)
    #     for row in csv_reader:
    #         if "/Season " in row[0]:
    #             media.add(row[0].split("/Season ")[0])
    #         else:
    #             media.add(row[0])
    #
    # with open(os.path.join(ROOT_DIR, "media_condensed.txt"), 'w', newline='') as file:
    #     csv_writer = csv.writer(file)
    #     for item in sorted(media):
    #         csv_writer.writerow([item])

    media = set()
    with open(os.path.join(ROOT_DIR, "media_rhys.csv"), 'r') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            if len(row) > 1:
                if row[1] == "TRUE":
                    media.add(row[0].removeprefix(" '"))
                    print("""
rsync -rltDv --no-perms --no-owner --no-group --info=progress2 --size-only --include="*/" --include="*.mkv" --exclude="*" "{}/" "/media/usbdrive/Shows/{}/"
                    """.format(row[0].removeprefix(" '").removesuffix("' "), row[0].split("/")[-1]).strip())
    print("du -sch {}".format(" ".join(f"'{m}'" for m in media)))
    print("du -sch {} | sort -nr".format(" ".join(f"'{m}'" for m in media)))
##############################################################################################################
    media = set()
    with open(os.path.join(ROOT_DIR, "media_rhys.csv"), 'r') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            if len(row) > 2:
                if row[2] == "TRUE":
                    media.add(row[0].removeprefix(" '").removesuffix("'"))
    print("""
rsync -rltDv --no-perms --no-owner --no-group --info=progress2 --size-only \\
  --include="*/" \\
  --include="*.mkv" \\
  --exclude="*" \\
{}  "/media/usbdrive/Movies"
                    """.format(" ".join(f"    '{m}' \\\n" for m in media)).strip())
    print("du -sch {}".format(" ".join(f"'{m}'" for m in media)))
    print("du -sch {} | sort -nr".format(" ".join(f"'{m}'" for m in media)))
##############################################################################################################
    media = set()
    with open(os.path.join(ROOT_DIR, "media_rhys.csv"), 'r') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            if len(row) > 3:
                if row[3] == "TRUE":
                    media.add(row[0].removeprefix(" '").removesuffix("'"))
    print("""
rsync -rltDv --no-perms --no-owner --no-group --info=progress2 --size-only \\
  --include="*/" \\
  --include="*.mkv" \\
  --exclude="*" \\
{}  "/media/usbdrive/Kids"
                    """.format(" ".join(f"    '{m}' \\\n" for m in media)).strip())
    print("du -sch {}".format(" ".join(f"'{m}'" for m in media)))
    print("du -sch {} | sort -nr".format(" ".join(f"'{m}'" for m in media)))
##############################################################################################################
    media = set()
    with open(os.path.join(ROOT_DIR, "media_rhys.csv"), 'r') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            if len(row) > 4:
                if row[4] == "TRUE":
                    media.add(row[0].removeprefix(" '").removesuffix("'"))
    print("""
rsync -rltDv --no-perms --no-owner --no-group --info=progress2 --size-only \\
  --include="*/" \\
  --include="*.mkv" \\
  --exclude="*" \\
{}  "/media/usbdrive/Comedy"
                    """.format(" ".join(f"    '{m}' \\\n" for m in media)).strip())
    print("du -sch {}".format(" ".join(f"'{m}'" for m in media)))
    print("du -sch {} | sort -nr".format(" ".join(f"'{m}'" for m in media)))
##############################################################################################################
    media = set()
    with open(os.path.join(ROOT_DIR, "media_rhys.csv"), 'r') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            if len(row) > 5:
                if row[5] == "TRUE":
                    media.add(row[0].removeprefix(" '"))
                    print("""
rsync -rltDv --no-perms --no-owner --no-group --info=progress2 --size-only --include="*/" --include="*.mkv" --exclude="*" "{}/" "/media/usbdrive/Comedy/{}/"
                    """.format(row[0].removeprefix(" '").removesuffix("' "), row[0].split("/")[-1]).strip())
    print("du -sch {}".format(" ".join(f"'{m}'" for m in media)))
    print("du -sch {} | sort -nr".format(" ".join(f"'{m}'" for m in media)))
##############################################################################################################
    media = set()
    with open(os.path.join(ROOT_DIR, "media_rhys.csv"), 'r') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            if len(row) > 6:
                if row[6] == "TRUE":
                    media.add(row[0].removeprefix(" '").removesuffix("'"))
    print("""
rsync -rltDv --no-perms --no-owner --no-group --info=progress2 --size-only \\
  --include="*/" \\
  --include="*.mkv" \\
  --exclude="*" \\
{}  "/media/usbdrive/Docos"
                    """.format(" ".join(f"    '{m}' \\\n" for m in media)).strip())
    print("du -sch {}".format(" ".join(f"'{m}'" for m in media)))
    print("du -sch {} | sort -nr".format(" ".join(f"'{m}'" for m in media)))
##############################################################################################################
    media = set()
    with open(os.path.join(ROOT_DIR, "media_rhys.csv"), 'r') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            if len(row) > 7:
                if row[7] == "TRUE":
                    media.add(row[0].removeprefix(" '"))
                    print("""
rsync -rltDv --no-perms --no-owner --no-group --info=progress2 --size-only --include="*/" --include="*.mkv" --exclude="*" "{}/" "/media/usbdrive/Shows/{}/"
                    """.format(row[0].removeprefix(" '").removesuffix("' "), row[0].split("/")[-1]).strip())
    print("du -sch {}".format(" ".join(f"'{m}'" for m in media)))
    print("du -sch {} | sort -nr".format(" ".join(f"'{m}'" for m in media)))
##############################################################################################################
    media = set()
    with open(os.path.join(ROOT_DIR, "media_rhys.csv"), 'r') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            if len(row) > 8:
                if row[8] == "TRUE":
                    media.add(row[0].removeprefix(" '"))
                    print("""
rsync -rltDv --no-perms --no-owner --no-group --info=progress2 --size-only --include="*/" --include="*.mkv" --exclude="*" "{}/" "/media/usbdrive/Shows/{}/"
                    """.format(row[0].removeprefix(" '").removesuffix("' "), row[0].split("/")[-1]).strip())
    print("du -sch {}".format(" ".join(f"'{m}'" for m in media)))
    print("du -sch {} | sort -nr".format(" ".join(f"'{m}'" for m in media)))

# make sure MacOS mounts
# Rearrange docos/shows into shows
# Label drives
# clean up temp files (failed rsync's), empty dirs
