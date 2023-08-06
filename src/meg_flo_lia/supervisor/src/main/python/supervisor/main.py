import json
import os.path
import socket

import docker
import sys
import time

RUN_CODE_ALL_UP = 0
RUN_CODE_SOME_ALIENS = 1
RUN_CODE_SOME_DOWN = 2
RUN_CODE_NONE_INSTALLED = 3
RUN_CODE_NOT_ALL_UP = 4

DEFAULT_SERVICES_PATH = "/root/home/monitor/latest/services.json"

HOST_NAME = socket.gethostname()


def docker_client_from_env():
    return docker.from_env()


def docker_container_name_parse(docker_container_attrs):
    return docker_container_attrs['Name'].replace("/", "") if 'Name' in docker_container_attrs else None


def docker_container_up(docker_container_attrs):
    up = False
    if 'State' in docker_container_attrs:
        if 'Health' in docker_container_attrs['State'] and 'Status' in docker_container_attrs['State']['Health']:
            if docker_container_attrs['State']['Health']['Status'] == "healthy":
                up = True
        elif 'Status' in docker_container_attrs['State']:
            if docker_container_attrs['State']['Status'] == "running":
                up = True
    return up


def docker_containers_provisioned(services_path):
    docker_containers_provisioned = []
    if os.path.isfile(services_path):
        with open(services_path, 'r') as services_file:
            docker_containers_provisioned_hosts = {}
            try:
                docker_containers_provisioned_hosts = json.load(services_file)
            except Exception as error:
                print("Error: Could not parse services file [{}]".format(services_path), file=sys.stderr)
            if HOST_NAME in docker_containers_provisioned_hosts:
                docker_containers_provisioned = docker_containers_provisioned_hosts[HOST_NAME]
    print("Docker container provisioned process run with containers [{}] installed".format(
        len(docker_containers_provisioned),
    ))
    return docker_containers_provisioned


def docker_container_status(services_path):
    docker_containers = {
        "installed": docker_containers_provisioned(services_path),
        "up": [],
        "down": [],
        "alien": [],
    }
    docker_client = None
    try:
        docker_client = docker_client_from_env()
    except Exception:
        pass
    if docker_client is None:
        print("Error: Could not get docker client", file=sys.stderr)
    else:
        for docker_container in docker_client.containers.list():
            docker_container_name = docker_container_name_parse(docker_container.attrs)
            if docker_container_name is not None and docker_container_name in docker_containers["installed"]:
                if docker_container_up(docker_container.attrs):
                    docker_containers["up"].append(docker_container_name)
            else:
                docker_containers["alien"].append(docker_container.id if docker_container_name is None else docker_container_name)
    for docker_container_name in docker_containers["installed"]:
        if docker_container_name not in docker_containers["up"]:
            docker_containers["down"].append(docker_container_name)
    print("Docker container status process completed with containers [{}] up, [{}] down and [{}] alien".format(
        len(docker_containers["up"]),
        len(docker_containers["down"]),
        len(docker_containers["alien"]),
    ))
    return docker_containers


def docker_container_status_publish(docker_containers):
    # TODO
    print(docker_containers)

    return {}


def docker_container_supervise(services_path=DEFAULT_SERVICES_PATH):
    run_time_start = time.time()
    run_code = RUN_CODE_ALL_UP
    docker_containers = docker_container_status(services_path)
    if len(docker_containers["installed"]) == 0:
        run_code = RUN_CODE_NONE_INSTALLED
    elif len(docker_containers["installed"]) != len(docker_containers["up"]):
        run_code = RUN_CODE_NOT_ALL_UP
    elif len(docker_containers["down"]) > 0:
        run_code = RUN_CODE_SOME_DOWN
    elif len(docker_containers["alien"]) > 0:
        run_code = RUN_CODE_SOME_ALIENS
    docker_container_status_publish(docker_containers)
    print("Docker container supervisor process completed in [{} ms] with return [{}]".format(
        int((time.time() - run_time_start) * 1000),
        run_code,
    ))
    return run_code


if __name__ == "__main__":
    exit(docker_container_supervise(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SERVICES_PATH))
