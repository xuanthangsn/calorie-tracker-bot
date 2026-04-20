# LLM response envelope — ReAct cycle

Models the **expected LLM output on every turn** inside the Task ReAct loop (design: *LLM reasoning* step). The client parses this JSON, builds the matching **Action**, runs it, and feeds the observation back until a terminal action ends the task.

---

## Top-level shape (strict)

Two keys only; no other top-level fields.

| Field | Type | Purpose |
|--------|------|---------|
| `thought` | string | Reasoning in response to the latest client message (user request + prior observations / `task_context`). |
| `action` | object | What to run this cycle; maps to `BaseAction`: `name` + `params` inside `ActionParam`. |

Illustrative JSON:

```json
{
  "thought": "…",
  "action": {
    "name": "<registered_action_name>",
    "params": { }
  }
}
```

---

## `action` object

| Field | Type | Purpose |
|--------|------|---------|
| `name` | string | Action identifier; must match a registered concrete action (e.g. tool or domain action). |
| `params` | object | Raw payload for that action; validated by `validate_param` → `ActionValidationError` if invalid. |

- `params` is the object stored in **`ActionParam`** (see **action_param.md**).
- Each concrete action defines its own required keys and types under `params`.

---

## Terminal cycle (task finished)

The envelope does **not** change. Completion is indicated by choosing the **`name` / `params`** pair that the runtime defines as **final reply** (e.g. send user-visible text and stop the loop). The Task then sets **`final_response`**, **`status: completed`**, and does not start another LLM cycle—per **task_component.md** and **agent_system_design.md** step 6.

---

## Errors (conceptual)

| Failure | Typical handling |
|---------|------------------|
| Invalid JSON, missing `thought` or `action`, missing `action.name` | Parse / Task-level error before action construction. |
| Unknown `action.name` | Task-level or dispatch error. |
| `params` fails schema for that action | `ActionValidationError`. |
| Execution failure | `ActionError` (or subclass); result still reported per ReAct step 4. |

---

## Implementation Constraint

- Use only gemini api as LLM provider
- Use google-genai package to make API call
- Use gemini-3-flash-preview for affordable cost, speed and intelligence

---

## Enforcing structured output (implementation strategy)

**Goal:** Every model turn must deserialize to the envelope above without ad-hoc string parsing.

**3 layers of enforcement:**
- **Layer 1. Enforce the LLM response generic structure**: 
    - enforce only the **envelope** (`thought` + `action` with `name` + open `params`). 
    - this is done by leveraging google-genai functionality for structured output (provide a schema at API calling)
- **Layer 2: Enforce the structured params for each specific action in LLM response**:
    - what goes *inside* `params` for each action is **not** modeled in one giant Gemini schema when making the API request; 
    - we instruct the LLM how it should construct the params for a specifc action by giving concrete instruction in the prompt, give examples,...
- **Layer 3: Enforce the structured params for a specific action in LLM response using retry in ReAct loop**
    - when LLM makes mistake by responding an invalid params for an action, in the next ReAct cycle, the app will give LLM context about its past mistake, and told LLM to make the correction
    


**LLM structured output enforcement workflow:**

1. **send API request to LLM with JSON schema enforcement for the only the envelop** 
  - create a JSON schema (using pydantic model) for the structure of the envelop
  - using google-genai api to enforce the structure of the response to follow the evelop json schema
  -  Keep **`params` a generic object** in the API schema; do **not** fold every tool’s param shape into that schema (too large, brittle).

2. **Parse and validate the response** 
  - throw error and stop the current task if: the reponse does not conform the envelop schema; action is not found

3. **Registry + `validate_param`** 
  - resolve `action.name` against a **registry**. 
  - try to initialize the action based on parsed param, if _validate_params failed, initiating new ReAct cycle indicating the errors to LLM, and ask it to return a correct response

4. **How the LLM knows `params`** 
  - supply a **tool catalog** in system/developer context: for each registered `name`, document required keys, types, and meaning (short table or mini JSON Schema per action). Prefer deriving or syncing this text from the specific action param schema defined in each action file, so there is **one source of truth** in code; the prompt is a **projection** for the model, not a second schema language. Optionally narrow what you inject when context allows (e.g. only a subset of actions).

5. **ReAct closes semantic gaps** 
  - wrong or incomplete `params` are normal. **`_validate_param`** failures become **observations** in the next cycle (“field X missing”, “invalid enum”, …). The model corrects `params` or changes `action.name` without unbounded blind retries on the same turn.


**Stack in one line:** Gemini + `google-genai` enforce the **envelope**; the **registry**, **tool catalog in prompt**, and **`_validate_param` + ReAct** enforce correct **`params`** — aligned with **action_component.md** / **action_param.md**.

---

## System prompt strategy (for ReAct turns)

```text
You are a calorie-tracking task agent operating in ReAct cycles.
For each turn:
1) Analyze the latest user request + prior observation.
2) Write `thought` describing what you should do next.
3) Choose exactly one action from the allowed action list.
4) Build `action.params` that exactly matches that chosen action schema.
5) If the task is finished, choose `final_answer`.

You must return exactly one JSON object (no markdown, no code fences) that follows this schema:
{
  "type": "object",
  "additionalProperties": false,
  "required": ["thought", "action"],
  "properties": {
    "thought": { "type": "string", "minLength": 1 },
    "action": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "params"],
      "properties": {
        "name": { "type": "string", "enum": ["read", "write", "final_answer"] },
        "params": { "type": "object" }
      }
    }
  }
}

Allowed actions and params:
- read: params = { path: non-empty string }
- write: params = { path: non-empty string, content: string }
- final_answer: params = { message: non-empty string }

Rules:
- Choose only one action per response.
- Params must match the chosen action schema exactly (no extra keys).
- Use final_answer only when the task is done, and put the final user-facing text in `params.message`.
- If previous observation reports validation error, correct it in this turn.
```
