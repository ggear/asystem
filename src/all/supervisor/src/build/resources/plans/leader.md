# Estate leader election

How the estate picks one `serve` to do a job no two hosts may do at once, why it is built the way it
is, and what it guarantees under each failure. **This work is built.** `probe_util_leader.go` is the
facility; `backup` (power the backup disk down, close a run) and `cluster` (publish
`supervisor/all/data/cluster`) are its two roles.

Status vocabulary: **built** is in the repo today, **ruled out** was tried and rejected on evidence.

---

## The shape, built

**A role is a name and an eligible host list, and a probe declares it.** A probe implementing
`campaigns()` returns its roles; `RunCycle` — which only `serve` runs — joins each once per process.
`watch` never campaigns: a hand-run `watch` on a host would otherwise stand as that host, and a host
whose `serve` is dead but whose `watch` is alive would hold the role while doing none of its work.

| Role | Eligible | Declared by |
|---|---|---|
| `backup` | `server` hosts, by `form_factor` in `config.json` | `backupProbe`, only on a `server` |
| `cluster` | `server` hosts, by `form_factor` in `config.json` | `clusterProbe` |

**Only `server` hosts (the Mac minis) ever lead.** `generate.py` writes each host's `form_factor` from
`.hosts` into `config.json`, and every role's eligible list is `leaderServers`, so an underpowered `edge`
Pi never stands. It is still watched by the cluster status like any other host.

**A caller asks `probe.Leading(role)` immediately before each side effect** and gets the answer and the
epoch it was won at. Nothing in the facility fences the work itself; a caller whose effect must not
repeat re-checks the epoch before acting, and stamps it on what it publishes (`leader_epoch` on the
backup estate status).

## The protocol, built

MQTT offers retained messages, wills and QoS 1 acknowledgements, and **no compare-and-set**. So the
election is not a claim that wins or loses atomically. Every candidate computes the same deterministic
answer from the same view, and time bounds how long two views can disagree.

1. **Candidacy.** A host stands only while it is **fit**: named in its own `config.json` eligible list
   and with a poll loop that has ticked within five pulses (30 s floor). A fit host holds a session
   whose will empties `supervisor/all/leader/<role>/candidate/<host>` and republishes that topic
   retained every `refresh`. An unfit host withdraws its candidacy once and yields, so a stalled
   `serve` or a config rolled out without it gives the role away instead of holding it idle.
2. **Freshness is arrival, never a timestamp.** Every receiver records when a candidacy or lease
   *arrived*, on its own monotonic clock, and treats it as fresh for `ttl`. The payload's `renewed_ts`
   is used only for a skew WARN, so no clock skew or clock step between hosts can split the estate. A
   retained entry from a dead session counts as fresh for `ttl` after a receiver attaches, which costs
   at most one `ttl` of deference and never a second holder.
3. **Decision.** `leaderElected` is pure. The host named by a fresh lease leads while its own candidacy is
   fresh, **whether or not the receiver's config lists it**, so an incumbent is never displaced by a
   host joining, restarting, or rolling out a config that drops it. Otherwise the lowest-named fresh
   candidate the receiver considers eligible leads.
4. **Settle.** A host that decides it is elected must keep deciding so for `settle` before it writes
   the lease or reports leading.
5. **Self-deposition.** `Leading` answers true only while the session is open, the host is standing, and
   both the last renewal and the last lease write were acknowledged within `ackWindow`, checked on every
   call, and only while the last lease that *arrived* names this host. Two hosts whose claims land in the
   same round trip both get acknowledged, but the broker delivers one final lease to both, so the loser
   stops on arrival rather than on its next tick. A lease write acknowledged after the session reattached
   is discarded, since the reattach reset the view the claim was made from.
6. **Presence.** A role may name a presence topic; `cluster` names `supervisor/all/status`. The holder
   keeps a second session whose will publishes `offline`, and publishes `online` on connect and every
   refresh; it publishes `offline` on yielding or resigning. A non-holder that has been attached for
   `settle` and sees no fresh lease publishes `offline` once per vacancy, which clears an `online` a
   broker restart kept after its holder's session died without a will.
7. **Resignation.** On shutdown `serve` calls `probe.Resign()` before publishing `offline`. It marks the
   campaign stopping and waits for any tick in flight, which re-checks stopping before every publish, so
   nothing can republish a candidacy or lease after it is cleared; presence is only opened while
   `Leading` is true under the presence lock, so a lost connection cannot leave an `online` session behind.
   It then clears the candidacy and,
   if held, the lease, under a 2 s budget for all roles together, because Docker's stop grace is 10 s.

## Why the numbers are what they are, built

| Constant | Production | Rule it satisfies |
|---|---|---|
| `refresh` | 5 s | the renewal cadence; the lease is rewritten on the same tick |
| `publishTimeout` | 3 s | below `refresh`, or renewals queue behind each other |
| `ackWindow` | 13 s | exactly `2 × refresh + publishTimeout`: one lost renewal is tolerated, two are not |
| `ttl` | 30 s | above `ackWindow + refresh`, so a live candidate can never read stale; measured on arrival, so clock skew does not enter it |
| `settle` | 20 s | above `ackWindow`, so a deposed holder has stopped before any successor can start |
| `keepAlive` / `pingTimeout` | 10 s / 5 s | the broker fires a will within 15 s of silence; paho notices within 15 s |

A unit test holds the rules in the right-hand column, so retuning one number cannot quietly break
another.

**The safety argument in one line:** a successor needs the old holder's candidacy gone (a will, at
least 15 s after the broker last heard from it, or the ttl) *and* `settle` more, while the old holder
stops within `ackWindow` of its last acknowledgement — and its last acknowledgement can be no later
than the broker's last packet from it.

## Failure modes, built

| Event | What happens | Bound |
|---|---|---|
| holder crashes or is `docker kill`ed | will clears its candidacy; the lowest remaining candidate settles and leads | ~15 s + `settle` |
| holder stops gracefully | `Resign` clears candidacy and lease; successor settles and leads | `settle` |
| holder's host restarts and rejoins | it is lower-named but the incumbent keeps the lease | no change |
| broker frozen or partitioned from the holder | holder deposes itself; nobody claims while nothing is acknowledged | `ackWindow` to yield |
| **one-way loss** — holder's publishes arrive, acks do not | holder yields; its candidacy and lease still look fresh, so nobody else claims until paho closes the socket on a missed PINGRESP and the broker fires the will | no leader for ~15 s + `settle`; **never two** |
| **vernemq release** (store flushed) | every session drops, every holder yields, every candidate reattaches to an empty store; the lowest-named host wins a fresh election | reconnect + `settle` |
| broker restart (store persists) | same; every retained entry arrives fresh on reattach, so the old holder re-wins as incumbent if it reattaches within `ttl`, otherwise the lowest-named host wins; a retained `online` is cleared by the first attached non-holder that sees no lease | reconnect + `settle`, `offline` within `settle` + `refresh` |
| **supervisor release** on any host | `install_pre.sh` sweeps only `supervisor/<host>/data|command|status`, never `all/`; the stopping `serve` resigns; the incoming one rejoins as a candidate | `settle` if it held a role |
| clock skew or a stepped clock | freshness is measured on arrival, so the election is unaffected by any skew; a live candidacy stamped more than 5 s off the receiver's clock logs one WARN per host | none |
| **`serve` hung** (poll loop stalled, session still up) | the holder is unfit, withdraws its candidacy and yields; a healthy host settles and leads | five pulses (30 s floor) + `settle` |
| **config rolled out without a holder** | the holder is unfit by its own config and withdraws; peers still on the old config ignore its lease once its candidacy is gone | one `refresh` + `settle` |
| **config rolled out without a non-holder** | the incumbent keeps the role, because a lease holder counts whatever the receiver's config says | no change |
| decommissioned host's retained candidacy | ignored as ineligible and stale; collected at the next vernemq release | none |

**What a flush costs each role.** `cluster` republishes its record the pulse after a new epoch is won,
because the engine publishes every cluster-kind record on an epoch change whether or not it is dirty.
`backup` keeps nothing between polls: the holder recomputes the estate run from retained topics every
minute, so a flushed `running` status is reopened from the servers' own retained scheduled stage
documents on the first minute a holder exists, and closed once every expected server's
`supervisor/<host>/backup/status` is terminal. Until it reopens, the reaper sees no run in progress,
the same exposure the per-host tertiary status has always had across a vernemq release during a backup.

## The topic layout, built

Every topic is `supervisor/<scope>/<kind>/…`. `<scope>` is a host name or `all`, and the
cluster side mirrors the host side wherever both exist, so one wildcard shape reads either.

| Topic | Scope | Writer | Retained |
|---|---|---|---|
| `supervisor/<host>/status` | host | that host's `serve` and its will | yes |
| `supervisor/<host>/data/host[/<metric>]` | host | that host's `serve` | yes |
| `supervisor/<host>/data/service/<service>[/<metric>]` | host | that host's `serve` | yes |
| `supervisor/<host>/command/…` | host | Home Assistant | no |
| `supervisor/<host>/backup/status` | host | that host's `serve` | yes |
| `supervisor/<host>/backup/stage/<stage>/status` | host | `backup.sh` | yes |
| `supervisor/<host>/backup/stage/primary/service/<service>/status` | host | `backup.sh` | yes |
| `supervisor/<host>/backup/stage/tertiary/scrub/status` | host | `backup.sh` | yes |
| `supervisor/all/status` | estate | the `cluster` holder's presence session and its will | yes |
| `supervisor/all/data/cluster` | estate | the `cluster` holder | yes |
| `supervisor/all/command/cluster` | estate | Home Assistant; acted on by the `cluster` holder alone | no |
| `supervisor/all/backup/status` | estate | the `backup` holder | yes |
| `supervisor/all/backup/reaper` | estate | `abackup auto` and the reaper's re-arm | yes |
| `supervisor/all/leader/<role>/lease` | estate | the holder of `<role>` | yes |
| `supervisor/all/leader/<role>/candidate/<host>` | estate | each candidate and its will | yes |

**`supervisor/all/status` falls under the `watch`'s `supervisor/+/status` subscription**, which is how
hosts announce themselves, so the watch skips the `all` scope rather than register a phantom host.
Every `serve` subscribes to `supervisor/all/command/cluster`, and a non-holder drops a command at
DEBUG, so estate-wide commands need no routing of their own once handling lands.

Two placement rules follow from releases. **Estate state lives under `all`**, because a host's
release sweeps everything under that host. And **the lease sits at `…/<role>/lease`, not at
`…/<role>`**: a topic that is also the parent of other topics collides in the generated schema tree,
where a topic is a directory holding a `payload` leaf.

## Ruled out

**The per-run backup lease** (publish, `brokerSettle`, read back, at 01:00 only). Two concurrent claimants
could each read back their own write, nobody took over from a leader that died mid-run, and "who
leads" and "a run is in progress" shared one topic. [`backup.md`](backup.md)'s *The cluster singleton*
has the detail.

**Every `serve` publishing the cluster status.** It needed no election, but two hosts with briefly
different views made the value flap, and five writers would have put five rows per pulse into
InfluxDB, so it could not be persisted.

**Lowest-named candidate wins, without incumbency.** It is simpler, but a lower-named host rejoining
after a restart would take a role from a healthy holder every time. That costs `settle` with no leader
and, for `backup`, a handover in the middle of coordinating a run.

## Tests

- **Decision table** —: incumbency, staleness either side of `ttl`,
  ineligible hosts and leases, unparseable leases.
- **Failover on a real broker** — three campaigns on a real broker with millisecond
  timings: one holder, a crash failover, an incumbent surviving a lower-named rejoin, a graceful
  handover, and never two holders at any 20 ms sample.
- **Frozen broker** — `docker pause` the broker: the holder
  yields inside `ackWindow` with nobody claiming, and one holder returns after `docker unpause`.
  Removing the acknowledgement check from `holding` fails it.
- **The systest**, against the real image and vernemq: the sole candidate wins both roles and marks the
  estate `online`; a rival faked from the test holds the `cluster` lease and `serve` defers, writing no
  lease, withholding the cluster topic and marking the estate `offline`, then reclaims, republishes and
  goes `online` when the rival leaves; a graceful stop resigns both roles and marks `offline`; a kill's
  wills clear both candidacies and mark `offline`; a broker restart re-wins both roles with new epochs.
