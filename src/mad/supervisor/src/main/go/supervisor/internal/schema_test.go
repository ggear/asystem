package internal

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
)

func setupTestContainer(t *testing.T) (testcontainers.Container, error) {
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
	return container, nil
}

func teardownTestContainer(container testcontainers.Container) {
	fmt.Println("Terminating containers ... ")
	ctx := context.Background()
	container.Terminate(ctx)
	fmt.Println("Finished terminating containers")
}

func getSchemaPath(schemaFilename string) string {
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

func TestGetVersion(t *testing.T) {
	tests := []struct {
		name        string
		schemaPath  string
		expected    string
		expectError bool
	}{
		{
			name:        "non-existent file",
			schemaPath:  "non-existent-file.json",
			expected:    "",
			expectError: true,
		},
		{
			name:        "invalid corrupt",
			schemaPath:  getSchemaPath("schema-invalid-corrupt.json"),
			expected:    "",
			expectError: true,
		},
		{
			name:        "invalid missing keys 1",
			schemaPath:  getSchemaPath("schema-invalid-missing-keys-1.json"),
			expected:    "",
			expectError: true,
		},
		{
			name:        "invalid missing keys 2",
			schemaPath:  getSchemaPath("schema-invalid-missing-keys-2.json"),
			expected:    "",
			expectError: true,
		},
		{
			name:        "invalid value format 1",
			schemaPath:  getSchemaPath("schema-invalid-value-format-1.json"),
			expected:    "",
			expectError: true,
		},
		{
			name:        "invalid value format 2",
			schemaPath:  getSchemaPath("schema-invalid-value-format-2.json"),
			expected:    "",
			expectError: true,
		},
		{
			name:        "invalid value format 3",
			schemaPath:  getSchemaPath("schema-invalid-value-format-3.json"),
			expected:    "",
			expectError: true,
		},
		{
			name:        "invalid value format 4",
			schemaPath:  getSchemaPath("schema-invalid-value-format-4.json"),
			expected:    "",
			expectError: true,
		},
		{
			name:        "valid",
			schemaPath:  getSchemaPath("schema-valid.json"),
			expected:    "10.100.6792",
			expectError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got, err := GetVersion(testCase.schemaPath)
			if (err != nil) != testCase.expectError || got != testCase.expected {
				t.Fatalf("GetVersion() = %v, %v; want %v, error? %v", got, err, testCase.expected, testCase.expectError)
			}
		})
	}
}

func TestGetServices(t *testing.T) {
	container, err := setupTestContainer(t)
	if err != nil {
		t.Fatalf("Could not start container: %v", err)
	}
	defer teardownTestContainer(container)

	tests := []struct {
		name        string
		hostname    string
		schemaPath  string
		expected    []string
		expectError bool
	}{
		{
			name:        "non-existent file",
			schemaPath:  "non-existent-file.json",
			expected:    nil,
			expectError: true,
		},
		{
			name:        "invalid corrupt",
			schemaPath:  getSchemaPath("schema-invalid-corrupt.json"),
			expected:    nil,
			expectError: true,
		},
		{
			name:        "invalid missing keys 1",
			schemaPath:  getSchemaPath("schema-invalid-missing-keys-1.json"),
			expected:    nil,
			expectError: true,
		},
		{
			name:        "invalid missing keys 2",
			schemaPath:  getSchemaPath("schema-invalid-missing-keys-2.json"),
			expected:    nil,
			expectError: true,
		},
		{
			name:        "invalid value format 1",
			schemaPath:  getSchemaPath("schema-invalid-value-format-1.json"),
			expected:    nil,
			expectError: true,
		},
		{
			name:        "invalid value format 2",
			schemaPath:  getSchemaPath("schema-invalid-value-format-2.json"),
			expected:    nil,
			expectError: true,
		},
		{
			name:        "invalid value format 3",
			schemaPath:  getSchemaPath("schema-invalid-value-format-3.json"),
			expected:    nil,
			expectError: true,
		},
		{
			name:        "invalid value format 4",
			schemaPath:  getSchemaPath("schema-invalid-value-format-4.json"),
			expected:    nil,
			expectError: true,
		},
		{
			name:        "valid nil-host",
			schemaPath:  getSchemaPath("schema-valid.json"),
			expected:    []string{},
			expectError: false,
		},
		{
			name:        "valid non-existent-host",
			hostname:    "non-existent-host",
			schemaPath:  getSchemaPath("schema-valid.json"),
			expected:    []string{},
			expectError: false,
		},
		{
			name:        "valid macmini-mad",
			hostname:    "macmini-mad",
			schemaPath:  getSchemaPath("schema-valid.json"),
			expected:    []string{"monitor", "plex", "sabnzbd", "sleep"},
			expectError: false,
		},
		{
			name:        "valid raspbpi-jen",
			hostname:    "raspbpi-jen",
			schemaPath:  getSchemaPath("schema-valid.json"),
			expected:    []string{"monitor", "sleep", "weewx", "zigbee2mqtt"},
			expectError: false,
		},
	}
	for _, testCase := range tests {
		t.Run(testCase.name, func(t *testing.T) {
			got, err := GetServices(testCase.hostname, testCase.schemaPath)
			if (err != nil) != testCase.expectError || !reflect.DeepEqual(got, testCase.expected) {
				t.Fatalf("GetServices() = %v, %v; want %v, error? %v", got, err, testCase.expected, testCase.expectError)
			}
		})
	}
}
