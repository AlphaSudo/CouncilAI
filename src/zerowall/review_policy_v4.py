"""Evidence labels are assessments, never a whitelist for delivering public text."""

from .review_policy_v3 import ledger_markdown as prior_ledger
from .review_policy_v3 import publication_decisions as assessed_decisions

POLICY_VERSION = "generic-publication-v4"


def ledger_markdown(snapshot):
    return prior_ledger(snapshot)


def publication_decisions(snapshot):
    return [
        dict(
            item,
            policy_version=POLICY_VERSION,
            publication_rule="qualification_only",
            origin="local_scoped_policy",
        )
        for item in assessed_decisions(snapshot)
    ]
