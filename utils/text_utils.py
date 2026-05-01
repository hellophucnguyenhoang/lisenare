import re


def normalize_currency(text: str) -> str:
    # "$5" -> "5 dollars"
    return re.sub(r"\$(\d+)", r"\1 dollars", text)


def extract_number_sequences(text: str):
    """
    Extract sequences like:
    - 6.30
    - 6:30
    - 630
    """
    return re.findall(r"\d+(?:[.:]\d+)?", text)


def to_digit_signature(num_str: str) -> str:
    """
    Convert:
    - "6.30" -> "630"
    - "6:30" -> "630"
    - "630"  -> "630"
    """
    return re.sub(r"[^\d]", "", num_str)


def replace_numbers_by_teacher(teacher_text: str, learner_text: str) -> str:
    teacher_nums = extract_number_sequences(teacher_text)

    for t_num in teacher_nums:
        t_sig = to_digit_signature(t_num)

        # Find matching number in learner text
        matches = re.finditer(r"\d+(?:[.:]\d+)?", learner_text)

        for match in matches:
            l_num = match.group()
            l_sig = to_digit_signature(l_num)

            # Match exact digit order
            if l_sig == t_sig:
                # Replace ONLY this occurrence
                learner_text = (
                    learner_text[: match.start()]
                    + t_num
                    + learner_text[match.end() :]
                )
                break  # move to next teacher number

    return learner_text


def normalize_for_pronunciation(teacher_text: str, learner_text: str):
    # --- Step 1: normalize currency ---
    teacher_text = normalize_currency(teacher_text)
    learner_text = normalize_currency(learner_text)

    # --- Step 2: align numbers ---
    learner_text = replace_numbers_by_teacher(teacher_text, learner_text)

    return teacher_text, learner_text
