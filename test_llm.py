from app.llm import ask_llm, extract_json
msgs = [{"role": "user", "content": 'Which state has the highest maternal mortality rate based on MOSPI data? Reply with ONLY this JSON object: {"state": "<state name>"}'}]
reply = ask_llm(msgs)
print("LLM reply:", reply)
obj = extract_json(reply)
print("Extracted JSON:", obj)