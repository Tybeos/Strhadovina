"""Solves the substitution for EVERY keyword on the first half of the cipher.

Uses the first half of cipher_oneline.txt. For every 13-letter keyword
(strahd_combos.txt then english_13.txt) it subtracts the key to get mid, then
solves the substitution alphabet with English quadgrams (no shortcut filter, so
nothing is skipped).

The substitution is solved smartly: a frequency seed places E on the most common
mid symbol, T on the next, and so on (ENGLISH_ORDER), and a steepest-ascent
hill-climb then runs to convergence from several diversified restarts.

Candidates are judged by statistical analysis against English, not by hunting
for English words (which a hill-climb can fake on nonsense). Two measures are
reported per key:
  - IoC of mid: a substitution only relabels letters, so IoC is invariant under
    it. A wrong key (mid scrambled, IoC ~0.038) therefore cannot be dressed up to
    look English, while the right key makes mid a substituted English text (IoC
    ~0.066). This is the honest signal and the primary ranking key.
  - chi-squared of the decoded text's letter frequencies versus English
    (statistic.ENGLISH_FREQUENCIES): low means the distribution matches English.
Results are ranked by IoC first, then by lowest chi-squared, so the key whose
statistics most match English floats to the top. Runs on all CPU cores.

Needs cipher_oneline.txt, english_quadgrams.txt, strahd_combos.txt and
english_13.txt in the same folder. Run: python3 solve_half.py
Live output -> solve_half_results.txt; ranked summary -> solve_half_ranked.txt.
"""

import math
import os
import random
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from statistic import ENGLISH_FREQUENCIES

HERE = Path(__file__).resolve().parent
CIPHER = HERE / "cipher_oneline.txt"
QUADS = HERE / "english_quadgrams.txt"
WORDLISTS = [HERE / "strahd_combos.txt", HERE / "english_13.txt"]
LIVE_LOG = HERE / "solve_half_results.txt"
RANKED = HERE / "solve_half_ranked.txt"

KEY_LENGTH = 13
SUB_RESTARTS = 5
ENGLISH_ORDER = "ETAOINSHRDLCUMWFGYPBVKJXQZ"
PROMISING_IOC = 0.058

DISPLAY_WORDS = (
    "THE AND THAT HAVE FOR NOT WITH YOU THIS BUT HIS FROM THEY SAY HER SHE WILL "
    "ONE ALL WOULD THERE THEIR WHAT OUT ABOUT WHO GET WHICH WHEN MAKE CAN LIKE "
    "TIME JUST HIM KNOW TAKE INTO YEAR YOUR GOOD SOME COULD THEM SEE OTHER THAN "
    "THEN NOW LOOK ONLY COME ITS OVER ALSO BACK AFTER USE TWO HOW OUR WORK WELL "
    "WAY EVEN NEW WANT ANY THESE GIVE DAY MOST ARE WAS HAD HAS WERE BEEN MORE "
    "VERY WHERE MUCH MANY SUCH HERE WORLD LIFE STILL SHOULD BEFORE NEVER BEING "
    "UNDER WHILE EVERY GREAT MUST FOUND PART NIGHT DARK BLOOD DEATH LORD KING "
    "LAND HEART HAND HEAD DOOR ROOM FIRE LIGHT SHALL UPON NAME LONG SAID MAN "
    "MEN ONE ARE WHO HIM HIS DAY OLD WAR END GOD EYE WAY OWN SUN SON"
).split()

WORKER_LP = None
WORKER_FL = None
WORKER_MID_BASE = None


def load_quadgrams():
    counts, total = {}, 0
    for line in QUADS.read_text(encoding="utf-8").splitlines():
        q, c = line.split()
        counts[q] = int(c)
        total += int(c)
    return {q: math.log10(c / total) for q, c in counts.items()}, math.log10(0.01 / total)


def quad(text, lp, fl):
    return sum(lp.get(text[i:i + 4], fl) for i in range(len(text) - 3))


def english_chi_squared(text):
    """Chi-squared of the text's letter frequencies versus English; low is best."""
    total = len(text)
    if total == 0:
        return float("inf")
    counts = Counter(text)
    score = 0.0
    for letter, percent in ENGLISH_FREQUENCIES.items():
        expected = percent / 100 * total
        observed = counts.get(letter, 0)
        score += (observed - expected) ** 2 / expected
    return score


def highlight_words(text):
    """Wraps recognizable English words in red for the console (display only)."""
    spans = []
    for word in DISPLAY_WORDS:
        start = text.find(word)
        while start != -1:
            spans.append((start, start + len(word)))
            start = text.find(word, start + 1)
    if not spans:
        return text
    spans.sort()
    merged = [list(spans[0])]
    for lo, hi in spans[1:]:
        if lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    out, pos = [], 0
    for lo, hi in merged:
        out.append(text[pos:lo])
        out.append(f"\033[31m{text[lo:hi]}\033[0m")
        pos = hi
    out.append(text[pos:])
    return "".join(out)


def index_of_coincidence(values):
    """Returns the index of coincidence of a sequence of numbers."""
    total = len(values)
    if total < 2:
        return 0.0
    counts = Counter(values)
    return sum(n * (n - 1) for n in counts.values()) / (total * (total - 1))


def frequency_seed(mid):
    """Seeds the substitution by putting E on the most common mid symbol, etc."""
    order = [value for value, _ in Counter(mid).most_common()]
    order += [value for value in range(26) if value not in order]
    perm = [0] * 26
    for rank, value in enumerate(order):
        perm[value] = ord(ENGLISH_ORDER[rank]) - 65
    return perm


def decode(mid, perm):
    """Applies a substitution (mid value -> letter) to produce text."""
    return "".join(chr(perm[v] + 65) for v in mid)


def solve_substitution(mid, lp, fl):
    """Cracks the monoalphabetic substitution of mid by steepest-ascent climbing.

    Each restart starts from the frequency seed (E on the most common symbol) and
    sweeps every symbol pair, keeping a swap only if it raises the quadgram score,
    repeating until a full sweep finds no improvement. Later restarts shuffle the
    seed so the search escapes the seed's basin.
    """
    best_text, best_score = None, None
    for restart in range(SUB_RESTARTS):
        perm = frequency_seed(mid)
        if restart:
            random.Random(restart).shuffle(perm)
        score = quad(decode(mid, perm), lp, fl)
        improved = True
        while improved:
            improved = False
            for a in range(25):
                for b in range(a + 1, 26):
                    perm[a], perm[b] = perm[b], perm[a]
                    s = quad(decode(mid, perm), lp, fl)
                    if s > score:
                        score, improved = s, True
                    else:
                        perm[a], perm[b] = perm[b], perm[a]
        if best_score is None or score > best_score:
            best_score, best_text = score, decode(mid, perm)
    return best_score, best_text


def load_words():
    seen, words = set(), []
    for path in WORDLISTS:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            w = line.strip().upper()
            if len(w) == KEY_LENGTH and w.isalpha() and w not in seen:
                seen.add(w)
                words.append(w)
    return words


def init_worker():
    global WORKER_LP, WORKER_FL, WORKER_MID_BASE
    WORKER_LP, WORKER_FL = load_quadgrams()
    labels = [ord(c) - 65 for c in CIPHER.read_text(encoding="utf-8").strip()]
    WORKER_MID_BASE = labels[:len(labels) // 2]


def process_keyword(keyword):
    key = [ord(c) - 65 for c in keyword]
    mid = [(WORKER_MID_BASE[i] - key[i % KEY_LENGTH]) % 26
           for i in range(len(WORKER_MID_BASE))]
    ioc = index_of_coincidence(mid)
    score, text = solve_substitution(mid, WORKER_LP, WORKER_FL)
    return ioc, english_chi_squared(text), score, keyword, text


def main():
    sys.stdout.reconfigure(line_buffering=True)
    words = load_words()
    cores = os.cpu_count() or 4
    print(f"Substituting EVERY key ({len(words)}) on the first half, {cores} cores. "
          f"Judged by statistics: high IoC and low chi-squared mean English.")

    by_english = lambda r: (round(r[0], 4), -r[1])

    results = []
    start = time.time()
    with LIVE_LOG.open("w", encoding="utf-8") as log, \
            ProcessPoolExecutor(max_workers=cores, initializer=init_worker) as pool:
        log.write("ioc\tchi2\tscore\tkey\ttext\n")
        for i, (ioc, chi2, score, key, text) in enumerate(
                pool.map(process_keyword, words, chunksize=4), 1):
            results.append((ioc, chi2, score, key, text))
            log.write(f"{ioc:.4f}\t{chi2:.1f}\t{score:.0f}\t{key}\t{text}\n")
            log.flush()
            if ioc >= PROMISING_IOC:
                print(f"  *** {key}: IoC {ioc:.4f}, chi2 {chi2:.1f}, score {score:.0f}")
                print(f"      {highlight_words(text)}")
            if i % 200 == 0:
                rate = i / (time.time() - start)
                best = max(results, key=by_english)
                print(f"  {i}/{len(words)}  best IoC {best[0]:.4f} ({best[3]}, "
                      f"chi2 {best[1]:.1f})  [{rate:.1f}/s, "
                      f"~{(len(words) - i) / rate / 60:.0f} min left]")

    results.sort(key=by_english, reverse=True)
    lines = ["Solved every key, ranked by IoC (invariant, cannot be faked) "
             "then lowest chi-squared versus English letter frequencies", ""]
    for ioc, chi2, score, key, text in results[:50]:
        lines.append(f"{key}  IoC={ioc:.4f}  chi2={chi2:.1f}  score={score:.0f}")
        lines.append(f"   {text}")
        lines.append("")
    RANKED.write_text("\n".join(lines) + "\n", encoding="utf-8")

    best = results[0]
    print(f"\nBest by IoC: {best[3]}  IoC={best[0]:.4f}  chi2={best[1]:.1f}  "
          f"score={best[2]:.0f}")
    print(highlight_words(best[4]))
    print(">>> high IoC: statistics match English!" if best[0] >= PROMISING_IOC else
          ">>> no key reaches English IoC; key not found in these lists.")
    print(f"(ranked -> {RANKED.name})")


if __name__ == "__main__":
    main()
