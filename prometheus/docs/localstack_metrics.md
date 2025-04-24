# LocalStack Metrics

## LocalStack Core/Request Handling Metrics

`localstack_request_processing_duration_seconds`

- **Description:** Time spent processing LocalStack service requests. This is done at the handler chain and is calculated as the duration from first *request handler* to the final *response handler*.
- **Labels:** `service`, `operation`, `status`, `status_code`
- **Type:** histogram

`localstack_in_flight_requests`

- **Description:** Total number of currently in-flight requests. This is a live number, and will be influenced by the scraping interval.
- **Labels:** `service`, `operation`
- **Type:** gauge

## LocalStack Event Poll Operation Metrics

`localstack_records_per_poll`

- **Description:** Number of records/events received in each poll operation
- **Labels:** `event_source`, `event_target`
- **Type:** histogram

`localstack_poll_events_duration_seconds`

- **Description:** Duration of each poll call in seconds
- **Labels:** `event_source`, `event_target`
- **Type:** histogram

`localstack_poll_miss_total`

- **Description:** Count of poll events with empty responses
- **Labels:** `event_source`, `event_target`
- **Type:** counter

`localstack_batch_size_efficiency_ratio`

- **Description:** Ratio of records received to configured maximum batch size
- **Labels:** `event_source`, `event_target`
- **Type:** histogram
- **Note:** This is useful for finding whether the configured batch size is efficiently pulling records. A higher number indicates that a configured `BatchSize` could be increased.

`localstack_batch_window_efficiency_ratio` (Not currently instrumented)

- **Description:** Ratio of poll duration to configured maximum batch window length
- **Labels:** `event_source`, `event_target`
- **Type:** histogram
- **Note:** Measures what proportion of the configured maximum batch window (set by `MaximumBatchingWindowInSeconds`) was actually used before returning. A lower ratio indicates that events were received quickly without needing to wait for the full window duration and that a window could be decreased.

## LocalStack Event Processing Metrics

`localstack_processed_events_total`

- **Description:** Total number of events processed
- **Labels:** `event_source`, `event_target`, `status`
- **Type:** counter

`localstack_in_flight_events`

- **Description:** Total number of event batches currently being processed by the target
- **Labels:** `event_source`, `event_target`
- **Type:** gauge

`localstack_event_propagation_delay_seconds`

- **Description:** End-to-end latency between event creation (at source) until just before being sent to a target for processing.
- **Labels:** `event_source`, `event_target`
- **Type:** histogram

`localstack_event_processing_errors_total`

- **Description:** Total number of event processing errors
- **Labels:** `event_source`, `event_target`, `error_type`
- **Type:** counter
