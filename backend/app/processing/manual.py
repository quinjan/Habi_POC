import re


SERVICE_CUES = {"labor", "installation", "hauling", "coring", "rental"}
MATERIAL_UNITS = {"pcs", "bags", "meters", "m", "kg"}


def parse_free_form_manual_entry(
    *,
    original_text: str,
    source_submission_id: int,
) -> dict | None:
    text = original_text.strip()
    name = _extract_name(text)
    quantity, unit = _extract_quantity_and_unit(text)
    price, currency = _extract_price(text)
    provider_name = _extract_provider(text)

    has_detail = any([quantity, price, provider_name])
    if not name or not has_detail:
        return None

    line_type = _infer_line_type(text=text, unit=unit)
    return {
        "line_type": line_type,
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "price": price,
        "currency": currency,
        "provider_name": provider_name,
        "purchase_date": None,
        "remarks_or_terms": None,
        "raw_text": original_text,
        "confidence": 0.72,
        "category_suggestion": _category_suggestion(name),
        "evidence": {
            "source_submission_id": source_submission_id,
            "snippet": original_text,
            "locator": "manual_source_entry.original_text",
        },
    }


def _extract_name(text: str) -> str | None:
    first_segment = text.split(",", 1)[0].strip()
    return first_segment or None


def _extract_quantity_and_unit(text: str) -> tuple[str | None, str | None]:
    match = re.search(
        r"\b(?P<quantity>\d+(?:\.\d+)?)\s*(?P<unit>pcs|bags|meters|m|kg)\b",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None, None
    return match.group("quantity"), match.group("unit").lower()


def _extract_price(text: str) -> tuple[str | None, str | None]:
    match = re.search(r"\b(?P<currency>PHP)\s*(?P<price>\d[\d,]*(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if match is None:
        return None, None
    return match.group("price").replace(",", ""), match.group("currency").upper()


def _extract_provider(text: str) -> str | None:
    match = re.search(
        r"\b(?:from|by|provider:)\s+(?P<provider>[A-Za-z0-9 &.'-]+?)(?:,|$)",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    return match.group("provider").strip()


def _infer_line_type(*, text: str, unit: str | None) -> str | None:
    lowered_text = text.casefold()
    if any(cue in lowered_text for cue in SERVICE_CUES):
        return "service"
    if unit in MATERIAL_UNITS:
        return "material"
    return None


def _category_suggestion(name: str) -> dict | None:
    lowered_name = name.casefold()
    if "pipe" in lowered_name:
        return {
            "top_level_category": "Plumbing",
            "subcategory": "Pipes",
        }
    return None
