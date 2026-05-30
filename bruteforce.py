"""Brute-forces the cipher key by trying wordlists in order, saving results live.

Reads the cipher and the English quadgram model from this repo, then tries every
key from the wordlists in order: first strahd_combos.txt (themed combinations),
then english_13.txt (all 13-letter English words). For each key it fixes the key
and hill-climbs the scrambled alphabet to best fit English (quadgram score).

Scores are appended to bruteforce_results.txt as it goes, so progress is never
lost if you stop it. Promising keys are flagged immediately, and a ranked
summary with decrypted text is written to bruteforce_ranked.txt at the end.

A correct key scores around -2800 (IoC ~0.066) and yields readable English;
wrong keys sit near -4800. Just run it (e.g. in an IDE): python3 bruteforce.py
"""

import math
import random
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CIPHER_FILE = HERE / "cipher_oneline.txt"
QUADGRAM_FILE = HERE / "english_quadgrams.txt"
WORDLISTS = [HERE / "strahd_combos.txt", HERE / "english_13.txt"]
LIVE_LOG = HERE / "bruteforce_results.txt"
RANKED_FILE = HERE / "bruteforce_ranked.txt"

KEY_LENGTH = 13
QUICK_SWAPS = 700
PROMISING = -3500
REFINE_RESTARTS = 15
TOP_TO_REFINE = 40


def load_quadgrams(path):
    """Loads quadgram log10 probabilities and a floor for unseen quadgrams."""
    counts, total = {}, 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        quad, count = line.split()
        counts[quad] = int(count)
        total += int(count)
    log_probs = {q: math.log10(c / total) for q, c in counts.items()}
    return log_probs, math.log10(0.01 / total)


def quadgram_score(text, log_probs, floor):
    """Returns the English quadgram log-probability of the text."""
    return sum(log_probs.get(text[i:i + 4], floor) for i in range(len(text) - 3))


def decrypt(labels, perm, key):
    """Decrypts: plaintext = perm[label] - key (mod 26), key repeating."""
    klen = len(key)
    return "".join(chr((perm[labels[i]] - key[i % klen]) % 26 + 65)
                   for i in range(len(labels)))


def index_of_coincidence(text):
    """Returns the index of coincidence (a readability sanity check)."""
    total = len(text)
    if total < 2:
        return 0.0
    counts = Counter(text)
    return sum(n * (n - 1) for n in counts.values()) / (total * (total - 1))


def capped_climb(labels, key, log_probs, floor, rng):
    """Fast rough alphabet hill-climb with a fixed swap budget."""
    perm = list(range(26))
    rng.shuffle(perm)
    current = quadgram_score(decrypt(labels, perm, key), log_probs, floor)
    for _ in range(QUICK_SWAPS):
        a, b = rng.randrange(26), rng.randrange(26)
        perm[a], perm[b] = perm[b], perm[a]
        score = quadgram_score(decrypt(labels, perm, key), log_probs, floor)
        if score > current:
            current = score
        else:
            perm[a], perm[b] = perm[b], perm[a]
    return current


def full_climb(labels, key, log_probs, floor, rng):
    """Accurate steepest-ascent alphabet hill-climb to convergence."""
    perm = list(range(26))
    rng.shuffle(perm)
    current = quadgram_score(decrypt(labels, perm, key), log_probs, floor)
    improved = True
    while improved:
        improved = False
        for a in range(25):
            for b in range(a + 1, 26):
                perm[a], perm[b] = perm[b], perm[a]
                score = quadgram_score(decrypt(labels, perm, key), log_probs, floor)
                if score > current:
                    current = score
                    improved = True
                else:
                    perm[a], perm[b] = perm[b], perm[a]
    return current, perm


def best_for_key(labels, keyword, log_probs, floor, restarts):
    """Accurate score and plaintext for one keyword via several full climbs."""
    key = [ord(c) - 65 for c in keyword]
    best = None
    for seed in range(restarts):
        score, perm = full_climb(labels, key, log_probs, floor, random.Random(seed))
        if best is None or score > best[0]:
            best = (score, decrypt(labels, perm, key))
    return best


def load_words():
    """Loads all 13-letter keys from the wordlists, in order, without duplicates."""
    seen, words = set(), []
    for path in WORDLISTS:
        if not path.exists():
            print(f"(skipping missing {path.name})")
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            word = line.strip().upper()
            if len(word) == KEY_LENGTH and word.isalpha() and word not in seen:
                seen.add(word)
                words.append(word)
    return words


def main():
    """Runs the brute force, logging every score and flagging promising keys."""
    sys.stdout.reconfigure(line_buffering=True)
    log_probs, floor = load_quadgrams(QUADGRAM_FILE)
    labels = [ord(c) - 65 for c in CIPHER_FILE.read_text(encoding="utf-8").strip()]
    words = load_words()
    print(f"Brute-forcing {len(words)} keys. Correct ~ -2800; wrong ~ -4800.")
    print(f"Live scores -> {LIVE_LOG.name}; ranked summary -> {RANKED_FILE.name}\n")

    scored = []
    start = time.time()
    with LIVE_LOG.open("w", encoding="utf-8") as log:
        log.write("score\tkey\n")
        for index, keyword in enumerate(words, 1):
            score = capped_climb(labels, [ord(c) - 65 for c in keyword],
                                 log_probs, floor, random.Random(0))
            scored.append((score, keyword))
            log.write(f"{score:.1f}\t{keyword}\n")
            log.flush()
            if score > PROMISING:
                full_score, plaintext = best_for_key(labels, keyword, log_probs,
                                                     floor, REFINE_RESTARTS)
                print(f"  *** PROMISING: {keyword}  score={full_score:.0f}  "
                      f"IoC={index_of_coincidence(plaintext):.4f}")
                print(f"      {plaintext[:90]}")
            if index % 50 == 0:
                elapsed = time.time() - start
                rate = index / elapsed
                eta = (len(words) - index) / rate
                print(f"  {index}/{len(words)} tried  "
                      f"best so far {max(scored)[1]} ({max(scored)[0]:.0f})  "
                      f"[{rate:.0f} keys/s, ~{eta / 60:.0f} min left]")

    print(f"\nQuick pass done in {time.time() - start:.0f}s. Refining top "
          f"{TOP_TO_REFINE}...")
    scored.sort(reverse=True)
    results = []
    for _, keyword in scored[:TOP_TO_REFINE]:
        score, plaintext = best_for_key(labels, keyword, log_probs, floor,
                                        REFINE_RESTARTS)
        results.append((score, keyword, plaintext))
    results.sort(reverse=True)

    lines = ["Brute-force ranked results (best first; correct ~ -2800, IoC ~0.066)", ""]
    for score, keyword, plaintext in results:
        lines.append(f"{keyword}  score={score:.1f}  IoC={index_of_coincidence(plaintext):.4f}")
        lines.append(f"   {plaintext}")
        lines.append("")
    RANKED_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    best = results[0]
    print(f"\nBEST: {best[1]}  score={best[0]:.0f}  "
          f"IoC={index_of_coincidence(best[2]):.4f}")
    print(best[2])
    if best[0] > PROMISING:
        print("\n>>> Looks promising - read the text above.")
    else:
        print("\n>>> Nothing cracked (all near random); key not in these lists.")


if __name__ == "__main__":
    main()
