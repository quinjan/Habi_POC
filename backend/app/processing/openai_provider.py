from dataclasses import dataclass
import json
import os


EXTRACTION_SYSTEM_PROMPT = (
    "Extract final/as-used construction purchase lines from the manual source text. "
    "Return only purchase-line candidates that are clearly materials or services. "
    "Use null for unknown fields instead of inventing values. Evidence must point "
    "to the whole preserved manual source entry."
)

PURCHASE_LINE_EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "line_type": {"type": "string", "enum": ["material", "service"]},
                    "name": {"type": "string", "minLength": 1, "maxLength": 255},
                    "quantity": {"type": ["string", "null"], "maxLength": 100},
                    "unit": {"type": ["string", "null"], "maxLength": 100},
                    "price": {"type": ["string", "null"], "maxLength": 100},
                    "currency": {"type": ["string", "null"], "maxLength": 10},
                    "currency_state": {
                        "type": "string",
                        "enum": ["source_stated", "defaulted", "unknown"],
                    },
                    "provider_name": {"type": ["string", "null"], "maxLength": 255},
                    "purchase_date": {
                        "type": ["string", "null"],
                        "description": "Full ISO date YYYY-MM-DD only, or null.",
                    },
                    "remarks_or_terms": {"type": ["string", "null"], "maxLength": 2000},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "category_suggestion": {
                        "anyOf": [
                            {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "top_level_category": {
                                        "type": ["string", "null"],
                                        "maxLength": 255,
                                    },
                                    "subcategory": {
                                        "type": ["string", "null"],
                                        "maxLength": 255,
                                    },
                                },
                                "required": ["top_level_category", "subcategory"],
                            },
                            {"type": "null"},
                        ]
                    },
                    "evidence": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "source_submission_id": {"type": "integer"},
                            "locator": {
                                "type": "string",
                                "enum": ["manual_source_entry.original_text"],
                            },
                        },
                        "required": ["source_submission_id", "locator"],
                    },
                },
                "required": [
                    "line_type",
                    "name",
                    "quantity",
                    "unit",
                    "price",
                    "currency",
                    "currency_state",
                    "provider_name",
                    "purchase_date",
                    "remarks_or_terms",
                    "confidence",
                    "category_suggestion",
                    "evidence",
                ],
            },
        }
    },
    "required": ["candidates"],
}


@dataclass(frozen=True)
class OpenAiProviderConfig:
    api_key: str
    model: str = "gpt-5.4-nano"
    base_url: str | None = None

    @classmethod
    def from_env(cls) -> "OpenAiProviderConfig":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for AI Extraction worker")
        return cls(
            api_key=api_key,
            model=os.getenv("OPENAI_MODEL", "gpt-5.4-nano"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )


class OpenAiExtractionProvider:
    provider_name = "openai"

    def __init__(self, config: OpenAiProviderConfig, client=None):
        self.config = config
        if client is None:
            from openai import OpenAI

            client_kwargs = {"api_key": config.api_key}
            if config.base_url is not None:
                client_kwargs["base_url"] = config.base_url
            client = OpenAI(**client_kwargs)
        self.client = client

    @property
    def model(self) -> str:
        return self.config.model

    def extract_purchase_lines(
        self,
        *,
        original_text: str,
        source_submission_id: int,
    ) -> dict:
        response = self.client.responses.create(
            model=self.config.model,
            input=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"source_submission_id: {source_submission_id}\n\n"
                        f"{original_text}"
                    ),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "habi_purchase_line_extraction",
                    "schema": PURCHASE_LINE_EXTRACTION_SCHEMA,
                    "strict": True,
                }
            },
        )
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            output_text = getattr(response, "output_text", None)
            if isinstance(output_text, str):
                try:
                    parsed = json.loads(output_text)
                except json.JSONDecodeError as error:
                    raise RuntimeError(
                        "OpenAI response did not contain valid JSON structured output"
                    ) from error
        if not isinstance(parsed, dict) or not isinstance(parsed.get("candidates"), list):
            raise RuntimeError("OpenAI response did not contain usable structured output")
        return parsed
