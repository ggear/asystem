package cmd

import (
	"fmt"
	"os"
	"regexp"
	"storage/internal/config"
	"strings"

	"github.com/spf13/cobra"
	"github.com/spf13/pflag"
)

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		_, _ = fmt.Fprintf(os.Stderr, "%s%v\n", prefixError, err)
		os.Exit(1)
	}
}

func init() {
	cobra.AddTemplateFunc("formatAliases", formatAliases)
	cobra.AddTemplateFunc("formatFlagUsages", formatFlagUsages)
	rootCmd.SetUsageTemplate(usageTemplate)
	rootCmd.PersistentFlags().StringP("config", "c", config.DefaultConfigPath, "path to config file")
	rootCmd.Flags().SortFlags = false
	rootCmd.PersistentFlags().SortFlags = false
	rootCmd.InheritedFlags().SortFlags = false
}

func formatAliases(aliases []string) string {
	return strings.Join(aliases, ", ")
}

func formatFlagUsages(flags *pflag.FlagSet) string {
	lines := strings.Split(strings.TrimRight(flags.FlagUsages(), "\n"), "\n")
	for index, line := range lines {
		lines[index] = flagDefaultPattern.ReplaceAllString(line, "(default [$1])")
	}
	return strings.Join(lines, "\n")
}

const (
	rootName        = "storage"
	rootDescription = "Show storage metrics"

	prefixError   = "Error: "
	prefixWarning = "Warning: "
)

const usageTemplate = `Usage:{{if .Runnable}}
  {{.UseLine}}{{end}}{{if .HasAvailableSubCommands}}
  {{.CommandPath}} [command]{{end}}{{if gt (len .Aliases) 0}}

Aliases:
  {{formatAliases .Aliases}}{{end}}{{if .HasExample}}

Examples:
{{.Example}}{{end}}{{if .HasAvailableSubCommands}}

Available Commands:{{range .Commands}}{{if (or .IsAvailableCommand (eq .Name "help"))}}
  {{rpad .Name .NamePadding }} {{.Short}}{{end}}{{end}}{{end}}{{if .HasAvailableLocalFlags}}

Flags:
{{formatFlagUsages .LocalFlags}}{{end}}{{if .HasAvailableInheritedFlags}}

Global Flags:
{{formatFlagUsages .InheritedFlags}}{{end}}{{if .HasHelpSubCommands}}

Additional help topics:{{range .Commands}}{{if .IsAdditionalHelpTopicCommand}}
  {{rpad .CommandPath .CommandPathPadding}} {{.Short}}{{end}}{{end}}{{end}}{{if .HasAvailableSubCommands}}

Use "{{.CommandPath}} [command] --help" for more information about a command.{{end}}
`

var flagDefaultPattern = regexp.MustCompile(`\(default "?(.*?)"?\)$`)

var rootCmd = &cobra.Command{
	Use:           rootName,
	Short:         rootDescription,
	Long:          rootDescription,
	SilenceUsage:  true,
	SilenceErrors: true,
	RunE: func(cmd *cobra.Command, args []string) error {
		if len(args) == 0 {
			return cmd.Help()
		}
		return nil
	},
}
