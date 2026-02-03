package cmd

import (
	"fmt"
	"os"
	"supervisor/internal/schema"

	"github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
	Use:           "supervisor [command]",
	Short:         "Run the supervisor processes",
	Long:          "Run the supervisor processes",
	SilenceUsage:  true,
	SilenceErrors: false,
	RunE: func(cmd *cobra.Command, args []string) error {
		showVersion, _ := cmd.Flags().GetBool("version")
		if showVersion {
			if schema, err := schema.Load(schema.DefaultPath); err != nil {
				return err
			} else {
				fmt.Println(schema.Version())
			}
			os.Exit(0)
		}
		if len(args) == 0 {
			return cmd.Help()
		}
		return nil
	},
}

func init() {
	rootCmd.PersistentFlags().BoolP("version", "v", false, "Display version information and exit")
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
