"""Explicit policy selection for current and historical publication snapshots."""

from . import review_policy_v1

POLICY_VERSION = review_policy_v1.POLICY_VERSION


def implementation(snapshot):
    contract = snapshot["contract"]
    protocol = contract.get("protocol_version")
    policy = contract.get("policy_version")
    if protocol == "reviewed_v1" and policy == review_policy_v1.POLICY_VERSION:
        return review_policy_v1
    if protocol == "reviewed_v2" and policy == "generic-publication-v2":
        from . import review_policy_v2

        return review_policy_v2
    if protocol == "reviewed_v3" and policy == "generic-publication-v3":
        from . import review_policy_v3

        return review_policy_v3
    if protocol == "reviewed_v4" and policy == "generic-publication-v4":
        from . import review_policy_v4

        return review_policy_v4
    raise ValueError("Unknown or mismatched review policy version")


def publication_decisions(snapshot):
    return implementation(snapshot).publication_decisions(snapshot)


def ledger_markdown(snapshot):
    return implementation(snapshot).ledger_markdown(snapshot)
