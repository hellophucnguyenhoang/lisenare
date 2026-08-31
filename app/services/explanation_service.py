import re
from collections.abc import Callable
from typing import Literal

from fastapi import status
from ollama import generate
from pydantic import BaseModel
from sqlmodel import Session

from app.exceptions import ErrorCode, RequestException
from app.schemas import ExplanationResponse
from utils.text_utils import (
    get_lenient_stems,
    is_valid_english,
    normalize_target_term,
)

from .brick_memory_service import calculate_sentence_familiarity


def build_vocab_prompts(word: str) -> str:
    # Since it's English only, we use a single strict directive
    return f"""Task: Act as a Literal Linguistic Parser.

[CORE DIRECTIVE]: 
You MUST use the input word "{word}" exactly as the <target>. 
Do not use synonyms, do not "soften" the term, and do not substitute it with a different word.

Rules:
1. Write ONE short explanation (DO NOT use the word "{word}" itself in the explanation).
2. Write 2-3 examples using the exact word "{word}".
3. You MUST follow the XML format below.

Example Input: apple
Example Output:
<target>apple</target>
<explanation>A round fruit with red, green, or yellow skin and a crisp, firm inside.</explanation>
<examples>
<example>She took a large bite out of the juicy red apple.</example>
<example>We went to the orchard to pick fresh apples from the trees.</example>
</examples>

Now do this:
Input: {word}
Output:""".strip()


def build_explanation_simplify_prompts(word: str, text: str) -> str:
    return f"""Task: Simplify the text for learners.
Rules:
- Use easy words.
- Do NOT use the word "{word}" in your output.
- Output format: <simplified>text</simplified>

Example:
Input word: happy
Input text: Feeling or showing pleasure, joy, or satisfaction.
Output: <simplified>Feeling good and enjoying something.</simplified>

Now do this:
Input word: {word}
Input text: {text}
Output:""".strip()


def build_example_simplify_prompts(word: str, text: str) -> str:
    return f"""Task: Simplify the sentence for learners.
Rules:
- Use easy words.
- You MUST include the word "{word}" in your output.
- Output format: <simplified>text</simplified>

Example:
Input word: happy
Input text: She looked happy after hearing the good news.
Output: <simplified>She felt happy after hearing the good news.</simplified>

Now do this:
Input word: {word}
Input text: {text}
Output:""".strip()


def generate_text(model: str, prompt: str) -> str:
    # No system prompt passed here
    response = generate(
        model=model,
        prompt=prompt,
    )
    return response.response


def extract_tags(text: str, tag: str) -> list[str]:
    pattern = rf"<{tag}>(.*?)</{tag}>"
    matches = re.findall(
        pattern,
        text,
        re.DOTALL,
    )
    return [m.strip() for m in matches]


def extract_first_tag(text: str, tag: str) -> str | None:
    matches = extract_tags(text, tag)
    if not matches:
        return None
    return matches[0]


def parse_vocab_response(raw_text: str) -> ExplanationResponse:
    """
    Parse the LLM output wrapped in tags into a structured schema.
    """
    target_term = extract_first_tag(raw_text, "target")
    explanation = extract_first_tag(raw_text, "explanation")
    examples = extract_tags(raw_text, "example")

    if target_term is None or explanation is None:
        raise ValueError(
            "LLM output did not contain an <target> or <explanation> tag."
        )

    return ExplanationResponse(
        target_term=target_term,
        explanation=explanation.strip(),
        examples=[ex.strip() for ex in examples if ex.strip()],
    )


class SimplificationMetric(BaseModel):
    """The familiarity score before and after
    a simplification of an explanation or a sentence example"""

    before_score: float
    after_score: float


def simplify_until_better(
    *,
    session: Session,
    learner_id: int,
    model: str,
    target_term: str,
    text: str,
    simplify_prompt_builder: Callable[[str, str], tuple[str, str]],
    mode: Literal["explanation", "example"],
    max_rounds: int = 2,
) -> tuple[str, SimplificationMetric]:
    """
    Simplify a text up to `max_rounds` times.
    Keep the simplified version only if its familiarity score is strictly higher.
    If simplification does not improve the score, stop and keep the current text.

    Returns:
        (final_text, SimplificationMetric(before_score, after_score))
    """
    current_text = text.strip()
    current_score = calculate_sentence_familiarity(
        session, learner_id, current_text
    )
    target_stems = get_lenient_stems(target_term)

    initial_score = current_score
    for _ in range(max_rounds):
        if current_score >= 1.0:
            break

        user_prompt = simplify_prompt_builder(target_term, current_text)
        raw_result = generate_text(
            model=model,
            prompt=user_prompt,
        )

        simplified = extract_first_tag(raw_result, "simplified")
        if simplified is None:
            break

        simplified = simplified.strip()
        if not simplified or simplified == current_text:
            break

        new_score = calculate_sentence_familiarity(
            session, learner_id, simplified
        )

        simplified_stems = get_lenient_stems(simplified)
        if mode == "explanation":
            # target_term KHÔNG ĐƯỢC LÀ tập con của simplified_stems
            term_condition = not target_stems.issubset(simplified_stems)
        else:
            # target_term BẮT BUỘC LÀ tập con của simplified_stems
            term_condition = target_stems.issubset(simplified_stems)

        # Keep only if it actually improves familiarity.
        if new_score > current_score and term_condition:
            current_text = simplified
            current_score = new_score
        else:
            break

    return current_text, SimplificationMetric(
        before_score=initial_score,
        after_score=current_score,
    )


class ExplanationEvaluationMetric(BaseModel):
    familiarity_before: float
    familiarity_after: float
    familiarity_improvement: float


def generate_vocab_item_for_learner(
    *,
    session: Session,
    learner_id: int,
    target_term: str,
    model: str = "gemma3:1b",
    max_simplification_rounds: int = 2,
) -> tuple[ExplanationResponse, ExplanationEvaluationMetric]:
    """
    Full pipeline:
    1. Generate explanation + examples with the LLM.
    2. Parse the tagged output.
    3. Score explanation and examples.
    4. Simplify explanation/examples if the score is not 1.0.
    5. Keep the simplified version only if it improves the score.
    """
    # Inside generate_vocab_item_for_learner:
    cleaned_word, is_english = normalize_target_term(target_term)
    if not is_english:
        raise RequestException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            debug_message=(
                f"Target term '{target_term}' is not a valid English word."
            ),
            error_code=ErrorCode.INVALID_EXPLANATION_RESPONSE,
        )

    # Now cleaned_word is a string, not a tuple
    user_prompt = build_vocab_prompts(cleaned_word)

    raw_result = generate_text(
        model=model,
        prompt=user_prompt,
    )
    print(f"{raw_result=}")

    item = parse_vocab_response(raw_text=raw_result)

    print("refine explanation")
    # Refine explanation
    item.explanation, explanation_metric = simplify_until_better(
        session=session,
        learner_id=learner_id,
        model=model,
        target_term=target_term,
        text=item.explanation,
        simplify_prompt_builder=build_explanation_simplify_prompts,
        mode="explanation",
        max_rounds=max_simplification_rounds,
    )

    print("refine example")
    # Refine each example independently
    refined_examples: list[str] = []
    example_metrics = []
    for example in item.examples:
        refined_example, example_metric = simplify_until_better(
            session=session,
            learner_id=learner_id,
            model=model,
            target_term=target_term,
            text=example,
            simplify_prompt_builder=build_example_simplify_prompts,
            mode="example",
            max_rounds=max_simplification_rounds,
        )
        refined_examples.append(refined_example)
        example_metrics.append(example_metric)

    item.examples = refined_examples

    # metrics
    before_scores = [
        explanation_metric.before_score,
    ]

    after_scores = [
        explanation_metric.after_score,
    ]
    for example_metric in example_metrics:
        before_scores.append(example_metric.before_score)
        after_scores.append(example_metric.after_score)
    overall_before = sum(before_scores) / len(before_scores)
    overall_after = sum(after_scores) / len(after_scores)

    evaluation_metric = ExplanationEvaluationMetric(
        familiarity_before=overall_before,
        familiarity_after=overall_after,
        familiarity_improvement=(overall_after - overall_before),
    )
    return item, evaluation_metric


def validate_explanation_response(
    response: ExplanationResponse,
) -> None:
    """
    Validate ExplanationResponse rules.

    Rules:
    - explanation MUST NOT contain target term
    - every example MUST contain target term

    Raises:
        RequestException
    """

    if not is_valid_english(response.target_term):
        raise RequestException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            debug_message=(
                f"Target term '{response.target_term}' "
                "is not a valid English word."
            ),
            error_code=ErrorCode.INVALID_EXPLANATION_RESPONSE,
        )

    target_stems = get_lenient_stems(response.target_term)

    if not target_stems:
        raise RequestException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            debug_message=(
                f"Target term '{response.target_term}' has no valid stems."
            ),
        )

    #
    # Validate explanation
    #

    explanation_stems = get_lenient_stems(response.explanation)

    explanation_overlap = target_stems & explanation_stems

    if explanation_overlap:
        raise RequestException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            debug_message=(
                "Explanation contains forbidden target term stems: "
                f"{sorted(explanation_overlap)}"
            ),
        )

    #
    # Validate examples
    #

    for i, example in enumerate(response.examples):
        example_stems = get_lenient_stems(example)

        if not target_stems.issubset(example_stems):
            print(f"{target_stems=}")
            print(f"{example_stems=}")
            raise RequestException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                debug_message=(
                    f"Example at index {i} does not fully contain "
                    f"target term '{response.target_term}': {example}"
                ),
            )
