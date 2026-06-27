# AI Provider Runtime Failures Mark Jobs Failed

If the AI provider is configured but a runtime call fails because the OpenAI API is unavailable, times out, rate limits, or returns an unusable response, the worker will mark the claimed Processing Job as `failed` with a useful error message. Source submission remains durable and separate from processing success, while missing provider configuration still causes the worker to refuse to start before claiming jobs.
