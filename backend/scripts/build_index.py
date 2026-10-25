"""チャンクを埋め込みモデルでベクトルに変え、Chroma に保存する。"""

import json
import re
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[2]
CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"
DB_DIR = ROOT / "data" / "index"
COLLECTION = "patch_notes"

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


if __name__ == "__main__":
    main()