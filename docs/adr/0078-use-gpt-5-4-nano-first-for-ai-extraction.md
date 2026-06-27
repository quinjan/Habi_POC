# Use GPT-5.4 Nano First For AI Extraction

Habi will default AI Extraction and AI-suggested category paths to `gpt-5.4-nano` through the OpenAI API, using strict structured outputs and backend validation to keep the harness responsible for correctness. `gpt-5.4-mini` is reserved as a later targeted escalation only if scorecard fixtures show the nano model misses too many useful candidates or produces inadequate suggestions for a specific step.
