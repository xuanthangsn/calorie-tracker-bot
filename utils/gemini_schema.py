"""Pydantic JSON Schema → google.genai.types.Schema for tool parameters."""
from __future__ import annotations

from typing import Any, Type

import jsonref
from google.genai.types import JSONSchema, Schema
from pydantic import BaseModel


def _const_to_enum(obj: Any) -> Any:
    """Gemini JSONSchema rejects JSON Schema `const`; use single-value `enum`."""
    if isinstance(obj, dict):
        if "const" in obj and isinstance(obj["const"], (str, int, float, bool)):
            d = {k: _const_to_enum(v) for k, v in obj.items() if k != "const"}
            d["enum"] = [obj["const"]]
            return d
        return {k: _const_to_enum(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_const_to_enum(x) for x in obj]
    return obj


def pydantic_model_to_gemini_parameters(model: Type[BaseModel]) -> Schema:
    """
    Build Gemini `Schema` for `FunctionDeclaration.parameters` from a Pydantic model.

    Steps: `model_json_schema` → jsonref inline → strip `$defs` → const→enum →
    `JSONSchema` → `Schema.from_json_schema`.
    """
    raw: dict[str, Any] = model.model_json_schema()
    raw = jsonref.replace_refs(raw, lazy_load=False)  # type: ignore[assignment]
    raw.pop("$defs", None)
    raw = _const_to_enum(raw)
    js = JSONSchema.model_validate(raw)
    return Schema.from_json_schema(json_schema=js)
