from localstack.extensions.api import Extension


class HelloWorldExtension(Extension):
    name = "hello-world"

    def on_platform_start(self):
        print("hello world: localstack is starting!")

    def on_platform_ready(self):
        print("hello world: localstack is running!")
