# Plan 0005 — Natural stage directions for S2

Created: 2026-09-28
Branch: `feature/natural-stage-directions`

## Goal

Let the owner write performance directions in natural Arabic or any other language using ordinary parentheses instead of remembering Fish S2 square-bracket tags.

Example owner input:

```text
(تتردد قليلًا) ما كنت أعرف ماذا أقول... (تتنهد بهدوء) اشتقت لك.
```

Controller request text:

```text
[تتردد قليلًا] ما كنت أعرف ماذا أقول... [تتنهد بهدوء] اشتقت لك.
```

Fish S2 remains responsible for interpreting the free-form instruction.

## Constraints

- No LLM, prompt enhancer, semantic scene inference, persona, or chat layer.
- Preserve existing manual `[tag]` syntax unchanged.
- Use deterministic local syntax normalization only.
- Do not make effect support depend on a closed list. Keep a small curated Arabic alias table only for common effects that map exactly to tags documented by the pinned Fish source; unknown directions remain open-domain free-form S2 instructions.
- Avoid converting empty, numeric-only, multiline, or unbalanced parentheses.
- Keep global emotion preset behavior compatible.
- Update owner-facing Telegram help and project documentation.
- Add focused tests for Arabic directions, multiple directions, manual tags, numeric parentheses, and malformed input.

## Implementation

1. Add a small stage-direction normalizer in `tts_settings.py`.
2. Canonicalize common Arabic effect phrases to documented Fish-native tags while preserving unknown descriptions as free-form instructions.
3. Add an optional consistency preset using only existing Fish request controls (`temperature`, `top_p`, `seed`), enabled by default and reversible without overwriting saved manual values.
4. Run the normalizer before the existing global emotion preset is prepended.
5. Update the generation/settings UI to explain canonical aliases and the consistency toggle.
6. Add regression tests.
7. Update README, architecture, memory, decisions, status, and progress.
8. Verify CI on the branch; do not merge until reviewed/accepted.

## Acceptance

- `(تتنهد بهدوء) مرحبًا` becomes `[sigh] مرحبًا`.
- `(تضحك بخفة)` becomes `[chuckle]`, `(تلهث)` becomes `[panting]`, and other curated exact aliases use only tags present in the pinned Fish README.
- Unknown compound directions such as `(بصوت متردد وكأنه يحاول ألا يبكي)` stay free-form inside `[ ]`.
- Stability mode sends the VoxPilot preset T=0.6, P=0.7, Seed=42 without overwriting stored normal-mode controls.
- Multiple parenthesized directions convert independently.
- Existing `[laughing]` text is untouched.
- `(2026)`, empty parentheses, unbalanced parentheses, and multiline parenthetical text remain literal.
- Selecting a global preset still prepends its Fish tag after stage-direction normalization.

## Validation result

GitHub Actions run `36478339131` passed on branch HEAD `1bd0ca5`: bootstrap shell syntax, Python compileall, and the full pytest suite all succeeded. Final documentation synchronization is committed afterward and requires its own matching CI before merge.


## 2026-09-28 reliability follow-up

Owner use showed that free-form performance instructions can vary between generations. The follow-up therefore prefers exact documented S2 tags for common Arabic effect phrases and adds a reversible consistency mode. This does not claim that S2 will obey every performance instruction deterministically; voice/reference characteristics and model generation can still affect the result. Validation of this follow-up is pending on the new branch HEAD.
