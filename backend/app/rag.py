"""検索したチャンクを Gemini に渡して、出典付きの回答を作る。"""

import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import errors
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")

# scripts/build_index.py と同じ値にする
DB_DIR = ROOT / "data" / "index"
COLLECTION = "patch_notes"
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
QUERY_PREFIX = "query: "

# 無料枠で使える Gemini のモデル。先頭から順に試し、混雑していたら次のモデルを使う
LLM_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]

# 混雑や回数制限など、別のモデルなら通る可能性があるエラーのコード
RETRYABLE_CODES = {429, 500, 503}

# 検索の順位がまだ不安定なので、多めに取って AI に渡す
TOP_K = 8

PROMPT = """あなたは FINAL FANTASY XIV のパッチノートに詳しいアシスタントです。
以下の「資料」だけを使って、質問に日本語で答えてください。

ルール:
- 資料に書かれていないことは答えず、「パッチノートからは分かりませんでした」と答える
- 同じ項目が複数のパッチで変更されている場合は、パッチ番号が一番新しいものを今の情報として答える
- PvE（通常のバトル）と PvP（見出しに「PvP」「フロントライン」などがあるもの）を区別する。質問に PvP と書かれていなければ PvE として答える
- 答えの根拠にしたパッチ番号を必ず書く

資料:
{context}

質問: {question}
"""

embedder = SentenceTransformer(EMBEDDING_MODEL)
collection = chromadb.PersistentClient(path=str(DB_DIR)).get_collection(COLLECTION)
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


class LLMUnavailableError(Exception):
    """すべてのモデルが混雑などで使えなかったときのエラー。"""


def search(question: str) -> list[dict]:
    """質問に近いチャンクを TOP_K 件取り、パッチの古い順に並べて返す。"""
    embedding = embedder.encode(QUERY_PREFIX + question, normalize_embeddings=True)
    result = collection.query(
        query_embeddings=[embedding.tolist()],
        n_results=TOP_K,
        include=["documents", "metadatas", "distances"],
    )
    hits = [
        {"text": doc, **meta, "score": 1 - dist}
        for doc, meta, dist in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0]
        )
    ]
    # 古い順に並べると、資料の中で変更の流れが追いやすくなる
    return sorted(hits, key=lambda h: h["order"])


def generate(prompt: str, models: list[str] | None = None) -> tuple[str, str]:
    """models（省略時は LLM_MODELS）を先頭から順に試し、(回答, 使ったモデル名) を返す。"""
    failures = []
    for model in models or LLM_MODELS:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            return response.text, model
        except errors.APIError as e:
            if e.code not in RETRYABLE_CODES:
                raise
            failures.append(f"{model}: {e.code}")
    raise LLMUnavailableError("、".join(failures))


def answer(question: str, models: list[str] | None = None) -> dict:
    hits = search(question)
    context = "\n\n---\n\n".join(hit["text"] for hit in hits)

    text, model = generate(PROMPT.format(context=context, question=question), models)

    return {
        "answer": text,
        "model": model,
        "sources": [
            {
                "version": hit["version"],
                "headings": hit["headings"],
                "url": hit["url"],
                "score": round(hit["score"], 3),
            }
            for hit in hits
        ],
    }