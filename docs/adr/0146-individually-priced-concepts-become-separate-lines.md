# Individually Priced Concepts Become Separate Lines

When free-form source evidence states or unambiguously supports an individual price for each Material or Service, GPT-5.5 creates separate Purchase Lines even when the concepts appear under one heading, Provider, invoice, or summary total. `Cement — PHP 20,000; Rebar — PHP 30,000; Total — PHP 50,000` therefore creates two priced Material Purchase Lines; the summary total remains source context and does not turn them into a bundle or get copied as another line price.

A multi-concept Bundled Purchase Line is used when the source presents one combined commercial price that cannot be attributed safely to individual concepts. Habi never allocates a shared total proportionally or invents component prices. This price-allocation boundary takes precedence over proximity and common Provider while retaining ADR 0144's rule that different Providers always force separate lines.

An unambiguous backend-calculated total from grounded quantity and unit price is individually attributable under ADR 0147.

ADR 0149 overrides this split when explicit source wording establishes one authoritative package price despite component quantities or unit prices.
