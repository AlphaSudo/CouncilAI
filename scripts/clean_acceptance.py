"""Verify the packaged distribution in a new environment, with no provider credentials."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from package_release import package

ROOT = Path(__file__).resolve().parents[1]


def run(evidence_prefix=None):
    archive = package()
    temp = Path(tempfile.mkdtemp(prefix="zerowall-clean-"))
    with zipfile.ZipFile(archive["path"]) as z:
        checks = json.loads(z.read("SOURCE_CHECKSUMS.json"))
        if set(z.namelist()) != set(checks) | {"SOURCE_CHECKSUMS.json"}:
            raise ValueError("Source inventory mismatch")
        for name, sha in checks.items():
            target = (temp / name).resolve()
            if not target.is_relative_to(temp.resolve()):
                raise ValueError("Unsafe source archive path")
            if hashlib.sha256(z.read(name)).hexdigest() != sha:
                raise ValueError("Source checksum mismatch")
        z.extractall(temp)
    env = dict(os.environ)
    env["NEBIUS_API_KEY"] = ""
    env["OPENROUTER_API_KEY"] = ""
    env["TAVILY_API_KEY"] = ""
    for key in ("ZAI_API_KEY", "GEMINI_API_KEY", "NVIDIA_NIM_API_KEY", "GROQ_API_KEY"):
        env[key] = ""
    env["ZEROWALL_DIRECT_FREE_CONFIRMED"] = "false"
    env.pop("ZEROWALL_DATA_DIR", None)
    python = (
        temp / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
    npm = "npm.cmd" if os.name == "nt" else "npm"
    results = []

    def command(args, timeout=240):
        print("Clean check: " + " ".join(str(a).replace(str(temp), "<clean>") for a in args), flush=True)
        result = subprocess.run(
            [str(a) for a in args],
            check=False,
            cwd=temp,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        results.append(
            {
                "command": [str(a).replace(str(temp), "<clean>") for a in args],
                "exit_code": result.returncode,
                "output_tail": (result.stdout + "\n" + result.stderr)[-4000:],
            }
        )
        if result.returncode:
            raise RuntimeError(
                "Clean acceptance command failed: "
                + str(args[0])
                + "\n"
                + results[-1]["output_tail"]
            )
        return result.stdout

    command([sys.executable, "-m", "venv", temp / ".venv"])
    command([python, "-m", "pip", "install", "-r", "requirements.lock"])
    command([python, "-m", "pip", "install", "--no-deps", "-e", "."])
    command([python, "scripts/setup_tokenizers.py"], timeout=360)
    command([npm, "ci", "--prefix", "apps/web"])
    command([npm, "run", "build", "--prefix", "apps/web"])
    command(
        [python, "-m", "pytest", "-q", "--junitxml=docs/validation/backend-results.xml"], timeout=900
    )
    seeded = json.loads(command([python, "scripts/seed_demo.py"]))
    doctor = json.loads(command([python, "scripts/doctor.py"]))
    reproduced = json.loads(
        command([python, "scripts/reproduce.py", "--analyze-only", seeded["export"]])
    )
    review_reproduction = json.loads(command([python, "scripts/seed_scoped_review.py"]))
    if (
        doctor["key_present"]
        or doctor["live_verification_present"]
        or doctor["budget"]["attempts"]
        or not reproduced["all_match"]
        or not review_reproduction["all_reproduced"]
    ):
        raise ValueError("Fresh credential-free acceptance failed")
    result = {
        "passed": True,
        "source_tree_sha256": archive["source_tree_sha256"],
        "archive_tested_sha256": archive["sha256"],
        "fresh_directory": str(temp),
        "provider_key_present": False,
        "paid_inference_requests": 0,
        "independent_human_operator": False,
        "commands": results,
        "doctor": doctor,
        "reproduced": reproduced,
        "review_reproduction": review_reproduction,
    }
    report_name = (
        evidence_prefix + "-clean-setup.json" if evidence_prefix else "clean-setup.json"
    )
    junit_name = (
        evidence_prefix + "-clean-backend.xml"
        if evidence_prefix
        else "backend-results.xml"
    )
    (ROOT / "docs/validation" / report_name).write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    shutil.copyfile(
        temp / "docs/validation/backend-results.xml",
        ROOT / "docs/validation" / junit_name,
    )
    print(
        json.dumps(
            {
                "passed": True,
                "source_tree_sha256": archive["source_tree_sha256"],
                "commands": len(results),
                "paid_inference_requests": 0,
                "pack_reproduces": reproduced["all_match"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    import argparse
    import re

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-prefix")
    args = parser.parse_args()
    if args.evidence_prefix and not re.fullmatch(r"[a-z0-9.-]+", args.evidence_prefix):
        raise ValueError("Evidence prefix must be a simple lowercase file stem")
    run(args.evidence_prefix)
