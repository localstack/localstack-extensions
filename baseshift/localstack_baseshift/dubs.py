"""
Self-hosted Baseshift Dubs: creates a Dub in Baseshift Cloud (via the `baseshift` CLI), and runs its
components (agent + replication server) next to LocalStack - either in a Kubernetes cluster in
LocalStack EKS (with the Baseshift Helm chart), or as plain Docker containers. The replication
server pushes the Docker snapshots of the Dub to the LocalStack ECR registry, from where clones can
be started via the clones API.
"""

import json
import logging
import os
import platform
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

import yaml
from localstack import config
from localstack.aws.connect import connect_to
from localstack.dns.server import get_dns_server, is_server_running
from localstack.utils.archives import download_and_extract
from localstack.utils.container_networking import get_main_container_name
from localstack.utils.container_utils.container_client import NoSuchNetwork
from localstack.utils.docker_utils import DOCKER_CLIENT

LOG = logging.getLogger(__name__)

# credentials of the Baseshift user to create Dubs with (via `baseshift auth login --method=direct`)
ENV_BASESHIFT_USER_EMAIL = "BASESHIFT_USER_EMAIL"
ENV_BASESHIFT_USER_PASSWORD = "BASESHIFT_USER_PASSWORD"

REGION = "us-east-1"
EKS_CLUSTER = "baseshift"
EKS_NODEGROUP = "default"
# Docker snapshots are pushed to this project (repository prefix) of the LocalStack ECR registry
REGISTRY_PROJECT = "baseshift"
DEFAULT_ENCRYPTION_PASSWORD = "localstack123"
HELM_VERSION = "v3.18.4"
# The replication server builds the snapshot images on top of base images from the Baseshift ECR
# registry (in real AWS). These names are resolved upstream instead of pointing to LocalStack.
UPSTREAM_DNS_PATTERNS = [
    r"^api\.ecr\.eu-west-1\.amazonaws\.com",
    r"^709697032780\.dkr\.ecr\.eu-west-1\.amazonaws\.com",
    r"^prod-eu-west-1-starport-layer-bucket\.s3\.eu-west-1\.amazonaws\.com",
]
# how the components of a Dub are deployed
DEPLOYMENT_KUBERNETES = "kubernetes"
DEPLOYMENT_DOCKER = "docker"
# defaults of the Baseshift Helm chart (used for the Docker deployment)
DEFAULT_GATEWAY = "aws-gw-elb.dubhub.io:50052"
DEFAULT_REPSERVER_IMAGE = (
    "registry.gitlab.com/dubhub/core/multi-ubuntu2404/repserver:master"
)
DEFAULT_AGENT_IMAGE = "public.ecr.aws/x5e2w4i3/proxy:master"
REPSERVER_PORTS = {"ssh": 22, "tokenServer": 15057, "proxyServer": 50055}
# user-defined Docker network for the components (on the default bridge network, containers cannot
# resolve each other by name), which LocalStack is attached to as well
DOCKER_NETWORK = "ls-baseshift-dubs"
DUB_NAME_REGEX = re.compile(r"^[a-z][a-z0-9-]{0,38}[a-z0-9]$")
# keep the last lines of the CLI/helm output of each Dub, for the API
MAX_LOG_LINES = 200


@dataclass
class Dub:
    name: str
    hostname: str
    port: int
    database: str
    username: str
    password: str = field(repr=False)
    engine: str = "postgres"
    encryption_password: str = field(default=DEFAULT_ENCRYPTION_PASSWORD, repr=False)
    deployment: str = DEPLOYMENT_DOCKER
    # masking policy (`{"manual_rules": [...]}`, as accepted by `baseshift dub masking set`)
    masking_policy: dict | None = None
    status: str = "creating"
    error: str | None = None
    log: list[str] = field(default_factory=list)

    @property
    def namespace(self) -> str:
        return f"baseshift-{self.name}"

    @property
    def container_prefix(self) -> str:
        return f"ls-baseshift-dub-{self.name}"

    @property
    def repository(self) -> str:
        return f"{REGISTRY_PROJECT}/{self.name}"

    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "status": self.status,
            "source": f"{self.hostname}:{self.port}/{self.database}",
            "engine": self.engine,
            "deployment": self.deployment,
            "log": self.log[-20:],
        }
        if self.deployment == DEPLOYMENT_KUBERNETES:
            result.update({"cluster": EKS_CLUSTER, "namespace": self.namespace})
        else:
            result["containers"] = [
                f"{self.container_prefix}-repserver",
                f"{self.container_prefix}-agent",
            ]
        if self.error:
            result["error"] = self.error
        return result


class DubManager:
    """Creates self-hosted Dubs, and deploys their components into LocalStack EKS or Docker."""

    def __init__(self):
        self.email = os.getenv(ENV_BASESHIFT_USER_EMAIL, "").strip()
        self.password = os.getenv(ENV_BASESHIFT_USER_PASSWORD, "")
        self.work_dir = os.path.join(config.dirs.var_libs, "baseshift")
        # separate home directory for the `baseshift` CLI, which stores its login in ~/.baseshift
        self.cli_home = os.path.join(self.work_dir, "home")
        self._dubs: dict[str, Dub] = {}
        self._lock = threading.RLock()
        self._login_lock = threading.Lock()
        self._logged_in_at = 0.0

    def configure_dns(self):
        if not is_server_running():
            return
        dns_server = get_dns_server()
        for pattern in UPSTREAM_DNS_PATTERNS:
            dns_server.add_skip(pattern)

    # API

    def list_dubs(self) -> list[Dub]:
        with self._lock:
            return list(self._dubs.values())

    def get_dub(self, name: str) -> Dub | None:
        with self._lock:
            return self._dubs.get(name)

    def create_dub(self, payload: dict) -> Dub:
        name = payload.get("name") or ""
        if not DUB_NAME_REGEX.match(name):
            raise ValueError(
                "Dub name must start with a letter, and consist of lowercase letters, digits, "
                "and dashes (max. 40 chars)"
            )
        missing = [
            key
            for key in ("hostname", "port", "database", "username", "password")
            if not payload.get(key)
        ]
        if missing:
            raise ValueError(f"Missing source database parameters: {missing}")
        deployment = payload.get("deployment") or DEPLOYMENT_DOCKER
        if deployment not in (DEPLOYMENT_KUBERNETES, DEPLOYMENT_DOCKER):
            raise ValueError(
                f"Deployment must be {DEPLOYMENT_KUBERNETES} or {DEPLOYMENT_DOCKER}"
            )
        masking_policy = payload.get("maskingPolicy")
        if masking_policy is not None and not isinstance(
            masking_policy.get("manual_rules")
            if isinstance(masking_policy, dict)
            else None,
            list,
        ):
            raise ValueError("Masking policy must contain a 'manual_rules' list")
        if not self.email or not self.password:
            raise ValueError(
                f"Set {ENV_BASESHIFT_USER_EMAIL} and {ENV_BASESHIFT_USER_PASSWORD} to create Dubs"
            )
        with self._lock:
            if dub := self._dubs.get(name):
                if dub.status != "failed":
                    raise KeyError(f"Dub {name} already exists")
            dub = Dub(
                name=name,
                hostname=payload["hostname"],
                port=int(payload["port"]),
                database=payload["database"],
                username=payload["username"],
                password=payload["password"],
                engine=payload.get("engine") or "postgres",
                encryption_password=payload.get("encryptionPassword")
                or DEFAULT_ENCRYPTION_PASSWORD,
                deployment=deployment,
                masking_policy=masking_policy,
            )
            self._dubs[name] = dub
        threading.Thread(target=self._run_create, args=(dub,), daemon=True).start()
        return dub

    def create_snapshot(self, name: str) -> Dub:
        return self._start_operation(name, "snapshotting", self._run_snapshot)

    def set_masking_policy(self, name: str, policy: dict) -> Dub:
        if not isinstance(policy.get("manual_rules"), list):
            raise ValueError("Masking policy must contain a 'manual_rules' list")
        return self._start_operation(
            name, "updating", lambda dub: self._run_set_masking(dub, policy)
        )

    def _start_operation(self, name: str, status: str, operation) -> Dub:
        """Run an operation on a ready Dub in the background, and set it to ready again afterwards."""
        with self._lock:
            dub = self._dubs.get(name)
            if not dub:
                raise LookupError(f"Dub {name} not found")
            if dub.status != "ready":
                raise ValueError(f"Dub {name} is not ready (status: {dub.status})")
            dub.status = status

        def _run():
            try:
                operation(dub)
                dub.status = "ready"
            except Exception as e:
                LOG.warning("Failed to update Baseshift Dub %s: %s", dub.name, e)
                dub.status = "failed"
                dub.error = str(e)

        threading.Thread(target=_run, daemon=True).start()
        return dub

    def get_snapshot_image(self, name: str) -> str | None:
        """Return the most recently pushed snapshot image of the Dub in LocalStack ECR."""
        ecr = connect_to(region_name=REGION).ecr
        images = []
        for repo in ecr.describe_repositories()["repositories"]:
            if not repo["repositoryName"].endswith(f"/{name}"):
                continue
            details = ecr.describe_images(repositoryName=repo["repositoryName"])
            for image in details["imageDetails"]:
                images.append((image["imagePushedAt"], repo["repositoryUri"], image))
        if not images:
            return None
        _, repo_uri, image = max(images, key=lambda entry: entry[0])
        if tags := image.get("imageTags"):
            return f"{repo_uri}:{tags[0]}"
        return f"{repo_uri}@{image['imageDigest']}"

    # create flow

    def _run_create(self, dub: Dub):
        try:
            os.makedirs(self.work_dir, exist_ok=True)
            values_file = os.path.join(self.work_dir, f"{dub.name}-values.yaml")
            if os.path.exists(values_file):
                self._log(dub, f"Dub {dub.name} already created, using {values_file}")
            else:
                self._log(dub, f"Creating self-hosted Dub {dub.name}")
                self._cli(dub, *self._create_args(dub, values_file), stdin=dub.password)
                # the CLI exits with code 0 on most errors (e.g., when not logged in)
                if not os.path.exists(values_file):
                    raise RuntimeError(f"Failed to create Dub {dub.name}")
            chart, chart_version = self._get_chart(dub)
            self._adjust_values(dub, values_file)

            dub.status = "deploying"
            if dub.deployment == DEPLOYMENT_DOCKER:
                self._deploy_docker(dub, values_file)
            else:
                kubeconfig = self._create_cluster(dub)
                self._log(
                    dub,
                    f"Installing the Baseshift components ({chart} {chart_version})",
                )
                self._run(
                    dub,
                    [self._helm_binary(), "upgrade", "--install", dub.name, chart,
                     "--version", chart_version,
                     "--namespace", dub.namespace, "--create-namespace",
                     "--values", values_file,
                     "--kubeconfig", kubeconfig,
                     "--wait", "--timeout", "20m"],
                )  # fmt: skip

            # resume the create flow of the CLI: wait for the components to connect, run the health
            # checks, and start the replication and the initial snapshot
            dub.status = "connecting"
            self._log(dub, "Waiting for the initial snapshot of the source database")
            self._cli(dub, "dub", "create", "--retry", "--dub", dub.name)
            self._check_snapshot_image(dub)
            if dub.masking_policy and not self._get_masking_rules(dub):
                # the policy passed to `dub create` is not applied to self-hosted Dubs, and the
                # policy can only be changed once the Dub is ready - apply it now, which re-creates
                # the masked replica and takes a new snapshot
                unmasked_image = self.get_snapshot_image(dub.name)
                self._run_set_masking(dub, dub.masking_policy)
                self._delete_image(unmasked_image)
            dub.status = "ready"
            LOG.info("Baseshift Dub %s is ready", dub.name)
        except Exception as e:
            LOG.warning("Failed to create Baseshift Dub %s: %s", dub.name, e)
            dub.status = "failed"
            dub.error = str(e)

    def _run_snapshot(self, dub: Dub):
        # wait for a running operation of the Dub (e.g., a restart after a policy change) to finish
        self._cli(dub, "dub", "status", "--dub", dub.name, "--watch")
        previous_image = self.get_snapshot_image(dub.name)
        self._log(dub, f"Taking a snapshot of Dub {dub.name}")
        self._cli(dub, "snapshot", "create", "--dub", dub.name, "--wait")
        self._check_snapshot_image(dub, previous_image)

    def _run_set_masking(self, dub: Dub, policy: dict):
        previous_image = self.get_snapshot_image(dub.name)
        self._log(dub, f"Updating the masking policy of Dub {dub.name}")
        policy_file = self._write_masking_policy(dub, policy)
        # restarting the Dub re-creates the masked replica, and takes a new snapshot
        self._cli(
            dub, "dub", "masking", "set", "--dub", dub.name, "--file", policy_file,
            "--restart-dub",
        )  # fmt: skip
        self._cli(dub, "dub", "status", "--dub", dub.name, "--watch")
        self._check_snapshot_image(dub, previous_image)

    def _get_masking_rules(self, dub: Dub) -> list[dict]:
        path = os.path.join(self.work_dir, f"{dub.name}-masking-policy-current.json")
        self._cli(dub, "dub", "masking", "get", "--dub", dub.name, "--output", path)
        with open(path) as f:
            return json.load(f).get("manual_rules") or []

    def _delete_image(self, image: str):
        """Delete a snapshot image (as returned by `get_snapshot_image`) from LocalStack ECR."""
        reference = image.split("/", 1)[1]
        if "@" in reference:
            repository, digest = reference.split("@")
            image_id = {"imageDigest": digest}
        else:
            repository, tag = reference.rsplit(":", 1)
            image_id = {"imageTag": tag}
        connect_to(region_name=REGION).ecr.batch_delete_image(
            repositoryName=repository, imageIds=[image_id]
        )

    def _write_masking_policy(self, dub: Dub, policy: dict) -> str:
        path = os.path.join(self.work_dir, f"{dub.name}-masking-policy.json")
        with open(path, "w") as f:
            json.dump(policy, f)
        return path

    def _check_snapshot_image(self, dub: Dub, previous_image: str | None = None):
        # the CLI exits with code 0 on most errors, and errors of the snapshot (e.g., when pushing
        # the image) are only logged by the replication server
        image = self.get_snapshot_image(dub.name)
        if not image or image == previous_image:
            raise RuntimeError(
                f"No new snapshot image of Dub {dub.name} found in LocalStack ECR - see the "
                "log, and the replication server logs in /dubhub/logs"
            )
        self._log(dub, f"Snapshot image: {image}")

    def _create_args(self, dub: Dub, values_file: str) -> list[str]:
        return [
            "dub", "create",
            "--deployment", "self-hosted",
            "--name", dub.name,
            "--engine", dub.engine,
            "--hostname", dub.hostname,
            "--port", str(dub.port),
            "--database", dub.database,
            "--username", dub.username,
            "--password-stdin",
            "--registry-type", "harbor",
            "--encryption-password", dub.encryption_password,
            "--values-path", values_file,
            "--no-watch",
            *(
                ["--masking-policy-file", self._write_masking_policy(dub, dub.masking_policy)]
                if dub.masking_policy
                else []
            ),
        ]  # fmt: skip

    def _get_chart(self, dub: Dub) -> tuple[str, str]:
        """Return the Helm chart reference of the Dub, from the install command the CLI suggests."""
        output = "\n".join(dub.log)
        if match := re.search(
            r"helm upgrade --install \S+ (\S+).*?--version (\S+)", output, re.S
        ):
            chart = match.groups()
            with open(os.path.join(self.work_dir, f"{dub.name}-chart"), "w") as f:
                f.write(" ".join(chart))
            return chart
        # the Dub was created before (e.g., before a restart)
        with open(os.path.join(self.work_dir, f"{dub.name}-chart")) as f:
            chart, version = f.read().split()
        return chart, version

    def _adjust_values(self, dub: Dub, values_file: str):
        """Adjust the generated Helm values for running the components against LocalStack."""
        ecr = connect_to(region_name=REGION).ecr
        try:
            repo = ecr.create_repository(repositoryName=dub.repository)["repository"]
        except ecr.exceptions.RepositoryAlreadyExistsException:
            repo = ecr.describe_repositories(repositoryNames=[dub.repository])[
                "repositories"
            ][0]
        registry, registry_port = repo["repositoryUri"].split("/")[0].split(":")
        with open(values_file) as f:
            values = yaml.safe_load(f)
        values["password"] = dub.encryption_password
        # LocalStack ECR is a plain Docker v2 registry, hence we use the generic ("harbor") provider
        # over HTTP, instead of the "aws_ecr" provider (which would call the real AWS ECR APIs)
        values["dockerSnapshotRegistry"] = {
            "enabled": True,
            "provider": "harbor",
            "registry": registry,
            "port": registry_port,
            "project": REGISTRY_PROJECT,
            "useTls": False,
            # LocalStack ECR does not enforce authentication
            "auth": {"type": "basic", "username": "AWS", "password": "test"},
        }
        # a local database needs far less than the production defaults
        values.setdefault("repserver", {})["storage"] = {"size": "10Gi"}
        values["repserver"]["resources"] = {
            "requests": {"cpu": "1", "memory": "2Gi"},
            "limits": {"cpu": "2", "memory": "4Gi"},
        }
        values.setdefault("agent", {})["resources"] = {
            "requests": {"cpu": "250m", "memory": "512Mi"},
            "limits": {"cpu": "1", "memory": "2Gi"},
        }
        values["agent"]["awsRegion"] = REGION
        # clones are started from the snapshot images via the clones API, not on the repserver
        values["cloneService"] = {"mode": "none"}
        with open(values_file, "w") as f:
            yaml.safe_dump(values, f, sort_keys=False)

    def _create_cluster(self, dub: Dub) -> str:
        """Create the EKS cluster for the Baseshift components (if needed), and return its kubeconfig."""
        clients = connect_to(region_name=REGION)
        eks = clients.eks
        subnets = [
            subnet["SubnetId"]
            for subnet in clients.ec2.describe_subnets(
                Filters=[{"Name": "default-for-az", "Values": ["true"]}]
            )["Subnets"]
        ]

        def _cluster_status() -> str | None:
            try:
                return eks.describe_cluster(name=EKS_CLUSTER)["cluster"]["status"]
            except eks.exceptions.ResourceNotFoundException:
                return None

        if _cluster_status() == "FAILED":
            # e.g., a k3d node failed to start - recreate the cluster
            self._log(dub, f"Deleting failed EKS cluster {EKS_CLUSTER}")
            eks.delete_cluster(name=EKS_CLUSTER)
            while _cluster_status():
                time.sleep(2)
        try:
            eks.create_cluster(
                name=EKS_CLUSTER,
                roleArn="arn:aws:iam::000000000000:role/eks-cluster",
                resourcesVpcConfig={"subnetIds": subnets},
            )
            self._log(dub, f"Creating EKS cluster {EKS_CLUSTER}")
        except eks.exceptions.ResourceInUseException:
            pass
        self._wait_for_eks(lambda: eks.describe_cluster(name=EKS_CLUSTER)["cluster"])
        # the control plane node does not run workloads - add a node for the Baseshift components
        try:
            eks.create_nodegroup(
                clusterName=EKS_CLUSTER,
                nodegroupName=EKS_NODEGROUP,
                nodeRole="arn:aws:iam::000000000000:role/eks-node",
                subnets=subnets,
                scalingConfig={"minSize": 1, "maxSize": 1, "desiredSize": 1},
            )
        except (
            eks.exceptions.ResourceInUseException,
            eks.exceptions.InvalidRequestException,
        ):
            pass
        self._wait_for_eks(
            lambda: eks.describe_nodegroup(
                clusterName=EKS_CLUSTER, nodegroupName=EKS_NODEGROUP
            )["nodegroup"]
        )

        # the API server of the LocalStack EKS cluster does not require authentication
        cluster = eks.describe_cluster(name=EKS_CLUSTER)["cluster"]
        kubeconfig = {
            "apiVersion": "v1",
            "kind": "Config",
            "clusters": [
                {
                    "name": EKS_CLUSTER,
                    "cluster": {
                        "server": cluster["endpoint"],
                        "certificate-authority-data": cluster["certificateAuthority"][
                            "data"
                        ],
                    },
                }
            ],
            "users": [{"name": EKS_CLUSTER, "user": {"token": "localstack"}}],
            "contexts": [
                {
                    "name": EKS_CLUSTER,
                    "context": {"cluster": EKS_CLUSTER, "user": EKS_CLUSTER},
                }
            ],
            "current-context": EKS_CLUSTER,
        }
        path = os.path.join(self.work_dir, "kubeconfig")
        with open(path, "w") as f:
            yaml.safe_dump(kubeconfig, f)
        os.chmod(path, 0o600)
        return path

    def _deploy_docker(self, dub: Dub, values_file: str):
        """
        Run the Baseshift components as containers next to LocalStack, equivalent to the resources
        of the Helm chart. The containers share a network with LocalStack, and use the LocalStack
        DNS server, so they can reach LocalStack (e.g., the RDS source database, and the ECR
        registry) via the `localhost.localstack.cloud` names. The data volumes (including the
        certificates of the enrolled replication server) are kept when LocalStack shuts down.
        """
        with open(values_file) as f:
            values = yaml.safe_load(f)
        client = DOCKER_CLIENT.client()
        repserver_image = self._image_name(values, "repserver", DEFAULT_REPSERVER_IMAGE)
        agent_image = self._image_name(values, "agent", DEFAULT_AGENT_IMAGE)
        credentials = values.get("imageCredentials") or {}
        auth_config = None
        if credentials.get("enabled"):
            auth_config = {
                "username": credentials["username"],
                "password": credentials["token"],
            }
        for image, auth in ((repserver_image, auth_config), (agent_image, None)):
            self._log(dub, f"Pulling image {image}")
            try:
                DOCKER_CLIENT.pull_image(image, auth_config=auth)
            except Exception as e:
                # e.g., a pull rate limit - continue with a local image, if available
                DOCKER_CLIENT.inspect_image(image, pull=False)
                self._log(dub, f"Failed to pull image {image}, using local image: {e}")

        # remove the containers of a previous deployment of this Dub (e.g., after a failure)
        self._remove_docker_containers(dub)
        repserver_name = f"{dub.container_prefix}-repserver"
        network = DOCKER_NETWORK
        # the embedded DNS server of the network resolves the container names, and forwards the
        # other names to the LocalStack DNS server (e.g., `localhost.localstack.cloud`)
        dns = [self._attach_localstack_to_network(network)]
        volumes = {
            f"{dub.container_prefix}-{name}": {"bind": f"/dubhub/{name}", "mode": "rw"}
            for name in ("targets", "logs", "certs")
        }
        # like the init container of the chart, create the directories, writable for the repserver
        client.containers.run(
            "busybox:1.36",
            ["sh", "-c", "mkdir -p /dubhub/logs/repserver && chmod -R 777 /dubhub"],
            volumes=volumes,
            remove=True,
        )
        repserver = values.get("repserver") or {}
        registry = values["dockerSnapshotRegistry"]
        self._log(dub, f"Starting the replication server ({repserver_name})")
        client.containers.run(
            repserver_image,
            name=repserver_name,
            hostname=repserver_name,
            detach=True,
            network=network,
            dns=dns,
            shm_size=repserver.get("sharedMemorySize", "512Mi").replace("Mi", "m"),
            volumes=volumes,
            restart_policy={"Name": "unless-stopped"},
            labels={"localstack.baseshift.dub": dub.name},
            environment={
                "SERVERID": values["serverId"],
                "ORGID": values["orgId"],
                "GATEWAY": values.get("gateway", DEFAULT_GATEWAY),
                "ENVIRONMENT": values.get("environment", "production"),
                "ENROLLMENT_TOKEN": values["enrollmentToken"],
                "CERT_DIR": "/dubhub/certs",
                "EXTRAFLAGS": f"-proxytimeout={repserver.get('proxyTimeout', '45s')}",
                "SERVERNAME": dub.name,
                "SERVERURI": f"{repserver_name}:{REPSERVER_PORTS['ssh']}",
                "PASSWORD": values["password"],
                "PROXYID": values["agent"]["id"],
                "PROXYTOKEN": values["agent"]["token"],
                "TDS_PORT_RANGE_START": "32768",
                "TDS_PORT_RANGE_END": "32812",
                "REPSERVERTAG": "master",
                "DOCKER_SNAPSHOT_REGISTRY_ENABLED": "true",
                "DOCKER_SNAPSHOT_REGISTRY_PROVIDER": registry["provider"],
                "DOCKER_SNAPSHOT_REGISTRY": registry["registry"],
                "DOCKER_SNAPSHOT_REGISTRY_PORT": str(registry["port"]),
                "DOCKER_SNAPSHOT_REGISTRY_PROJECT": registry["project"],
                "DOCKER_SNAPSHOT_REGISTRY_USE_TLS": str(registry["useTls"]).lower(),
                "DOCKER_SNAPSHOT_REGISTRY_AUTH_TYPE": registry["auth"]["type"],
                "DOCKER_SNAPSHOT_REGISTRY_USERNAME": registry["auth"]["username"],
                "DOCKER_SNAPSHOT_REGISTRY_PASSWORD": registry["auth"]["password"],
            },
        )
        self._log(dub, f"Starting the agent ({dub.container_prefix}-agent)")
        client.containers.run(
            agent_image,
            name=f"{dub.container_prefix}-agent",
            detach=True,
            network=network,
            dns=dns,
            # the agent exits if the repserver is not up yet - restart it until it connects
            restart_policy={"Name": "unless-stopped"},
            labels={"localstack.baseshift.dub": dub.name},
            environment={
                "T": values["agent"]["token"],
                "TOKENSERVER": f"{repserver_name}:{REPSERVER_PORTS['tokenServer']}",
                "GRPCSERVER": f"{repserver_name}:{REPSERVER_PORTS['proxyServer']}",
                "USETLS": "false",
                "AWS_REGION": REGION,
                "AWS_DEFAULT_REGION": REGION,
                "PROXY_SOURCE_CONNECT_TIMEOUT_SEC": "8",
                "PROXY_SOURCE_CONNECT_MAX_DURATION_SEC": "30",
                "PROXY_SOURCE_CONNECT_RETRY_DELAY_SEC": "3",
                "REQUESTED_RESTART_EXIT_CODE": "124",
                "EXIT_CONTAINER_ON_REQUESTED_RESTART": "true",
            },
        )

    @staticmethod
    def _attach_localstack_to_network(network: str) -> str:
        """Create the network, attach LocalStack to it, and return the IP of LocalStack in it."""
        container = get_main_container_name()
        if network not in DOCKER_CLIENT.get_networks(container):
            try:
                DOCKER_CLIENT.inspect_network(network)
            except NoSuchNetwork:
                DOCKER_CLIENT.create_network(network)
            DOCKER_CLIENT.connect_container_to_network(network, container)
        return DOCKER_CLIENT.get_container_ipv4_for_network(
            container_name_or_id=container, container_network=network
        )

    @staticmethod
    def _image_name(values: dict, component: str, default: str) -> str:
        image = (values.get(component) or {}).get("image") or {}
        if image.get("repository"):
            return f"{image['repository']}:{image.get('tag') or 'master'}"
        return default

    def _remove_docker_containers(self, dub: Dub):
        for suffix in ("agent", "repserver"):
            DOCKER_CLIENT.remove_container(
                f"{dub.container_prefix}-{suffix}", force=True, check_existence=False
            )

    def shutdown(self):
        """Remove the containers of Dubs deployed with Docker (EKS clusters are removed by LocalStack)."""
        for dub in self.list_dubs():
            if dub.deployment == DEPLOYMENT_DOCKER:
                self._remove_docker_containers(dub)

    @staticmethod
    def _wait_for_eks(describe_fn):
        """Wait until an EKS cluster or nodegroup (as returned by `describe_fn`) is active."""
        for _ in range(200):
            resource = describe_fn()
            if resource["status"] == "ACTIVE":
                return
            if resource["status"].endswith("FAILED"):
                raise RuntimeError(f"Failed to create EKS resource: {resource}")
            time.sleep(3)
        raise TimeoutError(f"EKS resource did not become active: {resource}")

    # tools

    def _cli(self, dub: Dub, *args: str, stdin: str | None = None):
        self._login(dub)
        self._run(dub, [*self._cli_command(), *args], stdin=stdin)

    def _login(self, dub: Dub):
        with self._login_lock:
            # the tokens of a direct login expire after an hour
            if time.time() - self._logged_in_at < 30 * 60:
                return
            self._log(dub, f"Logging in to Baseshift as {self.email}")
            # `auth login` is skipped if a (possibly expired) token exists - log out first
            self._run(dub, [*self._cli_command(), "auth", "logout"], check=False)
            self._run(
                dub,
                [*self._cli_command(), "auth", "login", "--method=direct",
                 "--email", self.email, "--password", self.password],
            )  # fmt: skip
            self._logged_in_at = time.time()

    @staticmethod
    def _cli_command() -> list[str]:
        # run the CLI with the Python interpreter of LocalStack (the CLI is installed as a
        # dependency of this extension, hence we pass on the module search path)
        return [
            sys.executable,
            "-c",
            "import sys, baseshift; sys.argv[0] = 'baseshift'; sys.exit(baseshift.main())",
        ]

    def _run(self, dub: Dub, cmd: list[str], stdin: str | None = None, check=True):
        os.makedirs(self.cli_home, exist_ok=True)
        env = {
            **os.environ,
            "HOME": self.cli_home,
            "PYTHONPATH": os.pathsep.join(sys.path),
            # plain progress output, without spinners
            "TERM": "dumb",
        }
        # LocalStack sets `no_proxy` with an IPv6 entry (`[::1]`), which httpx (used by the CLI)
        # fails to parse ("Invalid port")
        for key in ("no_proxy", "NO_PROXY"):
            if key in env:
                env[key] = ",".join(
                    host for host in env[key].split(",") if not host.startswith("[")
                )
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        if stdin is not None:
            process.stdin.write(stdin)
        process.stdin.close()
        for line in process.stdout:
            self._log(dub, line.rstrip())
        if (exit_code := process.wait()) and check:
            raise RuntimeError(
                f"Command failed with exit code {exit_code} - see the log"
            )

    def _helm_binary(self) -> str:
        arch = {"x86_64": "amd64", "aarch64": "arm64"}.get(
            platform.machine(), platform.machine()
        )
        target_dir = os.path.join(self.work_dir, f"helm-{HELM_VERSION}")
        binary = os.path.join(target_dir, f"linux-{arch}", "helm")
        if not os.path.exists(binary):
            download_and_extract(
                f"https://get.helm.sh/helm-{HELM_VERSION}-linux-{arch}.tar.gz",
                target_dir=target_dir,
                retries=2,
            )
        return binary

    def _log(self, dub: Dub, line: str):
        if not line.strip():
            return
        # don't leak the user password, in case the CLI echoes it
        if self.password:
            line = line.replace(self.password, "***")
        LOG.debug("Baseshift Dub %s: %s", dub.name, line)
        dub.log.append(line)
        del dub.log[:-MAX_LOG_LINES]
