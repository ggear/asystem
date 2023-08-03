import socket

import docker
import sys
import time

RUN_CODE_SUUCESS = 0
RUN_CODE_SOME_ALIENS = 1
RUN_CODE_SOME_DOWN = 2
RUN_CODE_NOT_ALL_UP = 3

DEFAULT_SERVICES_PATH = "/root/home/monitor/latest/services.json"

HOST_NAME = socket.gethostname()


def _docker_container_name(docker_container_attrs):
    return docker_container_attrs['Name'].replace("/", "") if 'Name' in docker_container_attrs else None


def _docker_container_up(docker_container_attrs):
    up = False
    if 'State' in docker_container_attrs:
        if 'Health' in docker_container_attrs['State'] and \
                'Status' in docker_container_attrs['State']['Health'] and \
                docker_container_attrs['State']['Health']['Status'] == "healthy":
            up = True
        elif 'Status' in docker_container_attrs['State'] and \
                docker_container_attrs['State']['Status'] == "running":
            up = True
    return up


def _docker_containers_provisioned(services_path):
    docker_containers_provisioned = []

    # TODO
    print(services_path)

    print("Docker container provisioned process run with containers [{}] installed".format(
        len(docker_containers_provisioned),
    ))
    return docker_containers_provisioned


def _docker_container_status(docker_containers_provisioned):
    docker_containers = {
        "installed": docker_containers_provisioned,
        "up": [],
        "down": [],
        "alien": [],
    }
    docker_client = None
    try:
        docker_client = docker.from_env()
    except Exception as error:
        pass
    for docker_container in docker_client.containers.list() if docker_client is not None else []:
        docker_container_name = _docker_container_name(docker_container.attrs)
        if docker_container_name is not None and docker_container_name in docker_containers["installed"]:
            if _docker_container_up(docker_container.attrs):
                docker_containers["up"].append(docker_container_name)
        else:
            docker_containers["alien"].append(docker_container.id if docker_container_name is None else docker_container_name)
    print("Docker container status process completed with containers [{}] up, [{}] down and [{}] alien".format(
        len(docker_containers["up"]),
        len(docker_containers["down"]),
        len(docker_containers["alien"]),
    ))
    return docker_containers


def _docker_container_status_publish(docker_containers):
    # TODO
    print(docker_containers)

    return {}


def _docker_container_supervise(services_path):
    run_time_start = time.time()
    run_code = RUN_CODE_SUUCESS
    docker_containers = _docker_container_status(_docker_containers_provisioned(services_path))
    if len(docker_containers["installed"]) != len(docker_containers["up"]):
        run_code = RUN_CODE_NOT_ALL_UP
    elif len(docker_containers["down"]) > 0:
        run_code = RUN_CODE_SOME_DOWN
    elif len(docker_containers["alien"]) > 0:
        run_code = RUN_CODE_SOME_ALIENS
    _docker_container_status_publish(docker_containers)
    print("Docker container supervisor process completed in [{}ms] with return [{}]".format(
        int((time.time() - run_time_start) * 1000),
        run_code,
    ))
    return run_code


if __name__ == "__main__":
    exit(_docker_container_supervise(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SERVICES_PATH))
