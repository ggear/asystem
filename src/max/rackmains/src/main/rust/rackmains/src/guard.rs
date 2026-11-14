use std::collections::{BTreeSet, HashSet, VecDeque};
use std::fmt;
use std::time::Duration;

use crate::metrics::{
    Frame, GUARD_BATTERY_SECONDS, GUARD_FAILED_HOSTS, GUARD_LAST_ACTION, GUARD_LIVE, GUARD_MAINS_SECONDS, GUARD_STATE,
};
use crate::nut::Flags;
use crate::outage::{DECISION_SHED, EVENT_DECISION};
use crate::policy::Policy;

pub const HOST_SHED_LAST: &str = "meg";
const BLIND_RESTORE_FACTOR: u32 = 2;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum State {
    Idle,
    Waiting,
    Shedding,
    Holding,
    Restoring,
}

impl fmt::Display for State {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            State::Idle => "idle",
            State::Waiting => "waiting",
            State::Shedding => "shedding",
            State::Holding => "holding",
            State::Restoring => "restoring",
        })
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Command {
    AsleepDeep,
    AsleepShallow,
    Awake,
}

impl Command {
    pub fn remote(self) -> &'static str {
        match self {
            Command::AsleepDeep => "asleep --deep",
            Command::AsleepShallow => "asleep --shallow --except rackmains",
            Command::Awake => "awake",
        }
    }
}

#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Call {
    pub host: String,
    pub command: Command,
}

#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Host {
    pub name: String,
    pub address: String,
    pub local: bool,
}

#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Row {
    pub event: &'static str,
    pub detail: String,
}

#[derive(Default, Debug, PartialEq, Eq)]
pub struct Output {
    pub calls: Vec<Call>,
    pub rows: Vec<Row>,
    pub ended: bool,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Sequence {
    Shed,
    Restore,
}

pub struct Guard {
    policy: Policy,
    live: bool,
    hosts: Vec<Host>,
    outage: bool,
    shed_started: bool,
    restore_wanted: bool,
    shed_after_restore: bool,
    last_flags: Flags,
    runtime_remaining: Option<Duration>,
    battery: Duration,
    mains: Duration,
    blind: Duration,
    sequence: Option<Sequence>,
    waves: VecDeque<Vec<Call>>,
    in_flight: HashSet<String>,
    failed: BTreeSet<String>,
    last_action: String,
}

impl Guard {
    pub fn new(policy: Policy, live: bool, hosts: Vec<Host>) -> Self {
        Guard {
            policy,
            live,
            hosts,
            outage: false,
            shed_started: false,
            restore_wanted: false,
            shed_after_restore: false,
            last_flags: Flags::default(),
            runtime_remaining: None,
            battery: Duration::ZERO,
            mains: Duration::ZERO,
            blind: Duration::ZERO,
            sequence: None,
            waves: VecDeque::new(),
            in_flight: HashSet::new(),
            failed: BTreeSet::new(),
            last_action: String::new(),
        }
    }

    pub fn resume(&mut self, battery: Duration, mains: Duration, shed: bool) {
        self.outage = true;
        self.shed_started = shed;
        self.battery = battery;
        self.mains = mains;
    }

    pub fn set_runtime_remaining(&mut self, runtime_remaining: Option<Duration>) {
        self.runtime_remaining = runtime_remaining;
    }

    pub fn set_policy(&mut self, policy: Policy) {
        self.policy = policy;
    }

    pub fn state(&self) -> State {
        match self.sequence {
            Some(Sequence::Restore) => State::Restoring,
            Some(Sequence::Shed) => State::Shedding,
            None if self.shed_started => State::Holding,
            None if self.outage => State::Waiting,
            None => State::Idle,
        }
    }

    pub fn in_outage(&self) -> bool {
        self.outage
    }

    pub fn failed_hosts(&self) -> Vec<String> {
        self.failed.iter().cloned().collect()
    }

    pub fn hosts_shed(&self) -> usize {
        usize::from(self.shed_started) * self.hosts.len()
    }

    pub fn step(&mut self, flags: Option<Flags>, dt: Duration) -> Output {
        let mut out = Output::default();
        match flags {
            Some(flags) if flags.raw_on_battery => {
                self.mains = Duration::ZERO;
                self.blind = Duration::ZERO;
                self.battery += dt;
                self.outage = true;
                if self.sequence == Some(Sequence::Restore) {
                    self.shed_after_restore = true;
                } else if self.restore_wanted {
                    self.restore_wanted = false;
                    self.decide(&mut out, "restore cancelled, back on battery");
                    self.begin(Sequence::Shed);
                }
                self.last_flags = flags;
                self.check_shed(flags, &mut out);
            }
            Some(flags) => {
                self.last_flags = flags;
                self.blind = Duration::ZERO;
                if self.outage {
                    self.mains += dt;
                    if self.mains >= self.policy.restore_mains {
                        self.want_restore(&mut out, "mains restore");
                    }
                }
            }
            None => {
                self.blind += dt;
                if self.outage && self.last_flags.raw_on_battery {
                    self.battery += dt;
                    self.check_shed(self.last_flags, &mut out);
                }
                if self.shed_started && self.blind >= self.policy.restore_mains * BLIND_RESTORE_FACTOR {
                    self.want_restore(&mut out, "blind restore, reads failing");
                }
            }
        }
        self.settle(&mut out);
        out
    }

    pub fn complete(&mut self, host: &str, command: Command, status: i32) -> Output {
        let mut out = Output::default();
        self.in_flight.remove(host);
        if status == 0 {
            self.failed.remove(host);
        } else {
            self.failed.insert(host.to_string());
        }
        self.last_action = format!("{host} {} status [{status}]", command.remote());
        self.settle(&mut out);
        out
    }

    pub fn metrics(&self, frame: &mut Frame) {
        frame.set_text(GUARD_STATE, &self.state().to_string());
        frame.set_bool(GUARD_LIVE, self.live);
        frame.set_int(GUARD_MAINS_SECONDS, self.mains.as_secs() as i64);
        frame.set_int(GUARD_BATTERY_SECONDS, self.battery.as_secs() as i64);
        frame.set_text(GUARD_FAILED_HOSTS, &self.failed_hosts().join(","));
        if !self.last_action.is_empty() {
            frame.set_text(GUARD_LAST_ACTION, &self.last_action);
        }
    }

    fn check_shed(&mut self, flags: Flags, out: &mut Output) {
        if self.shed_started || self.restore_wanted {
            return;
        }
        let timer_due = !flags.calibrating && self.battery >= self.policy.shed_battery;
        let lead_due = !flags.calibrating
            && self
                .policy
                .shed_runtime
                .zip(self.runtime_remaining)
                .is_some_and(|(runtime, runtime_remaining)| runtime_remaining <= runtime);
        let reason = if flags.low {
            "battery low"
        } else if lead_due {
            "estimated run time at the runtime"
        } else if timer_due {
            "shed time reached"
        } else {
            return;
        };
        self.decide(out, &format!("{DECISION_SHED} {reason}"));
        self.begin(Sequence::Shed);
    }

    fn want_restore(&mut self, out: &mut Output, reason: &str) {
        if self.restore_wanted || self.sequence == Some(Sequence::Restore) {
            return;
        }
        if self.shed_started {
            self.restore_wanted = true;
            self.decide(out, &format!("restore {reason}"));
        } else {
            self.decide(out, &format!("outage over {reason}"));
            self.finish(out);
        }
    }

    fn settle(&mut self, out: &mut Output) {
        if self.restore_wanted && self.sequence != Some(Sequence::Restore) {
            self.waves.clear();
            if self.in_flight.is_empty() {
                self.restore_wanted = false;
                self.begin(Sequence::Restore);
            }
        }
        if self.in_flight.is_empty() {
            match self.waves.pop_front() {
                Some(wave) => self.dispatch(wave, out),
                None => {
                    if self.sequence == Some(Sequence::Restore) {
                        self.sequence = None;
                        if self.shed_after_restore {
                            self.shed_after_restore = false;
                            self.shed_started = false;
                            self.mains = Duration::ZERO;
                        } else {
                            self.finish(out);
                        }
                    } else if self.sequence == Some(Sequence::Shed) {
                        self.sequence = None;
                    }
                }
            }
        }
    }

    fn begin(&mut self, sequence: Sequence) {
        self.sequence = Some(sequence);
        self.waves = self.plan(sequence);
        if sequence == Sequence::Shed {
            self.shed_started = true;
        }
    }

    fn dispatch(&mut self, wave: Vec<Call>, out: &mut Output) {
        for call in wave {
            self.in_flight.insert(call.host.clone());
            out.calls.push(call);
        }
    }

    fn finish(&mut self, out: &mut Output) {
        self.outage = false;
        self.shed_started = false;
        self.restore_wanted = false;
        self.battery = Duration::ZERO;
        self.mains = Duration::ZERO;
        out.ended = true;
    }

    fn decide(&self, out: &mut Output, detail: &str) {
        out.rows.push(Row {
            event: EVENT_DECISION,
            detail: format!(
                "{detail} guard_battery_seconds [{}] guard_mains_seconds [{}] guard_live [{}]",
                self.battery.as_secs(),
                self.mains.as_secs(),
                u8::from(self.live)
            ),
        });
    }

    fn plan(&self, sequence: Sequence) -> VecDeque<Vec<Call>> {
        let call = |host: &Host| Call {
            host: host.name.clone(),
            command: match sequence {
                Sequence::Restore => Command::Awake,
                Sequence::Shed if host.local => Command::AsleepShallow,
                Sequence::Shed => Command::AsleepDeep,
            },
        };
        let calls = |hosts: Vec<&Host>| hosts.into_iter().map(call).collect::<Vec<Call>>();
        let last = |host: &&Host| host.name == HOST_SHED_LAST;
        let mut waves = match sequence {
            Sequence::Shed => vec![
                calls(self.hosts.iter().filter(|host| !last(host)).collect()),
                calls(self.hosts.iter().filter(last).collect()),
            ],
            Sequence::Restore => vec![
                calls(self.hosts.iter().filter(|host| host.local).collect()),
                calls(self.hosts.iter().filter(|host| !host.local).filter(last).collect()),
                calls(
                    self.hosts
                        .iter()
                        .filter(|host| !host.local)
                        .filter(|host| !last(host))
                        .collect(),
                ),
            ],
        };
        waves.retain(|wave| !wave.is_empty());
        waves.into()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const SECOND: Duration = Duration::from_secs(1);

    fn policy() -> Policy {
        Policy {
            shed_battery: Duration::from_secs(120),
            restore_mains: Duration::from_secs(300),
            shed_runtime: None,
        }
    }

    fn hosts() -> Vec<Host> {
        ["mad", "max", "may", "meg"]
            .iter()
            .map(|name| Host {
                name: (*name).to_string(),
                address: format!("macmini-{name}"),
                local: *name == "max",
            })
            .collect()
    }

    fn guard() -> Guard {
        Guard::new(policy(), true, hosts())
    }

    fn battery() -> Flags {
        Flags {
            raw_on_battery: true,
            on_battery: true,
            ..Flags::default()
        }
    }

    fn mains() -> Flags {
        Flags::default()
    }

    fn run(guard: &mut Guard, flags: Option<Flags>, seconds: u64) -> Vec<Call> {
        let mut calls = Vec::new();
        for _ in 0..seconds {
            calls.extend(guard.step(flags, SECOND).calls);
        }
        calls
    }

    fn finish_all(guard: &mut Guard, calls: &[Call]) -> Vec<Call> {
        let mut next = Vec::new();
        for call in calls {
            next.extend(guard.complete(&call.host, call.command, 0).calls);
        }
        next
    }

    fn names(calls: &[Call]) -> Vec<&str> {
        let mut names: Vec<&str> = calls.iter().map(|call| call.host.as_str()).collect();
        names.sort_unstable();
        names
    }

    #[test]
    fn a_short_outage_never_sheds_and_resets_after_the_stable_period() {
        let mut guard = guard();
        assert!(run(&mut guard, Some(battery()), 119).is_empty());
        assert_eq!(guard.state(), State::Waiting);
        assert!(run(&mut guard, Some(mains()), 299).is_empty());
        assert!(guard.in_outage());
        let out = guard.step(Some(mains()), SECOND);
        assert!(out.ended);
        assert_eq!(guard.state(), State::Idle);
    }

    #[test]
    fn the_shed_time_sheds_the_followers_then_meg_and_max_shallow() {
        let mut guard = guard();
        run(&mut guard, Some(battery()), 119);
        let first = guard.step(Some(battery()), SECOND).calls;
        assert_eq!(names(&first), vec!["mad", "max", "may"]);
        assert!(first
            .iter()
            .all(|call| (call.host == "max") == (call.command == Command::AsleepShallow)));
        assert_eq!(guard.state(), State::Shedding);
        assert!(guard.complete("mad", Command::AsleepDeep, 0).calls.is_empty());
        assert!(guard.complete("max", Command::AsleepShallow, 0).calls.is_empty());
        let second = guard.complete("may", Command::AsleepDeep, 0).calls;
        assert_eq!(names(&second), vec!["meg"]);
        assert_eq!(guard.state(), State::Shedding);
        guard.complete("meg", Command::AsleepDeep, 0);
        assert_eq!(guard.state(), State::Holding);
        assert!(run(&mut guard, Some(battery()), 600).is_empty());
    }

    #[test]
    fn a_flapping_grid_sheds_at_the_accumulated_time() {
        let mut guard = guard();
        for _ in 0..2 {
            assert!(run(&mut guard, Some(battery()), 40).is_empty());
            assert!(run(&mut guard, Some(mains()), 100).is_empty());
        }
        assert!(!run(&mut guard, Some(battery()), 40).is_empty());
    }

    #[test]
    fn the_stable_period_of_mains_resets_the_clock() {
        let mut guard = guard();
        run(&mut guard, Some(battery()), 100);
        run(&mut guard, Some(mains()), 300);
        assert!(run(&mut guard, Some(battery()), 100).is_empty());
    }

    #[test]
    fn low_battery_sheds_at_once_even_during_calibration() {
        for (flags, sheds) in [
            (
                Flags {
                    raw_on_battery: true,
                    low: true,
                    ..Flags::default()
                },
                true,
            ),
            (
                Flags {
                    raw_on_battery: true,
                    low: true,
                    calibrating: true,
                    ..Flags::default()
                },
                true,
            ),
            (
                Flags {
                    raw_on_battery: true,
                    calibrating: true,
                    ..Flags::default()
                },
                false,
            ),
        ] {
            let mut guard = guard();
            assert_eq!(!run(&mut guard, Some(flags), 1).is_empty(), sheds, "flags {flags:?}");
        }
    }

    #[test]
    fn the_timer_shed_is_withheld_during_calibration() {
        let mut guard = guard();
        let calibrating = Some(Flags {
            raw_on_battery: true,
            calibrating: true,
            ..Flags::default()
        });
        assert!(run(&mut guard, calibrating, 600).is_empty());
    }

    #[test]
    fn failed_reads_do_not_stop_a_sequence_or_start_one() {
        let mut guard = guard();
        assert!(run(&mut guard, None, 1000).is_empty());
        assert_eq!(guard.state(), State::Idle);
        let calls = run(&mut guard, Some(battery()), 120);
        assert_eq!(calls.len(), 3);
        run(&mut guard, None, 100);
        assert_eq!(guard.state(), State::Shedding);
    }

    #[test]
    fn mains_after_a_shed_wakes_max_then_meg_then_the_rest() {
        let mut guard = guard();
        let shed = run(&mut guard, Some(battery()), 120);
        let second = finish_all(&mut guard, &shed);
        finish_all(&mut guard, &second);
        assert_eq!(guard.state(), State::Holding);
        assert!(run(&mut guard, Some(mains()), 299).is_empty());
        let first = guard.step(Some(mains()), SECOND).calls;
        assert_eq!(names(&first), vec!["max"]);
        assert_eq!(guard.state(), State::Restoring);
        let second = finish_all(&mut guard, &first);
        assert_eq!(names(&second), vec!["meg"]);
        let third = finish_all(&mut guard, &second);
        assert_eq!(names(&third), vec!["mad", "may"]);
        assert!(!guard.step(Some(mains()), SECOND).ended);
        let mut ended = false;
        for call in &third {
            ended |= guard.complete(&call.host, Command::Awake, 0).ended;
        }
        assert!(ended);
        assert_eq!(guard.state(), State::Idle);
    }

    #[test]
    fn a_restore_waits_for_a_shed_call_still_in_flight() {
        let mut guard = guard();
        let shed = run(&mut guard, Some(battery()), 120);
        assert_eq!(shed.len(), 3);
        assert!(run(&mut guard, Some(mains()), 300).is_empty());
        let after = guard.complete("mad", Command::AsleepDeep, 0).calls;
        assert!(after.is_empty());
        guard.complete("may", Command::AsleepDeep, 0);
        let awake = guard.complete("max", Command::AsleepShallow, 0).calls;
        assert_eq!(names(&awake), vec!["max"]);
        assert!(awake.iter().all(|call| call.command == Command::Awake));
    }

    #[test]
    fn reads_failing_after_a_shed_restore_blind_after_twice_the_stable_period() {
        let mut guard = guard();
        let shed = run(&mut guard, Some(battery()), 120);
        let second = finish_all(&mut guard, &shed);
        finish_all(&mut guard, &second);
        assert!(run(&mut guard, None, 599).is_empty());
        assert_eq!(names(&guard.step(None, SECOND).calls), vec!["max"]);
    }

    #[test]
    fn reads_failing_during_an_outage_keep_the_shed_clock_running() {
        let mut guard = guard();
        assert!(run(&mut guard, Some(battery()), 10).is_empty());
        assert!(run(&mut guard, None, 109).is_empty());
        assert_eq!(guard.step(None, SECOND).calls.len(), 3);
        assert_eq!(guard.state(), State::Shedding);
    }

    #[test]
    fn reads_failing_never_shed_or_restore_when_the_last_reading_was_mains() {
        let mut guard = guard();
        run(&mut guard, Some(battery()), 10);
        run(&mut guard, Some(mains()), 5);
        assert!(run(&mut guard, None, 5000).is_empty());
    }

    #[test]
    fn reads_failing_during_a_calibration_do_not_shed_on_the_timer() {
        let mut guard = guard();
        let calibrating = Some(Flags {
            raw_on_battery: true,
            calibrating: true,
            ..Flags::default()
        });
        run(&mut guard, calibrating, 10);
        assert!(run(&mut guard, None, 600).is_empty());
    }

    #[test]
    fn the_estimated_run_time_sheds_at_the_lead_and_not_before() {
        let mut policy = policy();
        policy.shed_runtime = Some(Duration::from_secs(60));
        let mut guard = Guard::new(policy, true, hosts());
        guard.set_runtime_remaining(Some(Duration::from_secs(61)));
        assert!(run(&mut guard, Some(battery()), 5).is_empty());
        guard.set_runtime_remaining(Some(Duration::from_secs(60)));
        assert_eq!(guard.step(Some(battery()), SECOND).calls.len(), 3);
    }

    #[test]
    fn a_missing_estimate_or_lead_leaves_the_timer_in_charge() {
        let mut guard = guard();
        guard.set_runtime_remaining(Some(Duration::from_secs(1)));
        assert!(run(&mut guard, Some(battery()), 10).is_empty());
        let mut policy = policy();
        policy.shed_runtime = Some(Duration::from_secs(60));
        let mut unestimated = Guard::new(policy, true, hosts());
        assert!(run(&mut unestimated, Some(battery()), 119).is_empty());
        assert_eq!(unestimated.step(Some(battery()), SECOND).calls.len(), 3);
    }

    #[test]
    fn the_estimated_run_time_is_withheld_during_a_calibration() {
        let mut policy = policy();
        policy.shed_runtime = Some(Duration::from_secs(60));
        let mut guard = Guard::new(policy, true, hosts());
        guard.set_runtime_remaining(Some(Duration::from_secs(5)));
        let calibrating = Some(Flags {
            raw_on_battery: true,
            calibrating: true,
            ..Flags::default()
        });
        assert!(run(&mut guard, calibrating, 30).is_empty());
    }

    #[test]
    fn a_failed_call_is_recorded_not_retried_and_cleared_by_a_later_success() {
        let mut guard = guard();
        let shed = run(&mut guard, Some(battery()), 120);
        assert_eq!(shed.len(), 3);
        assert!(guard.complete("may", Command::AsleepDeep, 4).calls.is_empty());
        assert_eq!(guard.failed_hosts(), vec!["may".to_string()]);
        guard.complete("may", Command::Awake, 0);
        assert!(guard.failed_hosts().is_empty());
    }

    #[test]
    fn a_resumed_guard_with_no_shed_on_record_sheds_once_the_time_is_past() {
        let mut guard = guard();
        guard.resume(Duration::from_secs(500), Duration::ZERO, false);
        assert_eq!(guard.step(Some(battery()), SECOND).calls.len(), 3);
    }

    #[test]
    fn a_resumed_guard_that_had_shed_does_not_shed_again_and_still_restores() {
        let mut guard = guard();
        guard.resume(Duration::from_secs(500), Duration::ZERO, true);
        assert!(run(&mut guard, Some(battery()), 10).is_empty());
        assert_eq!(guard.state(), State::Holding);
        assert!(run(&mut guard, Some(mains()), 299).is_empty());
        assert_eq!(names(&guard.step(Some(mains()), SECOND).calls), vec!["max"]);
    }

    #[test]
    fn mains_failing_again_before_the_restore_starts_cancels_it_and_sheds_every_host_afresh() {
        let mut guard = guard();
        assert_eq!(run(&mut guard, Some(battery()), 120).len(), 3);
        assert!(run(&mut guard, Some(mains()), 300).is_empty());
        assert!(run(&mut guard, Some(battery()), 1).is_empty());
        guard.complete("mad", Command::AsleepDeep, 0);
        guard.complete("may", Command::AsleepDeep, 0);
        let again = guard.complete("max", Command::AsleepShallow, 0).calls;
        assert_eq!(names(&again), vec!["mad", "max", "may"]);
        assert!(again.iter().all(|call| call.command != Command::Awake));
        let last = finish_all(&mut guard, &again);
        assert_eq!(names(&last), vec!["meg"]);
        assert!(run(&mut guard, Some(mains()), 299).is_empty());
        assert!(!guard.step(Some(mains()), SECOND).calls.is_empty() || guard.state() != State::Idle);
    }

    #[test]
    fn going_back_on_battery_during_a_restore_sheds_again_once_it_finishes_without_resetting_the_clock() {
        let mut guard = guard();
        let shed = run(&mut guard, Some(battery()), 120);
        let second = finish_all(&mut guard, &shed);
        finish_all(&mut guard, &second);
        run(&mut guard, Some(mains()), 300);
        assert_eq!(guard.state(), State::Restoring);
        assert!(run(&mut guard, Some(battery()), 1).is_empty());
        let mut next = finish_all(
            &mut guard,
            &[Call {
                host: "max".to_string(),
                command: Command::Awake,
            }],
        );
        while !next.is_empty() {
            next = finish_all(&mut guard, &next);
        }
        assert_ne!(guard.state(), State::Idle);
        assert_eq!(guard.step(Some(battery()), SECOND).calls.len(), 3);
    }

    #[test]
    fn a_resumed_guard_with_a_long_run_of_mains_ends_the_outage() {
        let mut guard = guard();
        guard.resume(Duration::from_secs(30), Duration::from_secs(299), false);
        assert!(guard.step(Some(mains()), SECOND).ended);
    }

    #[test]
    fn metrics_report_the_state_and_failed_hosts() {
        let mut guard = guard();
        run(&mut guard, Some(battery()), 120);
        guard.complete("mad", Command::AsleepDeep, 5);
        let mut frame = Frame::default();
        guard.metrics(&mut frame);
        assert_eq!(frame.text(GUARD_STATE), Some("shedding"));
        assert_eq!(frame.text(GUARD_FAILED_HOSTS), Some("mad"));
        assert!(frame.flag(GUARD_LIVE));
    }

    struct Lcg(u64);

    impl Lcg {
        fn next(&mut self, bound: u64) -> u64 {
            self.0 = self
                .0
                .wrapping_mul(6_364_136_223_846_793_005)
                .wrapping_add(1_442_695_040_888_963_407);
            (self.0 >> 33) % bound
        }
    }

    #[test]
    fn any_interleaving_never_double_dispatches_ends_once_and_leaves_every_called_host_awake() {
        let low = Flags {
            raw_on_battery: true,
            low: true,
            ..Flags::default()
        };
        let calibrating = Flags {
            raw_on_battery: true,
            calibrating: true,
            ..Flags::default()
        };
        for seed in 0..1500 {
            let mut random = Lcg(seed);
            let mut guard = guard();
            let mut in_flight: Vec<Call> = Vec::new();
            let mut last: std::collections::BTreeMap<String, Command> = std::collections::BTreeMap::new();
            let mut outages = 0;
            let mut ended = 0;
            let mut mode = 0;
            for tick in 0..4000 {
                let random_phase = tick < 1500;
                if tick % 25 == 0 {
                    mode = if random_phase { random.next(5) } else { 1 };
                }
                let flags = match mode {
                    0 => Some(battery()),
                    1 => Some(mains()),
                    2 => Some(calibrating),
                    3 => Some(low),
                    _ => None,
                };
                if matches!(flags, Some(flags) if flags.raw_on_battery) && !guard.in_outage() {
                    outages += 1;
                }
                let mut outputs = vec![guard.step(flags, SECOND)];
                let mut index = 0;
                while index < in_flight.len() {
                    if random.next(if random_phase { 4 } else { 2 }) == 0 {
                        let call = in_flight.remove(index);
                        let status = i32::from(random.next(5) == 0);
                        outputs.push(guard.complete(&call.host, call.command, status));
                    } else {
                        index += 1;
                    }
                }
                for output in outputs {
                    for call in output.calls {
                        assert!(
                            !in_flight.iter().any(|flying| flying.host == call.host),
                            "seed {seed} tick {tick} double dispatch to [{}]",
                            call.host
                        );
                        last.insert(call.host.clone(), call.command);
                        in_flight.push(call);
                    }
                    ended += usize::from(output.ended);
                }
            }
            assert!(in_flight.is_empty(), "seed {seed} calls never finished");
            assert_eq!(guard.state(), State::Idle, "seed {seed} not idle");
            assert!(ended <= outages, "seed {seed} ended [{ended}] outages [{outages}]");
            assert!(
                last.values().all(|command| *command == Command::Awake),
                "seed {seed} left a host asleep {last:?}"
            );
        }
    }
}
