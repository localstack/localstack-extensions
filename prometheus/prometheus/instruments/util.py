from localstack.services.lambda_.event_source_mapping.esm_event_processor import (
    EsmEventProcessor,
    EventProcessor,
)
from localstack.services.lambda_.event_source_mapping.pollers.poller import Poller


def get_event_target_from_procesor(processor: EventProcessor) -> str:
    if isinstance(processor, EsmEventProcessor):
        return "aws:lambda"

    if hasattr(processor, "event_target") and callable(processor.event_target):
        return processor.event_target()

    return "unknown"


# Utility function to extract record batching configuration
def record_batch_configuration(poller: Poller, event_source: dict) -> tuple[int, int]:
    batch_size = None
    batch_window = None

    # Extract configuration based on event source
    if event_source == "aws:sqs":
        if params := poller.source_parameters.get("PipeSourceSqsQueueParameters"):
            batch_size = params.get("BatchSize")
            batch_window = params.get("MaximumBatchingWindowInSeconds")
    elif event_source == "aws:dynamodb":
        if params := poller.source_parameters.get("DynamoDBStreamParameters"):
            batch_size = params.get("BatchSize")
            batch_window = params.get("MaximumBatchingWindowInSeconds")
    elif event_source == "aws:kinesis":
        if params := poller.source_parameters.get("KinesisStreamParameters"):
            batch_size = params.get("BatchSize")
            batch_window = params.get("MaximumBatchingWindowInSeconds")
    elif event_source == "aws:kafka" or event_source == "SelfManagedKafka":
        if params := poller.source_parameters.get(
            "PipeSourceManagedKafkaParameters", {}
        ) or poller.source_parameters.get("PipeSourceSelfManagedKafkaParameters", {}):
            batch_size = params.get("BatchSize")
            batch_window = params.get("MaximumBatchingWindowInSeconds")
    else:
        return ()

    return batch_size, batch_window
