# src/preprocess.py

import re
from nltk.corpus import stopwords

# Use standard stopword list but keep negations
NEGATIONS = {'not', 'no', 'never', 'nor', 'neither', 'none', 'cannot', 'cant', 'aint', 'wasnt', 'werent', 'didnt', 'doesnt', 'dont', 'hadnt', 'hasnt', 'havent', 'isnt', 'shouldnt', 'wouldnt'}
STOPWORDS = set(stopwords.words('english')) - NEGATIONS

def preprocess(text):
    text = text.lower()
    # Replace common contractions to make negations consistent
    text = re.sub(r"n't", " not", text)
    text = re.sub(r'[^a-z\s]', '', text)
    tokens = text.split()

    # Remove stopwords but keep the negations we just preserved
    tokens = [word for word in tokens if word not in STOPWORDS]

    return tokens
