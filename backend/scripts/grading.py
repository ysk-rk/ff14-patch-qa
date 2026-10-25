"""評価の採点と、検索の再現率の計算。AI を使わない決まった処理。
自動テスト（tests/test_grading.py）の対象。
"""

import re

from app.rules import is_pvp_text

# 回答にこの印で始まる行があれば、その行だけを採点する（経緯に書かれた古い値で◯にしないため）
CURRENT_VALUE_MARK = "【今の値】"

UNKNOWN_PHRASES = (
    "分かりませんでした",
    "わかりませんでした",
    "分からない",
    "わからない",
    "記載がありません",
    "記載されていません",
)


def normalize(text: str) -> str:
    """数字の比べ方をそろえる（「1,000」と「1000」、「%」と「％」を同じにする）。"""
    return text.replace(",", "").replace("，", "").replace("%", "％").replace(" ", "")


def contains_value(text: str, expected: str) -> bool:
    """回答に正解の数字が入っているか。「7.2」が「7.25」に一致しないよう前後も見る。"""
    pattern = rf"(?<![\d.]){re.escape(normalize(expected))}(?!\d)"
    return re.search(pattern, normalize(text)) is not None


def graded_part(text: str) -> str:
    """採点する部分。【今の値】の行があればその行だけ、なければ回答全体。"""
    for line in text.splitlines():
        if CURRENT_VALUE_MARK in line:
            return line
    return text


def says_unknown(text: str) -> bool:
    return any(p in text for p in UNKNOWN_PHRASES)


def is_pvp_hit(hit: dict) -> bool:
    return is_pvp_text(hit["headings"])


def evidence_ranks(question: dict, hits: list[dict]) -> dict[str, int | None] | None:
    """正解に必要なパッチごとに、そのチャンクが検索で何位だったか（拾えなければ None）。"""
    needed = question["evidence_versions"]
    if not needed:
        return None

    ranks: dict[str, int | None] = {v: None for v in needed}
    for hit in sorted(hits, key=lambda h: h["rank"]):
        version = hit["version"]
        if version not in ranks or ranks[version] is not None:
            continue
        if question["keyword"] not in hit["text"]:
            continue
        if question["mode"] == "pve" and is_pvp_hit(hit):
            continue
        if question["mode"] == "pvp" and not is_pvp_hit(hit):
            continue
        ranks[version] = hit["rank"]
    return ranks


def recall_at(ranks: dict[str, int | None] | None, k: int) -> float | None:
    """正解に必要なパッチのうち、上位 k 件に入っていた割合（0〜1）。"""
    if ranks is None:
        return None
    return sum(1 for r in ranks.values() if r is not None and r <= k) / len(ranks)


def grade(question: dict, text: str) -> bool:
    """回答を採点する。"""
    if question["kind"] == "unanswerable":
        return says_unknown(text)
    if question["kind"] == "history":
        # 変更の流れを答える質問は、必要なパッチ番号がすべて回答に入っているかで採点する
        if says_unknown(text):
            return False
        return all(contains_value(text, v) for v in question["evidence_versions"])
    return contains_value(graded_part(text), question["expected"])