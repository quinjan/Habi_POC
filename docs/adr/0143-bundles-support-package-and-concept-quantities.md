# Bundles Support Package And Concept Quantities

A Bundled Purchase Line may retain one optional source-stated Bundle Quantity and unit for the complete commercial package, while every Purchase Line Concept Link may independently retain a source-stated concept quantity and unit. For `One lot: supply and install 10 steel doors and 5 aluminum windows for PHP 150,000`, the line stores `1 lot`, the two Material links store `10 units` and `5 units`, and the installation Service link remains without a quantity unless the source states one. The combined price remains line-level under ADR 0142.

GPT-5.5 must ground every populated bundle-level or concept-level quantity in the candidate's verified spans and must not derive one level by summing, copying, or allocating the other. Standard single-concept Purchase Lines retain their existing line-level quantity representation; this decision adds per-link quantity semantics where a multi-concept bundle otherwise cannot preserve distinct source amounts.

Concept links may also retain source-stated component unit prices when explicit package pricing keeps the concepts bundled under ADR 0149; those values are not separate Purchase Line totals.
