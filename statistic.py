"""Letter and n-gram statistics for the normalized cipher.

Provides reusable analysis functions that other modules can import:
frequencies, English comparison, n-grams, index of coincidence, Kasiski
spacings, and per-column key-length estimation. Run directly to read
cipher_oneline.txt and write a full report to statistic.txt.
"""

from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ONELINE = HERE / "cipher_oneline.txt"
STATISTIC = HERE / "statistic.txt"

ENGLISH_IOC = 0.0667
RANDOM_IOC = 0.0385

ENGLISH_FREQUENCIES = {
    "E": 12.70, "T": 9.06, "A": 8.17, "O": 7.51, "I": 6.97, "N": 6.75,
    "S": 6.33, "H": 6.09, "R": 5.99, "D": 4.25, "L": 4.03, "C": 2.78,
    "U": 2.76, "M": 2.41, "W": 2.36, "F": 2.23, "G": 2.02, "Y": 1.97,
    "P": 1.93, "B": 1.29, "V": 0.98, "K": 0.77, "J": 0.15, "X": 0.15,
    "Q": 0.10, "Z": 0.07,
}


def character_counts(text):
    """Counts how often each character appears."""
    return Counter(text)


def character_frequencies(text):
    """Returns (character, count, percentage) sorted by count, descending."""
    total = len(text)
    return [(character, count, count / total * 100)
            for character, count in character_counts(text).most_common()]


def english_letters_by_frequency():
    """Returns English letters ordered from most to least frequent."""
    return [letter for letter, _ in
            sorted(ENGLISH_FREQUENCIES.items(), key=lambda kv: kv[1], reverse=True)]


def frequency_substitution(text):
    """Maps each character to the English letter of equal frequency rank."""
    english_order = english_letters_by_frequency()
    ranked = [character for character, _ in character_counts(text).most_common()]
    return {character: english_order[i]
            for i, character in enumerate(ranked) if i < len(english_order)}


def apply_substitution(text, mapping):
    """Replaces each character using the mapping, keeping unmapped ones."""
    return "".join(mapping.get(character, character) for character in text)


def index_of_coincidence(text):
    """Returns the index of coincidence, a hint at the cipher type."""
    total = len(text)
    if total < 2:
        return 0.0
    counts = character_counts(text)
    return sum(n * (n - 1) for n in counts.values()) / (total * (total - 1))


def english_comparison(text):
    """Returns (character, observed%, english%, difference) for each character."""
    total = len(text)
    counts = character_counts(text)
    rows = []
    for character, expected in sorted(ENGLISH_FREQUENCIES.items()):
        observed = counts.get(character, 0) / total * 100 if total else 0.0
        rows.append((character, observed, expected, observed - expected))
    return rows


def ngram_counts(text, n):
    """Counts overlapping n-grams of the given size."""
    return Counter(text[i:i + n] for i in range(len(text) - n + 1))


def most_common_ngrams(text, n, top=10):
    """Returns the most common n-grams with their counts."""
    return ngram_counts(text, n).most_common(top)


def repeated_sequences(text, length):
    """Maps each repeated sequence of the given length to its positions."""
    positions = {}
    for i in range(len(text) - length + 1):
        positions.setdefault(text[i:i + length], []).append(i)
    return {seq: pos for seq, pos in positions.items() if len(pos) > 1}


def kasiski_spacings(text, length=3):
    """Returns gaps between repeats of equal sequences (Kasiski test)."""
    spacings = []
    for positions in repeated_sequences(text, length).values():
        for earlier, later in zip(positions, positions[1:]):
            spacings.append(later - earlier)
    return spacings


def divisors(number, maximum):
    """Returns the divisors of number from 2 up to maximum."""
    return [d for d in range(2, maximum + 1) if number % d == 0]


def likely_key_lengths(text, length=3, max_length=20, top=5):
    """Ranks key lengths by how often they divide Kasiski spacings."""
    votes = Counter()
    for spacing in kasiski_spacings(text, length):
        for divisor in divisors(spacing, max_length):
            votes[divisor] += 1
    return votes.most_common(top)


def split_into_columns(text, key_length):
    """Splits text into key_length columns, every key_length-th character."""
    return ["".join(text[i::key_length]) for i in range(key_length)]


def average_column_ioc(text, key_length):
    """Returns the mean index of coincidence across all columns."""
    columns = split_into_columns(text, key_length)
    iocs = [index_of_coincidence(column) for column in columns]
    return sum(iocs) / len(iocs) if iocs else 0.0


def key_length_iocs(text, max_length=20):
    """Returns the average column IoC for each candidate key length."""
    return [(k, average_column_ioc(text, k)) for k in range(1, max_length + 1)]


def frequency_section(text):
    """Formats the character frequency table with the substitution guess."""
    mapping = frequency_substitution(text)
    lines = ["Character frequencies", "---------------------",
             "Char     Count   Percentage   Guess"]
    for character, count, percentage in character_frequencies(text):
        guess = mapping.get(character, "?")
        lines.append(f"{character:<8} {count:<7} {percentage:6.2f}%       {guess}")
    return lines


def substitution_section(text):
    """Formats the frequency-based substitution guess and decoded text."""
    decoded = apply_substitution(text, frequency_substitution(text))
    return ["Frequency substitution guess",
            "----------------------------",
            "Most frequent character maps to the most frequent English letter.",
            "",
            "Decoded text:",
            decoded]


def english_section(text):
    """Formats the observed-versus-English comparison table with the guess."""
    mapping = frequency_substitution(text)
    lines = ["English comparison (character vs English letter frequency)",
             "----------------------------------------------------------",
             "Char     Guess   Observed   English   Difference"]
    for character, observed, expected, difference in english_comparison(text):
        guess = mapping.get(character, "?")
        lines.append(f"{character:<8} {guess:<7} {observed:7.2f}%  {expected:6.2f}%   {difference:+6.2f}")
    return lines


def ngram_section(text):
    """Formats the most common bigrams and trigrams."""
    lines = ["Common bigrams and trigrams", "---------------------------"]
    lines.append("Bigrams:  " + ", ".join(
        f"{gram} ({count})" for gram, count in most_common_ngrams(text, 2)))
    lines.append("Trigrams: " + ", ".join(
        f"{gram} ({count})" for gram, count in most_common_ngrams(text, 3)))
    return lines


def key_length_section(text):
    """Formats the Kasiski and per-column key-length estimates."""
    lines = ["Key length estimation", "---------------------"]
    kasiski = likely_key_lengths(text)
    lines.append("Kasiski votes: " + (", ".join(
        f"{length} ({votes})" for length, votes in kasiski) or "none"))
    lines.append("")
    lines.append("Length   Avg column IoC")
    for length, ioc in key_length_iocs(text):
        marker = "  <- near English" if ioc >= ENGLISH_IOC * 0.9 else ""
        lines.append(f"{length:<8} {ioc:.4f}{marker}")
    return lines


def build_report(text):
    """Builds the full statistics report as text."""
    ioc = index_of_coincidence(text)
    counts = character_counts(text)

    lines = ["Cipher statistics", "================="]
    lines.append(f"Total characters: {len(text)}")
    lines.append(f"Unique characters: {len(counts)}")
    lines.append(f"Index of coincidence: {ioc:.4f} "
                 f"(English {ENGLISH_IOC}, random {RANDOM_IOC})")

    for section in (frequency_section, substitution_section, english_section,
                    ngram_section, key_length_section):
        lines.append("")
        lines.extend(section(text))

    return "\n".join(linres) + "\n"


def main():
    """Reads the oneline cipher and writes the statistics report."""
    text = ONELINE.read_text(encoding="utf-8").strip()
    STATISTIC.write_text(build_report(text), encoding="utf-8")
    print(f"statistic -> {STATISTIC.name} ({len(text)} chars analyzed)")


if __name__ == "__main__":
    main()
