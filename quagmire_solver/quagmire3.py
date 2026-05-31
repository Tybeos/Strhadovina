"""Full Quagmire III / IV breaker for the symbol cipher (console output only).

Unlike the simple "Vigenere + one scrambled alphabet" model, a true Quagmire
also has a scrambled OUTPUT alphabet (the keyword indexes into the keyed
alphabet, not plain A-Z). The decryption model here is therefore:

    plaintext[i] = A_inv[ ( B[symbol[i]] - shift[i mod 13] ) mod 26 ]

with TWO unknown 26-letter permutations:
  - B      maps each transcribed symbol to a number (input / cipher alphabet)
  - A_inv  maps the de-shifted number back to a plaintext letter (output alphabet)
and 13 unknown column shifts (the keyword, in keyed-alphabet space).

It searches B, A_inv and the shifts together by simulated annealing, scoring the
final plaintext with English quadgrams. This is a hard search (two permutations
plus shifts from ~700 characters), so convergence is not guaranteed; --selftest
proves the model and search on known plaintext.

Needs cipher_oneline.txt and english_quadgrams.txt in the same folder.
Run:
  python3 quagmire3.py KEYWORD     test one 13-letter key: find the alphabets
  python3 quagmire3.py             crack blind (search keyword and alphabets)
  python3 quagmire3.py --selftest  verify on a known Quagmire-III plaintext

Key mode fixes the keyword as the column shifts and searches both alphabets; a
correct keyword yields readable English (score well above -4000).
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

KEY_LENGTH = 13
RESTARTS = 30
ITERATIONS = 40000
START_TEMP = 12.0
COOLING = 0.99985

KEY_RESTARTS = 8
KEY_ITERATIONS = 30000


def load_quadgrams(path):
    """Loads quadgram log10 probabilities and a floor for unseen quadgrams."""
    counts, total = {}, 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        quad, count = line.split()
        counts[quad] = int(count)
        total += int(count)
    return {q: math.log10(c / total) for q, c in counts.items()}, math.log10(0.01 / total)


def quadgram_score(text, log_probs, floor):
    """Returns the English quadgram log-probability of the text."""
    return sum(log_probs.get(text[i:i + 4], floor) for i in range(len(text) - 3))


def inverse(perm):
    """Returns the inverse of a permutation given as a list of 26 values."""
    inv = [0] * 26
    for index, value in enumerate(perm):
        inv[value] = index
    return inv


def decrypt(labels, b_perm, a_inv, shifts):
    """Decrypts: plaintext = A_inv[(B[symbol] - shift) mod 26]."""
    return "".join(chr(a_inv[(b_perm[labels[i]] - shifts[i % KEY_LENGTH]) % 26] + 65)
                   for i in range(len(labels)))


def index_of_coincidence(text):
    """Returns the index of coincidence (a readability sanity check)."""
    total = len(text)
    if total < 2:
        return 0.0
    counts = Counter(text)
    return sum(n * (n - 1) for n in counts.values()) / (total * (total - 1))


def anneal(labels, log_probs, floor, rng):
    """One simulated-annealing run over B, A_inv and the shifts."""
    b_perm = list(range(26))
    rng.shuffle(b_perm)
    a_inv = list(range(26))
    rng.shuffle(a_inv)
    shifts = [rng.randrange(26) for _ in range(KEY_LENGTH)]
    current = quadgram_score(decrypt(labels, b_perm, a_inv, shifts), log_probs, floor)
    best = (current, b_perm[:], a_inv[:], shifts[:])

    temperature = START_TEMP
    for _ in range(ITERATIONS):
        temperature *= COOLING
        move = rng.random()
        if move < 0.45:
            target, x, y = b_perm, rng.randrange(26), rng.randrange(26)
            target[x], target[y] = target[y], target[x]
            undo = (b_perm, x, y, None)
        elif move < 0.90:
            target, x, y = a_inv, rng.randrange(26), rng.randrange(26)
            target[x], target[y] = target[y], target[x]
            undo = (a_inv, x, y, None)
        else:
            idx, old = rng.randrange(KEY_LENGTH), None
            old = shifts[idx]
            shifts[idx] = rng.randrange(26)
            undo = (None, idx, old, "shift")

        score = quadgram_score(decrypt(labels, b_perm, a_inv, shifts), log_probs, floor)
        delta = score - current
        if delta > 0 or rng.random() < math.exp(delta / max(temperature, 1e-6)):
            current = score
            if score > best[0]:
                best = (score, b_perm[:], a_inv[:], shifts[:])
        elif undo[3] == "shift":
            shifts[undo[1]] = undo[2]
        else:
            undo[0][undo[1]], undo[0][undo[2]] = undo[0][undo[2]], undo[0][undo[1]]

    return best


def solve(labels, log_probs, floor, restarts, seed_base=0):
    """Runs several annealing restarts and keeps the best decryption."""
    best = None
    for restart in range(restarts):
        result = anneal(labels, log_probs, floor, random.Random(seed_base + restart))
        if best is None or result[0] > best[0]:
            best = result
        print(f"  restart {restart + 1}/{restarts}: best score {best[0]:.0f}")
    return best


def anneal_alphabets(labels, shifts, log_probs, floor, rng):
    """One annealing run over B and A_inv with the keyword shifts held fixed."""
    b_perm = list(range(26))
    rng.shuffle(b_perm)
    a_inv = list(range(26))
    rng.shuffle(a_inv)
    current = quadgram_score(decrypt(labels, b_perm, a_inv, shifts), log_probs, floor)
    best = (current, b_perm[:], a_inv[:])

    temperature = START_TEMP
    for _ in range(KEY_ITERATIONS):
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


def test_key(labels, keyword, log_probs, floor):
    """Fixes a keyword as the shifts and finds the two alphabets for it."""
    shifts = [ord(c) - 65 for c in keyword]
    best = None
    for restart in range(KEY_RESTARTS):
        result = anneal_alphabets(labels, shifts, log_probs, floor,
                                  random.Random(restart))
        if best is None or result[0] > best[0]:
            best = result
    plaintext = decrypt(labels, best[1], best[2], shifts)
    return best[0], plaintext


def encrypt_quagmire(plaintext, b_perm, a_inv, shifts, rng):
    """Builds labels from known plaintext under the model (for the self-test)."""
    a_perm = inverse(a_inv)
    b_inv = inverse(b_perm)
    labels = []
    for i, character in enumerate(plaintext):
        value = (a_perm[ord(character) - 65] + shifts[i % KEY_LENGTH]) % 26
        labels.append(b_inv[value])
    return labels


def selftest(log_probs, floor):
    """Enciphers known English as a Quagmire III, then tries to recover it."""
    plain = ("WEHOLDTHESETRUTHSTOBESELFEVIDENTTHATALLMENARECREATEDEQUALTHATTHEY"
             "AREENDOWEDBYTHEIRCREATORWITHCERTAINUNALIENABLERIGHTSTHATAMONGTHESE"
             "ARELIFELIBERTYANDTHEPURSUITOFHAPPINESSTHATTOSECURETHESERIGHTSGOVERN"
             "MENTSAREINSTITUTEDAMONGMENDERIVINGTHEIRJUSTPOWERSFROMTHECONSENT")
    rng = random.Random(1)
    b_perm = list(range(26)); rng.shuffle(b_perm)
    a_inv = list(range(26)); rng.shuffle(a_inv)
    shifts = [rng.randrange(26) for _ in range(KEY_LENGTH)]
    labels = encrypt_quagmire(plain, b_perm, a_inv, shifts, rng)

    oracle = decrypt(labels, b_perm, a_inv, shifts)
    print(f"Model check (oracle with true keys): "
          f"{'OK' if oracle == plain else 'BROKEN'} on {len(plain)} chars")

    print("Searching from scratch (this is the hard part)...")
    score, b2, a2, s2 = solve(labels, log_probs, floor, restarts=8)
    recovered = decrypt(labels, b2, a2, s2)
    match = sum(x == y for x, y in zip(recovered, plain)) / len(plain)
    print(f"Recovered match: {match * 100:.1f}%  score {score:.0f}")
    print(recovered[:90])


def main():
    """Cracks the real cipher, or runs the self-test."""
    log_probs, floor = load_quadgrams(QUADGRAM_FILE)
    if "--selftest" in sys.argv:
        selftest(log_probs, floor)
        return

    labels = [ord(c) - 65 for c in CIPHER_FILE.read_text(encoding="utf-8").strip()]
    keywords = [a.strip().upper() for a in sys.argv[1:] if not a.startswith("--")]
    if keywords:
        for keyword in keywords:
            if len(keyword) != KEY_LENGTH or not keyword.isalpha():
                print(f"{keyword}: needs {KEY_LENGTH} letters A-Z, skipping")
                continue
            score, plaintext = test_key(labels, keyword, log_probs, floor)
            print(f"{keyword}: score={score:.0f}  IoC={index_of_coincidence(plaintext):.4f}")
            print(plaintext)
            print()
        return

    print(f"Quagmire III search: two alphabets + {KEY_LENGTH} shifts, "
          f"{RESTARTS} restarts. This is hard; convergence not guaranteed.")
    start = time.time()
    score, b_perm, a_inv, shifts = solve(labels, log_probs, floor, RESTARTS)
    plaintext = decrypt(labels, b_perm, a_inv, shifts)
    print(f"\nBest score {score:.0f}  IoC {index_of_coincidence(plaintext):.4f}  "
          f"({time.time() - start:.0f}s)")
    print(plaintext)
    print("\n>>> read the text; if it is English the cipher is broken, "
          "otherwise the search did not converge.")


if __name__ == "__main__":
    main()
