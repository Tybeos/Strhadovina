"""Breaks the cipher as a mixed-alphabet Vigenere by simulated annealing.

The symbols were transcribed to A-Z in order of first appearance, so the cipher
is a Vigenere whose alphabet is an unknown permutation. This solver searches for
the alphabet permutation and the period-13 key together, scoring candidate
decryptions with an English quadgram model. It needs english_quadgrams.txt
(download once; see the project notes). Results are compared against the random
baseline so a real solution stands out from noise.
"""

import math
import sys
from pathlib import Path

from solve import COMMON_WORDS, count_word_hits
from statistic import ENGLISH_FREQUENCIES, index_of_coincidence

HERE = Path(__file__).resolve().parent
ONELINE = HERE / "cipher_oneline.txt"
RANDOM_ONELINE = HERE / "random_oneline.txt"
QUADGRAMS = HERE / "english_quadgrams.txt"

ORD_A = ord("A")
KEY_LENGTH = 13
RESTARTS = 30

EXPECTED = [ENGLISH_FREQUENCIES[chr(i + ORD_A)] / 100 for i in range(26)]


def load_quadgrams(path):
    """Loads quadgram log10 probabilities and a floor for unseen quadgrams."""
    counts = {}
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        quad, count = line.split()
        counts[quad] = int(count)
        total += int(count)
    log_probs = {quad: math.log10(count / total) for quad, count in counts.items()}
    floor = math.log10(0.01 / total)
    return log_probs, floor


def quadgram_score(text, log_probs, floor):
    """Returns the English quadgram log-probability of the text."""
    return sum(log_probs.get(text[i:i + 4], floor) for i in range(len(text) - 3))


def solve_key(values):
    """Finds the period-13 key that best aligns each column with English."""
    key = []
    for column in range(KEY_LENGTH):
        histogram = [0] * 26
        for value in values[column::KEY_LENGTH]:
            histogram[value] += 1
        best_shift = max(range(26), key=lambda k: sum(
            histogram[(v + k) % 26] * EXPECTED[v] for v in range(26)))
        key.append(best_shift)
    return key


def evaluate(labels, perm, log_probs, floor):
    """Maps labels through perm, solves the key, returns (score, key, plaintext)."""
    values = [perm[label] for label in labels]
    key = solve_key(values)
    plaintext = "".join(chr((values[i] - key[i % KEY_LENGTH]) % 26 + ORD_A)
                        for i in range(len(values)))
    return quadgram_score(plaintext, log_probs, floor), key, plaintext


def climb(labels, log_probs, floor, rng):
    """Steepest-ascent hill-climb over the permutation from a random start."""
    perm = list(range(26))
    rng.shuffle(perm)
    current = evaluate(labels, perm, log_probs, floor)[0]
    improved = True
    while improved:
        improved = False
        for a in range(25):
            for b in range(a + 1, 26):
                perm[a], perm[b] = perm[b], perm[a]
                score = evaluate(labels, perm, log_probs, floor)[0]
                if score > current:
                    current = score
                    improved = True
                else:
                    perm[a], perm[b] = perm[b], perm[a]
    return current, perm


def solve(text, log_probs, floor, seed_base):
    """Runs many hill-climb restarts and keeps the best decryption."""
    import random
    labels = [ord(character) - ORD_A for character in text]
    best = None
    for restart in range(RESTARTS):
        score, perm = climb(labels, log_probs, floor, random.Random(seed_base + restart))
        if best is None or score > best[0]:
            best = (score, perm)
    return evaluate(labels, best[1], log_probs, floor)


def key_to_text(key):
    """Renders a numeric key as letters."""
    return "".join(chr(value + ORD_A) for value in key)


def evaluate_with_key(labels, perm, key, log_probs, floor):
    """Decrypts with a fixed key and the given permutation, returns (score, text)."""
    klen = len(key)
    plaintext = "".join(chr((perm[labels[i]] - key[i % klen]) % 26 + ORD_A)
                        for i in range(len(labels)))
    return quadgram_score(plaintext, log_probs, floor), plaintext


def climb_with_key(labels, key, log_probs, floor, rng):
    """Hill-climbs the permutation with the key held fixed."""
    perm = list(range(26))
    rng.shuffle(perm)
    current = evaluate_with_key(labels, perm, key, log_probs, floor)[0]
    improved = True
    while improved:
        improved = False
        for a in range(25):
            for b in range(a + 1, 26):
                perm[a], perm[b] = perm[b], perm[a]
                score = evaluate_with_key(labels, perm, key, log_probs, floor)[0]
                if score > current:
                    current = score
                    improved = True
                else:
                    perm[a], perm[b] = perm[b], perm[a]
    return current, perm


def test_key(text, keyword, log_probs, floor, restarts=8):
    """Tests one keyword: finds the best permutation and returns (score, plaintext)."""
    labels = [ord(character) - ORD_A for character in text]
    key = [ord(character) - ORD_A for character in keyword]
    best = None
    for restart in range(restarts):
        import random
        score, perm = climb_with_key(labels, key, log_probs, floor, random.Random(restart))
        if best is None or score > best[0]:
            best = (score, perm)
    return evaluate_with_key(labels, best[1], key, log_probs, floor)


def report(label, score, plaintext):
    """Prints a decryption result with its quality signals."""
    print(f"{label}: score={score:.1f}  IoC={index_of_coincidence(plaintext):.4f}  "
          f"words={count_word_hits(plaintext, COMMON_WORDS)}")
    print(plaintext)


def main():
    """Tests given keywords, or runs the full unguided solver with no arguments.

    A correct key yields a much higher score (around -2800 for this text) and an
    IoC near English (0.066); wrong keys sit near -4800 and IoC ~0.044.
    """
    log_probs, floor = load_quadgrams(QUADGRAMS)
    text = ONELINE.read_text(encoding="utf-8").strip()

    keywords = [word.strip().upper() for word in sys.argv[1:]]
    if keywords:
        print("Testing keywords (correct key scores ~ -2800, IoC ~0.066):")
        for keyword in keywords:
            score, plaintext = test_key(text, keyword, log_probs, floor)
            print()
            report(keyword, score, plaintext)
        return

    random_sample = next(line for line in
                         RANDOM_ONELINE.read_text(encoding="utf-8").splitlines() if line)
    print(f"Mixed-alphabet Vigenere hill-climb (key length {KEY_LENGTH}, "
          f"{RESTARTS} restarts)")
    score, key, plaintext = solve(text, log_probs, floor, seed_base=1000)
    random_score, _, _ = solve(random_sample, log_probs, floor, seed_base=5000)
    print()
    print(f"Random baseline score: {random_score:.1f}")
    print(f"Recovered key: {key_to_text(key)}")
    report("Cipher", score, plaintext)


if __name__ == "__main__":
    main()
