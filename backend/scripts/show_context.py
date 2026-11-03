"""AI に渡す資料とプロンプトを、AI を呼ばずに表示する（確認用）。

rag.py の answer と同じ方法で資料を探し、プロンプトを選ぶ。回数制限は使わない。
プロンプトの全文は data/debug/ に保存する（パッチノートの本文を含むので、公開しない場所に置く）。

使い方: python scripts\\show_context.py "質問" [--search hybrid]
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag import AUTO_HISTORY_PROMPT, DEFAULT_SEARCH, PROMPTS, SEARCH_MODES, search  # noqa: E402
from app.rules import choose_prompt  # noqa: E402

DEBUG_DIR = ROOT / "data" / "debug"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--search", choices=SEARCH_MODES, default=DEFAULT_SEARCH)
    args = parser.parse_args()

    hits = search(args.question, args.search)

    # rag.py の answer と同じ方法で、資料をつないでプロンプトを選ぶ
    context = "\n\n---\n\n".join(hit["text"] for hit in hits)
    used = choose_prompt(args.question)
    if used == "v1":
        used = AUTO_HISTORY_PROMPT
    prompt = PROMPTS[used].format(context=context, question=args.question)

    print(f"質問: {args.question}")
    print(f"検索: {args.search}  プロンプト: auto({used})")
    print()
    for hit in hits:
        label = "PvP" if hit.get("is_pvp") else "PvE"
        print(f"===== 検索{hit['rank']}位  パッチ{hit['version']}  {label}  近さ {hit['score']:.3f}")
        print(hit["text"])
        print()

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    out = DEBUG_DIR / "prompt.txt"
    out.write_text(prompt, encoding="utf-8")
    print(f"プロンプトの全文を保存しました: {out}")


if __name__ == "__main__":
    main()