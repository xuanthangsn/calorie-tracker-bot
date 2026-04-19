Single generic type **`ActionParam`** only (no abstract base, no extra param subclasses).

- **`params`**: object holding the raw payload (e.g. mapping from LLM JSON).
- **`to_dict()`**: serialize that payload for logs/tracing.

Each **concrete `BaseAction`** enforces its own schema: e.g. abstract **`validate_param(params: ActionParam) -> None`** runs **before** the instance finishes initializing (or as the first step of `__init__`), raises `ActionValidationError` if the payload does not match that action’s predefined schema.