# Parent and child usability review

Scope: all four parent web pages, shared navigation, task preview, feedback states,
forms, privacy presentation, responsive layout, keyboard and screen-reader access.
Layer: Web; one backward-compatible Gateway read route using the existing v1 schema.

| Part | Problem found | Change |
| --- | --- | --- |
| Colors | Swift 0–1 color values were interpreted as CSS 0–255, nearly black | Explicit CSS colors; final user-directed geometric candy palette on washed cyan |
| Layout | Phone-width column wasted desktop space | Responsive home/report grids and compact mobile cards |
| Navigation | Tiny labels and incomplete tab semantics | Named navigation buttons, active-page indication, mobile bottom navigation |
| Keyboard | Weak focus visibility; no skip link or focus movement | Focus rings, skip link, focused main content after navigation |
| Touch | Switch hit area only 32px tall | 48px controls and larger mobile navigation targets |
| Home | Main action had no handler | Working parent-and-child task preview and return control |
| Child presentation | No separation from metrics/settings | Focused preview without parent navigation, scores, recording or device commands |
| Task progress | Unexplained 64% appeared like an assessment | Show task context rather than an unexplained progress score |
| Metrics | Technical labels and unclear counts | Plain-language labels, units, record date and overlapping-count explanation |
| Reports | L3/L2 surfaced as unexplained progress; judgmental language | Explain help levels in disclosure, neutral evidence wording, four evidence-kind labels |
| Empty/error states | No-data and load-failure could look alike | Shared loading/offline state with retry, no false data-retention promise |
| Refresh | Stale notice only on home | Shared last-read-content notice and retry across parent pages |
| Device offline | Implied the user must fix unavailable hardware | Explicit demo/no-hardware explanation; actionable device link |
| Device controls | No pending/success feedback; overlapping edits possible | Disable controls during save, announce save result and rollback errors |
| Device detail | Firmware jargon given equal prominence | Move technical details into disclosure |
| Family defaults | Hard-coded values on every visit | Read existing plan through GET /v1/parent-constraints |
| Family interests | Save silently replaced topics and cleared exclusions | Editable interest/exclusion fields; preserve loaded values |
| Family editing | Draft lost when moving between parent tabs | Keep family form mounted between tabs; retain draft after save failure |
| Family validation | No field guidance or visible limits | Optional labels, context limit, topic validation, no private-data prompt |
| Demo disclosure | Buried mixed-language footer | Prominent plain-language demo banner and restart limitation |
| Privacy actions | Buttons implied actual export/erase | Explicit demo-only labels in a disclosure; existing confirmation/API unchanged |
| Motion | Animation without a clear opt-out would distract | Retain reduced-motion behavior |

## Validation

Regression tests were observed failing for the absent home action, lost plan values,
and missing GET endpoint (404). After implementation, web tests, typecheck and build
pass. Gateway regression tests pass. Browser/container results are recorded in the
associated change record after visual QA.

## Boundaries still in place

This improves the deployed demo; it is not a full child learning terminal. The child
screen is a parent-supervised task preview, not a live lesson or parental lock.
No new Agent dialogue, assessment, microphone/camera access, mastery writes or privacy
implementation is introduced. Real authentication, persistent storage and lesson
integration remain separate product work. Physical RDK X5 is excluded.

Final visual direction supersedes the initial warm-card iteration: handcrafted vector
scene, mint/sunflower/violet palette, 3% grain, dark outlines and hard paper shadows.
Browser verification of this final revision is blocked by usage-limit auto-review;
no final visual acceptance is claimed.
