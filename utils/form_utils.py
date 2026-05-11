from typing import TypeVar

from fastapi import Form, HTTPException, status
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class JsonFormBody:
    def __init__(self, model_class: type[T], field_name: str = "data"):
        self.model_class = model_class
        self.field_name = field_name

    def __call__(self, json_data: str = Form(...)) -> T:
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
