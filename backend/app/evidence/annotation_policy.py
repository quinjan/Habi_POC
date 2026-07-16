import re


def is_workflow_noise(value: str) -> bool:
    """Return whether source text is process/status noise rather than a qualifier."""
    normalized = " ".join(value.casefold().strip(" .!?:;-").split())
    if normalized in {
        "paid",
        "paid already",
        "already paid",
        "unpaid",
        "for approval",
        "pending approval",
        "awaiting approval",
        "approved",
        "rejected",
        "pending review",
        "reviewed",
        "submitted",
        "in progress",
        "completed",
        "done",
        "follow up",
        "follow-up",
    }:
        return True
    return bool(
        re.fullmatch(
            r"(?:payment|invoice) (?:received|paid|complete|completed|processed|settled)"
            r"|(?:follow[ -]?up|call|email|contact|remind|check with|ask)\b.*",
            normalized,
        )
    )
