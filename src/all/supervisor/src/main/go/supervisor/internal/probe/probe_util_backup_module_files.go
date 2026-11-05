package probe

import (
	"context"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"syscall"
	"time"
)

func BackupModuleTarget(_ context.Context, request BackupModuleRequest, stdout, stderr io.Writer) int {
	module, source, root, ok := resolveBackupModule(request, stderr, 3)
	if !ok {
		return 2
	}
	path, err := nameModuleArtefact(request, module, source, root, request.Arguments[1], request.Arguments[2])
	if err != nil {
		fmt.Fprintf(stderr, "Backup failed [%v]\n", err)
		return 1
	}
	fmt.Fprintln(stdout, path)
	return 0
}

func BackupModuleFiles(ctx context.Context, request BackupModuleRequest, stdout, stderr io.Writer) int {
	module, source, root, ok := resolveBackupModule(request, stderr, 1)
	if !ok {
		return 2
	}
	if request.Root == "" || len(request.Includes) == 0 {
		fmt.Fprintln(stderr, "Nothing to back up, pass the root and the include array to backup_files")
		return 1
	}
	dir := filepath.Join(source, request.Root)
	var missing []string
	for _, include := range request.Includes {
		if _, err := os.Lstat(filepath.Join(dir, include)); err != nil {
			missing = append(missing, include)
		}
	}
	if len(missing) > 0 {
		fmt.Fprintf(stderr, "Declared paths [%s] are absent from [%s]\n", strings.Join(missing, " "), dir)
		return 1
	}
	unmatched := unmatchedModuleEntries(dir, request.Includes, request.Excludes)
	target, err := nameModuleArtefact(request, module, source, root, backupFullSuffix, "tar.gz")
	if err != nil {
		fmt.Fprintf(stderr, "Backup failed [%v]\n", err)
		return 1
	}
	if err := os.WriteFile(filepath.Join(request.State, moduleIncludesLeaf), []byte(strings.Join(request.Includes, "\n")+"\n"), 0o644); err != nil {
		fmt.Fprintf(stderr, "Backup failed [%v]\n", err)
		return 1
	}
	if len(unmatched) > 0 {
		fmt.Fprintf(stdout, "Not backed up and not excluded [%s]\n", strings.Join(unmatched, " "))
	}
	attempts := 1
	if request.Live == "atomic" {
		attempts = moduleAtomicAttempts
	}
	arguments := []string{"--create", "--directory", dir, "--numeric-owner", "--preserve-permissions", "--exclude=" + treeBackupDirectory}
	for _, exclude := range request.Excludes {
		arguments = append(arguments, "--exclude="+exclude)
	}
	arguments = append(arguments, "--file", "-", "--")
	arguments = append(arguments, request.Includes...)
	archived := func() int {
		file, createErr := os.Create(target + ".tmp")
		if createErr != nil {
			fmt.Fprintf(stderr, "Backup [%s] could not be created [%v]\n", target+".tmp", createErr)
			return 2
		}
		defer func() { _ = file.Close() }()
		tar, gzip := exec.CommandContext(ctx, "tar", arguments...), exec.CommandContext(ctx, "gzip")
		tar.Stderr, gzip.Stderr, gzip.Stdout = stderr, stderr, file
		pipe, pipeErr := tar.StdoutPipe()
		if pipeErr != nil {
			return 2
		}
		gzip.Stdin = pipe
		if gzip.Start() != nil {
			return 2
		}
		tarErr := tar.Run()
		_ = pipe.Close()
		gzipErr := gzip.Wait()
		var exit *exec.ExitError
		switch {
		case errors.As(tarErr, &exit):
			if status, isWait := exit.Sys().(syscall.WaitStatus); isWait {
				return status.ExitStatus()
			}
			return 2
		case tarErr != nil || gzipErr != nil:
			return 2
		}
		return 0
	}
	for attempt := 1; ; attempt++ {
		status := archived()
		if status != 1 || attempt >= attempts {
			if status != 0 {
				fmt.Fprintf(stderr, "Tar exited [%d]\n", status)
				return 1
			}
			return 0
		}
		fmt.Fprintf(stderr, "Archive changed while being read, retrying attempt [%d] of [%d]\n", attempt, attempts)
		time.Sleep(moduleAtomicPause)
	}
}

func nameModuleArtefact(request BackupModuleRequest, module, source, root, suffix, extension string) (string, error) {
	if suffix == "" || extension == "" {
		return "", errors.New("cannot name the backup, pass the suffix and the extension to backup_target")
	}
	if suffix == backupDeltaSuffix && parentBackupRun(root, request.Run) == "" {
		return "", errors.New("cannot write a delta, no full backup is held locally for it to hang off")
	}
	path := filepath.Join(root, request.Run, fmt.Sprintf("%s_at_%s_from_%s%s.%s", module, request.Run, filepath.Base(source), suffix, extension))
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return "", err
	}
	if err := os.WriteFile(filepath.Join(request.State, moduleTargetLeaf), []byte(path+"\n"), 0o644); err != nil {
		return "", err
	}
	return path, nil
}

func unmatchedModuleEntries(dir string, includes, excludes []string) []string {
	deepest := 1
	for _, path := range append(append([]string{}, includes...), excludes...) {
		if depth := strings.Count(path, "/") + 1; depth > deepest {
			deepest = depth
		}
	}
	var entries []string
	_ = filepath.WalkDir(dir, func(path string, entry fs.DirEntry, err error) error {
		if err != nil || path == dir {
			return nil
		}
		relative, _ := filepath.Rel(dir, path)
		if strings.Count(relative, "/")+1 > deepest {
			if entry.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}
		entries = append(entries, relative)
		return nil
	})
	sort.Strings(entries)
	patterns := make([]*regexp.Regexp, len(excludes))
	for index, exclude := range excludes {
		patterns[index] = compileShellPattern(exclude)
	}
	var unmatched []string
	covered := func(entry string) bool {
		for _, path := range unmatched {
			if strings.HasPrefix(entry, path+"/") {
				return true
			}
		}
		for _, path := range includes {
			if entry == path || strings.HasPrefix(entry, path+"/") || strings.HasPrefix(path, entry+"/") {
				return true
			}
		}
		for index, path := range excludes {
			if patterns[index].MatchString(entry) || strings.HasPrefix(path, entry+"/") {
				return true
			}
		}
		return false
	}
	for _, entry := range entries {
		if entry == treeBackupDirectory || strings.HasPrefix(entry, treeBackupDirectory+"/") || covered(entry) {
			continue
		}
		unmatched = append(unmatched, entry)
	}
	return unmatched
}

func compileShellPattern(pattern string) *regexp.Regexp {
	var out strings.Builder
	for index := 0; index < len(pattern); index++ {
		switch character := pattern[index]; character {
		case '*':
			out.WriteString(".*")
		case '?':
			out.WriteString(".")
		case '[':
			end := strings.IndexByte(pattern[index:], ']')
			if end < 0 {
				out.WriteString(`\[`)
				continue
			}
			class := pattern[index+1 : index+end]
			if strings.HasPrefix(class, "!") {
				class = "^" + class[1:]
			}
			out.WriteString("[" + class + "]")
			index += end
		default:
			out.WriteString(regexp.QuoteMeta(string(character)))
		}
	}
	body := out.String()
	return regexp.MustCompile(`^(` + body + `|(.*/)?` + body + `|` + body + `/.*|(.*/)?` + body + `/.*)$`)
}

const (
	moduleAtomicAttempts = 3
	moduleAtomicPause    = 10 * time.Second
)
