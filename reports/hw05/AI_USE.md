AI_USE.md – HW5

# DATA260 HW5 AI Use Disclosure

## 1. How AI assistance was used

I used an AI assistant to help understand the HW5 requirements, plan the
software architecture, extend the existing HW4 FastAPI and MySQL project,
create Redux Toolkit files, and build the MCP servers. The assistant also
helped create validation schemas, CRUD functions, retry logic, fault
injection experiments, the `execute_tool` gateway, offline tests, and the
Ollama agent loop.

I used my own existing HW4 repository, database, credentials, local
environment, and assigned domain data. I manually created the files in my
repository, executed the commands, tested the application, reviewed the
outputs, and captured the required evidence screenshots.

## 2. Incorrect or unsuitable AI-produced output

The initial version of `agent.py` reused the variable name `result` for both
a tool response and the final agent summary. This caused an error when the
program attempted to access:

```python
result["steps"]


