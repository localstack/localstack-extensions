import os

import boto3
import psycopg2
import pytest
import requests
from localstack.utils.docker_utils import DOCKER_CLIENT
from localstack.utils.strings import short_uid
from localstack.utils.sync import retry

# Note: these tests connect to databases served by Baseshift clone containers. In CI, a plain
# Postgres image is used as a stand-in for a clone image (clone images are private to each Baseshift
# customer), and LocalStack is started with:
#   BASESHIFT_IMAGE=postgres:17 BASESHIFT_CLONE_POSTGRES_HOST_AUTH_METHOD=trust
# To run the tests against a real clone, override the user/database via the env variables below.

USER = os.environ.get("BASESHIFT_TEST_USER", "postgres")
DATABASE = os.environ.get("BASESHIFT_TEST_DATABASE", "postgres")
STAND_IN_IMAGE = "postgres:17"

GATEWAY_PORT = int(os.environ.get("GATEWAY_PORT", "4566"))
GATEWAY_ENDPOINT = ("localhost.localstack.cloud", GATEWAY_PORT)
HOST_PORT_ENDPOINT = ("localhost", 5432)
API_URL = f"http://baseshift.localhost.localstack.cloud:{GATEWAY_PORT}/clones"


def connect(host: str, port: int):
    def _connect():
        return psycopg2.connect(host=host, port=port, user=USER, dbname=DATABASE)

    return retry(_connect, retries=15, sleep=2.0)


def wait_for_clone_status(name: str, status: str = "running") -> dict:
    def _check():
        clone = requests.get(f"{API_URL}/{name}").json()
        assert clone["status"] == status, clone
        return clone

    return retry(_check, retries=60, sleep=2)


@pytest.fixture
def ecr_image():
    """Push the stand-in image into the LocalStack ECR registry, emulating a Docker snapshot of a Dub."""
    ecr = boto3.client(
        "ecr",
        endpoint_url=f"http://localhost.localstack.cloud:{GATEWAY_PORT}",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    repo_name = f"dub-snapshots/dub-{short_uid()}"
    repo_uri = ecr.create_repository(repositoryName=repo_name)["repository"][
        "repositoryUri"
    ]
    image = f"{repo_uri}:latest"
    DOCKER_CLIENT.tag_image(STAND_IN_IMAGE, image)
    DOCKER_CLIENT.push_image(image)
    # remove the local tag, to make sure the extension pulls the image from the registry
    DOCKER_CLIENT.remove_image(image)
    yield image
    ecr.delete_repository(repositoryName=repo_name, force=True)


@pytest.mark.parametrize(
    "endpoint", [GATEWAY_ENDPOINT, HOST_PORT_ENDPOINT], ids=["gateway", "host-port"]
)
def test_query_default_clone(endpoint):
    with connect(*endpoint) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT version()")
        assert "PostgreSQL" in cursor.fetchone()[0]


def test_default_clone_is_writable():
    table = f"test_{short_uid()}"
    with connect(*GATEWAY_ENDPOINT) as conn, conn.cursor() as cursor:
        cursor.execute(f"CREATE TABLE {table} (id SERIAL PRIMARY KEY, name TEXT)")
        cursor.execute(
            f"INSERT INTO {table} (name) VALUES (%s), (%s)", ("alice", "bob")
        )
        cursor.execute(f"SELECT name FROM {table} ORDER BY id")
        assert [row[0] for row in cursor.fetchall()] == ["alice", "bob"]
        cursor.execute(f"DROP TABLE {table}")


def test_concurrent_connections():
    connections = [connect(*GATEWAY_ENDPOINT) for _ in range(3)]
    try:
        for i, conn in enumerate(connections):
            with conn.cursor() as cursor:
                cursor.execute("SELECT %s", (i,))
                assert cursor.fetchone()[0] == i
    finally:
        for conn in connections:
            conn.close()


def test_list_clones():
    clones = requests.get(API_URL).json()["clones"]
    default = next(clone for clone in clones if clone["name"] == "default")
    assert default["status"] == "running"
    assert default["hostPort"] == 5432
    assert default["image"] == STAND_IN_IMAGE


def test_start_clone_from_ecr_image(ecr_image):
    name = f"pr-{short_uid()}"
    response = requests.post(
        API_URL,
        json={
            "name": name,
            "image": ecr_image,
            "env": {"POSTGRES_HOST_AUTH_METHOD": "trust"},
        },
    )
    assert response.status_code == 202
    try:
        clone = wait_for_clone_status(name)
        # the default clone owns the gateway and the default port, hence a separate host port is used
        assert clone["hostPort"] != 5432
        assert clone["endpoints"] == [f"localhost:{clone['hostPort']}"]

        with connect("localhost", clone["hostPort"]) as conn, conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1
    finally:
        assert requests.delete(f"{API_URL}/{name}").status_code == 204

    assert requests.get(f"{API_URL}/{name}").status_code == 404
    assert not DOCKER_CLIENT.is_container_running(f"ls-baseshift-clone-{name}")


def test_start_clone_with_invalid_image():
    name = f"broken-{short_uid()}"
    response = requests.post(
        API_URL, json={"name": name, "image": "localhost:1/does-not-exist"}
    )
    assert response.status_code == 202
    try:
        clone = wait_for_clone_status(name, "failed")
        assert clone["error"]
    finally:
        requests.delete(f"{API_URL}/{name}")


def test_api_errors():
    # invalid name
    response = requests.post(
        API_URL, json={"name": "Invalid_Name", "image": STAND_IN_IMAGE}
    )
    assert response.status_code == 400
    # missing image
    response = requests.post(API_URL, json={"name": "no-image"})
    assert response.status_code == 400
    # invalid database type
    response = requests.post(
        API_URL, json={"name": "mongo", "image": STAND_IN_IMAGE, "dbType": "mongodb"}
    )
    assert response.status_code == 400
    # duplicate name
    response = requests.post(API_URL, json={"name": "default", "image": STAND_IN_IMAGE})
    assert response.status_code == 409
    # unknown clone
    assert requests.get(f"{API_URL}/unknown").status_code == 404
    assert requests.delete(f"{API_URL}/unknown").status_code == 404
