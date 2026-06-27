# Use Fake AI Provider In Automated Tests

Automated behavior tests for AI Extraction will use an injected fake AI provider rather than calling the real OpenAI API. Real-model end-to-end and quality checks can be built separately, while the core test suite remains deterministic, credential-free, fast, and able to cover valid candidates, empty results, invalid output, and provider failures.
