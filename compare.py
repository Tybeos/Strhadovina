"""Compares the cipher against a random baseline.

Computes the same statistics as statistic.py for each of the random lines in
random_oneline.txt, averages them over all samples, and reports how the cipher
compares as a percentage difference. Writes the result to compare.txt.
"""

from pathlib import Path

from statistic import (
    character_counts,
    index_of_coincidence,
    key_length_iocs,
    most_common_ngrams,
)

HERE = Path(__file__).resolve().parent
ONELINE = HERE / "cipher_oneline.txt"
RANDOM_ONELINE = HERE / "random_oneline.txt"
COMPARE = HERE / "compare.txt"


def top_character_percentage(text):
    """Returns the percentage held by the most frequent character."""
    total = len(text)
    if not total:
        return 0.0
    return character_counts(text).most_common(1)[0][1] / total * 100


def max_ngram_count(text, n):
    """Returns how often the most repeated n-gram occurs."""
    common = most_common_ngrams(text, n, 1)
    return common[0][1] if common else 0


def best_key_length_ioc(text):
    """Returns the highest average column IoC across candidate key lengths."""
    return max((ioc for _, ioc in key_length_iocs(text)), default=0.0)


def compute_metrics(text):
    """Computes the scalar statistics used for comparison."""
    return {
        "Index of coincidence": index_of_coincidence(text),
        "Unique characters": len(character_counts(text)),
        "Top character %": top_character_percentage(text),
        "Max bigram count": max_ngram_count(text, 2),
        "Max trigram count": max_ngram_count(text, 3),
        "Best key-length IoC": best_key_length_ioc(text),
    }


def average_metrics(texts):
    """Averages each metric across all texts."""
    totals = {}
    for text in texts:
        for name, value in compute_metrics(text).items():
            totals[name] = totals.get(name, 0.0) + value
    count = len(texts)
    return {name: total / count for name, total in totals.items()}


def percentage_difference(cipher_value, random_value):
    """Returns how much the cipher exceeds the random average, in percent."""
    if random_value == 0:
        return 0.0
    return (cipher_value / random_value - 1) * 100


def build_comparison(cipher_text, random_texts):
    """Builds the cipher-versus-random comparison report."""
    cipher_metrics = compute_metrics(cipher_text)
    random_avg = average_metrics(random_texts)

    lines = ["Cipher vs random baseline",
             "=========================",
             "What it tracks: the same statistics measured on many purely random "
             "samples, so structure that beats random stands out.",
             "",
             f"Random samples: {len(random_texts)}",
             f"Characters per sample: {len(cipher_text)}",
             "",
             "Metric                  Cipher    Random avg   Difference"]
    for name in cipher_metrics:
        cipher_value = cipher_metrics[name]
        random_value = random_avg[name]
        diff = percentage_difference(cipher_value, random_value)
        lines.append(f"{name:<22} {cipher_value:8.4f}  {random_value:10.4f}   {diff:+7.1f}%")
    return "\n".join(lines) + "\n"


def main():
    """Reads the cipher and random baseline and writes the comparison."""
    cipher_text = ONELINE.read_text(encoding="utf-8").strip()
    random_texts = [line for line in
                    RANDOM_ONELINE.read_text(encoding="utf-8").splitlines() if line]

    report = build_comparison(cipher_text, random_texts)
    COMPARE.write_text(report, encoding="utf-8")
    print(report, end="")


if __name__ == "__main__":
    main()
