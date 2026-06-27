# Taxonomy Suggestion Matching Uses Normalized Exact Paths

Habi groups repeated AI-suggested category paths and remembers project-local taxonomy mappings using normalized exact paths: trim whitespace and case-fold each path segment, then compare the full path. This slice will not infer fuzzy matches, synonyms, or aliases, so similar but different paths remain separate until a reviewer explicitly maps them.
