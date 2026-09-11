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

  Pipeline             stop at the first failed stage
    publish   [scope]  stow, process, merge, refresh             (default: parents)
    process            normalise, analyse, act, report space
    analyse            probe the library, write the scripts

  Actions              run what analyse wrote, writing it if absent
    rename             apply the canonical naming
    check              verify streams and subtitles
    upscale            raise resolution to target
    reformat           remux without re-encoding
    transcode          re-encode to the target quality
    downscale          lower resolution to target
    merge              merge a split title, never in process

  Library
    clean     [dir]    delete generated metadata and scripts     (default: from $PWD)
    normalise [dir]    fix ownership and modes, strip junk       (default: from $PWD)
    ingress   [dir]    import the usb drive and downloads        (default: from $PWD)
    stow      [scope]  file staged content into the library      (default: parents)
    move      <share>  copy to another share, drop the source
    refresh            reconcile paths into Plex and scan
    truncate           trim the Google Sheet history

  Inspect
    find      <token>  print a cd per matching directory
    metadata           print this directory's spec and probes
    space              print share usage

  Tool
    mount              mount the remote shares, Darwin
    home               print the install bin directory
    help               this text, and a bare amedia prints it

  --force              analyse only, ignore what was probed      (default: off)
  --keep-going         carry on past a failed pipeline stage     (default: off)
  --share <index>      one share, not the one you are in         (default: all local)
  --quiet              summaries only, the default below a share (default: off)
  --verbose            one line per file, the default in a share (default: off)
  --dry-run            move only, print it and change nothing    (default: off)
```

Exit codes are `0` done, `1` work failed, `2` the command line was wrong — a refusal prints the
reason then the usage on stderr, `help` prints it on stdout, exactly as `backup.sh` does.

**The defaults column means one thing: the value used when the argument or flag is absent.** An
earlier draft mixed four kinds of statement into it — a value (`parents`), a requirement
(`required`), the condition under which a flag is already the default (`single share`), and a fact
about `help` (`default command`). Requirements are carried by `<required>` against `[optional]` and
stated nowhere else; the verbosity condition moved into the description, where it belongs; and
`help` being the default command is stated in its own description. **The word "scope" is reserved
for the library's `kids|parents|docos|comedy`**, which is what `stow [scope]` takes, so the resolver
concept below is an *extent* and the defaults say `from $PWD` rather than "this scope".

**`force` folded into `analyse --force`.** It was `analyse` with one flag and a narrower
precondition, and a verb named for how it behaves rather than what it does; three pipeline verbs
where two plus a flag will do is the repetition this refactor exists to remove.

**Groups are four kinds of thing, not three plus a grab bag.** `mount` mutates (it mounts
filesystems, and `space` calls it), and `home` and `help` are about the tool rather than the
library, so all three left `Inspect` for `Tool`. `refresh` and `truncate` stay under `Library`
because they publish its state rather than inspect it, and a separate `Publish` group was tried and
dropped once `publish` became a pipeline verb — one word, two meanings, in one help text.

`--share` is new and is the one capability the wrappers never had: extent is currently derivable
only from `$PWD`, so operating on share 11 from anywhere else means `cd`-ing there first.

### Pipelines are declared, and their stages stop on failure

`publish` exists because the sequence is typed by hand daily — `media-move && media-process &&
media-merge && media-refresh`, which in this vocabulary is `stow` then `process` then `merge` then
`refresh`: get a staged arrival into the library, run the pipeline over it, merge, tell Plex. It is a
different pipeline rather than a variant of `process`, so it is a verb and not a flag, and it is
named for where it ends.

Both pipelines are stage lists read by one runner, so there is one definition of what a pipeline is
and one exit policy:

```bash
PIPELINE_PROCESS=(normalise analyse rename check upscale reformat transcode downscale analyse space)
PIPELINE_PUBLISH=(stow process merge refresh)
```

The policy differs by relationship, and has to:

- **Between stages, stop at the first failure**, which is the `&&` typed by hand today. A failed
  `stow` means there is nothing to process; a failed `analyse` means the action scripts are stale or
  absent, so running actions next is wrong rather than merely unlucky.
- **Within `process`'s action loop, keep going.** One title failing to transcode must not strand the
  other two hundred or block `refresh`. That is the existing `|| RESULT=1` behaviour and it is right.
- **Exit with the first failing stage's own code**, not a flattened `1`, and print one summary line
  naming the stage — a twenty-minute run's exit code has scrolled away by the time it matters.
  `deploy.sh`'s `FAILURES+=()` block is the in-house shape.
- `--keep-going` overrides the between-stage stop, for a whole run's damage report in one pass.

```
$ amedia publish kids
==> stow       done, 3 titles
==> process    done, 2 transcoded, 1 failed
==> merge      skipped, process failed
amedia: publish stopped at [process], exit [1]
```

### Exit propagation is broken today, not merely unpropagated

**`find -exec` exits 0 even when every script it ran failed.** `-exec`'s status sets the truth value
of the *expression*, not `find`'s exit status, which is non-zero only for `find`'s own errors.
Measured on both implementations the module uses, against a script that exits 3:

```
$ find . -name fail.sh -exec "{}" \;     # BSD find and GNU gfind identical
find -exec status [0]
find pipeline PIPESTATUS[0] [0]
```

So `RESULT=${PIPESTATUS[0]}` in all seven action wrappers can never report a failure in the
in-a-media-directory case, and any `&&` chain built on those commands has been chaining on a status
that is always success. The fix goes in the one `dispatch_action`, so it lands for all seven at once
— iterate rather than `-exec`, through the process substitution `move.sh` already uses, so no
subshell eats the result:

```bash
while IFS= read -r -d '' action; do
  "${action}" || RESULT=1
done < <(${FIND_CMD} . -name "${verb}.sh" -print0)
```

### Both platforms keep working, by replicating what works today

Nothing here changes how a platform is detected or what it resolves to. `.env_media` stays exactly
as it is and remains the only place that branches on `uname`, `media.sh` reads its variables and adds
no platform test of its own, and the three remote-delegation mechanisms are carried over verbatim.
Verified against this Mac (Darwin 25.6, bash 5.3 from Homebrew) and `macmini-mad` (bash 5.2):

| | rue (Darwin, client) | macmini-* (Linux, server) |
|---|---|---|
| `SHARE_ROOT` | `/Users/graham/Desktop/share` | `/share` |
| `SHARE_DIRS_LOCAL` | **every** mounted share, all 11 across 4 hosts | this host's fstab `ext4` mounts only |
| What a share actually is | an SMB mount made by `mount` | a local disk |
| `.env` sourced from | the repo checkout | `/root/install/media/latest/.env`, a symlink to `/var/lib/asystem/install` |
| `FIND_CMD` | `gfind` | `find` |
| `PYTHON_DIR` | `${PYENV_ROOT}/versions/asystem/bin` | `/root/.pyenv/versions/${PYTHON_VERSION}/bin` |
| Present | `gecho` `grealpath` `duf` `mount_smbfs` `diskutil` | `duf` `lsblk` `setfacl` `getent` |
| Absent | `getent` `lsblk` `setfacl` | `gfind` and the `g*` aliases |

**The `local` extent means different things per platform, and must go on meaning them.** On Linux it
is this host's own disks; on Darwin `SHARE_DIRS_LOCAL` is set to *all* of `SHARE_DIRS`, so it is every
mounted share on every server. The extent resolver therefore reads `SHARE_DIRS_LOCAL` and never
recomputes or reinterprets it.

**Three remote-delegation mechanisms, all preserved unchanged:**

1. **The generated aggregate scripts self-delegate.** `script_source_exec_remote` reads `shares.csv`,
   and when `$HOSTNAME` is absent from it — which is the case on rue — ssh's `root@<host>` for each
   share host and runs the same script path there under that host's own `.env_media`, guarded on the
   name resolving and on the remote reporting that share index in its own `SHARE_DIRS_LOCAL`. This is
   why an action verb typed on the Mac executes on the server that owns the disk, and `dispatch_action`
   still runs exactly those scripts.
2. **`find` ssh's to `macmini-mad`** when `SHARE_ROOT != /share`, then maps the returned paths back
   with `${dir_found/#\/share/$SHARE_ROOT}`.
3. **`move`'s rsync half ssh's to the owning host** when the share is an SMB mount, quoting its
   arguments with `printf '%q'` and evaluating Linux-absolute `/share/<index>/...` paths on the server.

So the rule the code follows is: **`${FIND_CMD}` for anything run locally, bare `find` inside a remote
heredoc**, because the heredoc always lands on Linux. Both `move` and `find` already do this and it
survives the merge as-is.

**`media.sh` uses `#!/usr/bin/env bash` and does not contort for `/bin/bash`.** Today 22 scripts say
`#!/bin/bash` and three say `#!/usr/bin/env bash`, and that split matters on the Mac, where
`/bin/bash` is **3.2.57** with no associative arrays and no namerefs — `media-find.sh` needs
`declare -A` and the generated summarise body needs `local -n`, which is why both already point at
`env bash`. One merged file has one shebang and it is that one.

`env bash` is a bet on `PATH`, and it is worth knowing which way the bet runs:

```
$ /usr/bin/env bash -c 'echo $BASH_VERSION'              5.3.15   (a terminal, Homebrew first)
$ env -i /usr/bin/env bash -c 'echo $BASH_VERSION'       3.2.57   (a clean environment)
```

**This CLI is only ever run by hand from a terminal**, where the first line is what happens, and the
module's only non-interactive paths — `deploy.sh`'s ssh and the generated scripts' self-delegation —
both land on Linux, where `/bin/bash` is 5.2. So the bet is not exposed and the script is written for
the bash it actually gets. The **known limit**, recorded rather than designed around: wiring any of
this into launchd or cron on the Mac would need an absolute interpreter or an explicit `PATH`, because
that is the one context where `env bash` finds 3.2. The generated scripts already carry the same
condition.

One thing from the 3.2 exercise is kept because it is simply better: `find`'s `declare -A dirs_found`
is **redundant, not needed** — the result is already piped through `printf '%s\n' | sort`, so
`sort -u` dedupes and the array goes away. Command dispatch is a `case`, as `backup.sh` does it,
rather than an associative table.

**`--share <index>` resolves through `SHARE_DIRS`, never by string concatenation.** It is the one new
capability, and building `${SHARE_ROOT}/${index}` by hand would be the one place the design could
invent a path structure instead of reading the platform's — so it selects the matching entry from
`SHARE_DIRS_LOCAL` and refuses an index that host does not hold, naming what it does.

**`shares.csv` is found relative to the script**, as `$(media-home)/../shares.csv` does today, rather
than via `${LIB_ROOT}/../../shares.csv` as `media-mount.sh` does — the first works from a checkout and
from an install, the second only where the install tree exists. One `shares_file()` helper, the
checkout-safe form.

**`ln -vfns` is fine on both.** BSD `ln` takes `-v` and treats `-n` as `-h`, so the install line is
idempotent over an existing link to a file or to a directory; verified here. `/usr/local/bin` is on the
default macOS `PATH` via `/etc/paths`, and rue is form factor `client`, so it is already inside
`install.sh`'s `client|server` gate that links the commands.

**Platform-guarded verbs keep their guards**, all of which are absence-tolerant rather than
`uname`-tested where they can be: `mount` is Darwin-only and additionally skips when `$HOSTNAME` is in
`shares.csv`; `ingress` is Linux-only (`lsblk`, `mount -t exfat`) and now says so instead of exiting 0
silently; `normalise`'s ownership block is already inside a `Linux` test and its `setfacl` and
`getent` uses are `command -v`/`id` guarded, which is what makes them no-ops on the Mac rather than
errors; `space` calls `mount` first on Darwin only.

### `mount` works on both platforms, per each one's mechanism

`media-mount.sh` is Darwin-only by accident of its guard: it skips whenever `$HOSTNAME` appears in
`shares.csv`, which every macmini does, so on Linux it is a silent no-op returning 0. That leaves no
way to recover a dropped share from the CLI, and a dropped share is invisible — an unmounted
`/share/40` is just an empty directory to `space` and to every verb that loops `SHARE_DIRS`.

One verb, one meaning — **ensure every share this host expects is mounted** — with the mechanism
chosen per platform, which is the same shape as every other branch here:

| | rue (Darwin) | macmini-* (Linux) |
|---|---|---|
| What it expects | every `shares.csv` row, minus any naming this host | every fstab `/share/*` entry, ext4 and cifs alike |
| How it mounts | `mount_smbfs //GUEST:@<host>/share-<index>`, after `diskutil unmount force`, as today | access the path to trigger `x-systemd.automount` for cifs, `mount <dir>` for an absent non-automount entry |
| Why that way | the shares are SMB mounts this machine makes for itself | the cifs rows carry `x-systemd.automount,x-systemd.idle-timeout=0s`, so they mount on first access rather than at boot, and the ext4 rows carry `nofail`, so an absent one means the disk is missing and `mount` is the right recovery attempt |

Verification is shared: an **anchored** mount-table check per mountpoint — anchored because `move`
already demonstrates the bug of an unanchored one, where `/share/1` matches `/share/10` — plus the
`tmp` liveness probe `media-mount.sh` uses today, which is what catches a mount that exists but is
stale. It reports `mounted`, `already` or `failed` per share and accumulates the exit, so
`amedia mount` is worth running before a `space` or a `publish` on either machine.

`space` keeps calling it first on Darwin, as it does now; on Linux it may now do so too, since the
verb is no longer a no-op there.

### `ingress` is extent-aware, in two phases

`media-ingress.sh` hardcodes `/share/10` and returns 0 without a word on Darwin. Made extent-aware it
resolves like its two `[dir]` siblings, so all three read by one rule — but **ingress's unit is a
share, not a directory**, because `ingress.py` works on `<share>/tmp` and never on `media/`. So it is
the one verb where the `file` and `media` extents do not mean `$PWD`:

| Extent | What ingress operates on |
|---|---|
| `file`, `media`, `share` | the enclosing share's `tmp` |
| `local` | every local share's `tmp` |

**The two phases must be separated, because only one of them is per-share:**

- **import** — the usb drive, a per-*host* singleton. It mounts, rsyncs into one share's `tmp`, and
  runs once per invocation, into the **first share of the extent** — the lowest-numbered local share
  under the `local` extent, which on `mad` is `/share/10`, so today's hardcoded value falls out as the
  derived default and nothing has to name it.
- **sweep** — `ingress.py` over `<share>/tmp`, which is genuinely per-share and runs for every share
  in the extent. A share holding none of `usbdrive`, `usenet/finished` or `finished` is a real no-op:
  `_process` rglobs those three roots and renames nothing.

Without that split, the `local` extent would mount and rsync the usb drive into all three of `mad`'s
shares in turn.

**A failed import must not be swept.** `lib/ingress.sh` accumulates `|| RESULT=1` across the mount
and the rsync and then runs `ingress.py` regardless, so a half-transferred file is renamed into
`__RENAMED` and is indistinguishable from a finished arrival. Import failure is fatal to that share's
sweep and the run continues to the other shares, which is the same per-share-independent policy the
action loop uses.

**`[dir]` is validated as a share root**, not merely as a directory — `ingress.py` derives
`<dir>/tmp` from it, so any other directory silently sweeps nothing. Today's only check is `-d`; it
becomes membership of `SHARE_DIRS`, refused by name otherwise.

**Darwin skips, loudly.** The import phase is `lsblk` and `mount -t exfat`, neither of which exists
there, and the sweep chowns `1000:100`, which a guest SMB mount cannot do — so ingress stays
Linux-only as a whole, but says so rather than exiting 0 in silence as it does now.

### Extent, resolved once

The 20-line `if SHARE_DIR_MEDIA / elif SHARE_DIR / else loop SHARE_DIRS_LOCAL` block copied through
eleven scripts becomes one resolution at startup, against `$PWD`, `.env_media` and `--share` — called
the **extent**, since *scope* is the library's own word for `kids|parents|docos|comedy`:

| Extent | When | What a command operates on |
|---|---|---|
| `file` | `$PWD` is a movies/series file directory | `$PWD`, one title |
| `media` | `$PWD` is inside a `<share>/media` tree | `$PWD` |
| `share` | `$PWD` is inside a share root | `<share>/media` |
| `local` | anywhere else | every directory in `SHARE_DIRS_LOCAL` |

and two dispatchers, one per shape:

- `dispatch_action <verb>` (shape A) — `media` extent runs `${FIND_CMD} . -name <verb>.sh -exec {} \;`;
  `share` and `local` run each share's `tmp/scripts/media/<verb>.sh`, calling `command_analyse` first
  when it is absent.
- `dispatch_library <verb> [dir]` (shape B) — an explicit `dir` wins; otherwise `media` extent runs the
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
- **The `find -exec` status is always 0**, so the seven action wrappers cannot report a failure in
  the in-a-media-directory case at all — measured above, and the reason a hand-typed `&&` chain has
  been trusting a success it never earned.
- **The wrappers call each other by link name** (`media-analyse`, `media-clean`, `media-mount`), so
  they work only through `/usr/local/bin` and never from a source checkout; all become function calls.
- **`lib/ingress.sh` sweeps after a failed import.** The mount and the rsync only set `RESULT=1`, so
  `ingress.py` runs on a partial copy and files it into `__RENAMED` as a finished arrival.
- **`media-ingress.sh` exits 0 on Darwin without printing anything**, so a Mac run is indistinguishable
  from a successful one.
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
3. Each of the four extents for one shape A and one shape B verb, in a `target/runtime-unit/` fixture
   tree: a media directory, a share root, an arbitrary directory, and `--share`.
4. `amedia move 11 --dry-run` from a fixture title, and confirm no rsync and no delete ran.
5. Exit propagation, against a fixture whose generated action script exits non-zero: `amedia check`
   from a media directory must exit non-zero (it exits 0 today), `amedia process` must continue past it
   and still exit non-zero, and `amedia publish` must stop at that stage, name it, and exit with its
   code — with `--keep-going` running the remaining stages instead.
6. `amedia ingress` from a title, a share root and an arbitrary directory, against a fixture with two
   share roots — the first two sweep one share, the third sweeps both, the usb import is attempted once
   in each case, and `amedia ingress /tmp` is refused as not a share root.
7. `fab ut` from `src/test/python/unit` — the existing suite executes the generated action scripts, so
   it covers the `$(amedia home)` rewrite in `analyse.py`; add the `MEDIA_ACTIONS` equality assertion
   here.
8. `fab generate` in this module, and confirm `bin/lib/{ingress,analyse,refresh}.py` come back
   byte-identical apart from the intended `$(amedia home)` lines.
9. On rue, `amedia find`, `amedia space`, `amedia metadata` and one action verb from a media directory
   — the action must delegate over ssh to the owning macmini as it does today, and `amedia ingress`
   must print a Linux-only skip rather than succeeding silently.
10. On one server host after release, `amedia analyse` first, then `amedia space` and `amedia process`,
   and confirm `/usr/local/bin` holds `amedia` and no `media-*`.

## Expected outcome

21 entry points plus three `lib/` fragments, 738 lines, become one script of roughly 400 with one
command table, one extent resolver, two dispatchers and no duplicated branch — and adding an action
becomes an entry in `FileAction`, with no shell edit at all.

**No loss of functionality.** Every one of the 21 commands survives: 19 keep their name as a verb,
`force` becomes `analyse --force`, and `move` becomes the two commands it always was, `stow` and
`move`. Two things are added — the `publish` pipeline and `--share` — and nothing is dropped. The only
removals anywhere are of things that never worked: the dead `SCRIPT_PATH` in seven files, the
commented-out awk block in `space`, and `truncate`'s hardcoded production sheet GUID.

**macOS and Linux both keep working, because nothing about platform detection changes.**
`.env_media` stays the only file that branches on `uname` and is edited not at all; `media.sh` reads
its variables and adds no platform test of its own; `${FIND_CMD}` is used for everything run locally
and bare `find` only inside a remote heredoc, which always lands on Linux; and the shebang is
`env bash`, which in a terminal is the 5.3 the three existing `env bash` scripts already rely on. Every platform-absent binary stays
guarded the way it is today — `setfacl` and `getent` by `command -v`/`id`, `lsblk` by the Linux-only
`ingress`, `mount_smbfs` and `diskutil` by the Darwin branch of `mount`.

**rue and the macminis keep working despite their different `/share` layouts**, because no path is
ever rebuilt from parts. The extent resolver reads `SHARE_DIRS_LOCAL` and never recomputes it, so
`local` goes on meaning this host's own disks on Linux and every mounted share on Darwin, exactly as
it does now. `--share <index>` selects a matching entry from that same list rather than concatenating
`${SHARE_ROOT}/${index}`, and refuses an index the host does not hold. `shares.csv` is resolved
relative to the script, so it is found from a checkout and from an install. All three remote
delegations are preserved unchanged: the generated scripts self-delegating over ssh when `$HOSTNAME`
is absent from `shares.csv`, `find` reaching `macmini-mad` and mapping paths back with
`${dir_found/#\/share/$SHARE_ROOT}`, and `move`'s rsync half quoting its arguments and evaluating
Linux-absolute paths on the owning host.

**`mount` gains parity rather than losing it** — SMB mounts on rue as today, fstab-declared shares on
the macminis where it used to return 0 without acting, so a dropped cifs share is recoverable and
reported instead of appearing as an empty directory.

**And four things start working that do not today**: an action verb's failure is actually reported
(`find -exec` always exited 0), a pipeline stops at the stage that failed and names it, a failed usb
import is no longer swept into `__RENAMED` as a finished arrival, and an estate-wide action stops
re-running `analyse` once per share because of a mistyped variable.
