# cli

Collapse the 21 `media-*.sh` wrappers and the three shell fragments under `bin/lib/` into a single
`bin/media.sh`, linked once per host as `amedia`. **planned** — none of this is in the repo yet.
Status vocabulary: **built** is in the repo today, **planned** is not, **ruled out** was considered
and rejected on the evidence recorded beside it.

## Why

`src/main/resources/bin/` holds 21 entry points totalling 590 lines, of which 200 are nine files
whose only distinguishing content is a single filename in a `SCRIPT_NAME=` string, wrapped in the
same 20-line scope dispatch. Eleven scripts carry that dispatch. The repetition is not just bulk —
it is where the bugs are, because a fix applied to one copy reaches none of the others (see
"Defects the copies are hiding").

Counted by shape:

| Shape | Scripts | Lines | What varies between them |
|---|---|---|---|
| A — run the generated per-file action scripts | `rename` `check` `merge` `upscale` `transcode` `reformat` `downscale` | 160 | `SCRIPT_NAME` only — nothing else |
| B — run a `lib/` script against a working directory | `clean` `normalise` | 40 | `SCRIPT_NAME` only |
| C — run one of the `lib/*.py` entry points | `analyse` `force` `truncate` `refresh` `ingress` | 76 | the python file and its arguments |
| D — host utilities | `space` `mount` `find` `move` `metadata` `home` `process` | 314 | genuinely different work |

Shape A's one variable is already derivable: it is exactly `FileAction.script` for the actions that
carry one, which `lib/clean.sh` reads out of `analyse.py` today. Shape B is two more of the same. So
nine of the 21 scripts contain no information at all.

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
functions. Each is only ever reached through a wrapper or through a generated script, so nothing
loses an entry point and both callers become the one CLI.

Everything inline, no sourced fragments — `move`'s 161 lines included. The house precedent is
`src/all/supervisor/src/main/resources/image/backup.sh` at 1849 lines in one file; ~400 is not the
size that justifies splitting, and a sourced fragment reintroduces the "which file is the entry
point" question this change exists to answer.

### The CLI

Modelled on `backup.sh`: the command always comes first, the one positional after it is that
command's single argument, options are flags, and **help is the default** so a naked `amedia`
explains itself rather than starting a multi-hour transcode nobody asked for.

```
Usage: amedia [command] [argument] [options]

  Pipeline
    process            the full pipeline, normalise to space
    analyse            probe the library, write the scripts
    force              re-analyse this directory, ignoring cache

  Actions              run what analyse wrote, writing it if absent
    rename             apply the canonical naming
    check              verify streams and subtitles
    merge              merge a split title
    upscale            raise resolution to target
    transcode          re-encode to the target quality
    reformat           remux without re-encoding
    downscale          lower resolution to target

  Library
    clean     [dir]    delete generated metadata and scripts     (default: this scope)
    normalise [dir]    fix ownership and modes, strip junk       (default: this scope)
    ingress   [dir]    import the usb drive and downloads        (default: this share)
    stow      [scope]  file staged content into the library      (default: parents)
    move      <share>  copy to another share, drop the source    (required)
    refresh            reconcile paths into Plex and scan
    truncate           trim the Google Sheet history

  Inspect
    find      <token>  print a cd per matching directory         (required)
    metadata           print the local metadata and defaults
    space              print share usage
    mount              mount the remote shares, Darwin
    home               print the install bin directory
    help               this text                                 (default command)

  --verbose            one line per file                         (default: single share)
  --quiet              summaries only                            (default: every share)
  --share <index>      one share only                            (default: $PWD scope)
  --dry-run            print the move, change nothing            (default: off)
```

Exit codes are `0` done, `1` work failed, `2` the command line was wrong — a refusal prints the
reason then the usage on stderr, `help` prints it on stdout, exactly as `backup.sh` does.

Two defaults are stated in the usage because neither is a constant and no current wrapper documents
either. **Verbosity defaults on scope**: `media-analyse.sh` already passes `--verbose` from a media
directory or a share root and `--quiet` when it loops `SHARE_DIRS_LOCAL`, because one title's output
is worth reading and twelve shares' is not; the flags override in both directions. **`[dir]` means
"this scope", not `$PWD`**: the positional exists mainly for the generated scripts, which pass an
explicit share path.

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
  function against `$PWD`, and `share`/`local` prefer the share's generated script and fall back to
  the function.

Shape A's whole body is then `dispatch_action "${1}"`, so the seven scripts become **zero** lines:
they are entries in the action list, nothing more.

### `move` splits into `stow` and `move`

`media-move.sh` is two unrelated commands sharing one name, dispatched on
`! ${share_suffix} =~ ^media.*` — which directory you happen to be standing in decides both what the
argument means and how much damage a mistake does:

| | `stow` (was the mv workflow) | `move` (was the rsync workflow) |
|---|---|---|
| Where you must be | a share subdir **outside** `media/` | **inside** `media/`, ≥2 levels deep |
| Argument means | a scope — `parents`/`kids`/`docos`/`comedy` | a share index — `11` |
| Mechanism | local `mv -vn`, collision-renames `_1`/`_2`, prunes empty dirs | `rsync -avhPr` then `rm -rvf` the source |
| Crosses a filesystem | no | yes, and sometimes a host, over `ssh root@macmini-*` |
| Cost of getting it wrong | a misplaced title | a deleted source directory on another machine |

`move` keeps its name, narrowed to the case that genuinely moves bytes between filesystems, so
muscle memory stays correct for the command run on a full share. `stow` — put away in its proper
place — is four characters, collides with nothing in the module, and implies no travel. Each refusal
names the other verb, so the narrowing cannot strand anyone:

```
$ cd /share/10/tmp/usbdrive/__RENAMED && amedia move parents
amedia: [parents] is not a share index, did you mean [amedia stow parents]

$ cd "/share/10/media/parents/movies/Dune (2021)" && amedia stow kids
amedia: already in the library, did you mean [amedia move <share>]
```

**Ruled out: one `move` dispatching on the argument's shape** (numeric ⇒ share, word ⇒ scope). It
reads well and removes the `$PWD` mystery, but it keeps one verb doing two very different amounts of
damage, which is exactly what makes the current help text impossible to write.

Naming alternatives weighed and rejected: `adopt`/`transfer` (`transfer` is eight characters on a
daily command, `adopt` competes with supervisor's backup stages); `shelve`/`relocate` (`shelve`
means "set aside temporarily" to anyone with a git habit — the opposite of the intent); `file`/`move`
(`file` collides with `FileAction`, `MEDIA_FILE_SCRIPTS` and the `file` scope); `scope`/`share`
(symmetric and argument-named, but `share` is the most overloaded word in the module).

Three fixes the split enables that one verb cannot have:

1. **One default per verb** instead of `SHARE_INDEX_DESTINATION_DEFAULT` and
   `SHARE_SCOPE_DESTINATION_DEFAULT` side by side, exactly one of which is ever consulted.
2. **`move` requires its argument.** A defaulted destination on a path ending in
   `rm -rvf "${share_src}"*` is the wrong default to hold; the old implicit `11` is dropped. `stow`
   keeps `parents`, which is harmless.
3. **`--dry-run` earns its place on `move` alone**, printing the rsync and the delete it would run.
   It is deliberately not a global flag — there is nothing else in the CLI it would mean anything for.

### The action list is a mirrored vocabulary

`FileAction` in `src/main/python/media/analyse.py` **owns** the set of actions — it already drives
which per-file scripts are written and which survive a clean. `media.sh` declares the mirror

```bash
MEDIA_ACTIONS=(rename check merge upscale transcode reformat downscale)
```

with a comment naming `analyse.py`'s `MEDIA_FILE_SCRIPTS` as the owner, and `unit_test.py` asserts
the two sets are equal, failing loudly if either parse finds nothing. That is the standing rule for a
vocabulary crossing a language boundary that cannot share symbols, and the same shape as supervisor's
`BACKUP_STATE_*` against `metric.BackupState*`.

**Ruled out: deriving the list at runtime**, which is what `lib/clean.sh` does via
`python -c "from analyse import MEDIA_FILE_SCRIPTS"`. It is genuinely drift-free, but it costs a
measured **0.48 s** of interpreter and polars import on every invocation — paid by `clean`, by every
`process` run, and by `help`, which has to enumerate the actions to print them. A build-time test
buys the same guarantee for nothing at runtime, and lets `clean` drop the subprocess it pays now.

### Shared machinery, declared once

Beyond scope, these exist in most copies and become one function each: the `ROOT_DIR` +
`. .env_media` preamble; the `RESULT=0 … || RESULT=1 … exit ${RESULT}` accumulator (a `run()`, which
`lib/normalise.sh` already has); the "regenerate via analyse when the script is absent" guard; the
"am I in a media file root" test (`force` and `metadata` carry identical four-line copies); and the
`echo -n "…ing [dir] … "` / `done|failed` progress idiom.

Messages move to the `[$VAR]` bracket convention throughout — `move.sh` already writes
`[${share_dest}]` while `clean.sh` and `normalise.sh` write `'${WORKING_DIR}'`, and no two of the 21
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
# NOTES: Remove one release after this one, when no host can still carry a media-* link
for LINK in "/usr/local/bin/media-"*; do
  [ -L "${LINK}" ] && rm -vf "${LINK}"
done
ln -vfns ".../bin/media.sh" "/usr/local/bin/amedia"
```

`ln -fns` replaces whatever is there, link or not, without following an existing symlink into a
directory — so an upgrade and a reinstall are the same line and the new link needs no `rm`. The
`media-*` sweep is the transitional half: guarded on `-L` so the no-match literal is skipped, unable
to touch `/usr/local/bin/other-transcode`, and **deleted in the release after the one that ships
it**. Nothing else in `install.sh` changes.

### Callers outside `bin/`

1. **`deploy.sh`** — `COMMANDS_SINGLETON` / `COMMANDS_ALL_HOSTS` become verbs and the ssh line calls
   `${BIN_DIR}/media.sh <verb>`. It already runs by path rather than through the link, so it never
   depends on the migration having reached that host.
2. **`analyse.py`'s generated script headers** — five `$(media-home)` uses, two
   `$(media-home)/../shares.csv`, and `$(media-home)/lib/{clean,normalise}.sh`, becoming
   `$(amedia home)` and `amedia clean "${SHARE_DIR}"` / `amedia normalise "${SHARE_DIR}"`. This is why
   the library verbs take an optional explicit directory. The already-written copies under
   `<share>/tmp/scripts/media/` still say `media-home` and are covered — `install.sh` `rm -rf`s
   `${SHARE_DIR}/tmp/scripts` on every server host on every install, and the client Macs see those
   same trees over SMB — but the first `amedia analyse` after the release is what rewrites them, so
   run it before anything else.
3. **`media-space.sh` calling `media-mount`** — an internal function call.
4. **`lib/history.sh`** — one scrapbook line naming `media-reformat`, cosmetic.

`src/main/python/media/syncart.py` is a plan carried in a docstring proposing a 22nd wrapper,
`media-syncart.sh`, which copies "the three branches from media-analyse.sh" by name. Retarget it to
`amedia syncart`: under this design it is one entry in the command table and one function, and it
inherits the scope dispatch instead of copying it.

## Defects the copies are hiding

Found while reading the 21 scripts, all fixed by construction once there is one copy:

- **The shape A share loop tests the wrong variable.** All seven scripts run
  `[[ ! -f "${SHARE_DIR}/${SCRIPT_FILE}" ]] && { media-analyse …; }` *inside* the
  `for _SHARE_DIR in ${SHARE_DIRS_LOCAL}` loop, where `SHARE_DIR` is empty by definition of that
  branch. The test is therefore against `/tmp/scripts/media/<verb>.sh`, which never exists, so an
  estate-wide `media-transcode` re-runs `analyse` once per share and then runs a script it never
  checked for.
- **`media-truncate.sh` hardcodes the production sheet GUID** rather than reading
  `${MEDIA_GOOGLE_SHEET_GUID}`, so a dev-checkout run writes the production history sheet — the
  `.env_exec` override cannot reach it.
- **Shape A's `SCRIPT_PATH="${ROOT_DIR}/lib/<verb>.sh"` is dead in all seven** — no such file has
  ever existed in `lib/`.
- **`media-space.sh` propagates no result** (no `RESULT`, no `exit`) and its awk totals block is
  entirely commented out.
- **The wrappers call each other by link name** (`media-analyse`, `media-clean`, `media-mount`), so
  they work only through `/usr/local/bin` and never from a source checkout; all become function calls.
- **`move`'s staging walk loops `for share_type in series movies` only**, so an `audio` tree under
  `__RENAMED` is silently left behind.
- **`move` decides "is this share directly attached" with `mount | grep "${share_dir}" | grep "//"`**,
  an unanchored substring match on the mount table — `/share/1` matches `/share/10`, `/share/11` and
  `/share/12`. Anchor it when the code moves.

## Verification

No lint or typecheck gate exists on this module (no `pyproject.toml`, no `pyrightconfig.json`), so
the checks are explicit:

1. `shellcheck src/main/resources/bin/media.sh` clean, with any genuine false positive suppressed by
   a bare, narrowly-scoped `# shellcheck disable=SCxxxx`.
2. `amedia`, `amedia help`, `amedia bogus`, `amedia move`, `amedia transcode --bogus` — usage on
   stdout, usage on stdout, then three refusals on stderr with exit 2.
3. Each of the four scopes for one shape A and one shape B verb, in a `target/runtime-unit/` fixture
   tree: a media directory, a share root, an arbitrary directory, and `--share`.
4. `amedia move 11 --dry-run` from a fixture title, and confirm no rsync and no delete ran.
5. `fab ut` from `src/test/python/unit` — the existing suite executes the generated action scripts, so
   it covers the `$(amedia home)` rewrite in `analyse.py`; add the `MEDIA_ACTIONS` equality assertion
   here.
6. `fab generate` in this module, and confirm `bin/lib/{ingress,analyse,refresh}.py` come back
   byte-identical apart from the intended `$(amedia home)` lines.
7. On one server host after release, `amedia analyse` first, then `amedia space` and `amedia process`,
   and confirm `/usr/local/bin` holds `amedia` and no `media-*`.

## Expected outcome

21 entry points plus three `lib/` fragments, 738 lines, become one script of roughly 400 with one
command table, one scope resolver, two dispatchers and no duplicated branch — and adding an action
becomes an entry in `FileAction`, with no shell edit at all.
