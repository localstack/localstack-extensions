from localstack.services.lambda_.event_source_mapping.esm_event_processor import (
    EsmEventProcessor,
    EventProcessor,
)


def get_event_target_from_procesor(processor: EventProcessor) -> str:
    if isinstance(processor, EsmEventProcessor):
        return "aws:lambda"

    if hasattr(processor, "event_target") and callable(processor.event_target):
        return processor.event_target()

    return "unknown"
