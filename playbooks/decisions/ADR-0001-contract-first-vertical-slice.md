# ADR-0001: build the first cross-platform slice contract-first

**Status:** Accepted

## Context

The repository contains working initial backend, memory, knowledge, pointing, and intelligence components but no iOS parent app, device gateway, or RDK X5 runtime. Moving all existing components before integration would create broad path churn. Building isolated prototypes would create incompatible event models.

## Decision

Keep existing components in place. Add versioned JSON Schema contracts first, then implement Gateway, RDK runtime/simulator, and iOS consumers against the same fixtures.

## Alternatives

- Reorganize the full repository first: rejected because it couples the slice to unrelated path changes.
- Build iOS and RDK prototypes independently: rejected because contract drift would be immediate.

## Consequences

The repository remains temporarily mixed in layout, while new cross-platform code has stable boundaries. Any shared-field change must follow the contract-change workflow.

## Verification

Contract fixtures must pass in Python, Gateway, and Swift tests. The simulator-to-Gateway smoke test must complete the ordered device lifecycle.
