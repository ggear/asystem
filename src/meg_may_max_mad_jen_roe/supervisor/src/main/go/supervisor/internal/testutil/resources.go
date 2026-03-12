package testutil

import (
	"os"
	"path/filepath"
	"testing"
)

func FindDir(t *testing.T, dirs ...string) string {
	t.Helper()
	workingDirectory, err := os.Getwd()
	if err != nil {
		t.Fatalf("getwd failed: %v", err)
	}
	mainDir := ""
	searchDir := workingDirectory
	for {
		candidate := filepath.Join(searchDir, "supervisor", "src", "main")
		if info, err := os.Stat(candidate); err == nil && info.IsDir() {
			mainDir = candidate
			break
		}
		parent := filepath.Dir(searchDir)
		if parent == searchDir {
			t.Fatalf("main dir not found from [%s]", workingDirectory)
		}
		searchDir = parent
	}
	rootDir, err := filepath.Abs(filepath.Join(mainDir, "../.."))
	if err != nil {
		t.Fatalf("abs failed on path [%s]: %v", mainDir, err)
	}
	path := filepath.Join(append([]string{rootDir}, dirs...)...)
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("dir not found: %s (%v)", path, err)
	}
	return path
}

func FindFile(t *testing.T, filename string, dirs ...string) string {
	t.Helper()
	path := filepath.Join(append([]string{FindDir(t, dirs...)}, filename)...)
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("file not found: %s (%v)", path, err)
	}
	return path
}

func FindTestFile(t *testing.T, filename string, dirs ...string) string {
	t.Helper()
	return FindFile(t, filename, append([]string{"src", "test", "resources"}, dirs...)...)
}

var _ = FindDir
var _ = FindFile
var _ = FindTestFile
