"""Multi-core keyword brute force for the full Quagmire III model.

For each 13-letter keyword it fixes the keyword as the column shifts and searches
the two scrambled alphabets (input B and output A_inv) by simulated annealing,
scoring the decrypted text with English quadgrams. It runs every CPU core and
tries the wordlists in order: strahd_combos.txt first, then english_13.txt.

WARNING: the full model has two free alphabets, so it can bend almost any keyword
toward English-looking output. Scores alone are weak here, with many false
positives, so the ranked summary keeps the decrypted text for each top candidate
to read by eye. A truly correct keyword should read as real sentences.

Live scores go to quagmire_brute_results.txt; the ranked summary with decrypted
text goes to quagmire_brute_ranked.txt. Needs cipher_oneline.txt and
english_quadgrams.txt in this folder. Run: python3 quagmire_bruteforce.py
"""

import math
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from quagmire3 import decrypt, index_of_coincidence, load_quadgrams, quadgram_score

HERE = Path(__file__).resolve().parent
CIPHER_FILE = HERE / "cipher_oneline.txt"
QUADGRAM_FILE = HERE / "english_quadgrams.txt"
WORDLISTS = [HERE / "strahd_combos.txt", HERE / "english_13.txt"]
LIVE_LOG = HERE / "quagmire_brute_results.txt"
RANKED_FILE = HERE / "quagmire_brute_ranked.txt"

KEY_LENGTH = 13
QUICK_RESTARTS = 3
QUICK_ITERATIONS = 12000
REFINE_RESTARTS = 10
REFINE_ITERATIONS = 30000
START_TEMP = 10.0
COOLING = 0.9996
TOP_TO_REFINE = 50

WORKER_QUAD = None
WORKER_FLOOR = None
WORKER_LABELS = None

COMMON_WORDS = (
    "THE AND THAT HAVE FOR NOT WITH YOU THIS BUT HIS FROM THEY SAY HER SHE WILL "
    "ONE ALL WOULD THERE THEIR WHAT OUT ABOUT WHO GET WHICH WHEN MAKE CAN LIKE "
    "TIME JUST HIM KNOW TAKE PEOPLE INTO YEAR YOUR GOOD SOME COULD THEM SEE OTHER "
    "THAN THEN NOW LOOK ONLY COME ITS OVER THINK ALSO BACK AFTER USE TWO HOW OUR "
    "WORK FIRST WELL WAY EVEN NEW WANT BECAUSE ANY THESE GIVE DAY MOST ARE WAS HAD "
    "HAS WERE BEEN MORE VERY WHERE MUCH MANY SUCH HERE THROUGH WORLD LIFE STILL "
    "SHOULD BEFORE BETWEEN NEVER BEING UNDER MIGHT WHILE HOUSE EVERY GREAT MUST "
    "AGAIN FOUND PART PLACE WORD NIGHT DARK BLOOD DEATH LORD KING LAND HEART EYES "
    "HAND HEAD DOOR ROOM WATER FIRE LIGHT SHALL UPON THEE THOU HATH NAME LONG SAID "
    "EACH TELL DOES SET THREE WANT AIR WELL PLAY END HOME READ HAND PORT LARGE "
    "SPELL ADD EVEN LAND HERE MUST BIG HIGH SUCH FOLLOW ACT WHY ASK MEN CHANGE "
    "WENT LIGHT KIND OFF NEED HOUSE PICTURE TRY US AGAIN ANIMAL POINT MOTHER "
    "WORLD NEAR BUILD SELF EARTH FATHER HEAD STAND OWN PAGE SHOULD COUNTRY FOUND "
    "ANSWER SCHOOL GROW STUDY STILL LEARN PLANT COVER FOOD SUN FOUR THOUGHT LET "
    "KEEP EYE NEVER LAST DOOR BETWEEN CITY TREE CROSS SINCE HARD START MIGHT STORY"
).split()


def word_hits(text):
    """Counts how many common English words appear as substrings in the text."""
    return sum(text.count(word) for word in COMMON_WORDS)


def anneal_alphabets(labels, shifts, log_probs, floor, rng, iterations):
    """One annealing run over B and A_inv with the keyword shifts held fixed."""
    b_perm = list(range(26))
    rng.shuffle(b_perm)
    a_inv = list(range(26))
    rng.shuffle(a_inv)
    current = quadgram_score(decrypt(labels, b_perm, a_inv, shifts), log_probs, floor)
    best = (current, b_perm[:], a_inv[:])
    temperature = START_TEMP
    for _ in range(iterations):
        temperature *= COOLING
        target = b_perm if rng.random() < 0.5 else a_inv
        x, y = rng.randrange(26), rng.randrange(26)
        target[x], target[y] = target[y], target[x]
        score = quadgram_score(decrypt(labels, b_perm, a_inv, shifts), log_probs, floor)
        delta = score - current
        if delta > 0 or rng.random() < math.exp(delta / max(temperature, 1e-6)):
            current = score
            if score > best[0]:
                best = (score, b_perm[:], a_inv[:])
        else:
            target[x], target[y] = target[y], target[x]
    return best


def best_for_keyword(labels, keyword, log_probs, floor, restarts, iterations):
    """Returns (score, plaintext) for a keyword over several annealing restarts."""
    shifts = [ord(c) - 65 for c in keyword]
    best = None
    for seed in range(restarts):
        result = anneal_alphabets(labels, shifts, log_probs, floor,
                                  random.Random(seed), iterations)
        if best is None or result[0] > best[0]:
            best = result
    return best[0], decrypt(labels, best[1], best[2], shifts)


def load_words():
    """Loads all 13-letter keys from the wordlists, in order, without duplicates."""
    seen, words = set(), []
    for path in WORDLISTS:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            word = line.strip().upper()
            if len(word) == KEY_LENGTH and word.isalpha() and word not in seen:
                seen.add(word)
                words.append(word)
    return words


def init_worker():
    """Loads the quadgram model and cipher once per worker process."""
    global WORKER_QUAD, WORKER_FLOOR, WORKER_LABELS
    WORKER_QUAD, WORKER_FLOOR = load_quadgrams(QUADGRAM_FILE)
    WORKER_LABELS = [ord(c) - 65 for c in CIPHER_FILE.read_text(encoding="utf-8").strip()]


def quick_keyword(keyword):
    """Worker task: rough score for one keyword via a short two-alphabet search."""
    score, _ = best_for_keyword(WORKER_LABELS, keyword, WORKER_QUAD, WORKER_FLOOR,
                                QUICK_RESTARTS, QUICK_ITERATIONS)
    return score, keyword


def main():
    """Runs the parallel brute force, logs live, refines and ranks the top keys."""
    sys.stdout.reconfigure(line_buffering=True)
    log_probs, floor = load_quadgrams(QUADGRAM_FILE)
    labels = [ord(c) - 65 for c in CIPHER_FILE.read_text(encoding="utf-8").strip()]
    words = load_words()
    cores = os.cpu_count() or 4
    print(f"Brute-forcing {len(words)} keys on {cores} cores (Strahd first). "
          f"Full model overfits - read the text, not just the score.")

    start = time.time()
    scored = []
    with LIVE_LOG.open("w", encoding="utf-8") as log, \
            ProcessPoolExecutor(max_workers=cores, initializer=init_worker) as pool:
        log.write("score\tkey\n")
        for index, result in enumerate(pool.map(quick_keyword, words, chunksize=8), 1):
            scored.append(result)
            log.write(f"{result[0]:.1f}\t{result[1]}\n")
            log.flush()
            if index % 200 == 0:
                rate = index / (time.time() - start)
                eta = (len(words) - index) / rate
                print(f"  {index}/{len(words)} tried  best {max(scored)[1]} "
                      f"({max(scored)[0]:.0f})  [{rate:.1f}/s, ~{eta / 60:.0f} min left]")

    scored.sort(reverse=True)
    print(f"\nQuick pass {time.time() - start:.0f}s. Refining top {TOP_TO_REFINE} "
          "and ranking by real-word count...")
    results = []
    for _, keyword in scored[:TOP_TO_REFINE]:
        score, plaintext = best_for_keyword(labels, keyword, log_probs, floor,
                                            REFINE_RESTARTS, REFINE_ITERATIONS)
        results.append((word_hits(plaintext), score, keyword, plaintext))
    results.sort(reverse=True)

    lines = ["Quagmire III brute force, ranked by real English words found.",
             "Real plaintext has many word hits; quadgram-fluent gibberish has few.",
             ""]
    for hits, score, keyword, plaintext in results:
        lines.append(f"{keyword}  words={hits}  score={score:.1f}  "
                     f"IoC={index_of_coincidence(plaintext):.4f}")
        lines.append(f"   {plaintext}")
        lines.append("")
    RANKED_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    best = results[0]
    print(f"\nTop key by word count: {best[2]}  words={best[0]}  score={best[1]:.0f}")
    print(best[3])
    if best[0] >= 25:
        print("\n>>> Many real words - likely English, read it!")
    else:
        print("\n>>> Few real words everywhere - probably not cracked.")
    print(f"(ranked summary -> {RANKED_FILE.name})")


if __name__ == "__main__":
    main()
