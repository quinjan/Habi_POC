# Issue #53 intelligent XLSX prototype

> THROWAWAY PROTOTYPE — this branch is evidence for issue #53, not production code.

## Question

Can pinned `gpt-5.4-2026-03-05`, using one outbound-network-disabled
OpenAI hosted container and the managed `openai-spreadsheets` skill, inspect a
representative varied workbook and make exactly one `submit_candidate_batch`
call that:

- accounts for every worksheet and every non-empty cell on visible worksheets;
- proposes domain-useful final/as-used Purchase Lines;
- supplies field-level cell/range evidence that Habi can independently verify;
- completes at acceptable POC latency and cost?

The provisional submission contract exists only to make that question
measurable. Issue #51 owns the production contract.

This intentionally contradicts ADR-0113's worksheet-profile plus bounded-chunk
pipeline and ADR-0117's deterministic explicit-row extraction. Issue #53 is
testing the replacement architecture tracked by issue #49; issue #50 must
decide whether those ADRs are superseded before production implementation.

The Logic Prototype skill normally calls for an action-driven TUI. The
user-confirmed public seam for this question is instead one retry-disabled model
run: introducing interactive actions during the run would change the measured
cost, latency, and single-response behavior. The CLI therefore renders its full
state after each lifecycle transition but does not offer actions other than
termination.

## Run

Prepare the deterministic fixture without making an API call:

```powershell
python -m backend.app.xlsx.prototypes.issue_53_intelligent_xlsx --prepare-only
```

After a human explicitly approves the paid call:

```powershell
python -m backend.app.xlsx.prototypes.issue_53_intelligent_xlsx --approved-by "Quinjan"
```

The command uses `OPENAI_API_KEY` from the environment or the nearest ancestor
`.env`, without printing it. It writes sanitized run artifacts beneath the
ignored `.runs/` directory. It never writes the raw model response or shell
transcript.

At runtime it retrieves the curated skill metadata, records the live latest
version, and attaches that numeric version to the hosted container. If metadata
lookup cannot expose a numeric version, the compatibility fallback attaches
`latest` and records that limitation in the scorecard; failure to attach either
form fails the prototype before a model response is created.

## Deliberate fixture variation

The generated workbook contains:

- multiple worksheets with different layouts;
- merged title cells and multi-row headers;
- materials, services, and a bundled supply-and-install Purchase Line;
- external, internal, and unknown Provider States;
- shared and cross-sheet context;
- source-stated totals, a formula, notes, terms, workflow noise, and explicitly
  non-final rows.

## Prototype pass boundary

PASS requires all of the following in the single model response:

1. Exactly one `submit_candidate_batch` function call.
2. Every workbook worksheet is inventoried exactly once.
3. Every non-empty cell on visible worksheets is covered by an accounting
   range.
4. Every cited worksheet, range, coordinate, and exact cell value verifies
   against the preserved workbook.
5. Every important candidate field has evidence.
6. The six deliberately planted final/as-used Purchase Lines are represented,
   and the deliberately non-final/noise items are not candidates.
7. The hosted container is deleted.

The scorecard reports the observed latency and estimated GPT-5.4 plus container
cost. Whether those observations are acceptable is the decision recorded on
issue #53.
