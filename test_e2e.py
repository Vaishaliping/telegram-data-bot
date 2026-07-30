import json
from app.llm import ask_llm, extract_json
from app.logger import RunLogger

# Simulate the exact grading question
question = 'Which state has the highest maternal mortality rate based on MOSPI data? Reply with ONLY this JSON object and nothing else: {"answer": {"state": "<state name>"}, "log_url": "<public wget-able URL to your agent\'s JSONL log>"}'

run_log = RunLogger(chat_id=12345)
run_log.log("user", question)

msgs = [{"role": "user", "content": question}]
llm_reply = ask_llm(msgs)
run_log.log("assistant", llm_reply)

print("LLM reply:", llm_reply)

answer_obj = extract_json(llm_reply)
print("Extracted JSON:", answer_obj)

# Upload to Gist
log_url = run_log.upload_gist()
print("Log URL:", log_url)

# Final reply the bot would send
final = json.dumps({"answer": answer_obj, "log_url": log_url}, separators=(",", ":"))
print("\nFinal bot reply:")
print(final)
