"""Attempts to break the cipher as a Vigenere and recover the plaintext.

Runs three tests and writes solve.txt, each section labelled with what the
test is and what it tracks. Every test is also compared against the random
baseline in random_oneline.txt so real structure stands out:
  - autocorrelation (kappa) test: confirms the repeating key period
  - Shannon entropy: how much structure the text holds versus random
  - chi-squared key recovery: tries Vigenere, Beaufort and variant Beaufort,
    solving each column to rebuild the key, and decrypts with the best fit
  - English word matches: counts common words in the decryption versus random
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

SCHEMES = ("vigenere", "beaufort", "variant")

COMMON_WORDS = [
    "THE", "AND", "THAT", "HAVE", "FOR", "NOT", "WITH", "YOU", "THIS", "BUT",
    "HIS", "FROM", "THEY", "SAY", "HER", "SHE", "WILL", "ONE", "ALL", "WOULD",
    "THERE", "THEIR", "WHAT", "OUT", "ABOUT", "WHO", "GET", "WHICH", "WHEN",
    "MAKE", "CAN", "LIKE", "TIME", "JUST", "HIM", "KNOW", "TAKE", "PEOPLE",
    "INTO", "YEAR", "YOUR", "GOOD", "SOME", "COULD", "THEM", "SEE", "OTHER",
    "THAN", "THEN", "NOW", "LOOK", "ONLY", "COME", "ITS", "OVER", "THINK",
    "ALSO", "BACK", "AFTER", "USE", "TWO", "HOW", "OUR", "WORK", "FIRST",
    "WELL", "WAY", "EVEN", "NEW", "WANT", "BECAUSE", "ANY", "THESE", "GIVE",
    "DAY", "MOST", "ARE", "WAS", "HAD", "HAS", "WERE", "BEEN", "MORE", "VERY",
    "WHERE", "MUCH", "MANY", "SUCH", "HERE", "THROUGH", "WORLD", "LIFE",
]


def decrypt_letter(cipher_index, key_index, scheme):
    """Returns the plaintext index for one cipher/key pair under a scheme."""
    if scheme == "beaufort":
        return (key_index - cipher_index) % 26
    if scheme == "variant":
        return (cipher_index + key_index) % 26
    return (cipher_index - key_index) % 26


def decrypt_scheme(text, key, scheme):
    """Decrypts text with a repeating key under the given scheme."""
    return "".join(
        chr(decrypt_letter(ord(character) - ORD_A,
                           ord(key[i % len(key)]) - ORD_A, scheme) + ORD_A)
        for i, character in enumerate(text))


def decrypt_column(column, key_index, scheme):
    """Decrypts one column with a single key letter under the scheme."""
    return "".join(chr(decrypt_letter(ord(character) - ORD_A, key_index, scheme) + ORD_A)
                   for character in column)


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


def best_key_letter(column, scheme):
    """Finds the key letter whose decryption best fits English."""
    return min(range(26), key=lambda k: chi_squared(decrypt_column(column, k, scheme)))


def recover_key(text, key_length, scheme):
    """Recovers the key under a scheme by solving each column with chi-squared."""
    columns = split_into_columns(text, key_length)
    return "".join(chr(best_key_letter(column, scheme) + ORD_A) for column in columns)


def solve_all_schemes(text):
    """Solves the cipher under each scheme, sorted by best English fit."""
    key_length = detect_key_length(text)
    results = []
    for scheme in SCHEMES:
        key = recover_key(text, key_length, scheme)
        plaintext = decrypt_scheme(text, key, scheme)
        results.append((scheme, key, plaintext, chi_squared(plaintext)))
    return key_length, sorted(results, key=lambda result: result[3])


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


def decrypt_cipher(text):
    """Returns the plaintext from the best-fitting scheme."""
    _, results = solve_all_schemes(text)
    return results[0][2]


def count_word_hits(text, words):
    """Counts how many times any common word appears as a substring."""
    return sum(text.count(word) for word in words)


def found_words(text, words):
    """Returns the common words present in the text, longest first."""
    return sorted(((word, text.count(word)) for word in words if word in text),
                  key=lambda pair: (-len(pair[0]), -pair[1]))


def peak_coincidence(text):
    """Returns the strongest autocorrelation coincidence over all offsets."""
    return max(rate for _, rate in autocorrelation(text))


def solved_chi_squared(text, key_length, scheme="vigenere"):
    """Returns the chi-squared of the text decrypted under the given scheme."""
    key = recover_key(text, key_length, scheme)
    return chi_squared(decrypt_scheme(text, key, scheme))


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
    """Formats the chi-squared key recovery across all schemes."""
    key_length, results = solve_all_schemes(text)
    random_chi = average([solved_chi_squared(sample, key_length)
                          for sample in random_texts])
    body = [f"Key length: {key_length}",
            "(lower chi-squared = fits English better)",
            "",
            "Scheme     Key              Chi-squared"]
    for scheme, key, _, chi in results:
        body.append(f"{scheme:<10} {key:<15}  {chi:8.2f}")
    body.append(f"Random baseline chi-squared (avg): {random_chi:.2f}")

    best_scheme, best_key, best_plaintext, best_chi = results[0]
    body.append("")
    body.append(f"Best scheme: {best_scheme} (key {best_key}, chi-squared {best_chi:.2f})")
    body.append("Decrypted text (best scheme):")
    body.append(best_plaintext)
    return titled_section(
        "Cipher scheme key recovery",
        "tries Vigenere, Beaufort and variant Beaufort; lowest chi-squared wins.",
        body)


def word_section(text, random_texts):
    """Formats the common-word check on the decryption versus random."""
    plaintext = decrypt_cipher(text)
    cipher_hits = count_word_hits(plaintext, COMMON_WORDS)
    random_hits = average([count_word_hits(sample, COMMON_WORDS)
                           for sample in random_texts])
    found = found_words(plaintext, COMMON_WORDS)
    body = [f"Word list size: {len(COMMON_WORDS)} common English words",
            f"Hits in decryption: {cipher_hits}",
            f"Hits in random (avg): {random_hits:.2f}",
            baseline_line("Word hits", cipher_hits, random_hits),
            "",
            "Words found in decryption: " + (
                ", ".join(f"{word} ({count})" for word, count in found) or "none")]
    return titled_section(
        "English word matches",
        "common English words appearing in the decryption; more than random means real text.",
        body)


def build_report(text, random_texts):
    """Builds the full solver report as text."""
    lines = ["Vigenere solver", "==============="]
    for section in (autocorrelation_section, entropy_section,
                    solver_section, word_section):
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
