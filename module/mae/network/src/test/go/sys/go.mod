module github.com/ggear/asystem/tree/master/module/mae/network/src/test/go/sys

go 1.20

replace github.com/ggear/asystem/tree/master/module/mae/internet/src/main/go/pkg => ../../../main/go/pkg

require github.com/ggear/asystem/tree/master/module/mae/internet/src/main/go/pkg v0.0.0-00010101000000-000000000000

require (
	github.com/eclipse/paho.mqtt.golang v1.4.2 // indirect
	github.com/gorilla/websocket v1.4.2 // indirect
	github.com/sirupsen/logrus v1.9.0 // indirect
	golang.org/x/net v0.0.0-20200425230154-ff2c4b7c35a0 // indirect
	golang.org/x/sync v0.0.0-20210220032951-036812b2e83c // indirect
	golang.org/x/sys v0.0.0-20220715151400-c0bba94af5f8 // indirect
)
