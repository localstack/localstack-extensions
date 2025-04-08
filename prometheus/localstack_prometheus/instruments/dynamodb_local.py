import logging

from localstack.services.dynamodb.server import DynamodbServer
from localstack_prometheus.jmx_exporter.package import jmx_exporter_package

def create_shell_command_with_jmx_exporter(fn, self: DynamodbServer):
    installer = jmx_exporter_package.get_installer()
    installer.install()

    jmx_jar_path = installer.get_jmx_exporter_agent_jar_path()

    shell_cmd = fn(self)
    for i, parameter in enumerate(shell_cmd):
        if parameter.startswith("-javaagent:"):
            shell_cmd.insert(i, f"-javaagent:{jmx_jar_path}")

    return shell_cmd
