### This file defines the high level design of the agent

- **Task:**
  - a task requested by user
  - a finite number of react cycles until the agent completes the task and responds to the user
- **ReAct loop:**
  1. *Task trigger*: user requests a task, the request is sent to LLM
  2. *LLM reasoning*: LLM receives the request, produces THOUGHT + ACTION TO TAKE
  3. *Execute action*: the app receives THOUGHT + ACTION TO TAKE from LLM, executing the action, get the output from action executing
  4. *Send action executing result + context to LLM*: the app sends output from previous action executing + context about current reAct loop to LLM
  5. *Repeat cycle*: go back to 2, until LLM decides it has completed the task
  6. *Task accomplished*: the app receives LLM response that indicates it has completed the task, response to user
- **ReAct cycle:** step 2 + 3 + 4 + 5 inside reAct loop
- **Tool call/action call**
  1. write to file
  2. ask user for further clarification
    ...
- **LLM response in step 2**:
  - LLM response is a strictly structured json includes 2 main fields:
    - thought: the thought it produce in reponse to previous client message
    - action: a json object represent the action to take

