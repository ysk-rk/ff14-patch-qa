"""ジョブの調整の見出しの下で、ジョブではない見出し（「共通」やロールの名前）のチャンクを出す。

C-1（ジョブ名がある質問で、正解が「共通」の調整にある問題）の候補を探すためのもの。
PvE で、見出しの一つ上に JOB_SECTION_WORDS がすべて入り、一番下の見出しがジョブの名前
（job_names_from_headings で作った名前）に入らないチャンクを探す。
表の行からスキル名と変更の内容を出し、同じスキルの変更があるパッチも足す。
検索も AI も呼ばず、資料の作りだけを見る。

--wide を付けると、「アクション／特性において」の節の外も探す。PvE で、見出しのどこにも
ジョブの名前がなく、本文に「→」があるチャンクを、見出しごとの件数で出す。そのうち、本文に
評価用の問題（ジョブ名のある質問）の keyword か、ロールの見出しの下のスキル名があるチャンクだけ、行を出す。

使い方: python scripts\\find_common_answers.py [--wide] [--show 30]
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "scripts"))

from app.rules import (  # noqa: E402
    JOB_SECTION_WORDS,
    NOT_JOB_WORDS,
    is_pvp_text,
    job_names_from_headings,
    jobs_in,
)
from find_split_tables import skill_patches, table_rows  # noqa: E402

CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"
QUESTIONS = ROOT / "eval" / "questions.jsonl"


def load_chunks() -> list[dict]:
    with CHUNKS.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def is_common(headings: list[str], names: set[str]) -> bool:
    """ジョブの調整の見出しの下で、一番下の見出しがジョブの名前ではなければ True。"""
    if len(headings) < 2 or not all(w in headings[-2] for w in JOB_SECTION_WORDS):
        return False
    return not any(name.strip() in names for name in headings[-1].split("／"))


def used_in_eval() -> tuple[set[str], list[str]]:
    """評価用の問題の keyword（空白を除く）と、質問の文を返す。"""
    keywords, questions = set(), []
    with QUESTIONS.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                q = json.loads(line)
                if q.get("keyword"):
                    keywords.add(q["keyword"].replace(" ", ""))
                questions.append(q["question"].replace(" ", ""))
    return keywords, questions


def job_keywords(names: set[str]) -> set[str]:
    """評価用の問題のうち、質問にジョブ名があるものの keyword（空白を除く）を返す。"""
    words = set()
    with QUESTIONS.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                q = json.loads(line)
                if q.get("keyword") and jobs_in(q["question"], names):
                    words.add(q["keyword"].replace(" ", ""))
    return words


def role_skills(chunks: list[dict]) -> set[str]:
    """PvE で、一番下の見出しがロールや「共通」のチャンクの、表の1列目のスキル名を返す。"""
    skills = set()
    for c in chunks:
        h = c.get("headings") or []
        if h and not is_pvp_text(c["text"]) and any(w in h[-1] for w in NOT_JOB_WORDS):
            skills.update(s.replace(" ", "") for s, _ in table_rows(c["text"]))
    return skills


def show_wide(chunks: list[dict], names: set[str], show: int) -> None:
    found = [
        c for c in chunks
        if c.get("headings") and not is_pvp_text(c["text"]) and "→" in c["text"]
        and not jobs_in(" ".join(c["headings"]), names)
    ]
    jobs_words = job_keywords(names)
    roles = role_skills(chunks)

    counts = Counter(" > ".join(c["headings"]) for c in found)
    print(f"--wide の候補のチャンク: {len(found)}件（PvE、見出しにジョブの名前がなく、本文に「→」があるもの）")
    print(f"見出しごとの件数: {len(counts)}種類（多い順に上位{show}件）")
    for heading, n in counts.most_common(show):
        print(f"  {n}件  {heading}")
    print()

    print(f"照らし合わせた名前: 評価用のジョブのスキル {len(jobs_words)}個、ロールの見出しの下のスキル {sorted(roles)}\n")
    hits = []
    for c in found:
        text = c["text"].replace(" ", "")
        matched = sorted(w for w in jobs_words | roles if w in text)
        if matched:
            hits.append((c, matched))
    print(f"行を出したチャンク: {len(hits)}件\n")
    for c, matched in hits:
        print(f"{c['version']} / {' > '.join(c['headings'])} / {c['id']}  見つかった名前: {', '.join(matched)}")
        for t in c["text"].splitlines()[1:]:
            if any(w in t.replace(" ", "") for w in matched):
                print(f"    {t.strip()[:100]}")
        print()


def main() -> None:
    p = argparse.ArgumentParser(description="ジョブの調整の下の、ジョブではない見出しのチャンクを出す")
    p.add_argument("--wide", action="store_true", help="「アクション／特性において」の節の外も探す")
    p.add_argument("--show", type=int, default=30, help="表示する行（--wide では見出し）の件数")
    args = p.parse_args()

    chunks = load_chunks()
    if args.wide:
        names = job_names_from_headings([c.get("headings") or [] for c in chunks])
        show_wide(chunks, names, args.show)
        return
    names = job_names_from_headings([c.get("headings") or [] for c in chunks])
    table_chunks = [c for c in chunks if c.get("has_table") and c.get("headings")]
    patches = skill_patches(table_chunks)
    keywords, questions = used_in_eval()

    found = [
        c for c in chunks
        if c.get("headings") and not is_pvp_text(c["text"]) and is_common(c["headings"], names)
    ]

    print(f"候補のチャンク: {len(found)}件（PvE、ジョブの調整の下で、見出しがジョブではないもの）\n")
    print("見出しごとの件数:")
    for heading, n in Counter(c["headings"][-1] for c in found).most_common():
        versions = [c["version"] for c in found if c["headings"][-1] == heading]
        print(f"  {heading}: {n}件  （{', '.join(versions)}）")
    print()

    rows = []
    for c in found:
        table = list(table_rows(c["text"]))
        if not table:
            rows.append((c, None, None))
        for skill, change in table:
            rows.append((c, skill, change))

    print(f"行: {len(rows)}件（表の行。表のないチャンクは1行で出す）。印 * は評価用の64問で使っているスキル\n")
    for c, skill, change in rows[: args.show]:
        head = f"{c['version']} / {c['headings'][-1]} / {c['id']}"
        if skill is None:
            first = next((t for t in c["text"].splitlines()[1:] if t.strip()), "")
            print(f"{head}  （表なし）{first[:60]}")
            continue
        key = skill.replace(" ", "")
        mark = "*" if key in keywords or any(key in q for q in questions) else " "
        vs = patches[("pve", key)]
        print(f"{mark} {head}  {skill}: {change[:60]}  [変更のあるパッチ: {', '.join(sorted(vs, key=vs.get))}]")


if __name__ == "__main__":
    main()
