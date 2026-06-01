"""Transcription-integrity check for the cipher.

A single dropped or added symbol shifts everything after it out of the period-13
rhythm, so no key can decrypt the tail. This looks for such a slip: it tries
deleting one symbol at each position, and inserting one symbol at each position,
and reports which edits most raise the per-column index of coincidence (the
period-13 structure). Column IoC does not depend on the key, so this needs no
keyword. A clean error shows up as an edit that pushes IoC toward English (0.066);
a weak, spread-out result means the structure is disrupted in some other way.

Needs cipher_oneline.txt in the same folder. Run: python3 repair.py
"""

from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CIPHER_FILE = HERE / "cipher_oneline.txt"
PERIOD = 13


def ioc(text):
    """Returns the index of coincidence of a string."""
    total = len(text)
    if total < 2:
        return 0.0
    counts = Counter(text)
    return sum(n * (n - 1) for n in counts.values()) / (total * (total - 1))


def column_ioc(text):
    """Returns the average index of coincidence across the 13 columns."""
    return sum(ioc(text[j::PERIOD]) for j in range(PERIOD)) / PERIOD


def best_deletions(text, top=5):
    """Ranks single-symbol deletions by the column IoC they produce."""
    scored = [(column_ioc(text[:p] + text[p + 1:]), p) for p in range(len(text))]
    return sorted(scored, reverse=True)[:top]


def best_insertions(text, top=5):
    """Ranks single-symbol insertions by the column IoC they produce."""
    scored = [(column_ioc(text[:p] + "A" + text[p:]), p) for p in range(len(text) + 1)]
    return sorted(scored, reverse=True)[:top]


def main():
    """Reports the baseline column IoC and the most helpful single edits."""
    text = CIPHER_FILE.read_text(encoding="utf-8").strip()
    base = column_ioc(text)
    print(f"Baseline column IoC at period {PERIOD}: {base:.4f}  (English ~0.066)")
    print("A clean transcription slip would show one edit jumping toward 0.066.\n")

    print("Best single deletions (remove a symbol):")
    for value, position in best_deletions(text):
        print(f"  remove position {position} ('{text[position]}'): IoC -> {value:.4f}")

    print("\nBest single insertions (add a symbol):")
    for value, position in best_insertions(text):
        print(f"  insert at position {position}: IoC -> {value:.4f}")

    best = max(best_deletions(text, 1)[0][0], best_insertions(text, 1)[0][0])
    print(f"\nBest achievable with one edit: {best:.4f}")
    if best >= 0.060:
        print(">>> Big jump - that edit likely fixes a transcription error.")
    else:
        print(">>> Only a small rise; one edit does not restore the structure "
              "(multiple errors, non-English text, or a different cipher).")


if __name__ == "__main__":
    main()
