# Use Pinned GPT-5.4 With Tiered Reasoning

Free-form Manual Source Entry extraction uses the pinned `gpt-5.4-2026-03-05` snapshot. The normal production attempt uses `medium` reasoning. When the centralized retry flag from ADR 0127 permits a confirmation or repair, the one retry uses the same snapshot at `high` reasoning. Deployment variables remain overridable, and XLSX processing keeps its separate `OPENAI_MODEL` configuration.

The single paid POC evaluation from ADR 0151 also uses `gpt-5.4-2026-03-05` at `medium` reasoning, with application retries disabled and OpenAI client retries set to zero. It therefore measures the normal first-attempt configuration in exactly one authorized model call; retry behavior remains covered offline.

This supersedes only the GPT-5.5 model and `high`/`xhigh` reasoning defaults in ADR 0121 and ADR 0127. Their extraction contract, atomic validation, centralized retry control, and human-controlled evaluation workflow remain accepted.
