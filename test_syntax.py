import glob
import os
import spacy
from collections import Counter


def build_cefr_dict(folder_path="cefr_vocabs/"):
    """
    folder_path: directory that contains A1.txt, A2.txt, B1.txt, B2.txt, C1.txt
    returns: dictionary like {"go": "A1", "analysis": "C1", ...}
    """
    cefr_dict = {}

    # Pattern to match CEFR files
    for filepath in glob.glob(os.path.join(folder_path, "*.txt")):
        filename = os.path.basename(filepath)      # e.g. "A1.txt"
        level = filename.replace(".txt", "")       # e.g. "A1"

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip().lower()
                if word:
                    cefr_dict[word] = level
    return cefr_dict


def tokenize_clean(text, nlp):
    doc = nlp(text)
    words = []
    for tok in doc:
        # keep only real alphabetic words
        if tok.is_alpha and not tok.ent_type_:
            lemma = tok.lemma_.lower()
            if lemma in CEFR_DICT:
                words.append(lemma)
    return words

def normalize_length(x, k=200):
    """Normalize word count into 0-1 range."""
    return x / (x + k)

def extract_cefr_features(text):
    words = tokenize_clean(text, nlp)
    counts = Counter(CEFR_DICT[w] for w in words)
    total = sum(counts.values())
    if total == 0:
        return None  # No CEFR classifiable words
    percentages = {level: counts[level] / total for level in CEFR_LEVELS}
    norm_len = normalize_length(total)

    return {
        "percentages": percentages,
        "word_count": total,
        "normalized_length": norm_len
    }

def predict_cefr(text):
    features = extract_cefr_features(text)
    if features is None:
        return "Unknown", None
    
    percentages = features['percentages']
    score = sum(percentages[level] * i for i, level in enumerate(CEFR_LEVELS))
    score += features['normalized_length']

    if score < 0.3:
        level = "A1"
    elif score < 0.6:
        level = "A2"
    elif score < 0.7:
        level = "B1"
    elif score < 0.8:
        level = "B2"
    elif score < 1.5:
        level = "C1"
    else:
        level = "C2"
    
    return CEFR_LEVELS.index(level), level, features, score

text = """
    Our brains are busier than ever before. We’re assaulted with facts, pseudo facts, jibber-jabber, and rumour, all posing as information which we have to sift through and find out what we need to know and what we can ignore. At the same time, we are all doing more. Thirty years ago, travel agents made our airline reservations and salespeople helped us find what we needed in shops. Now we do most things ourselves. We’re doing the work of 10 different people while still trying to keep up with our lives, our families, our careers, our hobbies and our favourite TV shows, and helping us do all this is our smartphones. They’ve become part of the 21st-century mania for cramming as much as possible into every single spare moment.
But there’s a fly in the ointment. Although we think we’re multitasking – doing several things at once – this is a powerful and dangerous illusion. Earl Miller, a neuroscientist at Massachusetts Institute of Technology (MIT) and world expert on divided attention, says that our brains are ‘not wired to multitask well … . When people think they’re multitasking, they’re actually switching from one task to another very rapidly. And every time they do, there’s a cognitive cost in doing so.’ So we’re not actually keeping a lot of balls in the air like expert jugglers; we’re more like amateur plate spinners, frantically switching from one task to another, ignoring the one that’s not right in front of us but worried it’ll come crashing down any minute. Even though we think we’re getting a lot done, ironically, multitasking makes us demonstrably less efficient.
Multitasking has been found to increase the production of the stress hormone cortisol as well as the fight-or-flight hormone adrenaline, which can overstimulate your brain and cause mental fog or scrambled thinking. Multitasking creates a sort of craving, effectively rewarding the brain for losing focus and for constantly searching for external stimulation. To make matters worse, the area of the brain known as the prefrontal cortex has a novelty bias, meaning that its attention can be easily hijacked by something new – the proverbial shiny objects that we use to entice infants, for example. The irony here for those of us who are trying to focus amid competing activities is clear; the very brain region we need to rely on for staying on task is easily distracted.
Just having the opportunity to multitask is detrimental to cognitive performance. Glenn Wilson, former Visiting Professor of Psychology at Gresham College, London, calls it info-mania. His research found that being in situations where you’re trying to focus on a task when an email sits unread in your inbox reduces your effective Intelligence Quotient (IQ) by almost 10 points. Wilson showed that the cognitive losses from multitasking are even greater than those caused by fatigue.
Russ Poldrack, a neuroscientist at Stanford University, found that learning new information while multitasking causes the information to go to the wrong part of the brain. If students do their homework and watch TV at the same time, for instance, the information from their schoolwork goes into the striatum, a specialised region for storing new procedures and skills, as opposed to facts and ideas. Without the distraction of TV, the information goes into the hippocampus, where it’s organised and categorised in a variety of ways, making it easier to retrieve.
To make matters worse, lots of multitasking requires decision-making: ‘Do I answer this text message or ignore it? How do I respond to this?’ It turns out that decision-making is also very hard on our brains, and that little decisions appear to take up the same level of neural resources as big ones. We rapidly spiral into a depleted state in which, after making lots of insignificant decisions, we can end up making truly bad decisions about something important.
In discussing information overload with business leaders, top scientists and writers, email comes up again and again as a problem. It’s not a philosophical objection to email itself, but rather the mind-numbing volume of communication that comes in. When the 10-year-old son of my neuroscience colleague was asked what his father does for a living, he responded, ‘He answers emails.’ My colleague admitted that it’s not so far from the truth. We feel obliged to reply to our emails, but it seems impossible to do so and get anything else done.
"""


nlp = spacy.load("en_core_web_sm")
CEFR_DICT = build_cefr_dict()
CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
CEFR_WEIGHTS = {"A1":1, "A2":2, "B1":3, "B2":4, "C1":5, "C2":6}

if __name__ == "__main__":
    index, level, features, score = predict_cefr(text)
    print(level)
    print(score)
    print(features)
    