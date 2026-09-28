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
- Do not maintain a closed list of supported effects; S2 accepts open-domain natural-language inline instructions.
- Avoid converting empty, numeric-only, multiline, or unbalanced parentheses.
- Keep global emotion preset behavior compatible.
- Update owner-facing Telegram help and project documentation.
- Add focused tests for Arabic directions, multiple directions, manual tags, numeric parentheses, and malformed input.

## Implementation

1. Add a small stage-direction normalizer in `tts_settings.py`.
2. Run the normalizer before the existing global emotion preset is prepended.
3. Update the generation prompt to teach the parentheses syntax with one concise example.
4. Add regression tests.
5. Update README, architecture, memory, decisions, status, and progress.
6. Verify CI on the branch; do not merge until reviewed/accepted.

## Acceptance

- `(تتنهد بهدوء) مرحبًا` becomes `[تتنهد بهدوء] مرحبًا`.
- Multiple parenthesized directions convert independently.
- Existing `[laughing]` text is untouched.
- `(2026)`, empty parentheses, unbalanced parentheses, and multiline parenthetical text remain literal.
- Selecting a global preset still prepends its Fish tag after stage-direction normalization.

## Validation result

GitHub Actions run `36478339131` passed on branch HEAD `1bd0ca5`: bootstrap shell syntax, Python compileall, and the full pytest suite all succeeded. Final documentation synchronization is committed afterward and requires its own matching CI before merge.
