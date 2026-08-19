r"""
WARNING: Not implemented, this module is a plan only.

Seed Plex's own artwork onto disk as local assets, so every media directory carries the poster and
background Plex already displays, sized for a 4K 80" panel. All figures below were measured against
production Plex.

Why Plex is the source
    Matching a file to a title is the hard part and Plex has already done it for all 11,227 files
    (plex://movie/... guids). Going direct to TMDB/TVDB means re-solving matching and producing
    artwork that sometimes disagrees with what Plex shows, and since local assets override the
    agent, a wrong poster becomes permanently sticky. Taking the selected asset (item.thumbUrl /
    item.artUrl) guarantees seeding introduces zero visual change. Confirmed prerequisite:
    useLocalAssets is True on all 8 sections, 11 locations each.

Scope
    In      movie poster + background, show poster + background, season poster
    Out     episode thumbnails, collections, themes, clearlogos, candidate re-selection

    Episode thumbnails are deliberately excluded. refresh.py already calls section.analyze(), which
    generates them from the video itself, which both matches the file after analyse.py has
    transcoded it and avoids ~10k tiny downloads.

Storage layout
    movie       <film dir>/poster.jpg, <film dir>/fanart.jpg
    show        <show dir>/poster.jpg, <show dir>/fanart.jpg
    season      <show dir>/Season <n>/poster.jpg      (seasons are not zero padded on disk)

    Only these three names are valid, anything else is a naming fault handled by the validators.

Quality
    Measured sources vary from 960x1440 to 2000x3000 (poster) and 1920x1080 to 3840x2160 (art), at
    up to 3MB. So cap, do not force: fetch through the Plex photo transcoder with upscale=0 capped
    at 2000x3000 and 3840x2160. Native sources come down untouched, nothing is upscaled, because
    inflating a 960x1440 poster adds bytes and no detail. The transcoder still earns its place on
    size, measured 734KB to 187KB and 912KB to 314KB at 1000x1500.

    Report low resolution sources rather than upscaling them. A poster under ~1400px wide means a
    better candidate probably exists, items carry 9 to 113 of them. Fixing one is
    next(x for x in show.posters() if ...).select(), a human decision.

    Provider consistency needs no work, agent tv.plex.agents.series already selects tmdb on every
    show sampled, and provider approximates aspect ratio.

    Estimate ~3,000 poster bearing items x ~1.2MB ~= 3.5GB, confirm with --dry-run.

FileAction.SYNCART
    __order__ = 'RENAME CHECK MERGE UPSCALE TRANSCODE REFORMAT DOWNSCALE SYNCART NOTHING'
    SYNCART = True

    Placed last in the when/then chain, immediately before .otherwise(NOTHING), so artwork is only
    fetched once a file is settled in its final name, location and format and no poster is
    downloaded into a directory rename.sh is about to move. FileAction is a next-action classifier
    and media-process.sh re-analyses between phases, so a file needing both a transcode and a poster
    gets TRANSCODE now and SYNCART on the following pass.

    Only one label renumbers, SYNCART = 8 and NOTHING 8 -> 9. MEDIA_FILE_SCRIPTS picks up
    syncart.sh automatically from has_script. clean.sh derives that list at runtime from the shipped
    analyse.py, so cleanup needs no second edit. The list is load-bearing in both directions:
    <share>/tmp/scripts/media/ holds a wrapper per name and a .lib/<name>.sh aggregate, and
    analyse/clean/normalise survive a clean only because they are absent from MEDIA_FILE_SCRIPTS.
    Never replace it with a path glob, that would delete the running clean.sh.

analyse.py additions
    Artwork state is enriched, never persisted. ._metadata_<stem>_<ext>.yaml is a write-once cache,
    written only when absent and refreshed only by clean.sh deleting it, so persisting artwork state
    would be stale the moment syncart.py runs and refreshing it would mean re-ffprobing the library.
    Presence is a stat(), so it goes in via the existing _add_field, recomputed every run, and still
    reaches the Google Sheet because the sheet is written from the enriched dataframe.

        artwork_status      Ok | Missing | Unavailable | Invalid
        artwork_expected    asset paths this row implies (movie own dir, episode show and season)
        artwork_missing     expected paths that do not exist
        artwork_invalid     wrongly named artwork found nearby

    SYNCART appears in #metadata-summary like any other action. A #syncart-summary block after it
    itemises every Unavailable and Invalid row as a cd <dir> list, the way rename requirements are
    reported, because those are errors requiring human action.

Naming validators
    wrong name          folder.jpg, cover.jpg, <film>-poster.jpg     emit mv into existing rename.sh
    wrong location      season poster in the show dir                emit mv into existing rename.sh
    wrong extension     poster.png beside a valid poster.jpg         report Invalid, never delete

    Misnamed artwork is repaired through the existing rename mechanism and appears in the existing
    rename section, keeping one repair channel for "a file is in the wrong place". The syncart
    section reports only absence.

syncart.py
    Shipped like analyse.py and refresh.py via the generate.sh concatenation loop, landing in
    bin/lib/syncart.py. Reads ._metadata_* recursively under the invoking scope, so it never walks
    media files itself and never runs ffprobe.

    Blocking until Plex is idle. A preceding media-refresh triggers a scan plus agent metadata
    fetches, both asynchronous, since section.update() returns when the request is accepted, not
    when the scan completes. Downloading mid-flight would write 0 byte sentinels for items that were
    about to be fine. section.refreshing is a trap, it is False before a scan starts, so wait on
    server.activities draining and staying drained, which absorbs the gap between scan end and agent
    work starting:

        def _wait_plex_idle(_plex_server, _timeout=1800, _settle=15, _interval=5):
            deadline = time.time() + _timeout
            idle_since = None
            while time.time() < deadline:
                if _plex_server.activities:
                    idle_since = None
                elif idle_since is None:
                    idle_since = time.time()
                elif time.time() - idle_since >= _settle:
                    return True
                time.sleep(_interval)
            return False

    The deadline is mandatory, an item Plex cannot match never acquires artwork and would spin
    forever. On timeout log and continue, the sentinel already reports the outcome. Note /activities
    is modelled by plexapi but is not a documented API, the per-item thumb/art check is the durable
    fallback.

    Finding the items. Do not re-derive library names from paths, let Plex report its own locations
    and prefix match in both directions, which is depth agnostic and reuses the SHARE_ROOT to /share
    mapping refresh.py pinned down:

        target = "/share" + directory.removeprefix(share_root)

        for section in plex_server.library.sections():
            if not any(loc.startswith(target) or target.startswith(loc)
                       for loc in section.locations):
                continue
            for item in section.all():
                ...match on item.locations[0].startswith(target)...

    loc.startswith(target) catches "target is above" (/share/10 -> all its libraries),
    target.startswith(loc) catches "target is below" (a single film directory).

    Optimal download. Measured section.all() is 76 items in 0.2s with locations already populated
    and no per-item reload, show.seasons() is 0.02s. So one section.all() per in-scope section, 8
    calls maximum rather than 11,227; show.seasons() only for shows with a missing season poster; no
    show.episodes() at all; build a plex_path to item dict once and join against artwork_expected;
    download through the photo transcoder on a 4 to 8 worker pool. Self-verifying, if not exists
    then download, never keyed off analyse's output state, so an interrupted run resumes exactly
    where it stopped.

    The 0 byte sentinel. Where Plex has no artwork, unmatched (local:// guid) or the agent found
    nothing, write the asset path as a 0 byte file. analyse.py reads 0 bytes as Unavailable and
    reports it. syncart.py retries 0 byte files every run, since the retry costs one dict lookup
    against a section listing it already holds, so fixing the match in Plex and re-running heals it
    automatically with no state file. A 0 byte poster.jpg is inert to Plex so it cannot corrupt the
    library.

    Both cleanup scripts were checked and neither deletes the assets or the sentinels. clean.sh
    removes only named patterns and empty directories. normalise.sh removes nohup, .DS_Store and
    files matching .*/\.[^/]*\.[A-Za-z0-9]{6}$, which requires a leading dot and a six alphanumeric
    suffix, so poster.jpg and fanart.jpg never match. normalise.sh does set non-.sh files to
    640 graham:users on Linux, which the Plex container reads fine as PUID/PGID 0, but syncart.py
    should still call _set_permissions on write.

    Reclaiming Plex's copy. Once an asset is seeded, Plex's own downloaded copy in its metadata
    bundles is redundant, since useLocalAssets makes the local file win. Reclaim it through the
    supported mechanism only, never by deleting files under the Plex config volume: there is no API
    for that, it is unsupported and would risk a full re-scan and re-match of 11k items, and the
    media module has no access to plex's SERVICE_DATA_DIR in any case (different module, different
    host). Plex's butler tasks are the supported route and all three are already enabled on the
    server:

        plex_server.runButlerTask("CleanOldBundles")       stale artwork/metadata bundles
        plex_server.runButlerTask("CleanOldCacheFiles")    Cache/PhotoTranscoder renditions
        plex_server.runButlerTask("GarbageCollectBlobs")   orphaned artwork blobs

    Run them behind --reclaim, only at the end of a run that actually downloaded something, since
    they are heavy background jobs and forcing them outside Plex's own window competes with
    transcoding on the same box. They are asynchronous, so returning does not mean space is freed.

    The premise must be measured before this is trusted. Seeding does not obviously reduce total
    bytes: Plex still needs a rendition to serve clients and will transcode the local poster.jpg
    into its cache, so the likely outcome is not "reclaim" but a shift of roughly 3 to 9GB out of
    the Plex config volume onto the shares, against the ~3.5GB the assets add. That is worth doing
    only if the config volume is the constrained one. Note the 9 to 113 poster candidates per item
    are mostly remote URLs rather than stored files, so only the selected asset is reclaimable per
    item. Measure the config volume before and after a bounded --limit run on one library.

    Flags
        --dry-run   report counts and bytes, write nothing, use for the first pass
        --limit N   stop after N downloads, the real pacing knob for 11k files
        --force     re-download even when the asset exists
        --no-wait   skip the idle wait for interactive use
        --reclaim   run the butler cleanup tasks after a run that downloaded something

    --limit matters more than directory scoping for rollout, because the script is self-verifying
    media-syncart --limit 500 can be run repeatedly from the top and resumes each time. Directory
    scoping is the targeting tool, not the pacing tool.

media-syncart.sh
    _write_scripts already emits a global aggregate per action at <share>/tmp/scripts/media/, so
    adding SYNCART wires syncart.sh in automatically alongside downscale.sh. One deliberate
    departure: the other actions also emit one local script per file, which for syncart would mean
    11k Python interpreter starts each opening its own Plex connection. Instead the global
    syncart.sh makes a single syncart.py call scoped to the share and no per-file locals are
    emitted.

    Verb dispatch copies the three branches from media-analyse.sh. .env_media sets SHARE_DIR_MEDIA
    with a glob and the verb passes "${PWD}" through, so arbitrary depth scoping works with no new
    machinery: a single film dir, a scope/type dir, a share (-> <share>/media), or every entry in
    SHARE_DIRS_LOCAL.

    The clean/analyse bookend. analyse without clean is already the "ensure metadata exists"
    primitive, since the YAML is written only when absent, so a bare analyse creates what is missing
    and ffprobes only new files. clean is what forces a full re-probe, which is why media-analyse.sh
    only cleans in the deep branch.

        inside media/...      before: clean + analyse (bounded)   after: analyse, no clean
        share root / global   before: analyse, no clean           after: analyse, no clean

    That is one ffprobe pass and two stat passes. A second clean would cost two ffprobe passes to
    refresh what is only a stat(), and a clean at share root or global scope would delete the whole
    library's metadata cache and re-probe 11,227 files. The closing analyse should be conditional on
    syncart.py having downloaded anything, since most re-runs over a seeded library are no-ops.
    Global scope still gets it, so a full run does not leave every row reading Missing in the sheet.

Ordering
    Seeded artwork is invisible until Plex rescans, and once it rescans the local file wins
    permanently. syncart must also run after Plex has fetched agent artwork, which is what refresh
    triggers. So syncart goes after refresh and blocks until Plex is idle:

        normalise -> analyse -> rename -> check -> upscale -> reformat -> transcode -> downscale
                  -> analyse -> refresh -> syncart -> analyse -> space

    media-refresh is currently only in deploy.sh, not media-process.sh, and must be added there for
    syncart to have anything to collect. Rollback is symmetrical, delete the local assets and
    rescan.

Phases
    1   analyse.py artwork fields, FileAction.SYNCART, #syncart-summary, report only
    2   syncart.py and media-syncart.sh, --dry-run only
    3   downloads enabled, --limit, transcoder sizing
    4   idle wait
    5   0 byte sentinel and Unavailable reporting
    6   naming validators into rename.sh
    7   roll out with --limit, then wire into media-process.sh
    8   --reclaim, measured before and after on one library

    Phases 1 and 2 write nothing to the media tree and are safe to land independently. Phase 8 is
    conditional on its measurement showing a real gain.

Open questions
    1   Auto-rename misnamed artwork, or report only for the first pass?
    2   Season posters, seed them or let seasons inherit the show poster as Plex does by default?
    3   Is a network dependent, blocking step acceptable inside media-process.sh?
    4   --limit semantics across shares at global scope, N per share or N total?
    5   MEDIA_FILE_EXTENSIONS_IGNORE already contains png/jpg/jpeg so artwork files are skipped by
        the walk today. The validators need them recognised before that skip, not removed from the
        ignore set, otherwise they would enter the dataframe as media rows.
"""
