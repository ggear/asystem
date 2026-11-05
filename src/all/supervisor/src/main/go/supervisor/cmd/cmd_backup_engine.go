package cmd

import (
	"os"

	"supervisor/internal/engine"

	"github.com/spf13/cobra"
)

func init() {
	rootCmd.AddCommand(&cobra.Command{
		Use:                "backup-engine",
		Short:              "run the module backup engine on behalf of a generated backup.sh",
		Hidden:             true,
		DisableFlagParsing: true,
		Run: func(_ *cobra.Command, arguments []string) {
			os.Exit(engine.BackupEngine(arguments))
		},
	})
}
