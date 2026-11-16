"""チャンクを埋め込みモデルでベクトルに変え、Chroma に保存する。"""

import json
import re
import sys
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.rules import split_for_embedding  # noqa: E402

CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"
DB_DIR = ROOT / "data" / "index"
COLLECTION = "patch_notes"

# 長いチャンクを、埋め込みのモデルが読める長さの「かけら」に分けて入れるコレクション（改善11）
# かけらの ID は「チャンクの ID#番号」。元のチャンクの ID は parent_id に入れる
PIECES_COLLECTION = "patch_notes_pieces"

# 埋め込みのモデルが読める長さ（これより後ろは切り捨てられる）。「passage: 」と特別なトークンを含む
MAX_TOKENS = 512

# 日本語に対応した無料の埋め込みモデル（初回のみダウンロードされる）
MODEL_NAME = "intfloat/multilingual-e5-small"

# e5 系のモデルは、文書に「passage: 」、質問に「query: 」を付けて使う決まりがある
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "

# 見出しにこれらの言葉が入っているチャンクを PvP として扱う
PVP = re.compile(r"PvP|フロントライン|クリスタルコンフリクト")

BATCH_SIZE = 500


def main() -> None:
    chunks = [json.loads(line) for line in CHUNKS.open(encoding="utf-8")]
    print(f"{len(chunks)} チャンクを読み込みました")

    model = SentenceTransformer(MODEL_NAME)
    embeddings = model.encode(
        [PASSAGE_PREFIX + c["text"] for c in chunks],
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    client = chromadb.PersistentClient(path=str(DB_DIR))

    # 作り直すたびに古いデータを消してから入れ直す
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        collection.add(
            ids=[c["id"] for c in batch],
            embeddings=embeddings[start : start + BATCH_SIZE].tolist(),
            documents=[c["text"] for c in batch],
            metadatas=[
                {
                    "version": c["version"],
                    "order": c["order"],
                    "url": c["url"],
                    "has_table": c["has_table"],
                    "headings": " > ".join(c["headings"]),
                    "is_pvp": bool(PVP.search(" > ".join(c["headings"]))),
                }
                for c in batch
            ],
        )

    pvp = sum(1 for c in chunks if PVP.search(" > ".join(c["headings"])))
    print(f"完了: {collection.count()} 件（うち PvP {pvp} 件） → {DB_DIR}")

    build_pieces(chunks, model, client)


def build_pieces(chunks: list[dict], model: SentenceTransformer, client) -> None:
    """長いチャンクをかけらに分けて埋め込み、PIECES_COLLECTION に保存する。"""

    def count_tokens(text: str) -> int:
        # 実際に埋め込む文（「passage: 」付き）を、特別なトークンを含めて数える
        return len(model.tokenizer(PASSAGE_PREFIX + text)["input_ids"])

    pieces = []
    for c in chunks:
        for n, text in enumerate(split_for_embedding(c["text"], count_tokens, MAX_TOKENS), start=1):
            pieces.append(
                {
                    "id": f"{c['id']}#{n}",
                    "text": text,
                    "parent_id": c["id"],
                    "is_pvp": bool(PVP.search(" > ".join(c["headings"]))),
                }
            )
    print(f"{len(pieces)} 個のかけらに分けました。埋め込みます")

    embeddings = model.encode(
        [PASSAGE_PREFIX + p["text"] for p in pieces],
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    try:
        client.delete_collection(PIECES_COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(PIECES_COLLECTION, metadata={"hnsw:space": "cosine"})
    for start in range(0, len(pieces), BATCH_SIZE):
        batch = pieces[start : start + BATCH_SIZE]
        collection.add(
            ids=[p["id"] for p in batch],
            embeddings=embeddings[start : start + BATCH_SIZE].tolist(),
            documents=[p["text"] for p in batch],
            metadatas=[{"parent_id": p["parent_id"], "is_pvp": p["is_pvp"]} for p in batch],
        )

    over = [p["id"] for p in pieces if count_tokens(p["text"]) > MAX_TOKENS]
    split = len({p["parent_id"] for p in pieces if not p["id"].endswith("#1")})
    print(f"完了: かけら {collection.count()} 個（分けたチャンク {split} 件） → {PIECES_COLLECTION}")
    print(f"{MAX_TOKENS} トークンを超えたかけら: {len(over)} 個（1行だけで超える行）")
    for pid in over:
        print(f"  {pid}")


if __name__ == "__main__":
    main()