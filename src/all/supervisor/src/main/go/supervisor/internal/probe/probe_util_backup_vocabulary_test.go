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
	if len(declared) == 0 {
		t.Fatalf("parsed no declared states")
	}
	for _, source := range []string{"backup_manifest.sh", "restore_chain.sh"} {
		mirrored := map[string]string{}
		for _, match := range regexp.MustCompile(`(?m)^BACKUP_STATE_([A-Z]+)="([a-z]+)"$`).FindAllStringSubmatch(read("src/all/_/src/build/resources/"+source), -1) {
			mirrored[match[1]] = match[2]
		}
		if len(mirrored) == 0 {
			t.Fatalf("parsed no mirrored states from [%s]", source)
		}
		for name, word := range mirrored {
			if declared[name] != word {
				t.Errorf("%s BACKUP_STATE_%s = %q, want the declared %q", source, name, word, declared[name])
			}
		}
	}
}
