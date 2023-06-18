module github.com/ggear/asystem/tree/master/module/meg/network/src/main/go/cmd

go 1.20

require (
	github.com/eclipse/paho.mqtt.golang v1.4.2
	github.com/ggear/asystem/tree/master/module/meg/network/src/main/go/pkg v0.0.0-00010101000000-000000000000
	github.com/sirupsen/logrus v1.9.0
	github.com/spf13/cobra v1.6.1
)

require (
	github.com/gorilla/websocket v1.4.2 // indirect
	github.com/inconshreveable/mousetrap v1.0.1 // indirect
	github.com/spf13/pflag v1.0.5 // indirect
	golang.org/x/net v0.0.0-20200425230154-ff2c4b7c35a0 // indirect
	golang.org/x/sync v0.0.0-20210220032951-036812b2e83c // indirect
	golang.org/x/sys v0.0.0-20220715151400-c0bba94af5f8 // indirect
)

replace github.com/ggear/asystem/tree/master/module/meg/network/src/main/go/pkg => ../pkg
