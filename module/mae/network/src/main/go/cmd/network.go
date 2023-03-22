package main

import (
	"fmt"
	"github.com/ggear/asystem/tree/master/module/mae/internet/src/main/go/pkg"
	"time"
)

func main() {
	for true {
		fmt.Println(pkg.GetStatus("Server is up ..."))
		time.Sleep(30 * time.Second)
	}
}
