"""Standalone dictionary attack on the cipher's 13-letter key.

The cipher is a Quagmire: a Vigenere of period 13 over a scrambled 26-symbol
alphabet (the symbols were transcribed to A-Z in order of appearance, so the
alphabet is an unknown permutation). For every 13-letter word in a wordlist this
fixes the word as the key, hill-climbs the alphabet to best fit English (scored
by quadgrams), and ranks the words. The correct key scores far above the rest.

Self-contained: needs only this file plus two data files in the same folder:
  - cipher_oneline.txt      the cipher as one line of A-Z
  - english_quadgrams.txt   English quadgram counts, "QUAD COUNT" per line
        download: https://raw.githubusercontent.com/jameslyons/python_cryptanalysis/master/quadgrams.txt

Uses every CPU core, so it scales with a more powerful machine.

Run:   python3 campaign_attack.py [wordlist_path] [--top N]
       wordlist defaults to /usr/share/dict/words.
A correct key scores around -2800 (IoC ~0.066); wrong keys sit near -4800.
"""

import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CIPHER_FILE = HERE / "cipher_oneline.txt"
QUADGRAM_FILE = HERE / "english_quadgrams.txt"
RESULTS_FILE = HERE / "campaign_results.txt"

KEY_LENGTH = 13
QUICK_SWAPS = 1000
REFINE_RESTARTS = 20
TOP_TO_REFINE = 40

WORKER_QUAD = None
WORKER_FLOOR = None
WORKER_LABELS = None


def load_quadgrams(path):
    """Loads quadgram log10 probabilities and a floor for unseen quadgrams."""
    counts = {}
    total = 0
    import math
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        quad, count = line.split()
        counts[quad] = int(count)
        total += int(count)
    log_probs = {quad: math.log10(count / total) for quad, count in counts.items()}
    return log_probs, math.log10(0.01 / total)


def quadgram_score(text, log_probs, floor):
    """Returns the English quadgram log-probability of the text."""
    return sum(log_probs.get(text[i:i + 4], floor) for i in range(len(text) - 3))


def decrypt(labels, perm, key):
    """Decrypts: plaintext = perm[label] - key (mod 26), key repeating."""
    klen = len(key)
    return "".join(chr((perm[labels[i]] - key[i % klen]) % 26 + 65)
                   for i in range(len(labels)))


def evaluate(labels, perm, key, log_probs, floor):
    """Returns (quadgram score, plaintext) for a permutation and key."""
    plaintext = decrypt(labels, perm, key)
    return quadgram_score(plaintext, log_probs, floor), plaintext


def hill_climb(labels, key, log_probs, floor, rng, swaps=None):
    """Hill-climbs the alphabet permutation to maximise the quadgram score.

    With swaps=None it runs steepest ascent to convergence (accurate); with a
    swap budget it does a fast rough pass.
    """
    perm = list(range(26))
    rng.shuffle(perm)
    current = evaluate(labels, perm, key, log_probs, floor)[0]
    if swaps is None:
        improved = True
        while improved:
            improved = False
            for a in range(25):
                for b in range(a + 1, 26):
                    perm[a], perm[b] = perm[b], perm[a]
                    score = evaluate(labels, perm, key, log_probs, floor)[0]
                    if score > current:
                        current = score
                        improved = True
                    else:
                        perm[a], perm[b] = perm[b], perm[a]
    else:
        for _ in range(swaps):
            a, b = rng.randrange(26), rng.randrange(26)
            perm[a], perm[b] = perm[b], perm[a]
            score = evaluate(labels, perm, key, log_probs, floor)[0]
            if score > current:
                current = score
            else:
                perm[a], perm[b] = perm[b], perm[a]
    return current, perm


def load_keywords(wordlist_path):
    """Returns the unique 13-letter A-Z words from the wordlist, uppercased."""
    words = set()
    for line in Path(wordlist_path).read_text(encoding="utf-8",
                                              errors="ignore").splitlines():
        word = line.strip().upper()
        if len(word) == KEY_LENGTH and word.isalpha() and word.isascii():
            words.add(word)
    return sorted(words)


def init_worker(quad_path, cipher_path):
    """Loads the quadgram model and cipher once per worker process."""
    global WORKER_QUAD, WORKER_FLOOR, WORKER_LABELS
    WORKER_QUAD, WORKER_FLOOR = load_quadgrams(quad_path)
    text = Path(cipher_path).read_text(encoding="utf-8").strip()
    WORKER_LABELS = [ord(character) - 65 for character in text]


def quick_score(keyword):
    """Worker task: rough score for one keyword via a capped alphabet climb."""
    key = [ord(character) - 65 for character in keyword]
    score, _ = hill_climb(WORKER_LABELS, key, WORKER_QUAD, WORKER_FLOOR,
                          random.Random(0), swaps=QUICK_SWAPS)
    return score, keyword


def index_of_coincidence(text):
    """Returns the index of coincidence, a quick readability sanity check."""
    total = len(text)
    if total < 2:
        return 0.0
    from collections import Counter
    counts = Counter(text)
    return sum(n * (n - 1) for n in counts.values()) / (total * (total - 1))


def main():
    """Runs the parallel quick pass, refines the top candidates, writes results."""
    args = [a for a in sys.argv[1:] if a != "--top"]
    wordlist = args[0] if args else "/usr/share/dict/words"

    log_probs, floor = load_quadgrams(QUADGRAM_FILE)
    text = CIPHER_FILE.read_text(encoding="utf-8").strip()
    labels = [ord(character) - 65 for character in text]
    keywords = load_keywords(wordlist)

    import os
    workers = os.cpu_count() or 4
    print(f"{len(keywords)} keys of length {KEY_LENGTH}, {workers} cores. "
          f"Correct key scores ~ -2800.")

    start = time.time()
    scored = []
    with ProcessPoolExecutor(max_workers=workers, initializer=init_worker,
                             initargs=(str(QUADGRAM_FILE), str(CIPHER_FILE))) as pool:
        for index, result in enumerate(pool.map(quick_score, keywords, chunksize=20), 1):
            scored.append(result)
            if index % 2000 == 0:
                rate = index / (time.time() - start)
                print(f"  {index}/{len(keywords)}  best {max(scored)[1]} "
                      f"({max(scored)[0]:.0f})  [{rate:.0f} keys/s]")

    scored.sort(reverse=True)
    print(f"Quick pass done in {time.time() - start:.0f}s. Refining top "
          f"{TOP_TO_REFINE}...")

    results = []
    for _, keyword in scored[:TOP_TO_REFINE]:
        key = [ord(character) - 65 for character in keyword]
        best = None
        for seed in range(REFINE_RESTARTS):
            score, perm = hill_climb(labels, key, log_probs, floor, random.Random(seed))
            if best is None or score > best[0]:
                best = (score, decrypt(labels, perm, key))
        results.append((best[0], keyword, best[1]))
    results.sort(reverse=True)

    lines = ["Dictionary attack results (best first; correct key ~ -2800, IoC ~0.066)",
             ""]
    for score, keyword, plaintext in results:
        lines.append(f"{keyword}  score={score:.1f}  IoC={index_of_coincidence(plaintext):.4f}")
        lines.append(f"   {plaintext}")
        lines.append("")
    RESULTS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    best = results[0]
    print(f"\nBest key: {best[1]}  score={best[0]:.1f}  "
          f"IoC={index_of_coincidence(best[2]):.4f}")
    print(f"  {best[2][:100]}")
    print(f"(full ranking written to {RESULTS_FILE.name})")


if __name__ == "__main__":
    main()
