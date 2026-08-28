package probe

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"slices"
	"sort"
	"strings"
	"time"

	"supervisor/internal/config"
	"supervisor/internal/metric"
	"supervisor/internal/scribe"
)

const (
	driveBlockPath           = "sys/class/block"
	driveRotationalPath      = "queue/rotational"
	driveRemovablePath       = "removable"
	driveVendorPath          = "device/vendor"
	driveModelPath           = "device/model"
	driveUnknownHardware     = "unknown hardware"
	driveVendorWidth         = 8
	driveVendorPlaceholder   = "ATA"
	driveFlagSet             = "1"
	driveTransportUSB        = "usb"
	driveTransportInternal   = "internal"
	driveSmartCommand        = "smartctl"
	driveSmartExitUnreadable = 0b11
	drivePrefixNVME          = "nvme"
	driveNamespaceFirst      = "n1"
	driveKindNVME            = "nvme"
	driveKindSAT             = "sat"
	driveKindRealtek         = "sntrealtek"
	driveKindJMicron         = "sntjmicron"
	driveKindASMedia         = "sntasmedia"
	driveKindSCSI            = "scsi"
	driveResolveMax          = 8
	bytesPerSector           = 512.0
	bytesPerDataUnit         = 512000.0
	bytesPerGiB              = 1073741824.0
	bytesPerTB               = 1000000000000.0
	driveAttributeErrors     = 1
	driveAttributeWritten    = 241
	driveAttributeWrittenAlt = 246
)

type driveWear struct {
	kernel     string
	model      string
	reason     string
	life       float64
	rated      bool
	errored    bool
	unreadable bool
}

type driveIdentity struct {
	kernel     string
	node       string
	transport  string
	kinds      []string
	hardware   string
	excluded   string
	rotational bool
	removable  bool
	model      string
	rating     float64
	baseline   int64
	rated      bool
	identified bool
	warned     bool
}

func (s *mountSet) lifeUsedDrives() (int8, derivation, error) {
	taken, err := s.snapshot()
	if err != nil {
		return 0, derivation{}, err
	}
	worst := 0.0
	worstAt := ""
	rated := 0
	errored := 0
	for _, drive := range taken.drives {
		if drive.errored {
			errored++
		}
		if !drive.rated {
			continue
		}
		rated++
		if drive.life > worst {
			worst = drive.life
			worstAt = drive.kernel + "=" + drive.model
		}
	}
	if unreadable := driveUnreadable(taken.drives); len(unreadable) > 0 {
		return 0, derivation{}, fmt.Errorf("no drive wear read, [%d] of [%d] drives unreadable by smartctl [%s] [%w]",
			len(unreadable), len(taken.drives), strings.Join(unreadable, ", "), errEnvironment)
	}
	if rated == 0 {
		return 0, derivedInert(scribe.ActionSample, "computed [  0] pct life used, none of [%d] drives are rated and readable so the metric is inert and always ok, unrated [%s]",
			len(taken.drives), driveSummary(taken.drives)), nil
	}
	return int8Percent(worst), derived(scribe.ActionSample, "computed [%3d] pct life used, most worn of [%d] rated drives [%s], errored [%d] drives, unreadable [%d] drives, ok pulse at [<=90] pct trend at [<=80] pct and no new errors",
		int8Percent(worst), rated, worstAt, errored, len(driveUnreadable(taken.drives))), nil
}

func (s *mountSet) failedDrives() (int8, derivation, error) {
	taken, err := s.snapshot()
	if err != nil {
		return 0, derivation{}, err
	}
	if unreadable := driveUnreadable(taken.drives); len(unreadable) > 0 {
		return 0, derivation{}, fmt.Errorf("no drive errors read, [%d] of [%d] drives unreadable [%s] [%w]",
			len(unreadable), len(taken.drives), strings.Join(unreadable, ", "), errEnvironment)
	}
	if len(taken.drives) == 0 {
		return 0, derivedInert(scribe.ActionSample, "computed [  0] pct failed drive, host reports no drive so the metric is inert and always ok"), nil
	}
	errored := 0
	var failed []string
	for _, drive := range taken.drives {
		if drive.errored {
			errored++
			failed = append(failed, drive.kernel+"="+drive.model)
		}
	}
	return int8Percent(float64(errored) / float64(len(taken.drives)) * 100.0), derived(scribe.ActionSample, "computed [%3d] pct failed drive, errored [%d] of [%d] drives, ok only at [0] pct, failed [%s]",
		int8Percent(float64(errored)/float64(len(taken.drives))*100.0), errored, len(taken.drives), strings.Join(failed, ", ")), nil
}

func (s *mountSet) worn(mounts []mountUsage, collectStart time.Time) ([]driveWear, time.Time) {
	physicals := s.attached(mounts)
	s.mutex.Lock()
	previous, window := s.current, s.window
	s.mutex.Unlock()
	if previous != nil && config.SinceIncludingSuspend(previous.read) < window && slices.Equal(physicals, driveKernels(previous.drives)) {
		scribe.Log(scribe.SourceProbeDrives, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Debug("retained", collectStart, "[%3d] drive readings aged [%s] within [%s], not re-read", len(previous.drives), config.SinceIncludingSuspend(previous.read).Truncate(time.Second), window)
		return previous.drives, previous.read
	}
	drives := make([]driveWear, 0, len(physicals))
	for _, physical := range physicals {
		drives = append(drives, s.reading(physical))
	}
	return drives, config.NowIncludingSuspend()
}

func (s *mountSet) attached(mounts []mountUsage) []string {
	seen := map[string]bool{}
	var physicals []string
	for _, mount := range mounts {
		if mount.remote || !strings.HasPrefix(mount.device, "/dev/") {
			continue
		}
		physical := s.physical(mount.device)
		if physical == "" || seen[physical] {
			continue
		}
		seen[physical] = true
		physicals = append(physicals, physical)
	}
	sort.Strings(physicals)
	return physicals
}

func driveKernels(drives []driveWear) []string {
	kernels := make([]string, 0, len(drives))
	for _, drive := range drives {
		kernels = append(kernels, drive.kernel)
	}
	return kernels
}

func (s *mountSet) physical(device string) string {
	s.mutex.Lock()
	cached, found := s.physicals[device]
	s.mutex.Unlock()
	if found {
		return cached
	}
	resolved := s.resolve(strings.TrimPrefix(device, "/dev/"), 0)
	s.mutex.Lock()
	s.physicals[device] = resolved
	s.mutex.Unlock()
	return resolved
}

func (s *mountSet) resolve(kernel string, depth int) string {
	if kernel == "" || depth > driveResolveMax {
		return ""
	}
	if after, ok := strings.CutPrefix(kernel, "mapper/"); ok {
		return s.resolve(s.mapper(after), depth+1)
	}
	block := filepath.Join(s.root, driveBlockPath, kernel)
	target, err := os.Readlink(block)
	if err != nil {
		return ""
	}
	if slaves, err := os.ReadDir(filepath.Join(block, "slaves")); err == nil && len(slaves) > 0 {
		return s.resolve(slaves[0].Name(), depth+1)
	}
	if _, err := os.Stat(filepath.Join(block, "partition")); err == nil {
		return s.resolve(filepath.Base(filepath.Dir(target)), depth+1)
	}
	if controller := driveControllerOf(target); controller != "" {
		return controller
	}
	return kernel
}

func driveUnreadable(drives []driveWear) []string {
	var unreadable []string
	for _, drive := range drives {
		if drive.unreadable {
			unreadable = append(unreadable, drive.kernel+"="+drive.reason)
		}
	}
	sort.Strings(unreadable)
	return unreadable
}

func (s *mountSet) namespace(physical string) string {
	if !driveControllerPattern.MatchString(physical) {
		return physical
	}
	entries, err := os.ReadDir(filepath.Join(s.root, driveBlockPath))
	if err != nil {
		return physical + driveNamespaceFirst
	}
	names := make([]string, 0, len(entries))
	for _, entry := range entries {
		if driveNamespacePattern.MatchString(entry.Name()) && strings.HasPrefix(entry.Name(), physical+"n") {
			names = append(names, entry.Name())
		}
	}
	if len(names) == 0 {
		return physical + driveNamespaceFirst
	}
	sort.Strings(names)
	return names[0]
}

func driveKinds(physical string) []string {
	if strings.HasPrefix(physical, drivePrefixNVME) {
		return []string{driveKindNVME}
	}
	return []string{driveKindSAT, driveKindRealtek, driveKindJMicron, driveKindASMedia, driveKindSCSI}
}

func (s *mountSet) mapper(name string) string {
	entries, err := os.ReadDir(filepath.Join(s.root, driveBlockPath))
	if err != nil {
		return ""
	}
	for _, entry := range entries {
		if !strings.HasPrefix(entry.Name(), "dm-") {
			continue
		}
		data, err := os.ReadFile(filepath.Join(s.root, driveBlockPath, entry.Name(), "dm", "name"))
		if err != nil {
			continue
		}
		if strings.TrimSpace(string(data)) == name {
			return entry.Name()
		}
	}
	return ""
}

func (s *mountSet) reading(physical string) driveWear {
	identity := s.identity(physical)
	readingStart := time.Now()
	if driveIgnoring(identity.hardware) {
		if !identity.warned {
			identity.warned = true
			scribe.Log(scribe.SourceProbeDrives, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Info("excluded", readingStart, "[%s] at [%s] over [%s] as [%s] is declared not solid state, no wear rating applies so it is not counted in wear", physical, identity.node, identity.transport, identity.hardware)
		}
		scribe.Log(scribe.SourceProbeDrives, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Debug("examined", readingStart, "[%s] not considered, declared not solid state, as [%s] over [%s]", physical, identity.hardware, identity.transport)
		return driveWear{kernel: physical}
	}
	report, err := s.smart(identity.node, identity.kinds)
	if err != nil {
		if !identity.warned {
			identity.warned = true
			scribe.Log(scribe.SourceProbeDrives, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Warn("excluded", readingStart, "[%s] unreadable at [%s] over [%s] as [%s] with rotational [%v] removable [%v], not counted in wear, with [%v]", physical, identity.node, identity.transport, identity.hardware, identity.rotational, identity.removable, err)
		}
		scribe.Log(scribe.SourceProbeDrives, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Debug("examined", readingStart, "[%s] not considered, unreadable by smartctl, as [%s] over [%s]", physical, identity.hardware, identity.transport)
		return driveWear{kernel: physical, model: identity.model, unreadable: true, reason: err.Error()}
	}
	s.identifyFromReport(identity, report, readingStart)
	wear := driveWear{kernel: physical, model: identity.model, rated: identity.rated}
	if report.errors > identity.baseline {
		wear.errored = true
	}
	scribe.Log(scribe.SourceProbeDrives, scribe.SubjectMetric(metric.MetricHostFailedDrives), scribe.ActionSample).Debug("examined", readingStart, "[%s] errors [%3d] baseline [%3d] increased [%v], as [%s]", physical, report.errors, identity.baseline, wear.errored, identity.named())
	if !identity.rated {
		scribe.Log(scribe.SourceProbeDrives, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Debug("examined", readingStart, "[%s] not considered, %s, as [%s]", physical, identity.excluded, identity.named())
		return wear
	}
	computed := driveComputed(report.written, identity.rating)
	wear.life = driveLife(computed, report.estimate, report.estimated)
	estimate := "none"
	if report.estimated {
		estimate = fmt.Sprintf("%.1f", report.estimate)
	}
	scribe.Log(scribe.SourceProbeDrives, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Debug("examined", readingStart, "[%s] life [%3d] pct, computed [%.1f] drive [%s] pct, written [%.1f] of [%.0f] TB, as [%s]", physical, int8Percent(wear.life), computed, estimate, report.written/bytesPerTB, identity.rating, identity.named())
	return wear
}

func driveComputed(written, rating float64) float64 {
	if written <= 0 || rating <= 0 {
		return 0
	}
	return written / (rating * bytesPerTB) * 100.0
}

func driveLife(computed, estimate float64, estimated bool) float64 {
	if estimated && estimate > computed {
		return estimate
	}
	return computed
}

func (s *mountSet) identifyFromReport(identity *driveIdentity, report smartReport, identifyStart time.Time) {
	if identity.identified {
		return
	}
	identity.identified = true
	identity.model = report.model
	identity.baseline = report.errors
	switch {
	case !report.supported:
		identity.excluded = "reports no smart support"
		scribe.Log(scribe.SourceProbeDrives, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Info("excluded", identifyStart, "[%s] at [%s] reports no smart support with [%s], not counted in wear", identity.kernel, identity.node, report.reason)
	case driveRatings[report.model] > 0:
		identity.rating = driveRatings[report.model]
		identity.rated = true
	default:
		identity.excluded = "model absent from the ratings"
		scribe.Log(scribe.SourceProbeDrives, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionSample).Info("unlisted", identifyStart, "[%s] model [%s] absent from the ratings, not counted in wear", identity.kernel, report.model)
	}
}

func (s *mountSet) topology(physical string) (bool, bool, string, string) {
	rotational := s.flagged(physical, driveRotationalPath)
	removable := s.flagged(physical, driveRemovablePath)
	transport := driveTransportInternal
	if target, err := os.Readlink(filepath.Join(s.root, driveBlockPath, physical)); err == nil {
		for segment := range strings.SplitSeq(target, "/") {
			if strings.HasPrefix(segment, driveTransportUSB) {
				transport = driveTransportUSB
				break
			}
		}
	}
	hardware := driveHardware(s.described(physical, driveVendorPath), s.described(physical, driveModelPath))
	return rotational, removable, transport, hardware
}

func (s *mountSet) described(physical, path string) string {
	data, err := os.ReadFile(filepath.Join(s.root, driveBlockPath, physical, path))
	if err != nil {
		return ""
	}
	return strings.TrimRight(string(data), "\n")
}

func driveHardware(vendor, model string) string {
	spilled := len(vendor) == driveVendorWidth && !strings.HasSuffix(vendor, " ") && !strings.HasPrefix(model, " ")
	vendor = strings.TrimSpace(vendor)
	model = strings.TrimSpace(model)
	switch {
	case spilled:
		return vendor + model
	case vendor == "" || vendor == driveVendorPlaceholder:
		if model == "" {
			return driveUnknownHardware
		}
		return model
	case model == "":
		return vendor
	default:
		return vendor + " " + model
	}
}

func (s *mountSet) flagged(physical, path string) bool {
	data, err := os.ReadFile(filepath.Join(s.root, driveBlockPath, physical, path))
	if err != nil {
		return false
	}
	return strings.TrimSpace(string(data)) == driveFlagSet
}

func (i *driveIdentity) named() string {
	if i.model != "" {
		return i.model
	}
	return i.hardware
}

func (s *mountSet) identity(physical string) *driveIdentity {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	if cached, found := s.identities[physical]; found {
		return cached
	}
	topologyStart := time.Now()
	identity := &driveIdentity{kernel: physical, node: filepath.Join(s.root, "dev", s.namespace(physical)), kinds: driveKinds(physical)}
	identity.rotational, identity.removable, identity.transport, identity.hardware = s.topology(physical)
	s.identities[physical] = identity
	scribe.Log(scribe.SourceProbeDrives, scribe.SubjectMetric(metric.MetricHostLifeUsedDrives), scribe.ActionDiscover).Debug("topology", topologyStart, "[%s] as [%s] over [%s], rotational [%v] removable [%v], node [%s], probing as [%s]",
		physical, identity.hardware, identity.transport, identity.rotational, identity.removable, identity.node, strings.Join(identity.kinds, ","))
	return identity
}

type smartReport struct {
	data      bool
	estimated bool
	estimate  float64
	model     string
	reason    string
	written   float64
	errors    int64
	supported bool
}

func driveSmart(node string, kinds []string) (smartReport, error) {
	tried := map[string][]string{}
	var reasons []string
	var barren *smartReport
	for _, kind := range kinds {
		report, err := driveSmartKind(node, kind)
		if err == nil {
			if report.data {
				return report, nil
			}
			if barren == nil {
				barren = &report
			}
			continue
		}
		failure := smartFailure{}
		if !errors.As(err, &failure) {
			failure = smartFailure{kind: kind, reason: err.Error()}
		}
		if _, seen := tried[failure.reason]; !seen {
			reasons = append(reasons, failure.reason)
		}
		tried[failure.reason] = append(tried[failure.reason], failure.kind)
	}
	if barren != nil {
		return *barren, nil
	}
	folded := make([]string, 0, len(reasons))
	for _, reason := range reasons {
		folded = append(folded, fmt.Sprintf("%s as [%s]", reason, strings.Join(tried[reason], "] or [")))
	}
	return smartReport{}, errors.New(strings.Join(folded, ", "))
}

type smartFailure struct {
	kind   string
	reason string
}

func (e smartFailure) Error() string {
	return fmt.Sprintf("%s as [%s]", e.reason, e.kind)
}

func driveSmartKind(node, kind string) (smartReport, error) {
	ctx, cancel := context.WithTimeout(context.Background(), mountDeadline)
	defer cancel()
	output, err := exec.CommandContext(ctx, driveSmartCommand, "--json", "-d", kind, "-a", node).Output()
	if len(output) == 0 {
		if err == nil {
			return smartReport{}, smartFailure{kind: kind, reason: "returned no output"}
		}
		return smartReport{}, smartFailure{kind: kind, reason: fmt.Sprintf("failed with [%v]", err)}
	}
	var decoded struct {
		ModelName string `json:"model_name"`
		Smartctl  struct {
			ExitStatus int `json:"exit_status"`
			Messages   []struct {
				String string `json:"string"`
			} `json:"messages"`
		} `json:"smartctl"`
		SmartSupport struct {
			Available bool `json:"available"`
		} `json:"smart_support"`
		NvmeLog struct {
			DataUnitsWritten float64 `json:"data_units_written"`
			ErrorLogEntries  int64   `json:"num_err_log_entries"`
			PercentageUsed   float64 `json:"percentage_used"`
		} `json:"nvme_smart_health_information_log"`
		AtaAttributes struct {
			Table []struct {
				ID   int    `json:"id"`
				Name string `json:"name"`
				Raw  struct {
					Value float64 `json:"value"`
				} `json:"raw"`
			} `json:"table"`
		} `json:"ata_smart_attributes"`
	}
	if err := json.Unmarshal(output, &decoded); err != nil {
		return smartReport{}, smartFailure{kind: kind, reason: fmt.Sprintf("returned output that is not parseable with [%v]", err)}
	}
	if decoded.Smartctl.ExitStatus&driveSmartExitUnreadable != 0 {
		return smartReport{}, smartFailure{kind: kind, reason: fmt.Sprintf("could not open the node with status [%d] and [%s]", decoded.Smartctl.ExitStatus, driveSmartMessages(decoded.Smartctl.Messages))}
	}
	report := smartReport{model: strings.TrimSpace(decoded.ModelName)}
	report.supported = decoded.SmartSupport.Available || report.model != ""
	if decoded.NvmeLog.DataUnitsWritten > 0 {
		report.data = true
		report.written = decoded.NvmeLog.DataUnitsWritten * bytesPerDataUnit
		report.errors = decoded.NvmeLog.ErrorLogEntries
		report.estimated = true
		report.estimate = decoded.NvmeLog.PercentageUsed
		return report, nil
	}
	report.data = len(decoded.AtaAttributes.Table) > 0
	for _, attribute := range decoded.AtaAttributes.Table {
		switch attribute.ID {
		case driveAttributeErrors:
			report.errors = int64(attribute.Raw.Value)
		case driveAttributeWritten, driveAttributeWrittenAlt:
			if written := driveWritten(attribute.ID, attribute.Name, attribute.Raw.Value); written > 0 && (report.written == 0 || attribute.ID == driveAttributeWritten) {
				report.written = written
			}
		}
	}
	if len(decoded.AtaAttributes.Table) == 0 && decoded.NvmeLog.DataUnitsWritten == 0 {
		if decoded.Smartctl.ExitStatus != 0 || len(decoded.Smartctl.Messages) > 0 {
			return smartReport{}, smartFailure{kind: kind, reason: fmt.Sprintf("read no data with status [%d] and [%s]", decoded.Smartctl.ExitStatus, driveSmartMessages(decoded.Smartctl.Messages))}
		}
		report.supported = false
	}
	return report, nil
}

func driveSmartMessages(messages []struct {
	String string `json:"string"`
}) string {
	texts := make([]string, 0, len(messages))
	for _, message := range messages {
		if text := strings.TrimSpace(message.String); text != "" {
			texts = append(texts, text)
		}
	}
	if len(texts) == 0 {
		return "no message"
	}
	return strings.Join(texts, ", ")
}

func driveWritten(id int, name string, raw float64) float64 {
	if id == driveAttributeWrittenAlt && strings.Contains(strings.ToLower(name), "erase") {
		return 0
	}
	if strings.Contains(strings.ToLower(name), "gib") {
		return raw * bytesPerGiB
	}
	return raw * bytesPerSector
}

func driveSummary(drives []driveWear) string {
	if len(drives) == 0 {
		return "none"
	}
	named := make([]string, 0, len(drives))
	for _, drive := range drives {
		model := drive.model
		if model == "" {
			model = "unreadable"
		}
		named = append(named, drive.kernel+"="+model)
	}
	return strings.Join(named, " ")
}

func driveControllerOf(target string) string {
	segments := strings.Split(target, "/")
	for index, segment := range segments {
		if segment == "nvme" && index+1 < len(segments) {
			return segments[index+1]
		}
	}
	return ""
}

func driveIgnoring(hardware string) bool {
	lowered := strings.ToLower(hardware)
	for _, ignored := range driveIgnored {
		if strings.Contains(lowered, ignored) {
			return true
		}
	}
	return false
}

var driveIgnored = []string{"flash drive"}

var driveRatings = map[string]float64{
	"Lexar SSD NM790 4TB":   3000,
	"CT4000MX500SSD1":       1000,
	"CT4000P3PSSD8":         800,
	"CT2000MX500SSD1":       700,
	"Lexar SSD NQ710 2TB":   680,
	"CT2000P2SSD8":          600,
	"CT1000MX500SSD1":       360,
	"APPLE SSD AP0512Z":     300,
	"CT500MX500SSD1":        180,
	"KINGSTON SA400S37480G": 160,
	"CT480BX500SSD1":        120,
	"ST2000LM007-1R8174":    0,
}

var (
	driveControllerPattern = regexp.MustCompile(`^nvme[0-9]+$`)
	driveNamespacePattern  = regexp.MustCompile(`^nvme[0-9]+n[0-9]+$`)
)
