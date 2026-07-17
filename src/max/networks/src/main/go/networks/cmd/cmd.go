package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

const version = "0.0.0-SNAPSHOT"

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func init() {
	rootCmd.PersistentFlags().BoolP("version", "v", false, "display version information and exit")
	rootCmd.Flags().SortFlags = false
	rootCmd.PersistentFlags().SortFlags = false
	rootCmd.InheritedFlags().SortFlags = false
	rootCmd.AddCommand(serveCmd)
	rootCmd.AddCommand(checkCmd)
}

var rootCmd = &cobra.Command{
	Use:           "networks",
	Short:         rootDescription,
	Long:          rootDescription,
	SilenceUsage:  true,
	SilenceErrors: true,
	RunE: func(cmd *cobra.Command, args []string) error {
		showVersion, _ := cmd.Flags().GetBool("version")
		if showVersion {
			fmt.Println(version)
			os.Exit(0)
		}
		if len(args) == 0 {
			return cmd.Help()
		}
		return nil
	},
}

var serveCmd = &cobra.Command{
	Use:   "serve",
	Short: "Run the network health monitor daemon",
	RunE: func(cmd *cobra.Command, args []string) error {
		fmt.Println("networks serve: not implemented")
		return nil
	},
}

var checkCmd = &cobra.Command{
	Use:   "check",
	Short: "Run one health check cycle and exit",
	RunE: func(cmd *cobra.Command, args []string) error {
		fmt.Println("networks check: not implemented")
		return nil
	},
}

const rootDescription = "Monitor network health and publish status"
