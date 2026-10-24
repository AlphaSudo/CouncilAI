# Recovery and local operation

Run one server process per data directory. An OS file lock blocks a second executor and is released on process exit. SQLite uses WAL, `BEGIN IMMEDIATE` and a busy timeout. State changes, financial reservations and audit events commit transactionally. Calls are not kept inside a database transaction during network waits.

On restart, dispatched-but-unsettled reservations become unknown. In-flight call records become unknown; jobs and tool runs become interrupted. Unused parts of a schedule hold can be released because each dispatched call already owns its own transferred reservation. Queued jobs remain durable. Nothing automatically resends an ambiguous request.

Failed or interrupted council rounds preserve their validated seat submissions. Continue Missing Seats starts only missing work under the unchanged context. The default continuation blocks when a prior call has an unknown result. The typed API can explicitly authorize a newly reserved retry while retaining the old maximum, but the UI does not silently provide that authorization. Changed concern/context revisions require a fresh round. Two cross-review passes and three rounds per revision bound discussion; reopening records a new revision.

A pause prevents fresh dispatch. An in-flight request may still finish and be retained. Resume restores permission to dispatch; an interrupted/failed phase still needs the visible continuation control. Cancellation of queued experiments prevents their job from being claimed. Cancelling a running experiment preserves any late evidence and financial charge.

Back up with the server stopped using `scripts/backup.py`. It takes the executor lock, uses SQLite's backup operation, includes artifacts/exports, and hashes every included file. The API key and director-token file are excluded. Restore requires an empty destination and verifies paths, inventory, size and checksums before writing. It clears live verification and creates a new local director token on next startup. Reservations survive the restore. Re-run doctor and inspect mission state before continuing.

The current record schema is migration version 1. Do not manually edit research rows or financial states to bypass a gate. Keep backups before updating the application. The local service is not a public multi-tenant host; the default localhost binding, director cookie, same-origin control header and exact request schemas form its supported boundary.
