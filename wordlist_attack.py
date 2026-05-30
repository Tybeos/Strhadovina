"""Dictionary attack on the 13-letter Vigenere key.

For every 13-letter word in the system dictionary (plus a few themed terms), it
fixes that word as the key, hill-climbs the scrambled alphabet once, and scores
the result with English quadgrams. A correct key scores far above the rest
(around -2800, IoC ~0.066) while wrong keys sit near -4800. Prints the running
best and writes the ranked top results to wordlist_results.txt.
"""

import random
import sys
import time
from pathlib import Path

from anneal import (
    QUADGRAMS,
    climb_with_key,
    evaluate_with_key,
    load_quadgrams,
)
from statistic import index_of_coincidence

HERE = Path(__file__).resolve().parent
ONELINE = HERE / "cipher_oneline.txt"
DICTIONARY = Path("/usr/share/dict/words")
RESULTS = HERE / "wordlist_results.txt"
KEY_LENGTH = 13

THEMED = [
    "CURSEOFSTRAHD", "STRAHDVONZARO", "BAROVIANMISTS", "LANDOFBAROVIA",
    "RAVENLOFTLAND", "CASTLERAVENLO", "THEDARKPOWERS", "MISTSOFBAROVI",
]

def load_keywords():
    """Returns the 13-letter candidate keys: dictionary words plus themed terms."""
    words = set(THEMED)
    if DICTIONARY.exists():
        for line in DICTIONARY.read_text(encoding="utf-8", errors="ignore").splitlines():
            word = line.strip().upper()
            if len(word) == KEY_LENGTH and word.isalpha() and word.isascii():
                words.add(word)
    return sorted(words)


SWAPS = 1000


def capped_climb(labels, key, log_probs, floor, rng):
    """Hill-climbs the alphabet with a fixed swap budget (a fast rough pass)."""
    perm = list(range(26))
    rng.shuffle(perm)
    current = evaluate_with_key(labels, perm, key, log_probs, floor)[0]
    for _ in range(SWAPS):
        a, b = rng.randrange(26), rng.randrange(26)
        perm[a], perm[b] = perm[b], perm[a]
        score = evaluate_with_key(labels, perm, key, log_probs, floor)[0]
        if score > current:
            current = score
        else:
            perm[a], perm[b] = perm[b], perm[a]
    return current


def quick_score(labels, keyword, log_probs, floor):
    """Rough score for a keyword via one capped alphabet climb."""
    key = [ord(character) - ord("A") for character in keyword]
    return capped_climb(labels, key, log_probs, floor, random.Random(0))


def refine(labels, keyword, log_probs, floor, restarts=10):
    """Accurate score for a keyword via several full alphabet hill-climbs."""
    key = [ord(character) - ord("A") for character in keyword]
    best = None
    for seed in range(restarts):
        _, perm = climb_with_key(labels, key, log_probs, floor, random.Random(seed))
        result = evaluate_with_key(labels, perm, key, log_probs, floor)
        if best is None or result[0] > best[0]:
            best = result
    return best


def main():
    """Runs the dictionary attack and reports the best-scoring keys."""
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    log_probs, floor = load_quadgrams(QUADGRAMS)
    text = ONELINE.read_text(encoding="utf-8").strip()
    labels = [ord(character) - ord("A") for character in text]

    keywords = load_keywords()
    if limit:
        keywords = keywords[:limit]
    print(f"Testing {len(keywords)} keys of length {KEY_LENGTH} "
          f"(correct key scores ~ -2800)")

    scored = []
    start = time.time()
    for index, keyword in enumerate(keywords, 1):
        scored.append((quick_score(labels, keyword, log_probs, floor), keyword))
        if index % 1000 == 0:
            best = max(scored)
            rate = index / (time.time() - start)
            print(f"  {index}/{len(keywords)}  best so far: {best[1]} "
                  f"({best[0]:.0f})  [{rate:.0f} keys/s]")

    scored.sort(reverse=True)
    print(f"\nRefining the top candidates with full hill-climbs...")
    results = []
    for _, keyword in scored[:30]:
        score, plaintext = refine(labels, keyword, log_probs, floor)
        results.append((score, keyword, plaintext))
    results.sort(reverse=True)

    lines = ["Dictionary attack results (best first; correct key ~ -2800, IoC ~0.066)", ""]
    for score, keyword, plaintext in results:
        lines.append(f"{keyword}  score={score:.1f}  IoC={index_of_coincidence(plaintext):.4f}")
        lines.append(f"   {plaintext[:90]}")
    RESULTS.write_text("\n".join(lines) + "\n", encoding="utf-8")

    best = results[0]
    print(f"\nBest key: {best[1]}  score={best[0]:.1f}  "
          f"IoC={index_of_coincidence(best[2]):.4f}")
    print(f"  {best[2][:90]}")
    print(f"(full ranking written to {RESULTS.name})")


if __name__ == "__main__":
    main()
