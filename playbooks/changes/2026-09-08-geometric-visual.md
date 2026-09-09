# Change: Handcrafted geometric parent/child visuals

**Commit binding:** Same commit as this record.

## Summary

Apply the user's Neo-Childish Geometric brief: washed cyan paper (15% #7FD4E8),
mint/sunflower/violet cards, dark outlines, 3–5px hard shadows and 3% card grain.
Replace the glossy CSS orb with an original inline SVG scene: large sunflower and
small geometric figures at approximately 4:1 scale. Keep body text dark violet,
labels upright, controls large and decorative wobble limited to non-text elements.

## Layer

Web. No device capture or teaching decisions in the illustration.

## Contract impact

None.

## Files

`clients/web/src/components/PetOrb.tsx`, `clients/web/src/design/theme.css`,
`clients/web/src/features/RootApp.tsx`.

## Verification

Web tests and TypeScript checks pass. Final production build/container smoke recorded
below. Browser visual inspection was blocked by automatic approval review due to an
account usage limit; final visual acceptance is not claimed.

Final verification: all 18 repository checks pass; production Web/Gateway containers
are healthy on port 8081. Deployment smoke passes HTML, JavaScript, health,
dashboard and weekly report endpoints.

## Rollback

Revert the visual commit and rebuild Web. No state migration.

## Reusable knowledge

Use code-native SVG for geometric illustrations so text and layout remain accessible.
Do not copy normalized 0–1 channel values into numeric CSS rgb() channels.
