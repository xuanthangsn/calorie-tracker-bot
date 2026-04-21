# LLM response — action-centric envelope

This document describes an **alternative** structured-response shape for ReAct turns. It does **not** replace `llm_react_response.md`; that file remains the reference for the `thought` + nested `action` envelope. Action names and param semantics for concrete tools still follow **`implemented_actions.md`**.

---

## Top-level shape (strict)

Exactly three top-level keys: `action`, `thought`, `params`. No other top-level fields.

| Field | Type | Purpose |
|--------|------|---------|
| `action` | string | name of the chosen action |
| `thought` | string | reasoning for choosing this action |
| `params` | object | param of the action |

Illustrative JSON:

```json
{
  "action": "<action_name>",
  "thought": "<reason for choosing this action>",
  "params": { }
}
```

- **`params` per action** must match the schemas documented under **`read`**, **`write`**, and **`final_answer`** in **implemented_actions.md**
---

## Two layers of enforcement

### Layer 1 — Schemas in the prompt

- Inject into **system/developer** context the **full JSON contract** for each action the model must satisfy:
- another approach is using tool calling api of google-genai (second option, not employed for now)

### Layer 2 — Retry + remind (ReAct)

- On **`ActionValidationError`**, append an **observation** to the next client message: what failed, which field, expected shape (short, safe text).
- **Remind** the model of the correct `params` schema for the action it chose (or allow switching `action` if appropriate).
- **Bounded retries** at the Task level (finite `max_cycle`); no infinite same-turn loops.

---

## Runtime parsing (conceptual)

1. Parse JSON; ensure exactly `action`, `thought`, `params`.
2. Resolve `action` against the **registry**; unknown name → Task-level error (or terminal failure per product rules).
3. Build **`ActionParam(params)`** and construct the matching action; **`thought`** is not part of `ActionParam` — use it for logging/trace only and serve as context for the text ReAct cycle.
4. Execute; feed result + context into the next cycle unless `final_answer` completes the task.

## How to inject the current task context to each request
- task context is the context of past ReAct cycles of current task: **LLM reasoning + Tool call + Observation**
- this can be treated as conversational history between LLM and user
- inject this using the built-in conversatinal history capability of google-genai, for example:
```code
chat_history = [
    {"role": "user", "parts": [{"text": "Read the user.md file."}]},
    {"role": "model", "parts": [{"text": '{"action": "read", ...}'}]},
    {"role": "user", "parts": [{"text": "OBSERVATION: ..."}]}
]

response = client.models.generate_content(
    model='gemini-3-flash-preview',
    contents=chat_history,
    config=types.GenerateContentConfig(
        system_instruction=system_prompt_text, # <--- Injected here
        response_mime_type="application/json",
        temperature=0.0
    )
)
```
- format of observation (or tool calling output) before injecting to chat history:
```text
OBSERVATION: 
{
  "tool_executed": "read",
  "status": "success,
  "output": "..."
}
```
- format of LLM reasoning + tool selection before injecting to chat history: literal json response that LLM return from previous ReAct cycle
```text
{
  "action": "read",
  "thought": "Since 'user.md' was not found, I will check 'task_history.md' to see if the user's favorite hobby was mentioned in previous interactions.",
  "params": {
    "path": "task_history.md"
  }
}
```


## System prompt strategy

I have tested and this prompt seem to f**king work, brooo!!!

```text
You are an autonomous, logical AI assistant capable of solving complex problems by using tools. You operate in a continuous Thought -> Action -> Observation loop. 
You will be provided with the User's Original Request, and a history of your previous thoughts, actions, and the system's observations.
Your task is to give out your thought on what to do next, and choose exactly 1 tool from the provided list of tools.
Return your output as a JSON object strictly following the JSON SCHEMA defined for the tool that you choose.

### KNOWLEDGE MAP & FILE SYSTEM
You have access to a local file system to store and retrieve information. When you need specific context, consult the following file index to know which file to read or modify.
- `user.md`: Read this file if you need to know about the user's information, preferences, or profile.
- `task_history.md`: Read this file to understand previous tasks completed in past sessions.
- `scratchpad.md`: Write to this file if you need a place to temporarily store intermediate calculations or notes.

### AVAILABLE TOOLS
1. `read`: use this tool when you want to read something from the local file system
2. `write`: use this tool when you want to write something to the local file system
3. `final_answer`: use this tool when you want to formulate the final answer to user

## JSON SCHEMA FOR EACH ACTION
# Schema for `read`:
{
  "action": "read",
  "thought": "string <your step-by-step reasoning for choosing this tool>",
  "params": {
    "path": "string <filesystem path to read, MUST be inside the `memory/` folder>"
  }
}

# Schema for `write`:
{
  "action": "write",
  "thought": "string <your step-by-step reasoning for choosing this tool>",
  "params": {
    "path": "string <target file path>",
    "content": "string <full text to write>"
  }
}

# Schema for `final_answer`:
{
  "action": "final_answer",
  "thought": "string <your step-by-step reasoning for choosing this tool>",
  "params": {
    "message": "string <final response text to send to the user>"
  }
}

### STRICT FORMATTING RULES
1. You must respond ONLY with valid JSON.
2. Do not include any conversational text before or after the JSON output.
3. Do not wrap the JSON in markdown code blocks (e.g., ```json ... ```). Just return the raw JSON string.
4. Ensure all keys are enclosed in double quotes.
5. If a piece of information is missing from the text, use `null` instead of making something up.
```