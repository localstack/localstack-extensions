"""
Package for mailhog that downloads the mailhog binary from https://github.com/mailhog/MailHog.
"""
import os
from functools import lru_cache

from localstack.packages import GitHubReleaseInstaller, Package, PackageInstaller
from localstack.utils.platform import Arch, get_arch, get_os

_MAILHOG_VERSION = os.environ.get("MH_VERSION") or "v1.0.1"


class MailHogPackage(Package):
    def __init__(self, default_version: str = _MAILHOG_VERSION):
        super().__init__(name="MailHog", default_version=default_version)

    @lru_cache
    def _get_installer(self, version: str) -> PackageInstaller:
        return MailHogPackageInstaller(version)

    def get_versions(self) -> list[str]:
        return [_MAILHOG_VERSION]


class MailHogPackageInstaller(GitHubReleaseInstaller):
    def __init__(self, version: str):
        super().__init__("mailhog", version, "mailhog/MailHog")

    def _get_github_asset_name(self):
        arch = get_arch()
        operating_system = get_os()

        if arch == Arch.amd64:
            bin_file = f"MailHog_{operating_system}_amd64"
        elif arch == Arch.arm64:
            bin_file = f"MailHog_{operating_system}_arm"
        else:
            raise NotImplementedError(f"unknown architecture {arch}")

        # the extension would typically only be used in the container, so windows support is not needed,
        # but since there are windows binaries might as well add them
        if operating_system == "windows":
            bin_file += ".exe"

        return bin_file


mailhog_package = MailHogPackage()
