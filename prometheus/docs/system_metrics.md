# Sytem-level Metrics

##  Garbage Collection Metrics

`_gc_objects_collected_total`

- **Description:** Number of objects collected during garbage collection
- **Labels:** `generation`
- **Type:** counter

`_gc_objects_uncollectable_total`

- **Description:** Number of uncollectable objects found during garbage collection
- **Labels:** `generation`
- **Type:** counter

`_gc_collections_total`

- **Description:** Number of times this generation was collected
- **Labels:** `generation`
- **Type:** counter

##  Environment Metrics

`_info`

- **Description:**  platform information
- **Labels:** `implementation`, `major`, `minor`, `patchlevel`, `version`
- **Type:** gauge

## Process Metrics

`process_virtual_memory_bytes`

- **Description:** Virtual memory size in bytes
- **Labels:** none
- **Type:** gauge

`process_resident_memory_bytes`

- **Description:** Resident memory size in bytes
- **Labels:** none
- **Type:** gauge

`process_start_time_seconds`

- **Description:** Start time of the process since unix epoch in seconds
- **Labels:** none
- **Type:** gauge

`process_cpu_seconds_total`

- **Description:** Total user and system CPU time spent in seconds
- **Labels:** none
- **Type:** counter

`process_open_fds`

- **Description:** Number of open file descriptors
- **Labels:** none
- **Type:** gauge

`process_max_fds`

- **Description:** Maximum number of open file descriptors
- **Labels:** none
- **Type:** gauge
