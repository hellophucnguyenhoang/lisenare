from typing import Any

from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def model_validate(
        cls,
        obj: Any,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: Any | None = None,
        update: dict[str, Any] | None = None,
    ):
        if update:
            if isinstance(obj, dict):
                obj = {**obj, **update}
            else:

                class _Proxy:
                    def __init__(self, target: Any, overrides: dict[str, Any]):
                        self._target = target
                        self._overrides = overrides

                    def __getattr__(self, name: str) -> Any:
                        if name in self._overrides:
                            return self._overrides[name]
                        return getattr(self._target, name)

                obj = _Proxy(obj, update)

        return super().model_validate(
            obj,
            strict=strict,
            from_attributes=from_attributes,
            context=context,
        )
