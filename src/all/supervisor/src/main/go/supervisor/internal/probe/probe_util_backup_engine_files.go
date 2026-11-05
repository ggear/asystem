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

type backupFilesRequest struct {
	module   string
	source   string
	run      string
	state    string
	root     string
	live     string
	includes []string
	excludes []string
}

const (
	backupAtomicAttempts = 3
	backupAtomicPause    = 10 * time.Second
)

func backupEngineNamed(request backupFilesRequest, suffix, extension string) (string, error) {
	if suffix == "" || extension == "" {
		return "", errors.New("cannot name the backup, pass the suffix and the extension to backup_target")
	}
	root := filepath.Join(filepath.Dir(request.source), treeBackupDirectory)
	if suffix == backupDeltaSuffix && backupParent(root, request.run) == "" {
		return "", errors.New("cannot write a delta, no full backup is held locally for it to hang off")
	}
	path := filepath.Join(root, request.run, backupEngineName(request.module, request.run, filepath.Base(request.source), suffix, extension))
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return "", err
	}
	if err := os.WriteFile(filepath.Join(request.state, backupTargetLeaf), []byte(path+"\n"), 0o644); err != nil {
		return "", err
	}
	return path, nil
}

func backupEngineFiles(ctx context.Context, request backupFilesRequest, stdout, stderr io.Writer) error {
	if request.root == "" || len(request.includes) == 0 {
		return errors.New("nothing to back up, pass the root and the include array to backup_files")
	}
	dir := filepath.Join(request.source, request.root)
	var missing []string
	for _, include := range request.includes {
		if _, err := os.Lstat(filepath.Join(dir, include)); err != nil {
			missing = append(missing, include)
		}
	}
	if len(missing) > 0 {
		return fmt.Errorf("declared paths [%s] are absent from [%s]", strings.Join(missing, " "), dir)
	}
	unmatched := backupUnmatched(dir, request.includes, request.excludes)
	target, err := backupEngineNamed(request, backupFullSuffix, "tar.gz")
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(request.state, backupIncludesLeaf), []byte(strings.Join(request.includes, "\n")+"\n"), 0o644); err != nil {
		return err
	}
	if len(unmatched) > 0 {
		fmt.Fprintf(stdout, "Not backed up and not excluded [%s]\n", strings.Join(unmatched, " "))
	}
	attempts := 1
	if request.live == "atomic" {
		attempts = backupAtomicAttempts
	}
	arguments := []string{"--create", "--directory", dir, "--numeric-owner", "--preserve-permissions", "--exclude=backup"}
	for _, exclude := range request.excludes {
		arguments = append(arguments, "--exclude="+exclude)
	}
	arguments = append(arguments, "--file", "-", "--")
	arguments = append(arguments, request.includes...)
	for attempt := 1; ; attempt++ {
		status := backupEngineArchived(ctx, arguments, target+".tmp", stderr)
		if status != 1 || attempt >= attempts {
			if status != 0 {
				return fmt.Errorf("tar exited [%d]", status)
			}
			return nil
		}
		fmt.Fprintf(stderr, "Archive changed while being read, retrying attempt [%d] of [%d]\n", attempt, attempts)
		time.Sleep(backupAtomicPause)
	}
}

func backupEngineArchived(ctx context.Context, arguments []string, output string, stderr io.Writer) int {
	file, err := os.Create(output)
	if err != nil {
		fmt.Fprintf(stderr, "Backup [%s] could not be created [%v]\n", output, err)
		return 2
	}
	defer func() { _ = file.Close() }()
	tar := exec.CommandContext(ctx, "tar", arguments...)
	gzip := exec.CommandContext(ctx, "gzip")
	tar.Stderr, gzip.Stderr, gzip.Stdout = stderr, stderr, file
	pipe, err := tar.StdoutPipe()
	if err != nil {
		return 2
	}
	gzip.Stdin = pipe
	if err := gzip.Start(); err != nil {
		return 2
	}
	tarErr := tar.Run()
	_ = pipe.Close()
	gzipErr := gzip.Wait()
	var exit *exec.ExitError
	switch {
	case errors.As(tarErr, &exit):
		if status, ok := exit.Sys().(syscall.WaitStatus); ok {
			return status.ExitStatus()
		}
		return 2
	case tarErr != nil || gzipErr != nil:
		return 2
	}
	return 0
}

func backupUnmatched(dir string, includes, excludes []string) []string {
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
		patterns[index] = shellPattern(exclude)
	}
	var unmatched []string
	for _, entry := range entries {
		if entry == treeBackupDirectory || strings.HasPrefix(entry, treeBackupDirectory+"/") || backupCovered(entry, includes, excludes, patterns, unmatched) {
			continue
		}
		unmatched = append(unmatched, entry)
	}
	return unmatched
}

func backupCovered(entry string, includes, excludes []string, patterns []*regexp.Regexp, unmatched []string) bool {
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

func shellPattern(pattern string) *regexp.Regexp {
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
