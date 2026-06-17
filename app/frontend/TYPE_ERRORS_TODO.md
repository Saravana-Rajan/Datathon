# TypeScript errors bypassed for hackathon deploy

These were skipped via `typescript.ignoreBuildErrors: true` in `next.config.mjs`.
Fix before any production / non-hackathon release.

## Known errors

- `src/components/HeatmapLayer.tsx:65` — `new viz.HeatmapLayer({...})` flagged
  as "Expected 0 arguments, but got 1." The Google Maps visualization library
  types in `@types/google.maps` may need updating, or the constructor needs
  to be called via a cast: `new (viz.HeatmapLayer as any)({...})`.

## How to re-enable strict typing

1. Remove `typescript.ignoreBuildErrors` and `eslint.ignoreDuringBuilds`
   blocks from `next.config.mjs`.
2. Run `npm run build` and fix each error.
3. Consider running `npx tsc --noEmit` in CI to keep types honest.
