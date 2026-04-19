# Plan: `read` and `write` actions

Concrete actions under `BaseAction`; `params` is the object inside `ActionParam` (LLM JSON). Each subclass implements `validate_param` against the schema below; invalid payloads → `ActionValidationError`.

---

## `read`

**Behavior:** Read file contents at `path` (text). Optional bounds to avoid huge reads.

**Param schema (validation):**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["path"],
  "properties": {
    "path": { "type": "string", "minLength": 1 },
    "encoding": { "type": "string", "default": "utf-8" },
    "max_bytes": { "type": "integer", "minimum": 1, "maximum": 1048576 }
  }
}
```

- `path`: filesystem path to read.
- `encoding`: text decoding (default `utf-8`).
- `max_bytes`: optional cap; omit for implementation default or full read per product limits.

---

## `write`

**Behavior:** Write `content` to `path`. Support create-parent-dirs and append vs overwrite.

**Param schema (validation):**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["path", "content"],
  "properties": {
    "path": { "type": "string", "minLength": 1 },
    "content": { "type": "string" },
    "mode": { "type": "string", "enum": ["write", "append"], "default": "write" },
    "encoding": { "type": "string", "default": "utf-8" },
    "create_parents": { "type": "boolean", "default": true }
  }
}
```

- `path`: target file path.
- `content`: full text to write.
- `mode`: `write` truncates/creates; `append` appends.
- `encoding`: text encoding for bytes on disk.
- `create_parents`: if true, ensure parent directories exist before write.

---

## Implementation notes

- Class names: e.g. `ReadAction`, `WriteAction`; `name`: `"read"` / `"write"`.
- Validate in `validate_param` using the same rules as the schemas (library or hand checks).
- `_execute_impl`: perform I/O; map OS errors to `ActionError` as appropriate.
