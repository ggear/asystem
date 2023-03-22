package main

import (
	"fmt"
	"github.com/ggear/asystem/tree/master/module/mae/internet/src/main/go/pkg"
	"github.com/spf13/cobra"
	"os"
	"time"
)

var RootCmd = &cobra.Command{
	Use: "network",
	Run: func(cmd *cobra.Command, args []string) {
		once, _ := cmd.Flags().GetBool("once")
		if once {
			fmt.Println(pkg.GetStatus("Server is running once ..."))
		} else {
			for true {
				fmt.Println(pkg.GetStatus("Server is waking up to run ..."))
				time.Sleep(30 * time.Second)
			}
		}
	},
}

func init() {
	RootCmd.Flags().BoolP("once", "o", false, "run telemetry gather loop once with debug statements")
}

func main() {
	if err := RootCmd.Execute(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}
