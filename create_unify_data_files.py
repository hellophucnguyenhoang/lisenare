import pandas as pd

# Define mapping for each file to the unified column names
file_mappings = [
    {
        "input": "static_data/QA_Race.xlsx",
        "output": "static_data/QA_Race_unified.xlsx",
        "columns": {
            "Title": "title",
            "article": "passage",
            "Topic": "topic",
            "Question": "question",
            "Option": "option",
            "True_answer": "answer",
            "Explain": "explanation",
        },
    },
    {
        "input": "static_data/All_Passages_Questions.xlsx",
        "output": "static_data/All_Passages_Questions_unified.xlsx",
        "columns": {
            "title": "title",
            "passage": "passage",
            "topic": "topic",
            "Question": "question",
            "option": "option",
            "answer": "answer",
            "explanation": "explanation",
        },
    },
    {
        "input": "static_data/ResultCambridge_with_topic.xlsx",
        "output": "static_data/ResultCambridge_unified.xlsx",
        "columns": {
            "title": "title",
            "passage": "passage",
            "topic": "topic",
            "question": "question",
            "option": "option",
            "answer": "answer",
            "explanation": "explanation",
        },
    },
]


def unify_file(mapping: dict):
    df = pd.read_excel(mapping["input"])
    # Strip column names and lowercase them
    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]

    # Rename columns to unified names
    df = df.rename(columns=mapping["columns"])

    # Reorder columns
    unified_cols = ["title", "passage", "topic", "question", "option", "answer", "explanation"]
    # Keep only existing columns
    df = df[[c for c in unified_cols if c in df.columns]]

    # Save as CSV
    df.to_excel(mapping["output"], index=False)
    print(f"Saved unified file: {mapping['output']}")


def main():
    for mapping in file_mappings:
        unify_file(mapping)
    print("All files have been unified.")


if __name__ == "__main__":
    main()
