import pandas as pd
import re
import nltk
nltk.download('punkt')
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

data = pd.read_csv('emdr_filtered_results.csv')


# Check duplicates
data = data.drop_duplicates(subset=['content']).reset_index(drop=True)
data = data.drop_duplicates(subset=['id']).reset_index(drop=True)

# Handle NA
data = data.dropna(subset=['content'])

# Text cleaning
def clean_text(text):
    text = re.sub(r"http\S+", "", text)  # Remove URLs
    text = re.sub(r"[^a-zA-Z\s]", "", text)  # Remove special characters
    text = text.lower()
    return text

data['cleaned_content'] = data['content'].apply(clean_text)

print(data.head())

# Tokenization and lemmatization
lemmatizer = WordNetLemmatizer()

def process_text(text):
    tokens = word_tokenize(text)
    return " ".join([lemmatizer.lemmatize(token) for token in tokens])

data['processed_content'] = data['cleaned_content'].apply(process_text)

# save process
data.to_csv('processed_emdr_data.csv', index=False)
