package cmd

import (
	"fmt"
	"supervisor/internal/config"

	"github.com/spf13/cobra"
)

func init() {
	rootCmd.AddCommand(newCompletionCmd())
}

func newCompletionCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "completion",
		Short: completionDescription,
		Long:  completionDescription,
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			out := cmd.OutOrStdout()
			if err := cmd.Root().GenBashCompletionV2(out, true); err != nil {
				return err
			}
			if _, err := fmt.Fprintf(out, completionDispatch, config.InstallBinaryPath, rootName); err != nil {
				return err
			}
			for _, command := range cmd.Root().Commands() {
				for _, alias := range command.Aliases {
					if _, err := fmt.Fprintf(out, completionBinding, alias, command.Name()); err != nil {
						return err
					}
				}
			}
			return nil
		},
	}
}

const completionDescription = "Print the bash completion for supervisor and its host commands, eval it in a profile"

const completionDispatch = `
__supervisor_alias() {
  local typed="${COMP_WORDS[0]}" bin="%[1]s" verb="$1"
  local words=("${bin}" "${verb}" "${COMP_WORDS[@]:1}")
  local line="${bin} ${verb}${COMP_LINE#"${typed}"}"
  local point=$((COMP_POINT + ${#line} - ${#COMP_LINE}))
  local COMP_WORDS=("${words[@]}") COMP_CWORD=$((COMP_CWORD + 1)) COMP_LINE="${line}" COMP_POINT="${point}"
  __start_%[2]s
}
`

const completionBinding = `_%[1]s() { __supervisor_alias %[2]s; }
complete -o default -F _%[1]s %[1]s
`
