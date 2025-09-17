import os
import platform

from localstack.packages import InstallTarget, Package, PackageInstaller
from localstack.packages.core import (
    ArchiveDownloadAndExtractInstaller,
    PythonPackageInstaller,
)
from localstack.utils.files import chmod_r
from localstack.utils.platform import get_arch

TERRAFORM_VERSION = os.getenv("TERRAFORM_VERSION", "1.5.7")
TERRAFORM_URL_TEMPLATE = "https://releases.hashicorp.com/terraform/{version}/terraform_{version}_{os}_{arch}.zip"
TERRAFORM_CHECKSUM_URL_TEMPLATE = (
    "https://releases.hashicorp.com/terraform/{version}/terraform_{version}_SHA256SUMS"
)


class TerraformPackage(Package["TerraformPackageInstaller"]):
    def __init__(self) -> None:
        super().__init__("Terraform", TERRAFORM_VERSION)

    def get_versions(self) -> list[str]:
        return [TERRAFORM_VERSION]

    def _get_installer(self, version: str) -> "TerraformPackageInstaller":
        return TerraformPackageInstaller("terraform", version)


class TerraformPackageInstaller(ArchiveDownloadAndExtractInstaller):
    def _get_install_marker_path(self, install_dir: str) -> str:
        return os.path.join(install_dir, "terraform")

    def _get_download_url(self) -> str:
        system = platform.system().lower()
        arch = get_arch()
        return TERRAFORM_URL_TEMPLATE.format(
            version=TERRAFORM_VERSION, os=system, arch=arch
        )

    def _install(self, target: InstallTarget) -> None:
        super()._install(target)
        chmod_r(self.get_executable_path(), 0o777)  # type: ignore[arg-type]

    def _get_checksum_url(self) -> str | None:
        return TERRAFORM_CHECKSUM_URL_TEMPLATE.format(version=TERRAFORM_VERSION)


class TflocalPackage(Package):
    def __init__(self, default_version: str = "0.24.1"):
        super().__init__(name="terraform_local", default_version=default_version)

    def _get_installer(self, version: str) -> PackageInstaller:
        return TflocalPackageInstaller(version)

    def get_versions(self) -> list[str]:
        return [self.default_version]


class TflocalPackageInstaller(PythonPackageInstaller):
    def __init__(self, version: str):
        super().__init__("terraform_local", version)


tflocal_package = TflocalPackage()
terraform_package = TerraformPackage()
