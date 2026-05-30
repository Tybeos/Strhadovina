# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

This repo holds a cipher and tooling to normalize it. The original cipher is
written out with spaces and tabs between every letter; the tooling collapses it
into forms that are easier to analyze.

The cipher is English only. There is never any Czech anywhere in it, in any
form or place. All analysis assumes an English plaintext.

## Files

- `cipher_raw.txt` — the source cipher, letters separated by spaces and tabs.
- `cipher_nospaces.txt` — generated: each line with all whitespace removed, line
  structure preserved.
- `cipher_oneline.txt` — generated: every non-empty line joined into one line.
- `random_oneline.txt` — generated: 1000 random baseline lines, each the same
  length as oneline, drawn from the cipher's alphabet. Regenerated each run.
- `statistic.txt` — generated: frequencies, English comparison, n-grams, and
  key-length estimation.
- `normalize_cipher.py` — reads `cipher_raw.txt`, writes the nospaces and oneline variants.
- `statistic.py` — reads `cipher_oneline.txt`, writes `statistic.txt`. Its
  analysis functions are importable and reusable by other modules.
- `compare.py` — imports `statistic.py`, computes the same metrics for every
  line in `random_oneline.txt`, averages them, and writes `compare.txt` with
  the cipher's percentage difference from the random baseline.
- `compare.txt` — generated: cipher metrics versus the random baseline average.
- `solve.py` — imports `statistic.py`, runs the autocorrelation (kappa) test,
  Shannon entropy, and chi-squared per-column key recovery, then decrypts. Each
  test is also compared against the `random_oneline.txt` baseline average.
- `solve.txt` — generated: key-period confirmation, entropy, recovered key, and
  the attempted decryption.

`cipher_raw.txt` is the single source of truth. The two `.txt` outputs are
always regenerated from it and should not be edited by hand.

## Usage

```
python3 normalize_cipher.py
python3 statistic.py
python3 compare.py
python3 solve.py
```

Run `normalize_cipher.py` first; `statistic.py`, `compare.py` and `solve.py`
read its `cipher_oneline.txt` and `random_oneline.txt` outputs. Every generated
report labels each section with what the test is and what it tracks.

## Code conventions

- Write everything in English.
- Do not use `#` comments in code.
- Each function starts with a short, to-the-point docstring.
- Each module starts with a docstring describing what the module does.
- Keep code readable and clear.
