import csv
import os

if __name__ == "__main__":
    media_dirs = {}
    with open(os.path.join(os.path.dirname(__file__), "download", "media.csv"), 'r') as file:
        csv_reader = csv.reader(file)
        for row_dir in csv_reader:
            if row_dir[0].startswith(" '"):
                media_dir = row_dir[0].removeprefix(" '").removesuffix("'").replace('"', '\\"')
                if "/Season " in media_dir:
                    media_dir = media_dir.split("/Season ")[0]
                _, _, _, _, media_scope, media_type, *_ = media_dir.split("/")
                media_library = f"{media_scope}_{media_type}".lower()
                if media_library not in media_dirs:
                    media_dirs[media_library] = set([media_dir])
                else:
                    media_dirs[media_library].add(media_dir)
    for media_library, media_dirs in media_dirs.items():
        media_path = os.path.join(os.path.dirname(__file__), "filtered", f"media_{media_library}.csv")
        if not os.path.exists(media_path):
            with open(media_path, 'w') as file:
                csv_writer = csv.writer(file)
                csv_writer.writerow(["Directory", "Copy"])
                for media_dir in sorted(media_dirs):
                    csv_writer.writerow(
                        [media_dir, ""])
    media_dirs = {}
    for media_filename in os.listdir(os.path.join(os.path.dirname(__file__), "filtered")):
        if media_filename.startswith("media_") and media_filename.endswith(".csv"):
            _, media_scope, media_type = media_filename.split(".")[0].split("_")
            with open(os.path.join(os.path.dirname(__file__), "filtered", media_filename), 'r') as file:
                csv_reader = csv.reader(file)
                for row_dir in csv_reader:
                    if len(row_dir) > 1:
                        if row_dir[1] == "TRUE":
                            _, _, media_share, *_ = row_dir[0].split("/")
                            media_share = media_share[0]
                            if media_share not in media_dirs:
                                media_dirs[media_share] = [row_dir[0]]
                            else:
                                media_dirs[media_share].append(row_dir[0])
    for media_share in media_dirs:
        if media_dirs[media_share]:
            media_path = os.path.join(os.path.dirname(__file__), "programs",
                                      f"media_{media_share}.sh")
            with open(media_path, 'w') as file:
                file.write("#!/bin/bash\n\n")

                file.write("""
du -hsc --exclude='*__LARGE.mkv' \\
  {} | grep total
                """.format("  ".join(f"'{m}' \\\n" for m in media_dirs[media_share])).strip() + "\n")
                for media_dir in media_dirs[media_share]:
                    media_name = media_dir.split("/")[-1]
                    _, _, _, _, media_scope, media_type, *_ = media_dir.split("/")
                    file.write(f"""
mkdir -p '/media/usbdrive/{media_scope.title()} {media_type.title()}/{media_name}'
rsync -rltDv --no-perms --no-owner --no-group --info=progress2 --size-only \\
  --include='*/' \\
  --exclude='*__LARGE.mkv' \\
  --include='*.mkv' \\
  --exclude='*' '{media_dir}/' \\
  '/media/usbdrive/{media_scope.title()} {media_type.title()}/{media_name}/'
                            """.strip() + "\n")
                file.write(f"""
find '/media/usbdrive' -type d -empty -delete
find '/media/usbdrive' -type f -name '.*' -delete
                        """)
    parents_serieses = []
    with open(os.path.join(os.path.dirname(__file__), "filtered", "media_parents_series.csv"), 'r') as file:
        csv_reader = csv.reader(file)
        for row_dir in csv_reader:
            if len(row_dir) > 1:
                if row_dir[1] == "TRUE":
                    parents_serieses.append(row_dir[0].split("/")[-1])
    for parent_series in sorted(parents_serieses):
        print(parent_series)
