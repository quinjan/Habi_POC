# Invalid Manual Source Entries Are Rejected Before Job Creation

Manual Source Entry request validation should reject input that is not valid submitted evidence before creating a Source Submission or Processing Job, such as blank free-form text or malformed structured-row form data. Once a valid Source Submission and queued Processing Job exist, later worker failures represent processing or AI Extraction failures rather than basic submission validation errors.
