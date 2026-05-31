"""Little window app to test cipher keys by typing them.

Type a 13-letter keyword, press Enter or click Test, and it fixes that key,
hill-climbs the scrambled alphabet to fit English, and shows the score and the
decrypted text. A correct key scores around -2800 (IoC ~0.066) and reads as
English; wrong keys sit near -4800. Needs cipher_oneline.txt and
english_quadgrams.txt in the same folder. Run: python3 key_tester.py
"""

import math
import random
import threading
import tkinter as tk
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CIPHER_FILE = HERE / "cipher_oneline.txt"
QUADGRAM_FILE = HERE / "english_quadgrams.txt"
KEY_LENGTH = 13
RESTARTS = 8
PROMISING = -3500


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


def decrypt(labels, perm, key):
    """Decrypts: plaintext = perm[label] - key (mod 26), key repeating."""
    klen = len(key)
    return "".join(chr((perm[labels[i]] - key[i % klen]) % 26 + 65)
                   for i in range(len(labels)))


def index_of_coincidence(text):
    """Returns the index of coincidence (a readability sanity check)."""
    total = len(text)
    if total < 2:
        return 0.0
    counts = Counter(text)
    return sum(n * (n - 1) for n in counts.values()) / (total * (total - 1))


def full_climb(labels, key, log_probs, floor, rng):
    """Steepest-ascent alphabet hill-climb from a random start."""
    perm = list(range(26))
    rng.shuffle(perm)
    current = quadgram_score(decrypt(labels, perm, key), log_probs, floor)
    improved = True
    while improved:
        improved = False
        for a in range(25):
            for b in range(a + 1, 26):
                perm[a], perm[b] = perm[b], perm[a]
                score = quadgram_score(decrypt(labels, perm, key), log_probs, floor)
                if score > current:
                    current = score
                    improved = True
                else:
                    perm[a], perm[b] = perm[b], perm[a]
    return current, perm


def test_keyword(labels, keyword, log_probs, floor):
    """Returns (score, IoC, plaintext) for a keyword, best of several climbs."""
    key = [ord(c) - 65 for c in keyword]
    best = None
    for seed in range(RESTARTS):
        score, perm = full_climb(labels, key, log_probs, floor, random.Random(seed))
        if best is None or score > best[0]:
            best = (score, perm)
    plaintext = decrypt(labels, best[1], key)
    return best[0], index_of_coincidence(plaintext), plaintext


class App:
    """A tiny Tk window for typing and testing keys."""

    def __init__(self, root):
        """Builds the window and starts loading the English model."""
        self.root = root
        self.labels = None
        self.log_probs = None
        self.floor = None
        root.title("Strahd key tester")

        tk.Label(root, text="Type a 13-letter key:", font=("Helvetica", 13)).pack(
            padx=12, pady=(12, 4), anchor="w")
        self.entry = tk.Entry(root, font=("Courier", 16), width=24)
        self.entry.pack(padx=12, anchor="w")
        self.entry.bind("<Return>", lambda event: self.start_test())
        self.button = tk.Button(root, text="Test", command=self.start_test,
                                state="disabled", font=("Helvetica", 12))
        self.button.pack(padx=12, pady=8, anchor="w")
        self.status = tk.Label(root, text="Loading English model...",
                               font=("Helvetica", 12))
        self.status.pack(padx=12, anchor="w")
        self.output = tk.Text(root, width=80, height=12, font=("Courier", 11),
                              wrap="word")
        self.output.pack(padx=12, pady=12)

        threading.Thread(target=self.load_model, daemon=True).start()

    def load_model(self):
        """Loads the cipher and quadgrams, then enables the input."""
        text = CIPHER_FILE.read_text(encoding="utf-8").strip()
        self.labels = [ord(c) - 65 for c in text]
        self.log_probs, self.floor = load_quadgrams(QUADGRAM_FILE)
        self.root.after(0, self.ready)

    def ready(self):
        """Switches the UI to the ready state."""
        self.status.config(text="Ready. Correct key scores ~ -2800; wrong ~ -4800.")
        self.button.config(state="normal")
        self.entry.focus_set()

    def start_test(self):
        """Validates the typed key and launches the test in a thread."""
        if self.log_probs is None:
            return
        keyword = self.entry.get().strip().upper()
        if len(keyword) != KEY_LENGTH or not keyword.isalpha():
            self.status.config(text=f"Key must be {KEY_LENGTH} letters A-Z.")
            return
        self.button.config(state="disabled")
        self.status.config(text=f"Testing {keyword} ...")
        threading.Thread(target=self.run_test, args=(keyword,), daemon=True).start()

    def run_test(self, keyword):
        """Runs the test off the UI thread and posts the result back."""
        score, ioc, plaintext = test_keyword(self.labels, keyword,
                                              self.log_probs, self.floor)
        self.root.after(0, lambda: self.show_result(keyword, score, ioc, plaintext))

    def show_result(self, keyword, score, ioc, plaintext):
        """Displays the result and flags whether it looks promising."""
        promising = score > PROMISING
        verdict = "PROMISING - read the text!" if promising else "looks like noise"
        self.status.config(text=f"{keyword}: score {score:.0f}, IoC {ioc:.4f}  "
                                f"-> {verdict}",
                           fg=("dark green" if promising else "black"))
        self.output.delete("1.0", "end")
        self.output.insert("end", plaintext)
        self.button.config(state="normal")
        self.entry.focus_set()


def main():
    """Opens the app window."""
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
