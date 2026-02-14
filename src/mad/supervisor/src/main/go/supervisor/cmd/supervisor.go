package cmd

import (
	"fmt"
	"os"
	"supervisor/internal/config"

	"github.com/spf13/cobra"
)

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		_, _ = fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func init() {
	rootCmd.PersistentFlags().BoolP("version", "v", false, "Display version information and exit")
}

var rootCmd = &cobra.Command{
	Use:           "supervisor [command]",
	Short:         "Run the supervisor processes",
	Long:          "Run the supervisor processes",
	SilenceUsage:  true,
	SilenceErrors: false,
	RunE: func(cmd *cobra.Command, args []string) error {
		showVersion, _ := cmd.Flags().GetBool("version")
		if showVersion {
			if config, err := config.Load(config.DefaultConfigPath); err != nil {
				return err
			} else {
				fmt.Println(config.Version())
			}
			os.Exit(0)
		}
		if len(args) == 0 {
			return cmd.Help()
		}
		return nil
	},
}
