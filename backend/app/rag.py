"""検索したチャンクを Gemini に渡して、出典付きの回答を作る。"""

import json
from pathlib import Path

import chromadb
import numpy as np
from dotenv import load_dotenv
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from app.llm import LLMUnavailableError, generate  # noqa: F401（main.py と run_eval.py が rag から読み込んでいる）
from app.rules import (
    bigrams,
    choose_prompt,
    fix_current_value,
    fuse_ranks,
    is_pvp_text,
    job_names_from_headings,
    job_of,
    jobs_in,
)

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")

# scripts/build_index.py と同じ値にする
DB_DIR = ROOT / "data" / "index"
COLLECTION = "patch_notes"
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
QUERY_PREFIX = "query: "

# キーワード検索に使うチャンク（scripts/extract_chunks.py が作るもの）
CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"

# AI に渡す資料の件数
TOP_K = 8

# 検索のしかた
#   vector: 意味の近さだけで選ぶ
#   hybrid: 意味の近さとキーワードの一致の両方で選ぶ
SEARCH_MODES = ("vector", "hybrid")

# 画面（API）で使う検索のしかた。評価で効果を確かめてから切り替える
DEFAULT_SEARCH = "hybrid"

# hybrid のとき、それぞれの検索で候補にする件数
CANDIDATES = 30

# hybrid で2つの順位を合わせるときの定数（RRF でよく使われる値）
RRF_K = 60

# 質問のジョブと、資料の見出しのジョブが合うときに、hybrid の点数に足す値（0 なら足さない）
# 合わない資料は外さない（ジョブで絞り込むと、ほかの問題の資料を押し出した: q024）
JOB_BONUS = 1 / 61

RULES = """ルール:
- 資料に書かれていないことは答えず、「パッチノートからは分かりませんでした」と答える
- 同じ項目が複数のパッチで変更されている場合は、パッチ番号が一番新しいものを今の情報として答える
- PvE（通常のバトル）と PvP（見出しに「PvP」「フロントライン」などがあるもの）を区別する。質問に PvP と書かれていなければ PvE として答える
- 答えの根拠にしたパッチ番号を必ず書く"""

# 経緯の質問用のルール。RULES から2行目だけを入れ替えたもの
# （「一番新しいものを今の情報として答える」を経緯の質問にもあてはめて、
#   あとで上書きされた途中の変更を書き落とす失敗があった: t008、q021、q022）
RULES_HISTORY = """ルール:
- 資料に書かれていないことは答えず、「パッチノートからは分かりませんでした」と答える
- 同じ項目が複数のパッチで変更されている場合も、あとのパッチで上書きされた変更を省略しない。質問されたスキルや項目の変更を、パッチの古い順にすべて書く
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
    # （「何が変わった？」の質問で「分かりませんでした」と答える失敗があった）
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
    # v3: 質問の種類を AI に決めさせ、種類ごとに答え方を指示する
    # （q002 は直ったが、q009 と q011 の今の値を間違えるようになった）
    "v3": """あなたは FINAL FANTASY XIV のパッチノートに詳しいアシスタントです。
以下の「資料」だけを使って、質問に日本語で答えてください。

ルール:
- 「パッチノートからは分かりませんでした」と答えるのは、資料のどこにも、質問されたスキルや項目が出てこない場合だけにする。資料に出てくる場合は、分かる範囲で必ず答える
- 資料に書かれていないことを、推測や自分の知識で補わない
- PvE（通常のバトル）と PvP（見出しに「PvP」「フロントライン」などがあるもの）を区別する。質問に PvP と書かれていなければ PvE として答える
- 答えの根拠にしたパッチ番号を必ず書く

まず、質問が次のどれにあたるかを決める（決めた結果は書かなくてよい）。

A. 数値の今の値を聞いている（例:「今の威力は？」「上限値はいくつ？」「減衰率は？」）
B. 何が変わったか、変更の流れを聞いている（例:「何が変わった？」「どう調整された？」）
C. いつ変わったかを聞いている（例:「どのパッチ？」「いつから？」）

A の場合:
1. 質問された項目を1つに決める（例: 威力なのか、2体目以降の威力減衰率なのか）
2. 資料の中から、その項目が変わった箇所だけを、パッチの古い順に「パッチ番号: 変更前 → 変更後」の形で書き出す。1つの行に複数の変更が書かれている場合は、質問された項目の部分だけを取り出す
3. 一番新しいパッチの「変更後」の値を、今の値とする
4. 次の形で答える

【今の値】（今の値）（根拠: パッチ〇〇）
【変更の経緯】
- パッチ〇〇: 〇〇 → 〇〇

B の場合:
質問されたスキルや項目の変更を、項目を問わずすべて、パッチの古い順に次の形で書く。
- パッチ〇〇: （変更の内容）

C の場合:
変わったパッチの番号を答え、変更の内容を1文で添える。

資料:
{context}

質問: {question}
""",
    # v4: v1 のルールを、経緯の質問用（RULES_HISTORY）に入れ替えたもの
    "v4": """あなたは FINAL FANTASY XIV のパッチノートに詳しいアシスタントです。
以下の「資料」だけを使って、質問に日本語で答えてください。

""" + RULES_HISTORY + """

資料:
{context}

質問: {question}
""",
    # v5: v2 の手順の1と2に、質問されたジョブ・スキルの資料だけを使う指示を足したもの
    # （同じ「最大チャージ数」の変更が、より新しいパッチで別のジョブにあり、
    #   軽いモデルが答えるのをやめた: q018）
    "v5": """あなたは FINAL FANTASY XIV のパッチノートに詳しいアシスタントです。
以下の「資料」だけを使って、質問に日本語で答えてください。

""" + RULES + """

数値の今の値（威力、減衰率、上限値など）を聞かれた場合は、次の手順で答える:
1. 質問されたジョブとスキル、項目を1つに決める（例: 威力なのか、2体目以降の威力減衰率なのか）
2. 資料の中から、そのジョブのそのスキルの、その項目が変わった箇所だけを、パッチの古い順に「パッチ番号: 変更前 → 変更後」の形で書き出す。別のジョブや別のスキルの資料は、同じ項目（威力、最大チャージ数など）が書かれていても使わない。1つの行に複数の変更が書かれている場合は、質問された項目の部分だけを取り出す
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
    # auto: 質問の種類をコードで決めて、経緯の質問なら AUTO_HISTORY_PROMPT、それ以外なら AUTO_CURRENT_PROMPT を使う
    # （app/rules.py の choose_prompt と、下の pick_prompt を参照）
    "auto": None,
}

# 画面（API）で使うプロンプト
DEFAULT_PROMPT = "auto"

# auto で経緯の質問と判定されたときに使うプロンプト
# （choose_prompt は経緯の質問に "v1" を返す。前の結果と比べるときは "v1" に戻す）
AUTO_HISTORY_PROMPT = "v4"

# auto でそれ以外（今の値など）と判定されたときに使うプロンプト
# （choose_prompt はこの場合 "v2" を返す。前の結果と比べるときは "v2" に戻す）
AUTO_CURRENT_PROMPT = "v5"


def pick_prompt(question: str, prompt: str = DEFAULT_PROMPT) -> str:
    """実際に使うプロンプトの名前を返す。auto のときは、質問の種類で選ぶ。"""
    if prompt != "auto":
        return prompt
    return AUTO_HISTORY_PROMPT if choose_prompt(question) == "v1" else AUTO_CURRENT_PROMPT


def is_pvp_chunk(chunk: dict) -> bool:
    return is_pvp_text(" > ".join(chunk["headings"]))


def build_keyword_indexes() -> dict[bool, tuple[list[str], BM25Okapi]]:
    """PvP と PvP 以外に分けて、キーワード検索（BM25）の索引を作る。"""
    chunks = [json.loads(line) for line in CHUNKS.open(encoding="utf-8")]
    indexes = {}
    for pvp in (True, False):
        group = [c for c in chunks if is_pvp_chunk(c) == pvp]
        indexes[pvp] = ([c["id"] for c in group], BM25Okapi([bigrams(c["text"]) for c in group]))
    return indexes

def build_chunk_jobs() -> tuple[set[str], dict[str, set[str]]]:
    """チャンクの見出しから、ジョブとクラスの名前の一覧と、チャンクごとのジョブを作る。"""
    chunks = [json.loads(line) for line in CHUNKS.open(encoding="utf-8")]
    names = job_names_from_headings([c["headings"] for c in chunks])
    jobs = {c["id"]: (jobs_in(c["headings"][-1], names) if c["headings"] else set()) for c in chunks}
    return names, jobs

embedder = SentenceTransformer(EMBEDDING_MODEL)
collection = chromadb.PersistentClient(path=str(DB_DIR)).get_collection(COLLECTION)
keyword_indexes = build_keyword_indexes()
job_names, chunk_jobs = build_chunk_jobs()

def keyword_search(question: str, pvp: bool) -> list[str]:
    """キーワードの一致で、上位 CANDIDATES 件のチャンクの ID を返す。"""
    ids, index = keyword_indexes[pvp]
    scores = index.get_scores(bigrams(question))
    top = np.argsort(scores)[::-1][:CANDIDATES]
    return [ids[i] for i in top]


def search(question: str, mode: str = DEFAULT_SEARCH) -> list[dict]:
    """質問に近いチャンクを TOP_K 件取り、パッチの古い順に並べて返す。

    PvP の質問なら PvP のチャンクだけ、それ以外なら PvP 以外のチャンクだけを検索する。
    各チャンクには、検索での順位（rank）と、意味の近さ（score）を付ける。
    """
    pvp = is_pvp_text(question)
    embedding = embedder.encode(QUERY_PREFIX + question, normalize_embeddings=True)

    vector = collection.query(
        query_embeddings=[embedding.tolist()],
        n_results=CANDIDATES,
        where={"is_pvp": pvp},
        include=["distances"],
    )
    vector_ids = vector["ids"][0]

    if mode == "vector":
        ids = vector_ids[:TOP_K]
    else:
        # 2つの検索の順位から点数を付けて足し合わせる（RRF）。質問のジョブと合う資料には JOB_BONUS を足す
        job = job_of(question, job_names)
        boosted = {i for i, jobs in chunk_jobs.items() if job in jobs} if job else set()
        ranked = fuse_ranks([vector_ids, keyword_search(question, pvp)], RRF_K, boosted, JOB_BONUS)
        ids = ranked[:TOP_K]
        
    got = collection.get(ids=ids, include=["documents", "metadatas", "embeddings"])
    by_id = {
        chunk_id: (doc, meta, emb)
        for chunk_id, doc, meta, emb in zip(
            got["ids"], got["documents"], got["metadatas"], got["embeddings"]
        )
    }

    hits = []
    for rank, chunk_id in enumerate(ids, start=1):
        doc, meta, emb = by_id[chunk_id]
        hits.append(
            {
                "id": chunk_id,
                "text": doc,
                **meta,
                "score": float(np.dot(embedding, emb)),
                "rank": rank,
            }
        )
    # 古い順に並べると、資料の中で変更の流れが追いやすくなる
    return sorted(hits, key=lambda h: h["order"])


def answer(
    question: str,
    models: list[str] | None = None,
    prompt: str = DEFAULT_PROMPT,
    search_mode: str = DEFAULT_SEARCH,
) -> dict:
    hits = search(question, search_mode)
    context = "\n\n---\n\n".join(hit["text"] for hit in hits)

    used = pick_prompt(question, prompt)
    text, model = generate(PROMPTS[used].format(context=context, question=question), models)

    # auto のときだけ、今の値をコードで決め直す（v2 や v3 単体の評価には手を加えない）
    if prompt == "auto":
        text = fix_current_value(text)

    return {
        "answer": text,
        "model": model,
        "prompt": f"auto({used})" if prompt == "auto" else used,
        "search": search_mode,
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