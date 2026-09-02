import json
from typing import TypeVar

from fastapi import Form, HTTPException, status
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class JsonFormBody:
    """
    Parse a string inside a form field into a Pydantic model.
    """

    def __init__(self, model_class: type[T], field_name: str = "data"):
        self.model_class = model_class
        self.field_name = field_name

    def __call__(
        self,
        json_data: str = Form(
            description="A JSON string matching the specified schema."
        ),
    ) -> T:
        try:
            return self.model_class.model_validate_json(json_data)
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=e.errors(),
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON format for {self.model_class.__name__}",
            )


def get_model_example_string(model_class: type[BaseModel]) -> str:
    # 1. Get the Pydantic schema dictionary
    schema = model_class.model_json_schema()
    properties = schema.get("properties", {})

    mock_payload = {}

    # 2. Loop through fields to extract default values or type placeholders
    for field_name, field_info in properties.items():
        if "default" in field_info:
            mock_payload[field_name] = field_info["default"]
        elif "examples" in field_info and field_info["examples"]:
            mock_payload[field_name] = field_info["examples"][0]
        else:
            # Fallback to structural types based on OpenAPI types
            field_type = field_info.get("type")
            if field_type == "string":
                mock_payload[field_name] = "string"
            elif field_type in ("integer", "number"):
                mock_payload[field_name] = 0
            elif field_type == "boolean":
                mock_payload[field_name] = False
            elif field_type == "array":
                mock_payload[field_name] = []
            elif field_type == "object":
                mock_payload[field_name] = {}
            else:
                mock_payload[field_name] = "value"

    # 3. Serialize back into a nicely formatted string
    return json.dumps(mock_payload, indent=2)
