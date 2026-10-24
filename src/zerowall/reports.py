"""Fixed-snapshot, escaped reports and portable checksummed evidence packs."""

import hashlib, html, io, json, zipfile
from .db import canonical, now, uid, DomainError
from .analysis import calculate_bound, compare_trials, evaluate_rubric, decision_gates


def report_markdown(view):
    m = view["mission"]
    b = view["budget"]
    lines = [
        f"# {m['brief']['title']}",
        "",
        f"Mode: **{m['brief']['mode']}** · protocol `{m.get('protocol_hash', 'draft')}`",
        "",
        m["brief"]["goal"],
        "",
        f"Research provider: **{m['brief'].get('provider', 'nebius_token_factory')}**",
        "",
        "## Method and limits",
        "",
        "Four logical research seats; actual model identities and reuse are recorded below. The orchestrator does not vote. Fixture results are synthetic workflow demonstrations. Calculations are not physical measurements. API observations do not expose provider hardware, kernels, memory bandwidth or energy.",
        "",
        "## Budget",
        "",
        f"Settled: ${b['settled_usd']:.6f}; reserved: ${b['reserved_usd']:.6f}; unknown maximum: ${b['unknown_usd']:.6f}. Absolute provider allowance: ${b['absolute_cap_usd']}; authorized additional payments: $0.",
        "",
        "## Council and hypotheses",
        "",
    ]
    for r in view["rounds"]:
        lines += [
            f"### Round {r['id']}",
            f"Status: {r['status']} · context `{r['context_hash']}`",
        ]
        for s in r["seats"]:
            lines.append(f"- {s['name']}: {s['model']} ({s['state']})")
        for sub in r.get("submissions", []):
            lines += [
                "",
                f"**{sub['seat']}**: {sub['content']['mechanism']}",
                f"Prediction: {sub['content']['prediction']}",
                f"Kill rule: {sub['content']['kill_rule']}",
            ]
    lines += ["", "## Evidence", ""]
    for e in view["evidences"]:
        lines += [
            f"### {e['id']} · {e['evidence_class']}",
            f"Capability: `{e['capability']}` · artifact SHA-256: `{e['sha256']}`",
            "",
            "```json",
            json.dumps(e["result"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    lines += ["## Decisions and dissent", ""]
    for d in view["decisions"]:
        lines += [
            f"### {d['verdict']} · {d['status']}",
            d["conclusion"],
            "",
            f"Agreement: {d['agreement']}",
        ]
        lines += [f"- {g['id']} {g['name']}: **{g['status']}**" for g in d["gates"]]
        lines += ["", "Dissent:"] + [
            f"- {v}"
            for v in d["dissent"]
            or ["No dissent recorded; absence is not proof of unanimity."]
        ]
        lines += ["Reopen triggers:"] + [f"- {v}" for v in d["reopen_triggers"]]
    lines += ["", "## Reframes and next actions", ""]
    for r in view["reframes"]:
        lines += [
            f"- {r['reason']} → {r['interpretation']}",
            f"  Next: {r['next_action']}",
        ]
    lines += ["", "## Unresolved concerns", ""] + [
        f"- {x['text']} ({x['status']})" for x in view["concerns"]
    ]
    lines += [
        "",
        "## Interpretation",
        "",
        "Small task sets support bounded descriptive findings. Deterministic numeric, schema and source-ID checks do not establish general semantic quality. Human rubric annotations and independent live confirmation are separate evidence. Failed and unknown gates retain their labels. No universal model-council superiority or hardware optimization is claimed.",
        "",
        "## Reproduction",
        "",
        "Run `python scripts/verify_pack.py pack.zip` and `python scripts/reproduce.py pack.zip`. These commands use no API key, make no network request and incur no inference charge.",
    ]
    return "\n".join(lines)


def export_pack(research, mid):
    with research.store.tx() as c:
        view = research.view(c, mid)
        private = [
            r
            for r in view["rounds"]
            if not r["revealed"]
            and r["status"] not in ("cancelled", "stale", "failed", "interrupted")
        ]
        if private:
            raise DomainError(
                "Finish or reveal private rounds before exporting a public pack"
            )
        reservations = [
            dict(r)
            for r in c.execute("SELECT * FROM reservations WHERE mission_id=?", (mid,))
        ]
        trials = research.store.list(c, "trial", mid)
        runs = research.store.list(c, "run", mid)
        schedules = research.store.list(c, "schedule", mid)
        from .source_exports import export_values
        chats = research.store.list(c, 'chat', mid)
        enrichment = export_values(research, c, chats[0]) if chats else {}
        for d in view["decisions"]:
            s = research.store.get(c, d["step_id"], "step")
            d["current_gates"] = research.gates(c, s, d)
    view = research.artifacts.redact(view)
    files = {
        "research.json": canonical(view).encode(),
        "report.md": report_markdown(view).encode(),
    }
    files.update({name: value.encode() for name, value in enrichment.items()})
    body = html.escape(files["report.md"].decode())
    files["report.html"] = (
        "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>ZeroWall research report</title><style>body{max-width:1000px;margin:48px auto;padding:24px;background:#f6f5f0;color:#1b2927;font:16px/1.6 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>ZeroWall · Research report</h1><pre>"
        + body
        + "</pre></html>"
    ).encode()
    registries = {
        "research-map": view["causal_edges"],
        "hypothesis-registry": view["hypotheses"],
        "decision-ledger": view["decisions"],
        "concern-register": view["concerns"],
        "assumption-register": [
            {
                "decision_id": d["id"],
                "assumptions": d["assumptions"],
                "status": "untested",
            }
            for d in view["decisions"]
        ],
        "negative-results": [
            h
            for h in view["hypotheses"]
            if h["status"] in ("falsified", "blocked", "superseded")
        ],
        "tradeoffs": view["tradeoffs"],
        "bottleneck-timeline": view["reframes"],
        "next-actions": [
            {
                "owner": "human_director",
                "action": r["next_action"],
                "evidence_ids": r["evidence_ids"],
                "capability": None,
                "capability_status": "Requires the next director-approved typed plan; no execution authorized by this report.",
                "expected_evidence": "A provenance-recorded artifact and the frozen validators for the next discriminating test.",
                "completion_criterion": "The approved next experiment is terminal, its artifact verifies, and its result is reviewed.",
            }
            for r in view["reframes"]
        ],
        "budget-ledger": reservations,
        "runs": runs,
        "trials": trials,
        "schedules": schedules,
        "evidence-map": [
            {
                "evidence_id": e["id"],
                "artifact_id": e["artifact_id"],
                "sha256": e["sha256"],
                "run_id": e["run_id"],
                "experiment_id": e["experiment_id"],
                "evidence_class": e["evidence_class"],
            }
            for e in view["evidences"]
        ],
    }
    for name, value in registries.items():
        files[name + ".json"] = canonical(research.artifacts.redact(value)).encode()
    files["minority-report.md"] = (
        "# Minority report\n\n"
        + "\n".join(x for d in view["decisions"] for x in d["dissent"] or [])
    ).encode()
    files["causal-nodes.json"] = canonical(view.get("causal_nodes", [])).encode()
    files["challenge-groups.json"] = canonical(
        view.get("challenge_groups", [])
    ).encode()
    for artifact in view["artifacts"]:
        content = research.artifacts.read(artifact)
        files["artifacts/" + artifact["id"] + ".json"] = canonical(content).encode()
    for split in ("exploration", "confirmation"):
        files[f"tasks/{split}.json"] = (
            research.settings.root / f"benchmark/tasks/{split}.json"
        ).read_bytes()
    files["evaluators/hidden.json"] = (
        research.settings.root / "benchmark/evaluators/hidden.json"
    ).read_bytes()
    files["reproduce.json"] = canonical(
        {
            "schema_version": 1,
            "analysis_version": "paired-task-v1",
            "network_required": False,
            "claim_scope": "Replay stored deterministic calculations and comparisons; no new inference.",
            "created_at": now(),
            "mission_revision": view["mission"]["revision"],
            "protocol_hash": view["mission"].get("protocol_hash"),
        }
    ).encode()
    checksums = {
        name: hashlib.sha256(content).hexdigest() for name, content in files.items()
    }
    files["checksums.sha256"] = "\n".join(
        f"{sha}  {name}" for name, sha in sorted(checksums.items())
    ).encode()
    export_id = uid("export")
    folder = research.settings.data / "exports"
    folder.mkdir(exist_ok=True)
    path = folder / (export_id + ".zip")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
    if research.artifacts.files:
        research.artifacts.files.write('exports/' + path.name, archive.getvalue())
    else:
        path.write_bytes(archive.getvalue())
    record = {
        "id": export_id,
        "mission_id": mid,
        "filename": path.name,
        "sha256": hashlib.sha256(archive.getvalue()).hexdigest(),
        "files": len(files),
        "protocol_hash": view["mission"].get("protocol_hash"),
        "created_at": now(),
    }
    with research.store.tx() as c:
        research.store.put(c, "export", record)
        research.store.event(
            c, mid, "export.created", {"id": export_id, "sha256": record["sha256"]}
        )
    return record


def verify_pack(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive paths")
        if any(
            n.startswith(("/", "\\"))
            or ".." in n.replace("\\", "/").split("/")
            or ":" in n
            for n in names
        ):
            raise ValueError("Unsafe archive path")
        if sum(i.file_size for i in z.infolist()) > 100_000_000:
            raise ValueError("Pack exceeds 100 MB limit")
        checks = {
            line.split("  ", 1)[1]: line.split("  ", 1)[0]
            for line in z.read("checksums.sha256").decode().splitlines()
        }
        if set(names) - {"checksums.sha256"} != set(checks):
            raise ValueError("Checksum inventory mismatch")
        for name, sha in checks.items():
            if hashlib.sha256(z.read(name)).hexdigest() != sha:
                raise ValueError("Checksum mismatch: " + name)
        return {
            "valid": True,
            "files": len(checks),
            "protocol_hash": json.loads(z.read("reproduce.json")).get("protocol_hash"),
        }


def reproduce(path):
    verified = verify_pack(path)
    results = []
    decisions = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if not name.startswith("artifacts/"):
                continue
            item = json.loads(z.read(name))
            cap = item.get("plan", {}).get("capability")
            args = item.get("args")
            fn = {
                "analysis.calculate_bound": calculate_bound,
                "analysis.compare_trials": compare_trials,
                "analysis.evaluate_rubric": evaluate_rubric,
            }.get(cap)
            if fn:
                actual = fn(args)
                results.append(
                    {
                        "artifact": name,
                        "capability": cap,
                        "matches": digest_equal(actual, item["result"]),
                    }
                )
            if cap == "inference.run_benchmark" and item["result"].get("observations"):
                old = item["result"]
                actual = compare_trials(
                    {
                        "observations": old["observations"],
                        "material_saving": json.loads(z.read("research.json"))[
                            "mission"
                        ]["brief"]["material_saving"],
                        "latency_limit_ms": json.loads(z.read("research.json"))[
                            "mission"
                        ]["brief"]["latency_limit_ms"],
                    }
                )
                results.append(
                    {
                        "artifact": name,
                        "capability": cap,
                        "matches": all(
                            digest_equal(actual[k], old[k])
                            for k in ("cells", "comparisons", "log_cost_interaction")
                        ),
                    }
                )
        view = json.loads(z.read("research.json"))
        from .source_exports import verify_extension
        research_replay = verify_extension(z)
        for d in view["decisions"]:
            evidence = [e for e in view["evidences"] if e["id"] in d["evidence_ids"]]
            step = next(s for s in view["steps"] if s["id"] == d["step_id"])
            gates = decision_gates(evidence, view["budget"], step["revision"])
            expected = d.get("current_gates", d["gates"])
            decisions.append(
                {
                    "decision_id": d["id"],
                    "verdict": d["verdict"],
                    "approval_status": d["status"],
                    "gates_match": digest_equal(gates, expected),
                    "confirmation_allowed": all(g["status"] == "pass" for g in gates),
                    "gates": gates,
                }
            )
    return {
        "verification": verified,
        "research_replay": research_replay,
        "reanalysis": results,
        "decisions": decisions,
        "all_match": all(x["matches"] for x in results)
        and all(x["gates_match"] for x in decisions),
        "network_calls": 0,
    }


def digest_equal(a, b):
    return canonical(a) == canonical(b)
