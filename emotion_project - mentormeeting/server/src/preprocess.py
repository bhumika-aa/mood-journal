# src/preprocess.py

import re
from typing import List
from nltk.corpus import stopwords

class TextPreprocessor:
    """
    Handles text cleaning and tokenization.
    Preserves negations to ensure emotional context is not lost.
    """

    # Use standard stopword list but keep negations
    NEGATIONS = {
        'not', 'no', 'never', 'nor', 'neither', 'none', 'cannot', 
        'cant', 'aint', 'wasnt', 'werent', 'didnt', 'doesnt', 
        'dont', 'hadnt', 'hasnt', 'havent', 'isnt', 'shouldnt', 'wouldnt'
    }

    def __init__(self, lang: str = 'english'):
        self.stopwords = set(stopwords.words(lang)) - self.NEGATIONS

    def clean_text(self, text: str) -> str:
        """Lowercases and removes special characters while normalizing negations."""
        text = text.lower()
        # Replace common contractions to make negations consistent
        text = re.sub(r"n't", " not", text)
        text = re.sub(r'[^a-z\s]', '', text)
        return text

    def tokenize(self, text: str) -> List[str]:
        """Tokenizes text and removes stopwords (except negations)."""
        text = self.clean_text(text)
        tokens = text.split()
        return [word for word in tokens if word not in self.stopwords]

    def __call__(self, text: str) -> List[str]:
        """Convenience method to call preprocessor directly."""
        return self.tokenize(text)


# --- BACKWARD COMPATIBILITY ---
_default_preprocessor = None

def preprocess(text: str) -> List[str]:
    """Standalone function for backward compatibility."""
    global _default_preprocessor
    if _default_preprocessor is None:
        _default_preprocessor = TextPreprocessor()
    return _default_preprocessor.tokenize(text)
