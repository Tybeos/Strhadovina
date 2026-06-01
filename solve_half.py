"""Solves the substitution for EVERY keyword on the first half of the cipher.

Uses the first half of cipher_oneline.txt. For every 13-letter keyword
(strahd_combos.txt then english_13.txt) it subtracts the key, then fully solves
the substitution alphabet with English quadgrams (no shortcut filter, so nothing
is skipped). Each decrypted text is scored by how many real English words it
contains; results are written live and ranked by word count, so genuine English
floats to the top. Runs on all CPU cores.

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

HERE = Path(__file__).resolve().parent
CIPHER = HERE / "cipher_oneline.txt"
QUADS = HERE / "english_quadgrams.txt"
WORDLISTS = [HERE / "strahd_combos.txt", HERE / "english_13.txt"]
LIVE_LOG = HERE / "solve_half_results.txt"
RANKED = HERE / "solve_half_ranked.txt"

KEY_LENGTH = 13
SUB_RESTARTS = 8
SUB_ITERS = 4000
ENGLISH_ORDER = "ETAOINSHRDLCUMWFGYPBVKJXQZ"
PROMISING_WORDS = 15

COMMON_WORDS = (
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


def word_hits(text):
    return sum(text.count(w) for w in COMMON_WORDS)


def solve_substitution(mid, lp, fl):
    best_text, best_score = None, None
    for seed in range(SUB_RESTARTS):
        rng = random.Random(seed)
        perm = list(range(26))
        order = [v for v, _ in Counter(mid).most_common()]
        order += [v for v in range(26) if v not in order]
        for i, v in enumerate(order):
            perm[v] = ord(ENGLISH_ORDER[i]) - 65
        text = "".join(chr(perm[v] + 65) for v in mid)
        score = quad(text, lp, fl)
        for _ in range(SUB_ITERS):
            a, b = rng.randrange(26), rng.randrange(26)
            perm[a], perm[b] = perm[b], perm[a]
            cand = "".join(chr(perm[v] + 65) for v in mid)
            s = quad(cand, lp, fl)
            if s > score:
                score, text = s, cand
            else:
                perm[a], perm[b] = perm[b], perm[a]
        if best_score is None or score > best_score:
            best_score, best_text = score, text
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
    score, text = solve_substitution(mid, WORKER_LP, WORKER_FL)
    return word_hits(text), score, keyword, text


def main():
    sys.stdout.reconfigure(line_buffering=True)
    words = load_words()
    cores = os.cpu_count() or 4
    print(f"Substituting EVERY key ({len(words)}) on the first half, {cores} cores. "
          f"Real English has many word hits.")

    results = []
    start = time.time()
    with LIVE_LOG.open("w", encoding="utf-8") as log, \
            ProcessPoolExecutor(max_workers=cores, initializer=init_worker) as pool:
        log.write("words\tscore\tkey\ttext\n")
        for i, (hits, score, key, text) in enumerate(
                pool.map(process_keyword, words, chunksize=4), 1):
            results.append((hits, score, key, text))
            log.write(f"{hits}\t{score:.0f}\t{key}\t{text}\n")
            log.flush()
            if hits >= PROMISING_WORDS:
                print(f"  *** {key}: {hits} words, score {score:.0f}")
                print(f"      {text}")
            if i % 200 == 0:
                rate = i / (time.time() - start)
                print(f"  {i}/{len(words)}  best {max(results)[2]} "
                      f"({max(results)[0]} words)  [{rate:.1f}/s, "
                      f"~{(len(words) - i) / rate / 60:.0f} min left]")

    results.sort(reverse=True)
    lines = ["Solved every key, ranked by real English words (read the top texts)", ""]
    for hits, score, key, text in results[:50]:
        lines.append(f"{key}  words={hits}  score={score:.0f}")
        lines.append(f"   {text}")
        lines.append("")
    RANKED.write_text("\n".join(lines) + "\n", encoding="utf-8")

    best = results[0]
    print(f"\nBest by words: {best[2]}  words={best[0]}  score={best[1]:.0f}")
    print(best[3])
    print(">>> looks like English!" if best[0] >= PROMISING_WORDS else
          ">>> nothing reads as English; key not found.")
    print(f"(ranked -> {RANKED.name})")


if __name__ == "__main__":
    main()
