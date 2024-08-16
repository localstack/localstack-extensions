from localstack.extensions.api import Extension, http, aws

class MyExtension(Extension):
    name = "{{ cookiecutter.project_slug }}"

    def on_extension_load(self):
        print("MyExtension: extension is loaded")

    def on_platform_start(self):
        print("MyExtension: localstack is starting")

    def on_platform_ready(self):
        print("MyExtension: localstack is running")

    def update_gateway_routes(self, router: http.Router[http.RouteHandler]):
        pass

    def update_request_handlers(self, handlers: aws.CompositeHandler):
        pass

    def update_response_handlers(self, handlers: aws.CompositeResponseHandler):
        pass
