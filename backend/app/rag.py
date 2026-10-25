"""検索したチャンクを Gemini に渡して、出典付きの回答を作る。"""

import os
import re
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
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

# 答えのランダムさ。0 にすると、同じ質問には毎回なるべく同じ答えを返す
TEMPERATURE = 0

# 検索の順位がまだ不安定なので、多めに取って AI に渡す
TOP_K = 8

# 質問にこれらの言葉が入っていれば PvP の質問として扱う
PVP_WORDS = re.compile(r"PvP|フロントライン|クリスタルコンフリクト")

RULES = """ルール:
- 資料に書かれていないことは答えず、「パッチノートからは分かりませんでした」と答える
- 同じ項目が複数のパッチで変更されている場合は、パッチ番号が一番新しいものを今の情報として答える
- PvE（通常のバトル）と PvP（見出しに「PvP」「フロントライン」などがあるもの）を区別する。質問に PvP と書かれていなければ PvE として答える
- 答えの根拠にしたパッチ番号を必ず書く"""

PROMPTS = {
    # v1: 最初の版。ルールだけを伝えて、すぐに答えさせる
    "v1": """あなたは FINAL FANTASY XIV のパッチノートに詳しいアシスタントです。
以下の「資料」だけを使って、質問に日本語で答えてください。

""" + RULES + """

資料:
{context}

質問: {question}
""",
    # v2: 数値の今の値を聞かれたら、変更の経緯を古い順に書き出してから答えさせる
    "v2": """あなたは FINAL FANTASY XIV のパッチノートに詳しいアシスタントです。
以下の「資料」だけを使って、質問に日本語で答えてください。

""" + RULES + """

数値の今の値（威力、減衰率、上限値など）を聞かれた場合は、次の手順で答える:
1. 質問された項目を1つに決める（例: 威力なのか、2体目以降の威力減衰率なのか）
2. 資料の中から、その項目が変わった箇所だけを、パッチの古い順に「パッチ番号: 変更前 → 変更後」の形で書き出す。1つの行に複数の変更が書かれている場合は、質問された項目の部分だけを取り出す
3. 一番新しいパッチの「変更後」の値を、今の値とする
4. 次の形で答える

【今の値】（今の値）（根拠: パッチ〇〇）
【変更の経緯】
- パッチ〇〇: 〇〇 → 〇〇

それ以外の質問には、ふつうの文章で答える。

資料:
{context}

質問: {question}
""",
}

# 画面（API）で使うプロンプト。評価で効果を確かめてから切り替える
DEFAULT_PROMPT = "v2"

embedder = SentenceTransformer(EMBEDDING_MODEL)
collection = chromadb.PersistentClient(path=str(DB_DIR)).get_collection(COLLECTION)
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


class LLMUnavailableError(Exception):
    """すべてのモデルが混雑などで使えなかったときのエラー。"""


def search(question: str) -> list[dict]:
    """質問に近いチャンクを TOP_K 件取り、パッチの古い順に並べて返す。

    PvP の質問なら PvP のチャンクだけ、それ以外なら PvP 以外のチャンクだけを検索する。
    """
    embedding = embedder.encode(QUERY_PREFIX + question, normalize_embeddings=True)
    result = collection.query(
        query_embeddings=[embedding.tolist()],
        n_results=TOP_K,
        where={"is_pvp": bool(PVP_WORDS.search(question))},
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
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=TEMPERATURE),
            )
            return response.text, model
        except errors.APIError as e:
            if e.code not in RETRYABLE_CODES:
                raise
            failures.append(f"{model}: {e.code}")
    raise LLMUnavailableError("、".join(failures))


def answer(question: str, models: list[str] | None = None, prompt: str = DEFAULT_PROMPT) -> dict:
    hits = search(question)
    context = "\n\n---\n\n".join(hit["text"] for hit in hits)

    text, model = generate(PROMPTS[prompt].format(context=context, question=question), models)

    return {
        "answer": text,
        "model": model,
        "prompt": prompt,
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