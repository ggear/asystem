# cli

Collapse the 21 `media-*.sh` wrappers and the three shell fragments under `bin/lib/` into a single
`bin/media.sh`, linked once per host as `amedia`. **planned** — nothing here is in the repo yet.
Status vocabulary: **built** is in the repo today, **planned** is not, **ruled out** was considered
and rejected on the evidence recorded beside it.

## Why

`src/main/resources/bin/` holds 21 entry points totalling 590 lines, of which 200 are nine files
whose only distinguishing content is a single filename in a `SCRIPT_NAME=` string, wrapped in the
same 20-line scope dispatch. The repetition is not just bulk — it is where the bugs are, because a fix
applied to one copy reaches none of the others (see "Defects the copies are hiding").

Counted by shape:

| Shape | Scripts | Lines | What varies between them |
|---|---|---|---|
| A — run the generated per-file action scripts | `rename` `check` `merge` `upscale` `transcode` `reformat` `downscale` | 160 | `SCRIPT_NAME` only — nothing else |
| B — run a `lib/` script against a working directory | `clean` `normalise` | 40 | `SCRIPT_NAME` only |
| C — run one of the `lib/*.py` entry points | `analyse` `force` `truncate` `refresh` `ingress` | 76 | the python file and its arguments |
| D — host utilities | `space` `mount` `find` `move` `metadata` `home` `process` | 314 | genuinely different work |

Shape A is seven identical files whose one variable is already derivable: it is exactly
`FileAction.script` for the actions that carry one, which `lib/clean.sh` already reads out of
`analyse.py`. Shape B is two more. So nine of the 21 scripts contain no information at all.

## Design

### One file, one entry point

```
src/main/resources/bin/
  media.sh          the single entry point, ~400 lines
  .env_media        unchanged — still sourced by media.sh and by every generated script
  lib/
    analyse.py  ingress.py  refresh.py      generated from src/main/python/media/ (unchanged)
    other-transcode.rb                      vendored (unchanged)
    history.sh                              scrapbook, never executed (unchanged)
```

`lib/clean.sh`, `lib/normalise.sh` and `lib/ingress.sh` (148 lines) **collapse into `media.sh`** as
functions. They are only ever reached through a wrapper or through a generated script, so nothing
loses an entry point, and both of their callers become the one CLI.

Everything inline, no sourced fragments — `move`'s 161 lines included. The house precedent is
`src/all/supervisor/src/main/resources/image/backup.sh` at 1849 lines in one file; a `media.sh` of
~400 is not the size that justifies splitting, and a sourced fragment would reintroduce the "which
file is the entry point" question this change exists to answer.

### The CLI

Modelled on `backup.sh`: the command always comes first, the one positional after it is that
command's single argument, options are flags, and **help is the default** so a naked `amedia`
explains itself rather than starting a multi-hour transcode nobody asked for.

```
Usage: amedia [command] [argument] [options]

  Pipeline
    process              normalise, analyse, run every action, analyse again, report space
    analyse              probe the library and regenerate the action scripts
    force                re-analyse this media file directory, ignoring its cached metadata

  Actions                run the scripts analyse generated, generating them first if absent
    rename               apply the canonical library naming
    check                verify streams, languages and subtitles
    merge                merge the parts of a split title
    upscale              raise resolution to the target spec
    transcode            re-encode to the target quality and channels
    reformat             remux without re-encoding
    downscale            lower resolution to the target spec

  Library
    clean      [dir]     delete generated metadata and action scripts
    normalise  [dir]     fix ownership, modes and strip junk files
    ingress    [dir]     import the usb drive and finished downloads
    move       [dest]    relocate this directory to another scope, or rsync it to another share
    refresh              reconcile library paths into Plex and trigger a scan
    truncate             trim the history held in the Google Sheet

  Inspect
    find       <token>   print a cd for every library directory matching a token
    metadata             print this directory's probed metadata and its defaults spec
    space                print share usage
    mount                mount the remote shares, Darwin only
    home                 print the install bin directory
    help                 this text, and the default command

  --quiet | --verbose    verbosity handed to analyse and to the generated scripts
  --share <index>        one share only, rather than the scope $PWD implies
```

Exit codes are `0` done, `1` work failed, `2` the command line was wrong — a refusal prints the
reason then the usage on stderr, `help` prints it on stdout, exactly as `backup.sh` does.

`--share` is new and is the one capability the wrappers never had: scope is currently derivable only
from `$PWD`, so operating on share 11 from anywhere else means `cd`-ing there first.

### Scope, resolved once

The 20-line `if SHARE_DIR_MEDIA / elif SHARE_DIR / else loop SHARE_DIRS_LOCAL` block copied through
eleven scripts becomes one resolution at startup, against `$PWD`, `.env_media` and `--share`:

| Scope | When | What a command operates on |
|---|---|---|
| `file` | `$PWD` is a movies/series file directory | `$PWD`, one title |
| `media` | `$PWD` is inside a `<share>/media` tree | `$PWD` |
| `share` | `$PWD` is inside a share root | `<share>/media` |
| `local` | anywhere else | every directory in `SHARE_DIRS_LOCAL` |

and two dispatchers, one per shape:

- `dispatch_action <verb>` (shape A) — `media` scope runs `${FIND_CMD} . -name <verb>.sh -exec {} \;`;
  `share` and `local` run each share's `tmp/scripts/media/<verb>.sh`, calling `command_analyse` first
  when it is absent.
- `dispatch_library <verb> [dir]` (shape B) — an explicit `dir` wins; otherwise `media` scope runs the
  function against `$PWD`, and `share`/`local` prefer the share's generated script and fall back to the
  function.

Shape A's whole body is then `dispatch_action "${1}"`, so the seven scripts become **zero** lines:
they are entries in the action list, nothing more.

### The action list is a mirrored vocabulary

`FileAction` in `src/main/python/media/analyse.py` **owns** the set of actions — it already drives
which per-file scripts are written and which survive a clean. `media.sh` declares the mirror

```bash
MEDIA_ACTIONS=(rename check merge upscale transcode reformat downscale)
```

with a comment naming `analyse.py`'s `MEDIA_FILE_SCRIPTS` as the owner, and `unit_test.py` asserts
the two sets are equal, failing loudly if either parse finds nothing. That is the repo's standing
rule for a vocabulary crossing a language boundary that cannot share symbols, and the same shape as
supervisor's `BACKUP_STATE_*` against `metric.BackupState*`.

**Ruled out: deriving the list at runtime**, which is what `lib/clean.sh` does today via
`python -c "from analyse import MEDIA_FILE_SCRIPTS"`. It is genuinely drift-free, but it costs a
measured **0.48 s** of interpreter and polars import on every invocation — paid by `clean`, by every
`process` run, and by `help`, which has to enumerate the actions to print them. A build-time test
buys the same guarantee for nothing at runtime, and it lets `clean` drop the subprocess it pays now.

### Shared machinery, declared once

Beyond scope, these exist in most copies and become one function each: the `ROOT_DIR` +
`. .env_media` preamble; the `RESULT=0 … || RESULT=1 … exit ${RESULT}` accumulator (a `run()`, which
`lib/normalise.sh` already has); the "regenerate via analyse when the script is absent" guard; the
"am I in a media file root" test (`force` and `metadata` carry identical four-line copies); and the
`echo -n "…ing [dir] … " / done|failed` progress idiom.

Messages move to the repo's `[$VAR]` bracket convention throughout — `move.sh` already writes
`[${share_dest}]`, while `clean.sh` and `normalise.sh` write `'${WORKING_DIR}'`, and no two of the 21
agree.

`set -uo pipefail`, as `backup.sh` has it, and not `set -e`: the accumulate-a-result idiom is the
house pattern here, and `.env_media` is a file of `[[ … ]] && …` chains whose last line returns 1,
which `set -e` would turn into a failed source.

## Install and migration

`install.sh` currently links every `bin/*.sh` by its basename:

```bash
for SCRIPT in ".../bin/"*.sh; do
  rm -rf "/usr/local/bin/$(basename "${SCRIPT}" .sh)"
  ln -vs "${SCRIPT}" "/usr/local/bin/$(basename "${SCRIPT}" .sh)"
done
```

That loop goes, because the link name and the file name now differ:

```bash
# NOTES: Remove once every host has been released past the media-* links, one release after this one
for LINK in "/usr/local/bin/media-"*; do
  [ -L "${LINK}" ] && rm -vf "${LINK}"
done
ln -vfns ".../bin/media.sh" "/usr/local/bin/amedia"
```

`ln -fns` replaces whatever is there, link or not, without following an existing symlink into a
directory — so a reinstall and an upgrade are the same line, and no `rm` of the new link is needed.
The `media-*` sweep is the transitional half: it is guarded on `-L` so the no-match literal is
skipped, it cannot touch `/usr/local/bin/other-transcode`, and it **is deleted in the release after
the one that ships it**, when no host can still be carrying an old link. Nothing else in `install.sh`
changes.

### Callers outside `bin/`

Four things name the old commands and move with them:

1. **`deploy.sh`** — `COMMANDS_SINGLETON` / `COMMANDS_ALL_HOSTS` become verbs, and the ssh line calls
   `${BIN_DIR}/media.sh <verb>`. It already runs by path rather than through the link, so it never
   depends on the migration having reached that host.
2. **`analyse.py`'s generated script headers** — five `$(media-home)` uses, two
   `$(media-home)/../shares.csv`, and `$(media-home)/lib/{clean,normalise}.sh`, which become
   `$(amedia home)` and `amedia clean "${SHARE_DIR}"` / `amedia normalise "${SHARE_DIR}"`. This is why
   the library verbs take an optional explicit directory: it is the generated scripts' entry point.
   The already-written copies under `<share>/tmp/scripts/media/` still say `media-home`, and are
   covered — `install.sh` `rm -rf`s `${SHARE_DIR}/tmp/scripts` on every server host on every install,
   and the client Macs see those same trees over SMB — but the first `amedia analyse` after the
   release is what rewrites them, so run it before anything else.
3. **`media-space.sh` calling `media-mount`** — an internal function call.
4. **`lib/history.sh`** — one scrapbook line mentioning `media-reformat`, cosmetic.

`src/main/python/media/syncart.py` is a plan carried in a docstring that proposes a 22nd wrapper,
`media-syncart.sh`, and copies "the three branches from media-analyse.sh" by name. Retarget it to
`amedia syncart`: under this design it is one entry in the command table and one function, and it
inherits the scope dispatch instead of copying it.

## Defects the copies are hiding

Found while reading the 21 scripts, all of them fixed by construction once there is one copy:

- **The shape A share loop tests the wrong variable.** All seven scripts run
  `[[ ! -f "${SHARE_DIR}/${SCRIPT_FILE}" ]] && { media-analyse …; }` *inside* the
  `for _SHARE_DIR in ${SHARE_DIRS_LOCAL}` loop, where `SHARE_DIR` is empty by definition of that
  branch. So the test is against `/tmp/scripts/media/<verb>.sh`, which never exists, and a full-estate
  `amedia transcode` re-runs `analyse` once per share and then runs a script it never checked for.
- **`media-truncate.sh` hardcodes the production sheet GUID** rather than reading
  `${MEDIA_GOOGLE_SHEET_GUID}`, so running it from a dev checkout writes the production history sheet
  — the exec/test override in `.env_exec` cannot reach it.
- **Shape A's `SCRIPT_PATH="${ROOT_DIR}/lib/<verb>.sh"` is dead in all seven** — no such file has ever
  existed in `lib/`.
- **`media-space.sh` propagates no result** (no `RESULT`, no `exit`) and its awk totals block is
  entirely commented out.
- **The wrappers call each other by link name** (`media-analyse`, `media-clean`, `media-mount`), so
  they only work through `/usr/local/bin` and not from a source checkout; these all become function
  calls.

## Verification

There is no lint or typecheck gate on this module (no `pyproject.toml`, no `pyrightconfig.json`), so
the checks are explicit:

1. `shellcheck src/main/resources/bin/media.sh` clean, with any genuine false positive suppressed by
   a bare, narrowly-scoped `# shellcheck disable=SCxxxx`.
2. `amedia` with no arguments, `amedia help`, `amedia bogus` and `amedia transcode --bogus` —
   usage on stdout, usage on stdout, refusal plus usage on stderr with exit 2, likewise.
3. Each of the four scopes for one shape A and one shape B verb, in a `target/runtime-unit/` fixture
   tree: a media directory, a share root, an arbitrary directory, and `--share`.
4. `fab ut` from `src/test/python/unit` — the existing suite executes the generated action scripts,
   so it covers the `$(amedia home)` rewrite in `analyse.py`; add the `MEDIA_ACTIONS` equality
   assertion here.
5. `fab generate` in this module, and confirm `bin/lib/{ingress,analyse,refresh}.py` come back
   byte-identical apart from the intended `$(amedia home)` lines.
6. On one server host after release, `amedia analyse` first, then `amedia space` and `amedia process`,
   and confirm `/usr/local/bin` holds `amedia` and no `media-*`.

## Expected outcome

21 entry points plus three `lib/` fragments, 738 lines, become one script of roughly 400 with one
command table, one scope resolver, two dispatchers and no duplicated branch — and adding an action
becomes an entry in `FileAction`, with no shell edit at all.
