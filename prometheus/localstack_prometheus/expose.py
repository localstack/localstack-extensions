from localstack.extensions.api import http
from prometheus_client.exposition import choose_encoder


def retrieve_metrics(request: http.Request):
    """Expose the Prometheus metrics"""
    _generate_latest_metrics, content_type = choose_encoder(
        request.headers.get("Content-Type", "")
    )
    data = _generate_latest_metrics()
    return http.Response(response=data, status=200, mimetype=content_type)
