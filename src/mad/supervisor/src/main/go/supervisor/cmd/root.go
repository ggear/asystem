package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

const version = "v1.0.0"

var rootCmd = &cobra.Command{
	Use:   "supervisor [OPTIONS] [COMMAND]",
	Short: "Run the supervisor processes",
	Long: `Run the supervisor processes

Commands:
  run         Run the supervisor process to retrieve and publish stats from the system and perform supervisory duties
  stats       Show real-time system statistics
  help        Display this help message and exit`,
}

// Execute runs the root command.
func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func init() {
	rootCmd.PersistentFlags().BoolP("version", "v", false, "Display version information and exit")

	rootCmd.PersistentPreRun = func(cmd *cobra.Command, args []string) {
		showVersion, _ := cmd.Flags().GetBool("version")
		if showVersion {
			fmt.Println(version)
			os.Exit(0)
		}
	}
}
