"""FastAPI wrapper around chatbot.py."""
import json
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import chatbot


def _warm():
    try:
        chatbot.get_vectorstore()
        print("Index ready.")
    except Exception as e:
        print(f"Index not ready yet: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_warm, daemon=True).start()
    yield


app = FastAPI(title="RAG API", lifespan=lifespan)


class ChatRequest(BaseModel):
    question: str
    k: int = 5
    threshold: float = 0.2


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest):
    """Streams NDJSON events: one 'sources' event, then many 'token' events."""
    def gen():
        try:
            docs = chatbot.retrieve(req.question, req.k, req.threshold)
            sources = [
                {
                    "file": os.path.basename(d.metadata.get("source", "unknown")),
                    "text": d.page_content[:300],
                }
                for d in docs
            ]
            yield json.dumps({"type": "sources", "sources": sources}) + "\n"
            for token in chatbot.stream_answer(req.question, docs):
                yield json.dumps({"type": "token", "text": token}) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.post("/reindex")
def reindex():
    try:
        chatbot.reindex()
        return {"status": "reindexed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
