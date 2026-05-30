"""Computes letter statistics for the normalized cipher.

Reads cipher_oneline.txt and writes statistic.txt with a letter frequency
table, totals, and the index of coincidence as a hint at the cipher type.
"""

from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ONELINE = HERE / "cipher_oneline.txt"
STATISTIC = HERE / "statistic.txt"


def index_of_coincidence(counts, total):
    """Returns the index of coincidence, a hint at the cipher type."""
    if total < 2:
        return 0.0
    return sum(n * (n - 1) for n in counts.values()) / (total * (total - 1))


def build_statistics(text):
    """Builds a human-readable report of letter frequencies and stats."""
    total = len(text)
    counts = Counter(text)
    unique = len(counts)
    ioc = index_of_coincidence(counts, total)

    lines = []
    lines.append("Cipher statistics")
    lines.append("=================")
    lines.append(f"Total characters: {total}")
    lines.append(f"Unique characters: {unique}")
    lines.append(f"Index of coincidence: {ioc:.4f}")
    lines.append("")
    lines.append("Letter   Count   Percentage")
    lines.append("---------------------------")

    for letter, count in counts.most_common():
        percentage = count / total * 100
        lines.append(f"{letter:<8} {count:<7} {percentage:6.2f}%")

    most_common = counts.most_common(1)[0]
    least_common = counts.most_common()[-1]
    lines.append("")
    lines.append(f"Most frequent: {most_common[0]} ({most_common[1]}x)")
    lines.append(f"Least frequent: {least_common[0]} ({least_common[1]}x)")

    return "\n".join(lines) + "\n"


def main():
    """Reads the oneline cipher and writes the statistics report."""
    text = ONELINE.read_text(encoding="utf-8").strip()

    statistics = build_statistics(text)
    STATISTIC.write_text(statistics, encoding="utf-8")

    print(f"statistic -> {STATISTIC.name} ({len(text)} chars analyzed)")


if __name__ == "__main__":
    main()
