# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

This repo holds a cipher and tooling to normalize it. The original cipher is
written out with spaces and tabs between every letter; the tooling collapses it
into forms that are easier to analyze.

## Files

- `cipher_raw.txt` — the source cipher, letters separated by spaces and tabs.
- `cipher_nospaces.txt` — generated: each line with all whitespace removed, line
  structure preserved.
- `cipher_oneline.txt` — generated: every non-empty line joined into one line.
- `statistic.txt` — generated: letter frequency table and basic cipher stats.
- `normalize_cipher.py` — reads `cipher_raw.txt`, writes the nospaces and oneline variants.
- `statistic.py` — reads `cipher_oneline.txt`, writes `statistic.txt`.

`cipher_raw.txt` is the single source of truth. The two `.txt` outputs are
always regenerated from it and should not be edited by hand.

## Usage

```
python3 normalize_cipher.py
python3 statistic.py
```

Run `normalize_cipher.py` first; `statistic.py` reads its `cipher_oneline.txt` output.

## Code conventions

- Write everything in English.
- Do not use `#` comments in code.
- Each function starts with a short, to-the-point docstring.
- Each module starts with a docstring describing what the module does.
- Keep code readable and clear.
