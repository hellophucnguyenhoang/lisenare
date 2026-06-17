import pandas as pd
import requests

API_URL = "http://localhost:8000/explanations"

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwidXNlcm5hbWUiOiJwcmhydXJjcjA5IiwiZXhwIjoxNzgxNDk1MTkzfQ.-cWirBSHn_fbCC1KrvHX7uSQWRMDekTJkU0fcin3OS8"

INPUT_CSV = "evaluation_words.csv"
OUTPUT_CSV = "evaluation_results.csv"


def evaluate_word(word: str):
    payload = {"target_term": word}

    headers = {"Authorization": f"Bearer {TOKEN}"}

    try:
        response = requests.post(
            API_URL,
            json=payload,
            headers=headers,
            timeout=120,
        )

        response.raise_for_status()

        data = response.json()

        return {
            "success": True,
            "target_term": data.get("target_term"),
            "explanation": data.get("explanation"),
            "examples": " | ".join(data.get("examples", [])),
            "familiarity_before": data.get("familiarity_before"),
            "familiarity_after": data.get("familiarity_after"),
            "familiarity_improvement": data.get("familiarity_improvement"),
            "response_time_ms": data.get("response_time_ms"),
            "error": "",
        }

    except Exception as e:
        return {
            "success": False,
            "target_term": word,
            "explanation": "",
            "examples": "",
            "familiarity_before": None,
            "familiarity_after": None,
            "familiarity_improvement": None,
            "response_time_ms": None,
            "error": str(e),
        }


def main():
    words_df = pd.read_csv(INPUT_CSV)

    results = []

    total = len(words_df)

    for index, row in words_df.iterrows():
        level = row["level"]
        word = row["word"]

        print(f"[{index + 1}/{total}] Evaluating {word} ({level})")

        result = evaluate_word(word)

        result["level"] = level

        results.append(result)

        # backup sau mỗi request
        pd.DataFrame(results).to_csv(
            OUTPUT_CSV,
            index=False,
        )

    print(f"Done. Saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
