# 001 · Local control plane and hosted inference

Status: implemented in the development candidate, October 18, 2026.

The director authorized a local research council with Token Factory as its only required external inference service. Self-managed GPU execution, Nebius AI Cloud projects, SSH, local weights, and CUDA are outside the core. Genuinely free hardware work may follow the core as optional extension X1.

Python/FastAPI owns transitions, deterministic tools, reports and a single local executor. SQLite transactions own records, audit events, idempotency, jobs and integer micro-dollar reservations. React/TypeScript/Vite provides the director interface. Versioned content-addressed manifests make evidence inspectable and portable.

The default project already exists; use a project-scoped key in `.env.local`. The director's GitHub username is AlphaSudo. Account identifiers are not credentials and are deliberately absent from public application configuration.

The exact enabled model priority is Super VL, GLM 5.3 Flash, then Lightning, as recorded in `config/model_policy.json`. Four logical seats reuse the first verified available model. The controlled routing treatment can use the last available enabled model first only after explicit director approval. Optional DeepSeek stays disabled.

Existing-credit authorization is $25 total; additional personal payments and cloud hardware spending are $0. Live inference is currently locked at the director's explicit October 18 instruction because account billing controls have not been verified. Read-only catalog checks succeeded for all three requested model IDs. No paid inference is required for local development or fixture validation.

Every dispatch reserves a conservative maximum first. Ambiguous calls retain their maximum charge; full controlled benchmark schedules reserve their worst-case cost before starting. An OS lock enforces one executor per data directory. Restart marks in-flight calls unknown and requires explicit continuation rather than automatically replaying paid work.

This local development candidate does not establish NVIDIA runtime use, scientific optimization, external judging access, or a completed hackathon submission. Those require their own evidence.
