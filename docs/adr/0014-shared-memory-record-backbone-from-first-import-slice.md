# Shared Memory Record Backbone From First Import Slice

The first manual-source import slice will create imported Materials, Services, Providers, and Purchase Lines through a thin shared Memory Record backbone instead of separate unrelated tables. This keeps common project scoping, resolved category paths, active/archive state, and evidence links consistent from the first active Project Memory records, while leaving richer type-specific behavior to dedicated tables and later slices.
