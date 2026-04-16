- **Task:** a finite number of react cycles until the agent completes the task and responds to the user

- **ReAct loop:**
    1. *Task trigger*: user requests a task, the request is sent to LLM
    2. *LLM reasoning*: LLM receives the request, produces THOUGHT + ACTION TO TAKE
    3. *Execute action*: agent motor receives THOUGHT + ACTION TO TAKE from LLM, executing the action, get the output from action executing
    4. *Send action executing result + context to LLM*: agent motor sends output from previous action executing + context about current reAct loop to LLM
    5. *Repeat cycle*: go back to 2, until LLM decides it has completed the task
    6. *Task accomplished*: agent motor receives LLM response that indicates it has completed the task, response to user
    
- **ReAct cycle:** step 2 + 3 + 4 + 5 inside reAct loop

- **Tool call/action call**
