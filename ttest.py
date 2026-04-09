import json

data = {
    "native_text": "Chào buổi sáng",
    "target_text": "Good morning",
    "is_public": True,
    "collection_name": "My Daily English",
    "group_name": "Greetings",
    "brick_metadata": {
        "unit_type": "sentence",
        "structure": "simple",
        "function": "declarative",
        "grammar_points": [{"grammar_point": "present_simple"}],
    },
}


# Generate the string to paste into Swagger
json_string = json.dumps(data, ensure_ascii=False)
print(json_string)
