import logging
import typing as t

from localstack.extensions.patterns.webapp import WebAppExtension

from .backend.web import WebApp

LOG = logging.getLogger(__name__)


class MyExtension(WebAppExtension):
    name = "{{ cookiecutter.project_slug }}"
    
    def __init__(self):
        super().__init__(template_package_path=None)
        
    def collect_routes(self, routes: list[t.Any]):
        routes.append(WebApp())

