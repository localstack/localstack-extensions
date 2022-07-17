from localstack.extensions.api import Extension


class AwsReplicatorExtension(Extension):
    name = "aws-replicator"

    def on_platform_start(self):
        print("AWS replicator: localstack is starting!")
