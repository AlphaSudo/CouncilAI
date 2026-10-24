from pathlib import Path
import hashlib, json, math
from .db import canonical, DomainError, uid, now


class Artifacts:
    def __init__(self, root, secret="", files=None):
        self.root = Path(root)
        self.files = files
        self.secrets = [
            s for s in ([secret] if isinstance(secret, str) else secret) if s
        ]

    def redact(self, value):
        if isinstance(value, float) and not math.isfinite(value):
            return {'invalid_numeric': repr(value)}
        if isinstance(value, dict):
            return {
                k: (
                    "[REDACTED]"
                    if any(
                        s in k.lower()
                        for s in (
                            "api_key",
                            "authorization",
                            "cookie",
                            "director_token",
                        )
                    )
                    else self.redact(v)
                )
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [self.redact(v) for v in value]
        if isinstance(value, str):
            for secret in self.secrets:
                value = value.replace(secret, "[REDACTED]")
        return value

    def write(self, mission_id, kind, value):
        artifact_id = uid("artifact")
        content = canonical(self.redact(value)).encode()
        folder = self.root / mission_id
        if not self.files:
            folder.mkdir(exist_ok=True)
        path = folder / f"{artifact_id}.json"
        if self.files:
            self.files.write('artifacts/' + path.relative_to(self.root).as_posix(), content)
        else:
            path.write_bytes(content)
        return {
            "id": artifact_id,
            "mission_id": mission_id,
            "path": str(path.relative_to(self.root)),
            "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content),
            "kind": kind,
            "created_at": now(),
        }

    def read(self, artifact):
        path = (self.root / artifact["path"]).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise DomainError("Invalid artifact path", 400)
        content = self.files.read('artifacts/' + path.relative_to(self.root).as_posix(), artifact['sha256']) if self.files else path.read_bytes()
        if hashlib.sha256(content).hexdigest() != artifact["sha256"]:
            raise DomainError("Artifact integrity check failed", 422)
        return json.loads(content)
