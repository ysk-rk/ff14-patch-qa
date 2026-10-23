"""パッチノート Q&A の API。"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.rag import LLMUnavailableError, answer

app = FastAPI(title="FF14 Patch Notes Q&A")


class AskRequest(BaseModel):
    question: str


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    try:
        return answer(req.question)
    except LLMUnavailableError as e:
        raise HTTPException(
            status_code=503,
            detail=f"AIが混雑しています。少し待ってから試してください。（{e}）",
        )