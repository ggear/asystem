module github.com/ggear/asystem/tree/master/module/mae/network/src/main/go/cmd

go 1.20

replace github.com/ggear/asystem/tree/master/module/mae/internet/src/main/go/pkg => ../pkg

require (
	github.com/ggear/asystem/tree/master/module/mae/internet/src/main/go/pkg v0.0.0-00010101000000-000000000000
	github.com/spf13/cobra v1.6.1
)

require (
	github.com/inconshreveable/mousetrap v1.0.1 // indirect
	github.com/spf13/pflag v1.0.5 // indirect
)
