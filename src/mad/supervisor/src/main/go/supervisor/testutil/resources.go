package testutil

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
)

func SetupBrokerService(t *testing.T) (testcontainers.Container, string, error) {
	t.Helper()
	ctx := context.Background()
	req := testcontainers.ContainerRequest{
		Image:        "eclipse-mosquitto:2",
		ExposedPorts: []string{"1883/tcp"},
		WaitingFor:   wait.ForListeningPort("1883/tcp"),
	}
	container, err := testcontainers.GenericContainer(
		ctx,
		testcontainers.GenericContainerRequest{
			ContainerRequest: req,
			Started:          true,
		},
	)
	if err != nil {
		return nil, "", err
	}
	t.Cleanup(func() {
		_ = container.Terminate(context.Background())
	})
	host, err := container.Host(ctx)
	if err != nil {
		return nil, "", err
	}
	port, err := container.MappedPort(ctx, "1883")
	if err != nil {
		return nil, "", err
	}
	brokerURL := fmt.Sprintf("tcp://%s:%s", host, port.Port())
	return container, brokerURL, nil
}

func SetupSleepContainer(t *testing.T) (testcontainers.Container, error) {
	t.Helper()
	fmt.Println("Creating containers ... ")
	ctx := context.Background()
	req := testcontainers.ContainerRequest{
		Name:  "sleep",
		Image: "alpine",
		Cmd:   []string{"sleep", "99999"},
		WaitingFor: wait.ForAll(
			wait.ForLog(""),
		),
	}
	container, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: req,
		Started:          true,
	})
	if err != nil {
		return nil, err
	}
	fmt.Println("Finished creating containers")
	t.Cleanup(func() {
		fmt.Println("Terminating containers ... ")
		ctx := context.Background()
		container.Terminate(ctx)
		fmt.Println("Finished terminating containers")
	})
	return container, nil
}

func GetSchemaPath(schemaFilename string) string {
	dir, err := os.Getwd()
	if err != nil {
		panic(fmt.Sprintf("Error getting working directory: %v", err))
	}
	path := filepath.Join(dir, "..", "..", "..", "..", "test", "resources", schemaFilename)
	if _, err := os.Stat(path); err != nil {
		panic(fmt.Sprintf("Schema file does not exist: %v", err))
	}
	return path
}
