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
            r"|(?:follow[ -]?up|remind|check with)\b.*"
            r"|(?:call|email|contact|ask)\b.*\b(?:today|tomorrow|later|asap|now|urgently|"
            r"next (?:business )?(?:day|week)|to (?:approve|review|confirm|submit|send|process)|"
            r"for (?:approval|review|follow[ -]?up))\b.*",
            normalized,
        )
    )
