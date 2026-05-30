"""Attempts to break the cipher as a Vigenere and recover the plaintext.

Runs three tests and writes solve.txt, each section labelled with what the
test is and what it tracks. Every test is also compared against the random
baseline in random_oneline.txt so real structure stands out:
  - autocorrelation (kappa) test: confirms the repeating key period
  - Shannon entropy: how much structure the text holds versus random
  - chi-squared key recovery: solves each column to rebuild the key and decrypt
"""

import math
from pathlib import Path

from statistic import (
    ENGLISH_FREQUENCIES,
    character_counts,
    key_length_iocs,
    split_into_columns,
)

HERE = Path(__file__).resolve().parent
ONELINE = HERE / "cipher_oneline.txt"
RANDOM_ONELINE = HERE / "random_oneline.txt"
SOLVE = HERE / "solve.txt"

RANDOM_ENTROPY = math.log2(len(ENGLISH_FREQUENCIES))
ORD_A = ord("A")


def shift_character(character, shift):
    """Shifts an uppercase letter back by shift positions, wrapping around."""
    return chr((ord(character) - ORD_A - shift) % 26 + ORD_A)


def decrypt_shift(text, shift):
    """Decrypts a single Caesar shift across the whole text."""
    return "".join(shift_character(character, shift) for character in text)


def chi_squared(text):
    """Returns the chi-squared distance from English letter frequencies."""
    total = len(text)
    counts = character_counts(text)
    score = 0.0
    for letter, percentage in ENGLISH_FREQUENCIES.items():
        expected = percentage / 100 * total
        if expected:
            score += (counts.get(letter, 0) - expected) ** 2 / expected
    return score


def best_shift(column):
    """Finds the Caesar shift whose decryption best fits English."""
    return min(range(26), key=lambda shift: chi_squared(decrypt_shift(column, shift)))


def recover_key(text, key_length):
    """Recovers the Vigenere key by solving each column with chi-squared."""
    columns = split_into_columns(text, key_length)
    return "".join(chr(best_shift(column) + ORD_A) for column in columns)


def decrypt_vigenere(text, key):
    """Decrypts text with a repeating Vigenere key."""
    return "".join(
        shift_character(character, ord(key[i % len(key)]) - ORD_A)
        for i, character in enumerate(text))


def shift_coincidence(text, offset):
    """Returns the fraction of positions matching the text shifted by offset."""
    pairs = len(text) - offset
    if pairs < 1:
        return 0.0
    matches = sum(1 for i in range(pairs) if text[i] == text[i + offset])
    return matches / pairs


def autocorrelation(text, max_offset=20):
    """Returns the coincidence rate per offset; peaks mark the key period."""
    return [(offset, shift_coincidence(text, offset))
            for offset in range(1, max_offset + 1)]


def shannon_entropy(text):
    """Returns the Shannon entropy in bits per character."""
    total = len(text)
    if not total:
        return 0.0
    counts = character_counts(text)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def detect_key_length(text, max_length=20):
    """Picks the key length with the highest average column IoC."""
    return max(key_length_iocs(text, max_length), key=lambda pair: pair[1])[0]


def peak_coincidence(text):
    """Returns the strongest autocorrelation coincidence over all offsets."""
    return max(rate for _, rate in autocorrelation(text))


def solved_chi_squared(text, key_length):
    """Returns the chi-squared of the text decrypted with its recovered key."""
    key = recover_key(text, key_length)
    return chi_squared(decrypt_vigenere(text, key))


def average(values):
    """Returns the mean of the values, or zero when empty."""
    return sum(values) / len(values) if values else 0.0


def percentage_difference(value, baseline):
    """Returns how much value differs from the baseline, in percent."""
    if baseline == 0:
        return 0.0
    return (value / baseline - 1) * 100


def baseline_line(label, cipher_value, random_value):
    """Formats one cipher-versus-random comparison line."""
    diff = percentage_difference(cipher_value, random_value)
    return f"{label}: cipher {cipher_value:.4f}, random {random_value:.4f} ({diff:+.1f}%)"


def titled_section(title, info, body):
    """Builds a section with a title, underline and a one-line description."""
    return [title, "-" * len(title), f"What it tracks: {info}", ""] + body


def autocorrelation_section(text, random_texts):
    """Formats the autocorrelation (kappa) test results with random comparison."""
    scores = autocorrelation(text)
    best = max(scores, key=lambda pair: pair[1])
    random_peak = average([peak_coincidence(sample) for sample in random_texts])
    body = ["Offset   Coincidence"]
    for offset, rate in scores:
        marker = "  <- peak" if offset == best[0] else ""
        body.append(f"{offset:<8} {rate:.4f}{marker}")
    body.append("")
    body.append(f"Strongest period: {best[0]} (coincidence {best[1]:.4f})")
    body.append(baseline_line("Peak coincidence", best[1], random_peak))
    return titled_section(
        "Autocorrelation (kappa) test",
        "how often the text matches itself when shifted; peaks reveal the key period.",
        body)


def entropy_section(text, random_texts):
    """Formats the Shannon entropy result with random comparison."""
    entropy = shannon_entropy(text)
    random_entropy = average([shannon_entropy(sample) for sample in random_texts])
    body = [f"Entropy: {entropy:.4f} bits/char",
            f"Random maximum: {RANDOM_ENTROPY:.4f} bits/char",
            baseline_line("Entropy", entropy, random_entropy)]
    return titled_section(
        "Shannon entropy",
        "information per character; lower than random means more structure.",
        body)


def solver_section(text, random_texts):
    """Formats the chi-squared key recovery and the decrypted plaintext."""
    key_length = detect_key_length(text)
    key = recover_key(text, key_length)
    plaintext = decrypt_vigenere(text, key)
    cipher_chi = chi_squared(plaintext)
    random_chi = average([solved_chi_squared(sample, key_length)
                          for sample in random_texts])
    body = [f"Key length: {key_length}",
            f"Recovered key: {key}",
            baseline_line("Decrypted chi-squared", cipher_chi, random_chi),
            "(lower chi-squared than random means the decryption fits English better)",
            "",
            "Decrypted text:",
            plaintext]
    return titled_section(
        "Chi-squared key recovery",
        "each column's best English-fitting shift, combined into the key, then decrypted.",
        body)


def build_report(text, random_texts):
    """Builds the full solver report as text."""
    lines = ["Vigenere solver", "==============="]
    for section in (autocorrelation_section, entropy_section, solver_section):
        lines.append("")
        lines.extend(section(text, random_texts))
    return "\n".join(lines) + "\n"


def main():
    """Reads the cipher and random baseline and writes the solver report."""
    text = ONELINE.read_text(encoding="utf-8").strip()
    random_texts = [line for line in
                    RANDOM_ONELINE.read_text(encoding="utf-8").splitlines() if line]
    SOLVE.write_text(build_report(text, random_texts), encoding="utf-8")
    print(f"solve -> {SOLVE.name} ({len(text)} chars analyzed)")


if __name__ == "__main__":
    main()
