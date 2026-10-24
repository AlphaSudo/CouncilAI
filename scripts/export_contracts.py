from pathlib import Path
import json
from zerowall import contracts
from zerowall import answer_contracts

root = Path(__file__).resolve().parents[1] / "contracts"
root.mkdir(exist_ok=True)
count = 0
for name in dir(contracts):
    cls = getattr(contracts, name)
    if (
        isinstance(cls, type)
        and issubclass(cls, contracts.Contract)
        and cls is not contracts.Contract
    ):
        (root / (name + ".schema.json")).write_text(
            json.dumps(cls.model_json_schema(), indent=2), encoding="utf-8"
        )
        count += 1
print(f"Exported {count} validated JSON Schemas.")
for name in ("AnswerFinding", "FalsificationNote", "AnswerScrutiny", "StageResult", "ReviewWarning"):
    (root / (name + ".schema.json")).write_text(json.dumps(getattr(answer_contracts, name).model_json_schema(), indent=2), encoding="utf-8")
