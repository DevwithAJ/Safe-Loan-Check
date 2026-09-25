import re
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin


class NameLexicalFeatures(BaseEstimator, TransformerMixin):
    """Leakage-safe features derived only from the public app name.

    These features intentionally do not use RBI directory status, fuzzy-directory
    match score, source URL, label evidence, or any field assigned after the label.
    """

    KEYWORDS = [
        "loan", "cash", "rupee", "credit", "borrow", "lend", "money",
        "paisa", "finance", "instant", "quick", "easy", "kredit",
        "advance", "emi",
    ]

    FEATURE_NAMES = [
        "name_length_chars",
        "name_word_count",
        "name_digit_count",
        "name_symbol_count",
        "name_uppercase_ratio",
    ] + [f"name_has_{k}" for k in KEYWORDS]

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        rows = []
        for value in X:
            original = "" if value is None else str(value)
            lower = original.lower()
            normalized = re.sub(r"[^a-z0-9 ]+", " ", lower)
            words = [w for w in normalized.split() if w]
            n = max(len(original), 1)

            row = [
                float(len(original)),
                float(len(words)),
                float(sum(ch.isdigit() for ch in original)),
                float(sum((not ch.isalnum()) and (not ch.isspace()) for ch in original)),
                float(sum(ch.isupper() for ch in original) / n),
            ]
            row.extend(float(keyword in lower) for keyword in self.KEYWORDS)
            rows.append(row)

        return np.asarray(rows, dtype=float)

    def get_feature_names_out(self, input_features=None):
        return np.asarray(self.FEATURE_NAMES, dtype=object)
