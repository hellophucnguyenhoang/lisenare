import re


def clean_tag(name: str) -> str:
    """Clean a tag by lowering all and removing spaces and any strange characters beyond a-z and 0-9."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def clean_tags(tags: list[str]) -> list[str]:
    """Clean a list of tags by lowering all, removing spaces and strange characters beyond a-z and 0-9.

    Also splits any comma-separated strings within elements, deduplicating and removing empty strings.
    """
    cleaned_tags: list[str] = []
    seen: set[str] = set()
    for name in tags:
        for part in name.split(","):
            cleaned = clean_tag(part)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                cleaned_tags.append(cleaned)
    return cleaned_tags
