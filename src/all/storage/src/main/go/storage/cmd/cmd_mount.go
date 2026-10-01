package cmd

import (
	"fmt"
	"os"
	"storage/internal/config"
	"storage/internal/engine"

	"github.com/spf13/cobra"
)

func init() {
	rootCmd.AddCommand(newMountCmd())
}

func newMountCmd() *cobra.Command {
	return &cobra.Command{
		Use:     "mount",
		Aliases: []string{"amount"},
		Short:   mountDescription,
		Long:    mountDescription,
		RunE: func(cmd *cobra.Command, args []string) error {
			configPath, _ := cmd.Flags().GetString("config")
			cfg := config.Load(configPath)
			failed := false
			for _, result := range engine.Mount(cfg) {
				fmt.Println(result.Message)
				if result.Failed {
					failed = true
				}
			}
			if failed {
				os.Exit(1)
			}
			return nil
		},
	}
}

const mountDescription = "Mount what this host should have mounted"
