"""AI やデータに依存しない、決まった処理。自動テスト（tests/test_rules.py）の対象。"""

import re

# 質問や見出しにこれらの言葉が入っていれば PvP として扱う
PVP_WORDS = re.compile(r"PvP|フロントライン|クリスタルコンフリクト")

# auto のとき、これらの言葉が入った質問は「何が変わったか」「いつ変わったか」の質問として v1 で答える
HISTORY_WORDS = re.compile(r"何が変わ|どう変わ|どう調整|変更点|変更内容|どのパッチ|いつ")

# 【今の値】と【変更の経緯】の行
CURRENT_MARK = "【今の値】"
CHANGE_LINE = re.compile(r"^\s*[-・*]\s*パッチ\s*([\d.]+)\s*[:：]\s*(.+?)\s*→\s*(.+?)\s*$")


def is_pvp_text(text: str) -> bool:
    """質問や見出しが PvP に関するものか。"""
    return bool(PVP_WORDS.search(text))


def bigrams(text: str) -> list[str]:
    """日本語は単語の区切りがないため、2文字ずつに区切ってキーワード検索に使う。"""
    text = re.sub(r"\s+", "", text)
    return [text[i : i + 2] for i in range(len(text) - 1)]


def choose_prompt(question: str) -> str:
    """auto のときに使うプロンプトを、質問の言葉から決める。"""
    return "v1" if HISTORY_WORDS.search(question) else "v2"


def fix_current_value(text: str) -> str:
    """【変更の経緯】の中で一番新しいパッチの「変更後」を、【今の値】に入れ直す。

    AI が正しい経緯を書いたのに、今の値だけを間違えることがあるため、
    最後の一歩はコードで決める。経緯が書かれていなければ、そのまま返す。
    """
    lines = text.splitlines()
    changes = [m for line in lines if (m := CHANGE_LINE.match(line.replace("**", "")))]
    if not changes:
        return text

    latest = max(changes, key=lambda m: float(m.group(1)))
    current = f"{CURRENT_MARK}{latest.group(3)}（根拠: パッチ{latest.group(1)}）"

    for i, line in enumerate(lines):
        if CURRENT_MARK in line:
            lines[i] = current
            return "\n".join(lines)
    return "\n".join([current, *lines])


# ジョブの調整の見出し（一つ上の見出し）に含まれる言葉
#   例: 「アクション／特性において、以下の調整が行われます。」「PvPアクションにおいて、以下の調整が行われます。」
#   クイックパネルやヴァリアントアクションなど、ジョブではないアクションの見出しには「において」がない
JOB_SECTION_WORDS = ("アクション", "において")

# 新しいジョブが追加されたときの見出し（例:「新たなジョブ「魔獣使い」が実装されます。」）
NEW_JOB_PATTERN = re.compile(r"(?:新たなジョブ|リミテッドジョブ)「(.+?)」")

# ジョブの調整の見出しの下にあっても、ジョブではないもの（共通の調整と、ロールの名前）
# ロールの名前は、ジョブと違ってほとんど増えない
NOT_JOB_WORDS = ("共通", "DPS", "ヒーラー", "タンク")

# 7.0 より前に追加され、7.x のジョブの調整にも、新しいジョブの見出しにも出てこないジョブ
# これから追加されるジョブは NEW_JOB_PATTERN の見出しで入るので、ここには足さなくてよい
OLDER_JOBS = ("青魔道士",)


def job_names_from_headings(headings_list: list[list[str]]) -> set[str]:
    """チャンクの見出しから、ジョブとクラスの名前を集める。

    - ジョブの調整の見出し（JOB_SECTION_WORDS を含む）の下の、一番下の見出しを「／」で分ける（例:「格闘士／モンク」）
    - 新しいジョブの見出し（NEW_JOB_PATTERN）から、ジョブの名前を取り出す
    ジョブの一覧をコードに書かずにデータから作るので、新しいジョブが増えても、そのパッチノートを取り込めば入る。
    """
    names = set(OLDER_JOBS)
    for headings in headings_list:
        for heading in headings:
            names.update(name.strip() for name in NEW_JOB_PATTERN.findall(heading))
        if len(headings) < 2 or not all(w in headings[-2] for w in JOB_SECTION_WORDS):
            continue
        for name in headings[-1].split("／"):
            name = name.strip()
            if not name or name.isascii() or any(w in name for w in NOT_JOB_WORDS):
                continue
            names.add(name)
    return names


def jobs_in(text: str, names: set[str]) -> set[str]:
    """文に出てくるジョブとクラスの名前を返す。ほかの名前の一部になっている名前は外す。"""
    found = {n for n in names if n in text}
    return {n for n in found if not any(n != m and n in m for m in found)}


def job_of(text: str, names: set[str]) -> str | None:
    """文に出てくる名前が1つだけなら、その名前を返す。0個や2個以上なら None。"""
    found = jobs_in(text, names)
    return next(iter(found)) if len(found) == 1 else None


def fuse_ranks(
    rankings: list[list[str]],
    k: int,
    boosted: set[str] = frozenset(),
    bonus: float = 0.0,
) -> list[str]:
    """複数の検索の順位を RRF で合わせ、点数の高い順に ID を返す。

    boosted に入っている ID には bonus を足す。候補にない ID は足さない（順位を変えるだけで、外しもしない）。
    """
    scores: dict[str, float] = {}
    for ranked in rankings:
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (k + rank)
    for chunk_id in scores:
        if chunk_id in boosted:
            scores[chunk_id] += bonus
    return sorted(scores, key=lambda i: scores[i], reverse=True)