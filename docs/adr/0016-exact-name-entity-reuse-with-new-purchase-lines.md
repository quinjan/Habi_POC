# Exact-Name Entity Reuse With New Purchase Lines

Manual-source imports will reuse active Material, Service, and Provider memory records by exact normalized name within the selected Project Workspace, but each approved candidate will create a new Purchase Line. This gives the first import slice minimal duplicate control for reusable entities while preserving Purchase Lines as source-backed purchasing facts that should only be merged through explicit human-reviewed merge behavior.
