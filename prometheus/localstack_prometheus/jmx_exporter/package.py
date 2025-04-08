"""
Package for Prometheus JMX exporter that downloads the JMX exporter JAR from https://github.com/prometheus/jmx_exporter.
"""

import os
from functools import lru_cache

from localstack.packages import GitHubReleaseInstaller, Package, PackageInstaller
from localstack.packages.java import JavaInstallerMixin

_JMX_EXPORTER_VERSION = os.environ.get("JMX_VERSION") or "1.20.0"


class JmxExporterPackage(Package):
    def __init__(self, default_version: str = _JMX_EXPORTER_VERSION):
        super().__init__(name="JmxExporter", default_version=default_version)

    @lru_cache
    def _get_installer(self, version: str) -> PackageInstaller:
        return JmxExporterPackageInstaller(version)

    def get_versions(self) -> list[str]:
        return [_JMX_EXPORTER_VERSION]


class JmxExporterPackageInstaller(JavaInstallerMixin, GitHubReleaseInstaller):
    def __init__(self, version: str):
        super().__init__("jmx_exporter", version, "prometheus/jmx_exporter")

    def _get_github_asset_name(self):
        return f"jmx_prometheus_javaagent-{self.version}.jar"
    
    def get_jmx_exporter_agent_jar_path(self) -> str:
        return self._get_install_marker_path(self.get_installed_dir())

jmx_exporter_package = JmxExporterPackage()
