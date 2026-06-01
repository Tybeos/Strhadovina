"""Single-file key solver for the cipher, in the shift-then-substitute order.

The model: the transcribed symbols were made by shifting plaintext letters that
had first been put through one substitution alphabet. So decryption is two steps
for a candidate keyword:

  step 1  mid[i] = (symbol[i] - keyword[i mod 13]) mod 26      (undo the shift)
  step 2  plaintext = substitution(mid)                        (undo the alphabet)

How it tests whether real text is there, in two cheap-to-strong stages:
  - FAST filter: after step 1, measure the index of coincidence of mid. A wrong
    keyword leaves mid scrambled (IoC ~0.04); the correct keyword makes mid a
    plain substitution of English, so its IoC jumps to ~0.066. This is instant
    and cannot be overfit, so it ranks all keywords in one pass.
  - READ check: for the top keywords it solves the substitution (frequency seed
    plus quadgram hill-climb) and counts real English words, so you can read and
    confirm the winner.

Tries strahd_combos.txt then english_13.txt. Needs cipher_oneline.txt and
english_quadgrams.txt in the same folder. Run: python3 solver.py
"""

import math
import random
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CIPHER_FILE = HERE / "cipher_oneline.txt"
QUADGRAM_FILE = HERE / "english_quadgrams.txt"
WORDLISTS = [HERE / "strahd_combos.txt", HERE / "english_13.txt"]
RESULTS_FILE = HERE / "solver_results.txt"

KEY_LENGTH = 13
TOP_BY_IOC = 60
SUB_RESTARTS = 6
ENGLISH_ORDER = "ETAOINSHRDLCUMWFGYPBVKJXQZ"
COMMON_WORDS = (
    "THE AND THAT HAVE FOR NOT WITH YOU THIS BUT HIS FROM THEY HER SHE WILL ONE "
    "ALL WOULD THERE THEIR WHAT OUT ABOUT WHO GET WHICH WHEN MAKE CAN LIKE TIME "
    "JUST HIM KNOW TAKE INTO YEAR YOUR GOOD SOME COULD THEM SEE OTHER THAN THEN "
    "NOW LOOK ONLY COME OVER THINK ALSO BACK AFTER USE TWO HOW OUR WORK FIRST "
    "WELL WAY EVEN NEW WANT ANY THESE GIVE DAY MOST ARE WAS HAD HAS WERE BEEN "
    "MORE VERY WHERE MUCH MANY SUCH HERE WORLD LIFE NIGHT DARK BLOOD DEATH LORD "
    "KING LAND HEART HAND DOOR ROOM FIRE LIGHT UPON NAME SAID INTO MUST GREAT "
    "HOUSE EVERY SHALL THEE THOU HATH FEAR ALIVE DEAD WALK TOWER CASTLE MIST"
).split()


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


def index_of_coincidence(values):
    """Returns the index of coincidence of a sequence of numbers."""
    total = len(values)
    if total < 2:
        return 0.0
    counts = Counter(values)
    return sum(n * (n - 1) for n in counts.values()) / (total * (total - 1))


def apply_keyword(labels, keyword):
    """Step 1: subtracts the repeating keyword shift, returns the mid values."""
    key = [ord(c) - 65 for c in keyword]
    return [(labels[i] - key[i % KEY_LENGTH]) % 26 for i in range(len(labels))]


def frequency_seed(mid):
    """Seeds the substitution by matching mid frequencies to English order."""
    order = [value for value, _ in Counter(mid).most_common()]
    for value in range(26):
        if value not in order:
            order.append(value)
    seed = [0] * 26
    for rank, value in enumerate(order):
        seed[value] = ord(ENGLISH_ORDER[rank]) - 65
    return seed


def decode(mid, sub):
    """Applies a substitution (mid value -> letter) to produce plaintext."""
    return "".join(chr(sub[value] + 65) for value in mid)


def solve_substitution(mid, log_probs, floor):
    """Step 2: cracks the monoalphabetic substitution of mid into English."""
    best = None
    for restart in range(SUB_RESTARTS):
        rng = random.Random(restart)
        sub = frequency_seed(mid)
        if restart:
            rng.shuffle(sub)
        current = quadgram_score(decode(mid, sub), log_probs, floor)
        improved = True
        while improved:
            improved = False
            for a in range(25):
                for b in range(a + 1, 26):
                    sub[a], sub[b] = sub[b], sub[a]
                    score = quadgram_score(decode(mid, sub), log_probs, floor)
                    if score > current:
                        current = score
                        improved = True
                    else:
                        sub[a], sub[b] = sub[b], sub[a]
        if best is None or current > best[0]:
            best = (current, decode(mid, sub))
    return best


def word_hits(text):
    """Counts common English words appearing as substrings in the text."""
    return sum(text.count(word) for word in COMMON_WORDS)


def load_words():
    """Loads the 13-letter keys from the wordlists, in order, without duplicates."""
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


def main():
    """Ranks keywords by the IoC filter, solves the top ones, writes results."""
    labels = [ord(c) - 65 for c in CIPHER_FILE.read_text(encoding="utf-8").strip()]
    words = load_words()
    print(f"Stage 1: IoC filter over {len(words)} keywords "
          "(English ~0.066, random ~0.038)...")

    start = time.time()
    ranked = sorted(((index_of_coincidence(apply_keyword(labels, word)), word)
                     for word in words), reverse=True)
    print(f"  done in {time.time() - start:.0f}s. Best IoC: {ranked[0][0]:.4f} "
          f"({ranked[0][1]})")

    log_probs, floor = load_quadgrams(QUADGRAM_FILE)
    print(f"\nStage 2: solving the substitution for the top {TOP_BY_IOC} keywords...")
    results = []
    for ioc, keyword in ranked[:TOP_BY_IOC]:
        score, plaintext = solve_substitution(apply_keyword(labels, keyword),
                                              log_probs, floor)
        results.append((word_hits(plaintext), ioc, keyword, plaintext))
    results.sort(reverse=True)

    lines = ["Solver results, ranked by real English words found.", ""]
    for hits, ioc, keyword, plaintext in results:
        lines.append(f"{keyword}  words={hits}  IoC={ioc:.4f}")
        lines.append(f"   {plaintext}")
        lines.append("")
    RESULTS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    best = results[0]
    print(f"\nBest: {best[2]}  words={best[0]}  IoC={best[1]:.4f}")
    print(best[3][:120])
    if best[0] >= 25 and best[1] >= 0.058:
        print("\n>>> High IoC and many words - this is very likely the key!")
    else:
        print("\n>>> No keyword stands out; the key is not in these lists "
              "(or the cipher is built differently).")
    print(f"(full ranking -> {RESULTS_FILE.name})")


if __name__ == "__main__":
    main()
