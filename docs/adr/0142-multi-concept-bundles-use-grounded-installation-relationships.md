# Multi-Concept Bundles Use Grounded Installation Relationships

A standard Purchase Line has exactly one linked Material or Service, while a Bundled Purchase Line has two or more distinct linked concepts presented by the source as one combined commercial fact. A bundle may contain multiple Materials, multiple Services, or any mixture; its one combined price remains on the Purchase Line instead of being allocated or converted into Unknown per-link prices. Habi derives standard versus bundled shape from link count and does not accept a separate model `line_type`.

Material-and-Service co-occurrence does not by itself mean supply-and-install. GPT-5.5 returns exact source-grounded Installation Relationships, each connecting one installation Service link to the one or more Material links it installs. A known External or Internal Provider receives Material Supplier when any Material link exists, Service Provider when any Service link exists, and Supply-and-Install Provider only when at least one valid Installation Relationship exists; Unknown Provider receives no role. This supports two Materials installed through one Service, partial installation coverage, and multiple installation Services without falsely treating hauling, delivery, or unrelated work as installation.

Each concept retains its own Memory-Aware Name, Observed Name Text, Project Memory match, and new-record taxonomy behavior. This supersedes ADR 0114's exactly-one-Material/one-Service bundle and automatic all-three-role rule, ADR 0126's maximum-two free-form concept shape, and ADR 0141's requirement to split multiple Materials with a combined total into separate Unknown-price Purchase Lines. ADR 0139 and ADR 0140 still prevent worked-on objects and incidental transaction terms from becoming unsupported concept links.

Bundle-level and per-concept quantity semantics follow ADR 0143.

Bundle Provider identity follows ADR 0144: different Providers force separate Purchase Lines even when source text gives one unallocated combined total.

Bundle concept-link count follows ADR 0145 and has no fixed free-form cap or truncation behavior.

Individually attributable concept prices follow ADR 0146 and produce separate Purchase Lines; a bundle retains only an unallocated combined price.

Explicit package pricing follows ADR 0149 and retains one bundle even when compatible component arithmetic is available.
