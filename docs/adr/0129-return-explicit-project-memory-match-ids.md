# Return Explicit Project Memory Match IDs

For every grounded Material, Service, or external Provider in a GPT-5.5 free-form candidate, the model will return either the explicit ID of one proposed active Project Memory match or `null` for a new concept. Habi validates that a claimed record is active, belongs to the selected Project Workspace, has the required record type, and has the exact display name and category that were supplied in that request; a failed claim is invalid output and follows the configured repair or atomic-failure policy. Internal and Unknown Provider States always carry a null Provider match.

The candidate retains both exact Observed Name Text or Observed Provider Text and the normalized proposed name, so source wording such as `Eagle Portland` may visibly propose `Eagle Portland Cement` with Material Memory Record ID 42. An explicit ID makes semantic matching auditable and prevents a model-authored name or badge from masquerading as a real Project Memory association; import reuse still follows reviewed candidate behavior and backend authority rather than the AI claim alone.

Material, Service, and external Provider Proposed Project Memory Matches are reviewed through the creatable Memory-Aware Name control defined by ADR 0130.
