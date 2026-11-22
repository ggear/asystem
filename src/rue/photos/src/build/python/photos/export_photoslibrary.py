import json
import os.path
import shutil
import string
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from os.path import abspath, dirname, expanduser, isdir, join, realpath

import osxphotos
import urllib3
from Foundation import NSIndexSet
from osxphotos import ExportOptions, PhotoExporter
from pathvalidate import sanitize_filepath

import Photos
from asystem import load_bootstrap_env

urllib3.disable_warnings()

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

DIR_PHOTOS_DB = "/Users/graham/Pictures/Photos Library.photoslibrary"

FOLDER_PUBLISHED = "Published"

PHOTOS_ACCESS_READ_WRITE = 2
PHOTOS_AUTHORIZED = 3

WIDTH_ALBUM = len("The Pi-rates of the~")
WIDTH_NAME = len("IMG_1996.HE~")


def reorder(current, target, move, read_back, label, apply):
    rank = {identifier: position for position, identifier in enumerate(target)}
    moves = 0
    while True:
        ranks = [rank[identifier] for identifier in current]
        best = [1] * len(ranks)
        previous = [-1] * len(ranks)
        for i in range(len(ranks)):
            for j in range(i):
                if ranks[j] < ranks[i] and best[j] + 1 > best[i]:
                    best[i] = best[j] + 1
                    previous[i] = j
        end = max(range(len(ranks)), key=lambda i: best[i])
        keep = set()
        while end != -1:
            keep.add(current[end])
            end = previous[end]
        misplaced = next((i for i in range(len(current)) if current[i] not in keep), None)
        if misplaced is None:
            return moves
        identifier = current[misplaced]
        remaining = [other for other in current if other != identifier]
        destination = 0
        for position, other in enumerate(remaining):
            if other in keep and rank[other] < rank[identifier]:
                destination = position + 1
        expected = list(remaining)
        expected.insert(destination, identifier)
        if apply:
            move(misplaced, destination)
            if read_back() != expected:
                sys.exit(f"Build generate script [photos] unexpected order after move label [{label}] from [{misplaced}] to [{destination}]")
        current = expected
        moves += 1


def fit(text, width):
    return f"{text if len(text) <= width else text[: width - 1] + '~':<{width}}"


if __name__ == "__main__":
    load_bootstrap_env(DIR_ROOT)

    if Photos.PHPhotoLibrary.authorizationStatusForAccessLevel_(PHOTOS_ACCESS_READ_WRITE) != PHOTOS_AUTHORIZED:
        sys.exit("Build generate script [photos] photos access not authorized")

    library = Photos.PHPhotoLibrary.sharedPhotoLibrary()
    top = Photos.PHCollectionList.fetchTopLevelUserCollectionsWithOptions_(None)
    folder = next(top.objectAtIndex_(i) for i in range(top.count()) if top.objectAtIndex_(i).localizedTitle() == FOLDER_PUBLISHED and isinstance(top.objectAtIndex_(i), Photos.PHCollectionList))
    fetch_options = Photos.PHFetchOptions.alloc().init()
    fetch_options.setIncludeHiddenAssets_(True)

    def read_assets(album):
        fetched = Photos.PHAsset.fetchAssetsInAssetCollection_options_(album, fetch_options)
        return [(fetched.objectAtIndex_(i).localIdentifier(), fetched.objectAtIndex_(i).creationDate().timeIntervalSince1970()) for i in range(fetched.count())]

    def read_albums():
        fetched = Photos.PHCollection.fetchCollectionsInCollectionList_options_(folder, None)
        return [fetched.objectAtIndex_(i) for i in range(fetched.count())]

    def perform(change, label):
        success, error = library.performChangesAndWait_error_(change, None)
        if not success:
            sys.exit(f"Build generate script [photos] move failed label [{label}] error [{error}]")

    published_albums = read_albums()
    titles = {album.localIdentifier(): album.localizedTitle() for album in published_albums}
    assets = {album.localIdentifier(): read_assets(album) for album in published_albums}
    dates = {identifier: min(date for _, date in album_assets) for identifier, album_assets in assets.items() if album_assets}
    ordered = [album.localIdentifier() for album in published_albums]
    album_target = sorted(ordered, key=lambda identifier: -dates.get(identifier, 0))
    photo_targets = {identifier: [asset for asset, _ in sorted(album_assets, key=lambda pair: pair[1])] for identifier, album_assets in assets.items() if album_assets}

    def photo_moves_for(album, apply):
        identifier = album.localIdentifier()

        def move(source, destination):
            def change():
                request = Photos.PHAssetCollectionChangeRequest.changeRequestForAssetCollection_(album)
                request.moveAssetsAtIndexes_toIndex_(NSIndexSet.indexSetWithIndex_(source), destination)

            perform(change, titles[identifier])

        return reorder([asset for asset, _ in assets[identifier]], photo_targets[identifier], move, lambda: [asset for asset, _ in read_assets(album)], titles[identifier], apply)

    def album_moves_for(apply):
        def move(source, destination):
            def change():
                request = Photos.PHCollectionListChangeRequest.changeRequestForCollectionList_(folder)
                request.moveChildCollectionsAtIndexes_toIndex_(NSIndexSet.indexSetWithIndex_(source), destination)

            perform(change, FOLDER_PUBLISHED)

        return reorder(ordered, album_target, move, lambda: [album.localIdentifier() for album in read_albums()], FOLDER_PUBLISHED, apply)

    planned_photos = {album.localIdentifier(): photo_moves_for(album, False) for album in published_albums if album.localIdentifier() in photo_targets}
    if album_moves_for(False) or any(planned_photos.values()):
        backup_path = expanduser(f"~/Backup/photos/published_order_{datetime.now(UTC):%Y%m%d_%H%M%S}.json")
        os.makedirs(dirname(backup_path), exist_ok=True)
        with open(backup_path, "w") as backup_file:
            json.dump({"albums": [{"id": identifier, "title": titles[identifier], "assets": [asset for asset, _ in assets[identifier]]} for identifier in ordered]}, backup_file, indent=1)
        print(f"Build generate script [photos] backup written [{backup_path}]")
        for album in published_albums:
            if planned_photos.get(album.localIdentifier()):
                print(
                    f"Build generate script [photos] album [{fit(titles[album.localIdentifier()], WIDTH_ALBUM)}] photos [{len(assets[album.localIdentifier()]):>5}] moves [{photo_moves_for(album, True):>5}]"
                )
        print(f"Build generate script [photos] folder [{FOLDER_PUBLISHED}] albums [{len(published_albums):>5}] moves [{album_moves_for(True):>5}]")
    else:
        print(f"Build generate script [photos] folder [{FOLDER_PUBLISHED}] albums [{len(published_albums):>5}] already ordered")

    export_root_path = join(DIR_ROOT, "../../../../../Backup/photos/photo_album_draft")

    def load_draft_albums():
        loaded_db = osxphotos.PhotosDB(expanduser(DIR_PHOTOS_DB))
        return loaded_db, [album for folder in loaded_db.folder_info if folder.title == "Draft" for album in folder.album_info]

    def is_not_downloaded(photo):
        return not photo.path or (photo.hasadjustments and not photo.path_edited)

    def not_downloaded(album):
        return [photo for photo in album.photos if not photo.intrash and is_not_downloaded(photo)]

    photos_db, draft_albums = load_draft_albums()
    movies = [f"[{photo.original_filename}] in album [{album.title}]" for album in draft_albums for photo in album.photos if not photo.intrash and photo.ismovie]
    if movies:
        raise Exception(f"Draft albums contain movies {movies}")
    pending = [photo for album in draft_albums for photo in not_downloaded(album)]
    if pending:
        with tempfile.TemporaryDirectory() as fetch_path:
            for fetch_index, photo in enumerate(pending, 1):
                fetch_info = PhotoExporter(photo).export(
                    fetch_path,
                    f"{photo.uuid}.jpg",
                    ExportOptions(jpeg_quality=0.0, convert_to_jpeg=True, edited=photo.hasadjustments, use_photokit=True, download_missing=True),
                )
                if fetch_info.error:
                    raise Exception(f"Fetch failed for [{photo.original_filename}] error [{fetch_info.error}]")
                print(f"Build generate script [photos] fetched [{fetch_index:>3}] of [{len(pending):>3}] image [{fit(photo.original_filename, WIDTH_NAME)}]")
                sys.stdout.flush()
        photos_db, draft_albums = load_draft_albums()
    not_downloaded_total = 0
    for album in draft_albums:
        album_photos = [photo for photo in album.photos if not photo.intrash]
        not_downloaded_count = len(not_downloaded(album))
        not_downloaded_total += not_downloaded_count
        print(
            f"Build generate script [photos] album [{fit(album.title, WIDTH_ALBUM)}] downloaded [{len(album_photos) - not_downloaded_count:>5}] not downloaded [{not_downloaded_count:>5}] total [{len(album_photos):>5}]"
        )
    library_photos = [photo for photo in photos_db.photos(movies=True) if not photo.intrash]
    library_not_downloaded = sum(1 for photo in library_photos if is_not_downloaded(photo))
    print(
        f"Build generate script [photos] album [{'*' * WIDTH_ALBUM}] downloaded [{len(library_photos) - library_not_downloaded:>5}] not downloaded [{library_not_downloaded:>5}] total [{len(library_photos):>5}]"
    )
    if not_downloaded_total:
        print(f"Build generate script [photos] aborted as originals not downloaded [{not_downloaded_total}]", file=sys.stderr)
        sys.exit(1)
    shutil.rmtree(export_root_path, ignore_errors=True)
    os.mkdir(export_root_path)
    for album in draft_albums:
        album_label = f"[{fit(album.title, WIDTH_ALBUM)}]"
        index = 1
        export_date = None
        for photo in album.photos:
            if photo.intrash:
                continue
            photo_label = f"[{fit(photo.original_filename, WIDTH_NAME)}]"
            album_name = sanitize_filepath(album.title, platform="auto").translate(str.maketrans("", "", string.punctuation)).replace(" ", "_").encode("ascii", "ignore").decode("UTF-8")
            export_path = abspath(join(export_root_path, album_name))
            if not isdir(export_path):
                os.makedirs(export_path)
            photo_name = f"{album_name}_{index:03d}.jpg"
            export_info = PhotoExporter(photo).export(
                export_path,
                photo_name,
                ExportOptions(update=True, location=True, persons=True, jpeg_quality=0.0, convert_to_jpeg=True, edited=photo.hasadjustments),
            )
            if not export_info.exported:
                raise Exception(
                    f"Image {photo_label} from album {album_label} not exported missing [{export_info.missing}] edited [{photo.hasadjustments}] path [{photo.path}] path_edited [{photo.path_edited}]"
                )
            exported_path = join(export_path, photo_name)
            if export_info.exported[0] != exported_path:
                if os.path.splitext(export_info.exported[0])[1].lower() not in (".jpg", ".jpeg"):
                    raise Exception(f"Exported file is not a jpeg [{export_info.exported[0]}] for [{photo.original_filename}] from album [{album.title}]")
                os.replace(export_info.exported[0], exported_path)
            if export_date is None:
                try:
                    export_date = datetime.strptime(
                        subprocess.run(["exiftool", "-T", "-DateTimeOriginal", exported_path], capture_output=True).stdout.decode("utf-8").strip().split(" ")[0], "%Y:%m:%d"
                    ).replace(tzinfo=UTC)
                except Exception as exception:
                    raise Exception(f"Could not parse original date time on file [{photo.original_filename}] from album [{album.title}]") from exception
            subprocess.run(
                [
                    "exiftool",
                    "-q",
                    "-wm",
                    "w",
                    "-m",
                    "-overwrite_original",
                    "-AllDates={} {:02d}:{:02d}:{:02d}".format(export_date.strftime("%Y:%m:%d"), 12 + int(index / 60), index % 60, 0),
                    exported_path,
                ]
            )
            index += 1
            print(f"Build generate script [photos] image {photo_label} from album {album_label} exported to [{photo_name}]")
            sys.stdout.flush()

            # TODO: Add document manual process -
            #  if DLSR: pause iCloud,
            #  import, create albums, delete unwanted photos, empty trash, export
            #  if DLSR: delete last import, empty trash, import new albums, unpause iCloud
            #  upload new albums to Google
            #  if DSLR or Janes Phone delete photos on device

    subprocess.run(["open", export_root_path])
