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

**The name is not new, it is the estate's existing convention.** `supervisor`'s `install_post.sh`
already writes `atop`, `atops` and `abackup` into `/usr/local/bin`, so `a<verb-or-module>` is the
established shape for an asystem CLI and `amedia` is the media module taking its place in it rather
than inventing a prefix. Verified free on both platforms — `command -v amedia` and
`compgen -c | grep -x amedia` return nothing on rue or on `macmini-mad`, whose `/usr/local/bin` holds
exactly `abackup atop atops other-transcode` and the 21 `media-*` links this plan retires.

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

  --force              analyse only, re-probe every file first   (default: off)
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

**The flag is what `force` did, which is not what its name suggests.** `--force` in `analyse.py` only
changes how an already-probed file is *classified*; what makes a re-probe happen is deleting the
cached `._metadata_*.yaml`, which is why `media-force.sh` runs `media-clean` before it. So
`analyse --force` is `clean` then `analyse` over the resolved extent, and the help line says
"re-probe every file first" rather than "ignore what was probed". Note plain `analyse` already
cleans in the `file`/`media` extents and does not in `share`/`local` — an inconsistency inherited
from `media-analyse.sh`, kept deliberately so the merge changes no behaviour it was not asked to.

**`--force` is accepted in every extent, unguarded** — a decision, not an oversight. `media-force.sh`
refuses outside a media file root, so today there is no way to force a re-probe of a whole share
short of deleting the metadata by hand; the flag becomes that capability. The cost is stated plainly
because nothing else states it: `amedia analyse --force` typed anywhere outside a share deletes
every cached probe on every local share and re-ffprobes the estate, which is hours. It is the one
place in this CLI where a single flag is that expensive, and the two things that keep it honest are
that `--force` is never in a pipeline stage list and that the extent is echoed in the progress line
before any work starts, so a `local` run announces what it is about to do.

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

`space` calls it first on **both** platforms. On Darwin that is what it does now; on Linux it is new
and is the point of giving the verb Linux behaviour at all — `space` is the last stage of `process`
and the command you run to ask whether a share is full, and a dropped cifs share answers that
question with an empty directory and a plausible-looking table. The cost is one anchored mount-table
check per mountpoint on a command that already shells out to `duf`.

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

**`file` dispatches exactly as `media` does, for every command but `metadata`.** The row is in the
table because two commands need to know they are standing in one title's directory, not because the
dispatchers branch on it — the seven action wrappers test only `SHARE_DIR_MEDIA` today and finding
nothing beneath a leaf directory is already the right answer, so giving `file` its own action
dispatch would change behaviour to no end. It is `metadata`'s precondition, and `analyse`'s cleaning
rule above; with `--force` unguarded it is no longer a precondition of anything else. Resolving it as
an extent rather than as a per-command test is what removes the identical four-line
`basename/dirname` block that `force` and `metadata` each carry.

and two dispatchers, one per shape:

- `dispatch_action <verb>` (shape A) — `file` and `media` extents run
  `${FIND_CMD} . -name <verb>.sh -print0` and iterate (see "Exit propagation"); `share` and `local`
  run each share's `tmp/scripts/media/<verb>.sh`, calling `command_analyse` first when it is absent.
- `dispatch_library <verb> [dir]` (shape B) — an explicit `dir` wins; otherwise `file`/`media` extents
  run the function against `$PWD`, and `share`/`local` prefer the share's generated script and fall
  back to the function.

Shape A's whole body is then `dispatch_action "${1}"`, so the seven scripts become **zero** lines:
they are entries in the action list, nothing more.

**`--quiet`/`--verbose` are not only display flags, and the merge must not treat them as such.** The
generated `analyse.sh` takes `${1}` as the verbosity *and* `${2:-/media}` as the subpath under the
share, and today's wrapper passes the pair together — `--verbose "media"` in the `share` extent,
`--quiet "/"` in the `local` extent — so the second positional is what decides whether the run
analyses `<share>/media` or the whole of `<share>`. Read as a display flag alone, `--quiet` looks
free to move and the path argument disappears with it, which analyses the wrong root in one of the
two extents and would pass every test that only counts actions. So `dispatch_library analyse` passes
**both**, deriving the subpath from the extent and the verbosity from the flags, and the default when
neither flag is given stays extent-derived — verbose in a share, quiet across `local` — which is what
the help line means by "the default below a share". The right fix at the generated end is to give
`analyse.sh` a named second argument rather than a positional, but that is `analyse.py`'s to make and
this plan only commits to not silently dropping it.

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

### Generated scripts resolve the bin directory, they never call the link

**Nothing generated may depend on a `/usr/local/bin` link, because the link is not always on the
machine the code runs on.** Three mechanisms execute a string on a *different* host than the one you
typed on — the generated aggregate scripts' self-delegation (`analyse.py`'s `HOST_DIRS`/`HOST_CMD`),
`move`'s rsync half, and `find`'s ssh to `macmini-mad` — and the first two carry `$(media-home)`
*inside* the remote command. A release reaches hosts one at a time, so renaming the link creates a
window where rue's rewritten scripts ask a macmini for `amedia` while that macmini still has only
`media-home`, and the reverse for a macmini that is released first. Ordering the rollout would only
narrow the window, and `fab release` ordering is not the module's to control.

So the dependency goes rather than the window being managed. Every generated script, and every
remote command string, resolves the bin directory itself:

```bash
MEDIA_BIN_INSTALL="/var/lib/asystem/install/media/latest/bin"
MEDIA_BIN_DIR="${MEDIA_BIN_DIR:-${MEDIA_BIN_INSTALL}}"
[ -f "${MEDIA_BIN_DIR}/.env_media" ] || { echo "Missing bin directory [${MEDIA_BIN_DIR}]" >&2; exit 1; }
. "${MEDIA_BIN_DIR}/.env_media"
```

**That path is not a new hardcoding — it is the one `.env_media` already carries**, on both
platforms, as `LIB_ROOT=/var/lib/asystem/install/media/latest/bin/lib`. `$(media-home)` resolves to
exactly it on every installed host, client and server alike; the command substitution was only ever
buying the checkout case, which the `MEDIA_BIN_DIR` override buys instead and more explicitly.

Three rules fall out of it:

1. **The two halves are distinct and must stay distinct.** `MEDIA_BIN_DIR` is the local, overridable
   one; `MEDIA_BIN_INSTALL` is the literal that goes into an ssh command string. A checkout override
   must never be interpolated into a command that lands on a server, where that path does not exist.
2. **The override is what makes the generated scripts testable.** `unit_test.py` runs from a checkout
   with no install tree, so exporting `MEDIA_BIN_DIR` at the top of the suite is the only way an
   aggregate script can be executed under test at all — see the verification steps below, which is
   where this stops being theoretical.
3. **`amedia home` survives as a verb** (it is in the help, and it is what you type to find the
   install), but nothing in the repo calls it any more. That is the whole of the migration risk: with
   no generated artifact and no remote string naming a link, the rename is a change to what an
   operator types and to nothing else.

## Install and migration

`install.sh` currently links every `bin/*.sh` by its basename, through the `latest` symlink:

```bash
for SCRIPT in "/var/lib/asystem/install/media/latest/bin/"*.sh; do
  rm -rf "/usr/local/bin/$(basename "${SCRIPT}" .sh)"
  ln -vs "${SCRIPT}" "/usr/local/bin/$(basename "${SCRIPT}" .sh)"
done
```

That loop goes. **`amedia` is installed exactly as `atop`, `atops` and `abackup` are** — the same
four lines in the same order that `src/all/supervisor/install_post.sh` uses for each of them: make
the target executable, `rm -f` the command, write it with a `cat >` heredoc, `chmod +x` it. Not a
symlink, and not a variation on one:

```bash
SERVICE_INSTALL_LATEST="/var/lib/asystem/install/${SERVICE_NAME}/latest"

# NOTES: Remove one release after this one, when no host can still carry a media-* link
for LINK in "/usr/local/bin/media-"*; do
  [ -L "${LINK}" ] && rm -vf "${LINK}"
done
chmod +x "${SERVICE_INSTALL_LATEST}/bin/media.sh"
rm -f /usr/local/bin/amedia
cat >/usr/local/bin/amedia <<EOF
#!/bin/bash

${SERVICE_INSTALL_LATEST}/bin/media.sh "\$@"

EOF
chmod +x /usr/local/bin/amedia
```

The result on a host is the same three-line file the others are — `#!/bin/bash`, a blank line, the
install path with `"$@"`, a trailing blank line — so `cat /usr/local/bin/a*` reads as one family
rather than as three conventions. The `\$@` escape is what keeps the heredoc from expanding it at
install time, exactly as supervisor writes it; everything else in the body is expanded, which is the
point.

**What is copied is the shape, not the gating.** supervisor writes `atop` and `atops` on every host
and gates `abackup` on `edge|server`; `amedia` stays inside the `client|server` gate the link loop
already sits in, which is what puts it on rue and the four macminis and keeps it off the rest. Same
family, each member scoped to the hosts its command means something on.

**Ruled out: `ln -vfns` to the script**, which an earlier draft of this plan specified. It works —
BSD `ln` takes `-v` and treats `-n` as `-h`, so it is idempotent over an existing link on both
platforms — but it would be a *third* mechanism for the same job in one estate, and the two that
exist (this module's `ln -vs` loop, supervisor's heredoc) already disagree. Note the advantage is
**not** version-independence: the existing loop already links through `latest`, so a symlink survives
a release just as well. What the wrapper buys is consistency with `atop`/`atops`/`abackup`, an
explicit `"$@"` so there is one place to read what the entry point receives, and a `$0` that is the
real script, so `media.sh`'s `readlink -f "$0"` preamble needs no thought about symlink resolution.

**`SERVICE_INSTALL_LATEST` rather than supervisor's `SERVICE_INSTALL`, and the difference is forced.**
supervisor's `install_post.sh` binds `SERVICE_INSTALL` to the `latest` path; this module's
`install.sh` already binds the same name to the *versioned*
`/var/lib/asystem/install/media/${SERVICE_VERSION_ABSOLUTE}`, because it is a full install script
rather than a post hook. Reusing the name would either shadow the versioned path the rest of the file
depends on or bake a retired version home into a wrapper that outlives it. So the shape is copied and
the spelling is not, and the new variable earns its keep beyond the wrapper: `install.sh` currently
repeats the literal `/var/lib/asystem/install/media/latest/` on four lines (the `other-transcode`
copy, the `gspread_pandas` config, the `chmod +x`, and the link loop), and all four become it.

That literal now exists in exactly two places in the module — `install.sh` as
`SERVICE_INSTALL_LATEST`, and `analyse.py` as the `MEDIA_BIN_INSTALL` it generates into every script
header. That is a constant crossing a shell↔Python boundary that cannot share a symbol, so it follows
the house rule for one: mirrored names, and a `unit_test.py` assertion that the path `install.sh`
assigns and the path `analyse.py` emits are equal, failing loudly if either parse finds nothing.

The `media-*` sweep is the transitional half, guarded on `-L` for one reason only: an unmatched glob
leaves the literal `/usr/local/bin/media-*` as the loop variable, and `-L` is what skips it. (The
earlier draft justified the guard as protecting `other-transcode`, which it does not need to — a
`media-*` glob cannot match that name. The real hazard is the unmatched literal, and it is the same
reason `[ -L ]` rather than `[ -e ]`.) The sweep is **deleted in the release after the one that ships
it**.

**No shim is needed and the rollout needs no ordering**, because of the section above: no generated
script and no remote command string names a link, so a half-released estate has nothing to skew.
What a not-yet-released host loses is the ability to *type* `amedia`, which is a person's problem
for an hour and not a pipeline's.

**The existing `chmod +x` line goes with the loop it served.** It marks `bin/*.sh` **and**
`bin/lib/*.sh` executable, and after the collapse the first glob matches one file and the second
matches only `history.sh` — a scrapbook the plan says is never executed, leaving a line whose only
remaining job is one deletion away from an unmatched-glob failure. The snippet above chmods
`bin/media.sh` by name instead, which is both what supervisor does for `supervisor` and
`image/backup.sh` and the only thing that still needs it: nothing under `lib/` is executed by
anything once `clean.sh`, `normalise.sh` and `ingress.sh` are functions. Nothing else in `install.sh`
changes.

**Rollback is by path, and is worth saying out loud** since the install deletes every `media-*` link
in the same pass that creates `amedia`. The scripts are not gone: the install layout retains the
previous version's tree beside the current one — `macmini-mad` carries `10.200.1307` and
`10.200.1337` with `latest` pointing at the second — so
`/var/lib/asystem/install/media/<previous>/bin/media-<verb>.sh` is still there and still executable,
and a full rollback is that release's own `install.sh install`. There is no bespoke recovery step to
design, which is the only reason this paragraph is short.

### Callers outside `bin/`

1. **`deploy.sh`** — `COMMANDS_SINGLETON` / `COMMANDS_ALL_HOSTS` become verbs and the ssh line calls
   `${BIN_DIR}/media.sh <verb>`. It runs by path rather than through the link, so it never depends on
   the migration having reached that host — but the path it runs is the *remote* one, so a checkout
   updated to verb form against a host still carrying the old release calls `media.sh` where only
   `media-clean.sh` exists. `deploy.sh` is an operator hook run by hand, never by `fab release`, so
   the rule is simply that it is run after the release it belongs to, and its four verbs fail loudly
   (`FAILURES+=()`, non-zero exit) rather than silently if it is not.
2. **`analyse.py`'s generated script headers** — five `$(media-home)` uses, two
   `$(media-home)/../shares.csv`, and `$(media-home)/lib/{clean,normalise}.sh`. All eight become
   `${MEDIA_BIN_DIR}` (or `${MEDIA_BIN_INSTALL}` in the two remote command strings, `HOST_DIRS` and
   `HOST_CMD`), and the last two become `"${MEDIA_BIN_DIR}/media.sh" clean "${SHARE_DIR}"` /
   `… normalise "${SHARE_DIR}"` — by path, not through the link. This is why the library verbs take an
   optional explicit directory. The already-written copies under `<share>/tmp/scripts/media/` still
   say `media-home` and are covered — `install.sh` `rm -rf`s `${SHARE_DIR}/tmp/scripts` on every
   server host on every install, and the client Macs see those same trees over SMB — but the first
   `amedia analyse` after the release is what rewrites them, so run it before anything else.
3. **`media-move.sh`'s two `$(media-home)` uses**, which the earlier draft of this plan missed. Line
   90 reads `$(media-home)/../shares.csv` locally and becomes the `shares_file()` helper; line 84
   embeds `. $(media-home)/.env_media` in a string executed **on the remote server** via
   `ssh root@${share_host}`, and becomes `${MEDIA_BIN_INSTALL}`. The second is the same class as
   `analyse.py`'s `HOST_CMD` and is the reason rule 1 of the section above exists.
4. **`media-space.sh` calling `media-mount`** — an internal function call.
5. **`lib/history.sh`** — one scrapbook line naming `media-reformat`, cosmetic.

`src/main/python/media/syncart.py` is a plan carried in a docstring proposing a 22nd wrapper,
`media-syncart.sh`, which copies "the three branches from media-analyse.sh" by name. It is **not in
the command table above and must not be added until it is built** — a help text that advertises a
verb the script does not implement is worse than no plan for it. What this plan commits to is the
shape it lands in when it does: `amedia syncart`, one entry in the command table and one function,
inheriting the extent resolution instead of copying the three branches.

## Defects the copies are hiding

Found while reading the 21 scripts, all fixed by construction once there is one copy:

- **The shape A share loop tests the wrong variable.** All seven scripts run
  `[[ ! -f "${SHARE_DIR}/${SCRIPT_FILE}" ]] && { media-analyse …; }` *inside* the
  `for _SHARE_DIR in ${SHARE_DIRS_LOCAL}` loop, where `SHARE_DIR` is empty by definition of that
  branch. The test is therefore against `/tmp/scripts/media/<verb>.sh`, which never exists, so an
  estate-wide `media-transcode` re-runs `analyse` once per share and then runs a script it never
  checked for.
- **`media-truncate.sh` hardcodes both the production sheet GUID and the library root.** It passes
  the literal `14W6B24…` rather than `${MEDIA_GOOGLE_SHEET_GUID}`, so a dev-checkout run writes the
  production history sheet and the `.env_exec` override cannot reach it; and it passes the literal
  `/share`, which is `SHARE_ROOT` on Linux only, so the command cannot run from rue at all. One line,
  two literals, and both must be replaced or the fix is half done.
- **Shape A's `SCRIPT_PATH="${ROOT_DIR}/lib/<verb>.sh"` is dead in all seven** — no such file has
  ever existed in `lib/`.
- **`media-space.sh` propagates no result** (no `RESULT`, no `exit`) and its awk totals block is
  entirely commented out.
- **The `find -exec` status is always 0**, so the seven action wrappers cannot report a failure in
  the in-a-media-directory case at all — measured above, and the reason a hand-typed `&&` chain has
  been trusting a success it never earned.
- **The wrappers call each other by link name** (`media-analyse`, `media-clean`, `media-mount`), so
  they work only through `/usr/local/bin` and never from a source checkout; all become function calls.
- **`move` and the generated scripts call a link name *on a remote host*.** `media-move.sh:84` and
  `analyse.py`'s `HOST_DIRS`/`HOST_CMD` put `$(media-home)` inside a string run over
  `ssh root@macmini-*`, so they depend on the other machine's `/usr/local/bin` as well as their own.
  That is the whole of the rename's migration risk and is why it is retired rather than renamed — see
  "Generated scripts resolve the bin directory".
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
7. `fab ut` from `src/test/python/unit` — add the `MEDIA_ACTIONS` equality assertion here, and the
   install-path one beside it (`SERVICE_INSTALL_LATEST` in `install.sh` against the
   `MEDIA_BIN_INSTALL` that `analyse.py` emits). **The
   suite does not currently reach the bin-directory rewrite and must not be assumed to**: it walks the
   fixture tree for `<verb>.sh` while explicitly skipping anything under `/tmp/scripts/media`, so it
   executes only the *per-file* scripts, which carry `BASH_EXIT_HANDLER` and have never named
   `media-home`. Every `$(media-home)` lives in the *aggregate* scripts, which nothing executes under
   test — which is the highest-risk edit in this change sitting on zero coverage.
8. **A new case that executes an aggregate script**, since step 7 does not. Export
   `MEDIA_BIN_DIR="$(pwd)/../../../main/resources/bin"` and run the generated
   `<share>/tmp/scripts/media/analyse.sh` and one action aggregate from the fixture tree — asserting
   they resolve `.env_media` from the override and exit 0, and that with `MEDIA_BIN_DIR` pointed at a
   directory holding no `.env_media` they exit non-zero with the missing-directory message rather than
   sourcing nothing and continuing. This is the test the rewrite actually needs, and it is only
   writable because the override exists.
9. `grep -rn 'media-[a-z]' src/main/python/media src/main/resources/bin deploy.sh install.sh`
   returns nothing but `lib/history.sh`'s scrapbook line and the `media-*` sweep in `install.sh` — the
   mechanical check that no link name survives anywhere, local or inside an ssh heredoc. Run it
   *after* the rewrite and before the release; it is the cheapest of these steps and the one that
   catches the site the reading missed, which is how `move.sh:84` was found in the first place.
10. `fab generate` in this module, and confirm `bin/lib/{ingress,analyse,refresh}.py` come back
   byte-identical apart from the intended `${MEDIA_BIN_DIR}` / `${MEDIA_BIN_INSTALL}` lines.
11. `amedia analyse --force` from a share root, against a two-share fixture — it must clean and
   re-probe that share and **not** the other, and from an arbitrary directory it must do both. This
   is new behaviour (`media-force.sh` refuses outside a media file root), so it is asserted rather
   than assumed.
12. On rue, `amedia find`, `amedia space`, `amedia metadata` and one action verb from a media directory
   — the action must delegate over ssh to the owning macmini as it does today, and `amedia ingress`
   must print a Linux-only skip rather than succeeding silently.
13. `amedia truncate` from a checkout, and confirm it writes the `.env_exec` sheet and not the
   production one, having read `${MEDIA_GOOGLE_SHEET_GUID}` and `${SHARE_ROOT}` rather than the two
   literals it carries today. This is the one defect whose fix is invisible from the outside — the
   command succeeds either way, against whichever sheet it was given.
14. On one server host after release, `amedia analyse` first, then `amedia space` and `amedia process`,
   and confirm `/usr/local/bin` holds `amedia` and no `media-*`. `cat /usr/local/bin/a*` must show
   four files of the same shape — `amedia` beside `abackup`, `atop` and `atops`, each a `#!/bin/bash`
   wrapper calling an install path through `latest` with `"$@"`. A symlink, a different body, or a
   versioned path in `amedia` means the convention was approximated rather than followed.
15. **The skew check, run once while the estate is half released**: from rue, an action verb on a
   share owned by a host that has *not* yet taken the release, and the same from a released macmini
   against an unreleased one. Both must work, because neither names a link. If either fails, the
   bin-directory rewrite is incomplete and the grep in step 9 missed a site.

## Expected outcome

21 entry points plus three `lib/` fragments, 738 lines, become one script of roughly 400 with one
command table, one extent resolver, two dispatchers and no duplicated branch — and adding an action
becomes an entry in `FileAction`, with no shell edit at all.

**No loss of functionality.** Every one of the 21 commands survives: 19 keep their name as a verb,
`force` becomes `analyse --force`, and `move` becomes the two commands it always was, `stow` and
`move`. Three things are added — the `publish` pipeline, `--share`, and a forced re-probe of a whole
share, which `--force` makes reachable for the first time — and nothing is dropped. **One behaviour
deliberately widens**: `media-force.sh` refuses outside a media file root and `analyse --force` does
not, so this is not a pure refactor and the `--force` paragraph above states what that costs when it
is typed from the wrong directory. The only removals anywhere are of things that never worked: the
dead `SCRIPT_PATH` in seven files, the commented-out awk block in `space`, and `truncate`'s
hardcoded production sheet GUID and `/share` root.

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
Linux-absolute paths on the owning host — the last two with their `$(media-home)` replaced by the
install literal, so they no longer depend on the other machine's `/usr/local/bin`.

**`mount` gains parity rather than losing it** — SMB mounts on rue as today, fstab-declared shares on
the macminis where it used to return 0 without acting, so a dropped cifs share is recoverable and
reported instead of appearing as an empty directory.

**And five things start working that do not today**: an action verb's failure is actually reported
(`find -exec` always exited 0), a pipeline stops at the stage that failed and names it, a failed usb
import is no longer swept into `__RENAMED` as a finished arrival, an estate-wide action stops
re-running `analyse` once per share because of a mistyped variable, and `truncate` becomes runnable
from rue against the sheet its environment names rather than the production one.

**And one thing stops being possible to get wrong**: no generated artifact and no remote command
string names a `/usr/local/bin` link any more, so the class of failure where a command works on the
machine you typed it on and not on the machine it delegates to — which the rename would have
created, and which the current `$(media-home)` already risks on any host whose install is behind —
cannot occur.
