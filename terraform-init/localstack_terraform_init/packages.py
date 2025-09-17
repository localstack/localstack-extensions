from localstack.packages import Package, PackageInstaller
from localstack.packages.core import PythonPackageInstaller


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
