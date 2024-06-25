from typing import Any, Iterable

from localstack.http import Router

from werkzeug.routing import (
    RuleFactory,
    Map,
    Rule,
    Submount as WerkzeugSubmount,
    Subdomain as WerkzeugSubdomain,
)


class Subdomain(WerkzeugSubdomain):
    def __init__(
        self,
        subdomain: str,
        rules: RuleFactory | Iterable[RuleFactory],
        use_host_pattern: bool = True,
    ):
        super().__init__(
            subdomain, [rules] if isinstance(rules, RuleFactory) else rules
        )
        self.use_host_pattern = use_host_pattern

    def get_rules(self, map: Map) -> Iterable[Rule]:
        if not self.use_host_pattern:
            return super().get_rules(map)

        for rule in super().get_rules(map):
            rule.host = f"{self.subdomain}.<__host__>"
            yield rule


class Submount(WerkzeugSubmount):
    def __init__(self, path: str, rules: RuleFactory | Iterable[RuleFactory]) -> None:
        super().__init__(path, [rules] if isinstance(rules, RuleFactory) else rules)


class Routes(RuleFactory):
    """
    Wraps an object that uses @route decorators ase a RuleFactory that can be added to a router.
    """

    def __init__(self, obj: Any):
        self.obj = obj

    def get_rules(self, map: Map) -> Iterable[Rule]:
        router = Router() # type: ignore
        router.add(self.obj)
        return router.url_map._rules