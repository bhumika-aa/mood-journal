# src/preprocess.py

import re
from nltk.corpus import stopwords

# Use standard stopword list (removes common meaningless words)
STOPWORDS = set(stopwords.words('english'))

def preprocess(text):
    text = text.lower()
    text = re.sub(r'[^a-z\s]', '', text)
    tokens = text.split()

    # Remove stopwords to reduce noise and vocabulary size
    tokens = [word for word in tokens if word not in STOPWORDS]

    return tokens
