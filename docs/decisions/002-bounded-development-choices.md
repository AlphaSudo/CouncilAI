# 002 · Conservative retry, similarity and distribution choices

The local implementation uses zero automatic JSON-repair or HTTP retries. A failed round preserves valid seats, raw invalid output and reservations; explicit continuation creates a newly reserved attempt. This bounds hidden behavior more tightly than the plan's allowance of at most one automatic/schema repair. HTTP 429 backoff is persisted and enforced before an explicit subsequent attempt.

Related-proposal suggestions use fixed local domain-concept normalization plus cosine overlap. This avoids an extra model service, model-weight download or inference charge. The UI/API call it an approximate suggestion. It is not a reliable learned semantic similarity estimate and cannot suppress an experiment or determine a finding.

The development test build is distributed as a credential-free source ZIP with a prebuilt UI, locked dependencies, tests, setup and reproduction tools. It uses the existing workstation and no hosting budget. Public repository/download publication and independent human setup verification remain external release actions. The implementation does not imply that a public judging URL or a finished Devpost entry exists.

These choices preserve the director's scope and budget. Streaming/structured-output probes, genuine model experiments and any final claim await the explicitly deferred billing verification.
