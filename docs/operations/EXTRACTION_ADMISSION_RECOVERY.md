# Extraction metadata recovery

On October 23, 2026, a completed Super extraction was rejected because two observation classification rationales were omitted and two audit descriptors used null for unused numerator/denominator text fields.

Admission policy `council-admission/2` records absent, null or blank observation rationales as explicitly not supplied, without inventing an explanation or changing the model's classification. A previously complete observation assessment becomes partial. The observations remain unverified. Null numerator/denominator fields become empty, unspecified text; a resource ratio with missing terms still fails its structural completeness check. Existing valid values, source references, claim coverage and raw receipts remain unchanged. Invalid field objects, fabricated classifications and invalid references still fail atomically.

Every adjustment is retained in the admission record with before/after values, paths and reasons. The extraction prompt explicitly requests observation reasons and text ratio fields. Frozen legacy protocols are unchanged.

The completed reply `call_bfc9f3fe95314aad` in `chat_45c739b53a0a42b8` was validated on a database copy, then restored using the existing guarded, idempotent local restoration path. Six claims, two observations and two audit descriptors were retained. The chat remains paused before scrutiny. No inference, automatic retry or automatic resume occurred; all original calls, reservations and prior messages were compared and remained unchanged. A SQLite backup was created before restoration.

Validation: 24 admission/recovery checks and 57 review/Beam regression checks passed. The regression cases include unknown sources, missing coverage, fabricated verified classifications, malformed objects, incomplete ratio accounting and repeated local recovery with no added calls or financial changes.

Evidence: `docs/validation/extraction-metadata-recovery.xml`, `docs/validation/extraction-metadata-regression.xml` and `docs/validation/extraction-metadata-live-recovery.json`.
