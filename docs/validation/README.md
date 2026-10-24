# Published validation evidence

This directory publishes the public model catalogs needed by offline regression
tests and the scrubbed cloud-container report. The latter records the tested image,
application source hashes, memory limit and software-test result. It explicitly
distinguishes local Postgres and a Storage transport double from a real cloud deployment.

Developer screenshots, runtime traces, generated JUnit logs, personal chat identifiers
and local working evidence remain excluded from the public repository. Historical
engineering documents can refer to those local artifacts; their absence from this
repository does not claim that cloud deployment or live judging acceptance passed.

Reproduce the public checks using the test sources, `scripts/check_cloud_container.py`
and the commands in `docs/operations/VERCEL_SUPABASE.md`. Provider transport doubles
test software behavior, not answer quality or live provider latency.
