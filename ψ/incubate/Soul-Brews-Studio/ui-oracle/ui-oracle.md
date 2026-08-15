# ui-oracle Incubation Log

## Source
- **Origin**: ./origin/ → `~/Code/github.com/Soul-Brews-Studio/ui-oracle/`
- **GitHub**: https://github.com/Soul-Brews-Studio/ui-oracle

## Sessions

### 2026-05-05 — default mode

- **Branch**: `chore/calver-hmm-indexer` (existing — not yet at main)
- **Status**: active — set up to fix qwen3 + ADD button click bug
- **Initial state**: 1 changed file
- **Last commit**: `8aa8d56 chore: add calver HMM + bump v26.5.2-alpha.1704`

### Investigation context

The `studio.buildwithoracle.com/map` page renders 3 embedding engines (nomic, bge-m3, qwen3). Clicking "+ ADD" on qwen3 (now populated with 20,844 docs after Round 5 indexer run) **does nothing**:

- Button is visible + enabled (Playwright confirmed via `/click-test`)
- Click fires but **zero network requests** observed
- No console errors
- Same code path is presumably wired for `nomic` (which also shows + ADD) — likely same bug there too

### Suspected root cause

`apps/studio/src/pages/Map.tsx:168` — `addGlobe(key, model)`:

```ts
async function addGlobe(key: string, model: string) {
  if (globes.some(g => g.key === key) || loadingModel) return;
  setLoadingModel(key);
  try {
    const data = await getMap3d(key);
    if (data.documents.length === 0) return;
    ...
```

Hypothesis: stale `loadingModel` state from a prior failed/cancelled fetch is non-null, causing the early return at line 169. Or `globes.some(g => g.key === key)` is matching on a phantom entry.

### To investigate next

1. Add `console.log` in `addGlobe` first line to confirm function entry
2. Check current `loadingModel` state via React devtools
3. Try clicking nomic — same noop?
4. Check if there's a stale `globes[]` entry with `key === 'qwen3'` even though no globe rendered

### Key files

- `apps/studio/src/pages/Map.tsx` — the engine list + click handlers
- `apps/studio/src/api/oracle.ts:228` — `getMap3d()` fetch wrapper
- `apps/studio/src/components/planets/EngineList.tsx` — alternative engine UI (not the one rendering here)
