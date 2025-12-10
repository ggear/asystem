package internal

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"regexp"
	"sort"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
)

const SchemaDefaultPath = "/root/install/supervisor/latest/image/schema.json"
const dockerContainerNameIgnoredPattern = `^reaper_`

func GetServices(hostName string, schemaPath string) ([]string, error) {
	schemaMap, err := getSchema(schemaPath)
	if err != nil {
		return nil, err
	}
	rootMap, ok := schemaMap["asystem"].(map[string]any)
	if !ok {
		return nil, errors.New("missing asystem")
	}
	hostNameMap, ok := rootMap["services"].(map[string]any)
	if !ok {
		return nil, errors.New("missing services")
	}
	for hostNameKey, services := range hostNameMap {
		if hostNameKey == "" {
			return nil, errors.New("empty host name found")
		}
		if serviceSlice, ok := services.([]any); ok {
			for _, service := range serviceSlice {
				serviceStr, ok := service.(string)
				if !ok || serviceStr == "" {
					return nil, errors.New("empty service entry found")
				}
			}
		}
	}
	serviceMap, ok := hostNameMap[hostName].([]any)
	if !ok {
		return []string{}, nil
	}
	serviceSlice := make([]string, len(serviceMap))
	for index, value := range serviceMap {
		serviceSlice[index], ok = value.(string)
		if !ok {
			return nil, errors.New("invalid service entry")
		}
	}
	dockerClient, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		return nil, err
	}
	dockerContainerSlice, err := dockerClient.ContainerList(context.Background(), container.ListOptions{})
	if err != nil {
		return nil, err
	}
	servicesMap := make(map[string]bool)
	for _, service := range serviceSlice {
		if service != "" {
			servicesMap[service] = true
		}
	}
	for _, container := range dockerContainerSlice {
		if len(container.Names) > 0 {
			containerName := container.Names[0][1:]
			if containerName != "" && !regexp.MustCompile(dockerContainerNameIgnoredPattern).MatchString(containerName) && !servicesMap[containerName] {
				serviceSlice = append(serviceSlice, containerName)
			}
		}
	}
	sort.Strings(serviceSlice)
	return serviceSlice, nil
}

func GetVersion(schemaPath string) (string, error) {
	schemaMap, err := getSchema(schemaPath)
	if err != nil {
		return "", err
	}
	rootMap, ok := schemaMap["asystem"].(map[string]any)
	if !ok {
		return "", errors.New("missing asystem")
	}
	version, ok := rootMap["version"].(string)
	if !ok {
		return "", errors.New("missing version")
	}
	if !regexp.MustCompile(`^\d{2}\.\d{3}\.\d{4}$`).MatchString(version) {
		return "", fmt.Errorf("invalid version format [%s]", version)
	}
	return version, nil
}

func getSchema(schemaPath string) (map[string]any, error) {
	schemaString, readErr := os.ReadFile(schemaPath)
	if readErr != nil {
		return nil, readErr
	}
	var schemaMap map[string]any
	if unmarshalErr := json.Unmarshal([]byte(schemaString), &schemaMap); unmarshalErr != nil {
		return nil, unmarshalErr
	}
	return schemaMap, nil
}

func contains(slice []string, str string) bool {
	for _, v := range slice {
		if v == str {
			return true
		}
	}
	return false
}
