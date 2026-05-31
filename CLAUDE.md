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
  Shannon entropy, chi-squared per-column key recovery across the Vigenere,
  Beaufort and variant Beaufort schemes (then decrypts with the best fit), and a
  common-English-word match count. Each test is also compared against the
  `random_oneline.txt` baseline average.
- `solve.txt` — generated: key-period confirmation, entropy, recovered key, and
  the attempted decryption.
- `keylength.py` — shows the key-length evidence as one table: autocorrelation,
  column IoC, and Kasiski side by side per length, each compared to the random
  baseline (all 1000 lines), plus a harmonic check, with the verdict (period 13).
- `autocorr.py` — full autocorrelation across every shift, writes
  `autocorr_full.txt`; multiples of 13 are marked and stay elevated far across
  the text, confirming the period.
- `wordlist_attack.py` — dictionary attack on the 13-letter key: tests every
  13-letter word in `/usr/share/dict/words` (plus themed terms), fixing each as
  the key and hill-climbing the alphabet, then refines the top candidates.
  Writes `wordlist_results.txt`.
- `campaign_attack.py` — standalone, multi-core version of the dictionary attack
  for running on a more powerful machine. Self-contained (needs only itself,
  `cipher_oneline.txt`, and `english_quadgrams.txt`). Run:
  `python3 campaign_attack.py [wordlist]`. Writes `campaign_results.txt`.
- `strahd_offline.py` — one-file offline multi-core cracker with the cipher and
  ~15k 13-letter keys (Strahd terms + all dictionary words) embedded; needs only
  `english_quadgrams.txt`. Console output only. `python3 strahd_offline.py` to
  crack, or `python3 strahd_offline.py KEYWORD` to test one key.
- `bruteforce.py` — runs the key brute force from text wordlists in order
  (`strahd_combos.txt` then `english_13.txt`), logging every score live to
  `bruteforce_results.txt` and writing a ranked summary to
  `bruteforce_ranked.txt`. Made to just Run in an IDE.
- `strahd_combos.txt` / `english_13.txt` — the two wordlists it reads.
- `key_tester.py` — small tkinter window app: type a 13-letter key, press Enter,
  and it hill-climbs the alphabet and shows the score and decrypted text. For
  trying keys by hand without the command line.
- `quagmire_solver/` — self-contained folder (with its own copies of
  `cipher_oneline.txt` and `english_quadgrams.txt`) holding `quagmire3.py`, the
  full Quagmire III/IV breaker that solves TWO scrambled alphabets plus the
  shifts. `python3 quagmire3.py KEYWORD` fixes a keyword and finds the alphabets;
  no-arg runs a blind search; `--selftest` validates on known plaintext (100%).
- `hypoteze.py` — scratchpad for testing cipher-cracking ideas. Each hypothesis
  transforms the text and is scored by IoC, best-scheme chi-squared, and word
  hits. Grows over time; add a function and register it in `HYPOTHESES`.
- `anneal.py` — mixed-alphabet Vigenere (Quagmire) breaker: hill-climbs the
  26-symbol alphabet permutation, solving the period-13 key each step, scored by
  English quadgrams. Needs `english_quadgrams.txt` (downloaded, gitignored).
  Verified correct on known plaintext, but the unguided search does not converge
  from ~700 chars. With a candidate key it is reliable: `python3 anneal.py KEY1
  KEY2 ...` fixes each 13-letter keyword and hill-climbs only the permutation.
  A correct key scores ~ -2800 with IoC ~0.066; wrong keys sit near -4800.

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
