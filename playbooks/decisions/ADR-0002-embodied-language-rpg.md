# ADR-0002: Use a finite embodied-language RPG loop

**Status:** Accepted

## Context

The current learning slice can select a target, scaffold a reply, render a reviewed prompt and wait for a
device ACK, but its Story proposal is not a real quest state machine. The product direction requires a
child's meaningful English speech to change a persistent story world and cause the next real-world quest.
The system is for children, so unconstrained generation, implicit physical-device actions and client-written
world state are unacceptable.

## Decision

Implement the first product loop as a server-authoritative finite state machine:

```text
Object → Role → Speech Act → Virtual Action → World State → Next Quest
```

Story seeds, nodes, roles, criteria, prompts, virtual items and transitions are reviewed versioned assets.
The Director selects one action; a deterministic resolver checks Speech Act slots; Shared State commits
evidence, world event and revision atomically; Interaction is the only child-facing voice; Device Gateway
is the only component that emits transport-level commands.

The first seed is `milk_picnic.v1` with `collect_milk`, `find_red_cup` and `picnic_ready` nodes. Story rewards
are virtual and never imply that the system opened an appliance or moved a real object.

## Alternatives

- **Object-triggered conversation:** rejected because speech does not have an observable consequence or
  generate a next quest.
- **LLM-generated open world:** rejected for the MVP because node reachability, safety, replay, review and
  deterministic evaluation would not be enforceable.
- **Client-owned quest state:** rejected because clients must not write learning or world truth and retries
  could duplicate rewards.
- **Treat target-expression similarity as quest success:** rejected because it confuses semantic slots with
  surface overlap and already produces false positives/negatives.
- **One visible personality per object:** rejected because the child-facing identity must remain stable.

## Consequences

- Product behavior is inspectable, replayable and safe to test without hardware.
- Quest completion and mastery evidence remain separate concepts.
- New story content requires asset validation and review before runtime use.
- The MVP is deliberately narrow; expressive open-world generation is deferred until finite-loop evidence
  shows where generation is valuable.
- Shared contracts and persistence must carry revisioned RPG decisions before clients can consume them.

## Verification

Conformance is demonstrated by contract fixtures, seed graph validation, Director and Interaction unit tests,
Shared State transaction/replay tests, and a synthetic device smoke that completes the two-node quest while
also testing wrong slots, low-confidence input and duplicate execution.
