"""質問に近いチャンクを検索して表示する（確認用）。

使い方: python scripts\\search.py "質問"
"""

import sys

import chromadb
from sentence_transformers import SentenceTransformer

from build_index import COLLECTION, DB_DIR, MODEL_NAME, QUERY_PREFIX

TOP_K = 5


def main() -> None:
    question = sys.argv[1]

    model = SentenceTransformer(MODEL_NAME)
    embedding = model.encode(QUERY_PREFIX + question, normalize_embeddings=True)

    collection = chromadb.PersistentClient(path=str(DB_DIR)).get_collection(COLLECTION)
    result = collection.query(
        query_embeddings=[embedding.tolist()],
        n_results=TOP_K,
        include=["documents", "metadatas", "distances"],
    )

    for rank, (doc, meta, dist) in enumerate(
        zip(result["documents"][0], result["metadatas"][0], result["distances"][0]), start=1
    ):
        print(f"===== {rank}位  パッチ{meta['version']}  近さ {1 - dist:.3f}")
        print(doc[:300])
        print()


if __name__ == "__main__":
    main()