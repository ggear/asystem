package probe

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"
)

func BackupEngine(ctx context.Context, arguments []string, stdout, stderr io.Writer) int {
	if len(arguments) == 0 {
		fmt.Fprintln(stderr, "usage backup-engine run|accept|target|files|parent|epoch|contract")
		return 2
	}
	verb, rest := arguments[0], arguments[1:]
	flags, positional := backupEngineFlags(rest)
	request := backupFilesRequest{
		module: flags.value("module"), source: flags.value("source"), run: flags.value("run"), state: flags.value("state"),
		root: flags.value("root"), live: flags.value("live"), includes: flags["include"], excludes: flags["exclude"],
	}
	switch verb {
	case "contract":
		fmt.Fprintln(stdout, backupEngineContract)
		return 0
	case "run":
		env, err := backupEngineEnvOf(os.Getenv, time.Now())
		if err != nil {
			fmt.Fprintf(stderr, "Backup could not start [%v]\n", err)
			return 2
		}
		return backupEngineRun(ctx, env, stdout, stderr)
	case "accept":
		if len(positional) != 2 {
			fmt.Fprintln(stderr, "usage backup-engine accept <source> <run>")
			return 2
		}
		if err := acceptBackupRun(filepath.Join(filepath.Dir(positional[0]), treeBackupDirectory), positional[1]); err != nil {
			fmt.Fprintln(stderr, backupEngineFault(err))
			return 1
		}
		fmt.Fprintf(stdout, "Accepted run [%s]\n", positional[1])
		return 0
	case "target":
		if len(positional) != 2 {
			fmt.Fprintln(stderr, "usage backup-engine target <suffix> <extension>")
			return 2
		}
		path, err := backupEngineNamed(request, positional[0], positional[1])
		if err != nil {
			fmt.Fprintln(stderr, backupEngineFault(err))
			return 1
		}
		fmt.Fprintln(stdout, path)
		return 0
	case "files":
		if err := backupEngineFiles(ctx, request, stdout, stderr); err != nil {
			fmt.Fprintln(stderr, backupEngineFault(err))
			return 1
		}
		return 0
	case "parent":
		fmt.Fprintln(stdout, backupParent(filepath.Join(filepath.Dir(request.source), treeBackupDirectory), request.run))
		return 0
	case "epoch":
		if len(positional) != 1 || len(positional[0]) < len("2006-01-02_15-04-05") {
			fmt.Fprintln(stdout, 0)
			return 0
		}
		stamp := positional[0][len(positional[0])-len("2006-01-02_15-04-05"):]
		fmt.Fprintln(stdout, backupRunTime(stamp).Unix())
		return 0
	}
	fmt.Fprintf(stderr, "unknown backup-engine verb [%s]\n", verb)
	return 2
}

type backupEngineFlagSet map[string][]string

func (f backupEngineFlagSet) value(name string) string {
	if values := f[name]; len(values) > 0 {
		return values[len(values)-1]
	}
	return ""
}

func backupEngineFlags(arguments []string) (backupEngineFlagSet, []string) {
	flags := backupEngineFlagSet{}
	var positional []string
	for index := 0; index < len(arguments); index++ {
		argument := arguments[index]
		name, found := strings.CutPrefix(argument, "--")
		if !found {
			positional = append(positional, argument)
			continue
		}
		if key, value, split := strings.Cut(name, "="); split {
			flags[key] = append(flags[key], value)
		} else if index+1 < len(arguments) {
			flags[name] = append(flags[name], arguments[index+1])
			index++
		}
	}
	return flags, positional
}

func backupEngineFault(err error) string {
	return strings.ToUpper(err.Error()[:1]) + err.Error()[1:]
}
