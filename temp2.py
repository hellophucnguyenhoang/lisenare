from phonemizer import phonemize
from phonemizer.separator import Separator

text = "What is your name?"

# Define custom separators: 
# - phone: space between each IPA character
# - word: double space (or any string) between words
# - syllable: only works with 'festival' backend, usually kept as None for espeak
sep = Separator(phone=' ', word='  ')

ipa_result = phonemize(
    text, 
    language='en-us', 
    backend='espeak', 
    separator=sep, 
    strip=True
)

print(f"Raw: {text}")
print(f"IPA: {ipa_result}")
