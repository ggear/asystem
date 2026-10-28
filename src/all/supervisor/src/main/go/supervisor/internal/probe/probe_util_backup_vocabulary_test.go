package probe

import (
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"testing"
)

func TestProbeUtilBackupVocabulary_ShellStatesMirrorTheDeclaredWords(t *testing.T) {
	_, here, _, _ := runtime.Caller(0)
	repo := filepath.Join(filepath.Dir(here), "../../../../../../../../..")
	read := func(relative string) string {
		data, err := os.ReadFile(filepath.Join(repo, relative))
		if err != nil {
			t.Fatalf("read [%s]: %v", relative, err)
		}
		return string(data)
	}
	declared := map[string]string{}
	for _, match := range regexp.MustCompile(`\bBackupState([A-Za-z]+)\s*=\s*"([a-z]+)"`).FindAllStringSubmatch(read("src/all/supervisor/src/main/go/supervisor/internal/metric/metric_schema.go"), -1) {
		declared[strings.ToUpper(match[1])] = match[2]
	}
	mirrored := map[string]string{}
	for _, match := range regexp.MustCompile(`(?m)^BACKUP_STATE_([A-Z]+)="([a-z]+)"$`).FindAllStringSubmatch(read("src/all/_/src/build/resources/backup_manifest.sh"), -1) {
		mirrored[match[1]] = match[2]
	}
	if len(declared) == 0 || len(mirrored) == 0 {
		t.Fatalf("parsed declared [%d] and mirrored [%d] states, want both non-empty", len(declared), len(mirrored))
	}
	for name, word := range mirrored {
		if declared[name] != word {
			t.Errorf("BACKUP_STATE_%s = %q, want the declared %q", name, word, declared[name])
		}
	}
}
