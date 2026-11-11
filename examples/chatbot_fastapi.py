"""Example: a chatbot endpoint protected by Kalkan.

    pip install fastapi uvicorn openai ./clients/python
    KALKAN_URL=http://localhost:8088 KALKAN_KEY=... uvicorn examples.chatbot_fastapi:app --port 9000
"""
import os

from fastapi import FastAPI
from pydantic import BaseModel

from kalkan_client import AsyncKalkanClient

kalkan = AsyncKalkanClient(os.getenv("KALKAN_URL", "http://localhost:8088"), os.getenv("KALKAN_KEY"),
                           fail_mode="closed")
app = FastAPI()
REFUSAL = "Bu isteği güvenlik nedeniyle işleyemiyorum. Sorunuzu farklı şekilde sorabilir misiniz?"


class Chat(BaseModel):
    message: str
    conversation_id: str | None = None


async def call_llm(message: str) -> str:  # replace with your LLM call
    return f"(LLM answer to: {message})"


@app.post("/chat")
async def chat(req: Chat):
    verdict = await kalkan.check(req.message, conversation_id=req.conversation_id)
    if verdict.decision == "block":
        return {"reply": REFUSAL, "kalkan": verdict.request_id}
    reply = await call_llm(req.message)
    # "flag": answered, but worth logging / showing to a human reviewer
    return {"reply": reply, "kalkan": verdict.request_id, "flagged": verdict.decision == "flag"}
