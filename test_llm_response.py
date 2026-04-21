
from __future__ import annotations

import json
import os
import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from google import genai
from google.genai import types
import config



MODEL_NAME = "gemini-3-flash-preview"


SYSTEM_PROMPT = """You are an autonomous, logical AI assistant capable of solving complex problems by using tools. You operate in a continuous Thought -> Action -> Observation loop. 
You will be provided with the User's Original Request, and a history of your previous thoughts, actions, and the system's observations.
Your task is to give out your thought on what to do next, and choose exactly 1 tool from the provided list of tools.
Return your output as a JSON object strictly following the JSON SCHEMA defined for the tool that you choose.

### KNOWLEDGE MAP & FILE SYSTEM
You have access to a local file system to store and retrieve information. When you need specific context, consult the following file index to know which file to read or modify.
- `user.md`: Read this file if you need to know about the user's information, preferences, or profile.

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
    "path": "string <target file path>"
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
"""


def main() -> None:
    api_key = config.GEMINI_API_KEY
    if not api_key:
        print("GEMINI_API_KEY is required.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)


    mock_failed_read = "{\"tool_executed\": \"read\", \"status\": \"failed\", \"output\": \"Failed to read, no such file\" }"
    mock_success_read = "{\"tool_executed\": \"read\", \"status\": \"success\", \"output\": \"Hi, my name is Tran Xuan Thang, I'm a huge fan of Cristiano Ronaldo, the Worlcup 2026 is coming and I can't wait to watch him play. I'm really into fitness and I want to build a lean, muscular body\"}"
    contents = [
        {"role": "user", "parts": [{"text": "what is my favourite hobby?"}]},
        {"role": "model", "parts": [{"text": "{\"action\":\"read\",\"thought\":\"The user is asking about their favorite hobby. I need to check the user's profile information stored in 'user.md' to find this answer.\",\"params\":{\"path\":\"user.md\"}}"}]},
        {"role": "user", "parts": [{"text": f"OBSERVATION: {mock_failed_read}"}]},
    ]

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.0,
        ),
    )

    raw_text = (response.text or "").strip()
    if not raw_text:
        print("FAIL: Empty response text from model.")
        sys.exit(2)

    print(raw_text)

if __name__ == "__main__":
    main()
