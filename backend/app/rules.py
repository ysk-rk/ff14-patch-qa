"""AI やデータに依存しない、決まった処理。自動テスト（tests/test_rules.py）の対象。"""

import re
from collections.abc import Callable

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


# 改善14: 拡張パッケージの境目で、古い値を今の値として答えない
# 7.0 のジョブのスキルの調整はパッチノートの本文になく（「詳しくは『こちら』」でジョブガイドへ）、
# 8.0 も同じ作りなら、7.x の最後の変更の値を今の値として答えてしまうため、【今の値】を「分かりませんでした」に差し替える
# 対象は、今の値の質問（auto で v5）で、質問にジョブ名があるものだけ。False なら前の動き
EXPANSION_GUARD = True

EXPANSION_UNKNOWN = (
    "{mark}分かりませんでした（最後の変更はパッチ{version}ですが、そのあと拡張パッケージ{expansion}.0で"
    "スキルが作り直された可能性があり、パッチノートだけでは今の値を確かめられません）"
)


def major_version(version: str) -> int:
    """版の先頭の数（拡張パッケージの番号）を返す（例: "7.57" → 7、"8.01" → 8）。"""
    return int(version.split(".")[0])


def latest_expansion(versions) -> int:
    """取り込んだパッチの版の一覧から、最新の拡張パッケージの番号を返す（コードに 8 などを書かない）。"""
    return max(major_version(v) for v in versions)


def guard_expansion(text: str, question: str, expansion: int, names: set[str]) -> str:
    """fix_current_value のあとの答えで、根拠のパッチが最新の拡張パッケージより前なら【今の値】を差し替える。

    - 経緯の質問（choose_prompt が "v1"）と、質問にジョブ名がない質問は、そのまま返す
    - 【変更の経緯】がない答え（「分かりませんでした」など）は、そのまま返す
    - 根拠のパッチは fix_current_value と同じく、経緯の中で一番新しいパッチ。【変更の経緯】はそのまま残す
    """
    if choose_prompt(question) == "v1" or job_of(question, names) is None:
        return text
    lines = text.splitlines()
    changes = [m for line in lines if (m := CHANGE_LINE.match(line.replace("**", "")))]
    if not changes:
        return text

    version = max(changes, key=lambda m: float(m.group(1))).group(1)
    if major_version(version) >= expansion:
        return text

    unknown = EXPANSION_UNKNOWN.format(mark=CURRENT_MARK, version=version, expansion=expansion)
    for i, line in enumerate(lines):
        if CURRENT_MARK in line:
            lines[i] = unknown
            return "\n".join(lines)
    return "\n".join([unknown, *lines])


# ジョブの調整の見出し（一つ上の見出し）に含まれる言葉
#   例: 「アクション／特性において、以下の調整が行われます。」「PvPアクションにおいて、以下の調整が行われます。」
#   クイックパネルやヴァリアントアクションなど、ジョブではないアクションの見出しには「において」がない
JOB_SECTION_WORDS = ("アクション", "において")

# 新しいジョブが追加されたときの見出し（例:「新たなジョブ「魔獣使い」が実装されます。」）
NEW_JOB_PATTERN = re.compile(r"(?:新たなジョブ|リミテッドジョブ)「(.+?)」")

# 改善14: 新しいジョブの見出しに名前が2つ以上あるとき、すべての名前を取る
# NEW_JOB_PATTERN は「新たなジョブ「ヴァイパー」「ピクトマンサー」」から、ヴァイパーだけを取る。
# 8.0 では新しいジョブが2つ出るので、2つ目のジョブも、調整のパッチを待たずに名前の一覧に入れる。
# 「新たなジョブ」「リミテッドジョブ」のすぐあとに続く「」の並び（間は何もないか、「と」「、」「・」のどれか1文字）だけを取る
# （「新たなジョブ「A」が実装されます。クエスト「B」を…」の B は取らない）。False なら前の動き（NEW_JOB_PATTERN）
NEW_JOB_ALL_NAMES = True

NEW_JOB_NAMES_PATTERN = re.compile(r"(?:新たなジョブ|リミテッドジョブ)(「[^」]+」(?:[と、・]?「[^」]+」)*)")
QUOTED_NAME = re.compile(r"「([^」]+)」")

# ジョブの調整の見出しの下にあっても、ジョブではないもの（共通の調整と、ロールの名前）
# ロールの名前は、ジョブと違ってほとんど増えない
NOT_JOB_WORDS = ("共通", "DPS", "ヒーラー", "タンク")

# 7.0 より前に追加され、7.x のジョブの調整にも、新しいジョブの見出しにも出てこないジョブ
# これから追加されるジョブは NEW_JOB_PATTERN の見出しで入るので、ここには足さなくてよい
OLDER_JOBS = ("青魔道士",)


def new_job_names(heading: str, all_names: bool = NEW_JOB_ALL_NAMES) -> list[str]:
    """新しいジョブの見出しから、ジョブの名前を取り出す。

    all_names が True なら、続く「」の名前をすべて取る（NEW_JOB_NAMES_PATTERN）。False なら1つ目だけ（NEW_JOB_PATTERN）。
    """
    if not all_names:
        return [name.strip() for name in NEW_JOB_PATTERN.findall(heading)]
    return [name.strip() for run in NEW_JOB_NAMES_PATTERN.findall(heading) for name in QUOTED_NAME.findall(run)]


def job_names_from_headings(headings_list: list[list[str]], all_names: bool = NEW_JOB_ALL_NAMES) -> set[str]:
    """チャンクの見出しから、ジョブとクラスの名前を集める。

    - ジョブの調整の見出し（JOB_SECTION_WORDS を含む）の下の、一番下の見出しを「／」で分ける（例:「格闘士／モンク」）
    - 新しいジョブの見出し（NEW_JOB_PATTERN）から、ジョブの名前を取り出す
      （all_names が True なら、見出しにある名前をすべて取る。new_job_names を参照）
    ジョブの一覧をコードに書かずにデータから作るので、新しいジョブが増えても、そのパッチノートを取り込めば入る。
    """
    names = set(OLDER_JOBS)
    for headings in headings_list:
        for heading in headings:
            names.update(new_job_names(heading, all_names))
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


# 箇条書きの「- スキル名」の行（例: 7.16-0021 の「- 浄化」）。文の箇条書きと分けるため、空白や句読点のない短い行だけ
BULLET_SKILL = re.compile(r"^-\s*([^\s。、，,：:（）()]{1,30})$")


def table_skill_names(text: str) -> set[str]:
    """チャンクの本文の表から、行の1列目のスキル名を取り出す。見出しの行と区切りの行は除く。

    見出しの行は「名称」の表だけでなく「アイテム名」などの表もあるので、区切りの行（|---|）のすぐ上の行を見出しとみなす。
    """
    rows: list[list[str]] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [x.strip() for x in line.strip().strip("|").split("|")]
        if all(set(x) <= set("-: ") for x in cells):
            if rows:
                rows.pop()  # 区切りの行のすぐ上は見出しの行
            continue
        rows.append(cells)
    return {cells[0] for cells in rows if len(cells) >= 2 and cells[0] and cells[0] != "名称"}


def bullet_skill_names(text: str) -> set[str]:
    """チャンクの本文から、箇条書きの「- スキル名」の行のスキル名を取り出す。"""
    names = set()
    for line in text.splitlines():
        m = BULLET_SKILL.match(line.strip())
        if m:
            names.add(m.group(1))
    return names


def skill_names_in(text: str) -> set[str]:
    """チャンクの本文から、表の行の1列目と、箇条書きの「- スキル名」の行のスキル名を取り出す。"""
    return table_skill_names(text) | bullet_skill_names(text)


def skills_in(question: str, names: set[str]) -> set[str]:
    """質問の中にあるスキル名を返す。ほかに見つかった、より長い名前の中に入っている名前は外す（jobs_in と同じ考え方）。

    例: 「シールドスマイト」がある質問では「スマイト」を外す。
    """
    return jobs_in(question, names)


# 改善13: ロールクエストの見出し（例:「≪ヒーラー（白魔道士／学者／占星術師／賢者）≫」）
ROLE_QUEST_HEADING = re.compile(r"^≪([^（≫]+)（([^）]+)）≫$")

# ロールの名前の読み替え（ジョブの調整の見出しの書き方が、ロールクエストの見出しと違うもの）
ROLE_ALIASES = {"HEALER": "ヒーラー"}

# ジョブの調整の見出しの下の「共通」と、AI に渡すときの書き方
COMMON_HEADING = "共通"
COMMON_LABEL = "共通（すべてのジョブ）"


def role_jobs_from_headings(headings_list: list[list[str]], names: set[str]) -> dict[str, list[str]]:
    """「≪ロール名（ジョブ名／ジョブ名…）≫」の見出しから、ロールとジョブの対応を作る。

    ジョブ名は、ジョブの一覧（names）にあるものだけを、見出しの並びのまま入れる。
    ロールとジョブの対応をコードに書かずにデータから作るので、ロールクエストの見出しが増えれば入る。
    """
    roles: dict[str, list[str]] = {}
    for headings in headings_list:
        for heading in headings:
            m = ROLE_QUEST_HEADING.match(heading.strip())
            if not m:
                continue
            jobs = [j.strip() for j in m.group(2).split("／") if j.strip() in names]
            if jobs:
                roles.setdefault(m.group(1).strip(), jobs)
    return roles


def label_role_heading(line: str, roles: dict[str, list[str]]) -> str:
    """見出しの行（「[パッチ7.1] … > ヒーラー」）の一番下の見出しに、ジョブ名を書き足した行を返す。

    - 一番下の見出しがロール名（ROLE_ALIASES で読み替えたあと）なら「ヒーラー（白魔道士／学者／…）」にする
    - ちょうど「共通」なら「共通（すべてのジョブ）」にする（「全クラフタークラス共通」などは変えない）
    - それ以外はそのまま返す
    """
    head, sep, last = line.rpartition(" > ")
    if not sep:
        return line
    if last == COMMON_HEADING:
        return f"{head}{sep}{COMMON_LABEL}"
    role = ROLE_ALIASES.get(last, last)
    if role in roles:
        return f"{head}{sep}{last}（{'／'.join(roles[role])}）"
    return line


def boosted_chunks(
    question: str,
    job: str | None,
    chunk_jobs: dict[str, set[str]],
    role_chunk_skills: dict[str, set[str]],
    all_skills: set[str],
) -> set[str]:
    """JOB_BONUS を足すチャンクの ID を返す（改善12）。

    - 見出しのジョブが質問のジョブと合うチャンク
    - ロールや共通のチャンク（role_chunk_skills）のうち、表や箇条書きのスキル名が質問の中にあるもの
    質問のジョブが決まらない（None）ときは空にする。
    """
    if job is None:
        return set()
    found = skills_in(question, all_skills)
    ids = {i for i, jobs in chunk_jobs.items() if job in jobs}
    ids |= {i for i, skills in role_chunk_skills.items() if skills & found}
    return ids


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


def split_for_embedding(text: str, count_tokens: Callable[[str], int], max_tokens: int) -> list[str]:
    """埋め込みのモデルが読める長さに収まるよう、チャンクを「かけら」に分ける。

    埋め込みのモデルは max_tokens より後ろを切り捨てるので、長いチャンクの後ろの行が検索で見つからない（m007）。
    - 全体が max_tokens 以下なら、text をそのまま1つだけ返す
    - 1行目（「[パッチ…] …」の見出しの行）を、すべてのかけらの先頭に付ける
    - 2行目から後ろを、行の区切りで前から順に詰め、max_tokens を超えそうになったら次のかけらにする
    - 1行だけで max_tokens を超える行は、切らずに、その行だけで1つのかけらにする
    count_tokens は、文字列のトークン数を返す関数（トークナイザーには依存しない）。
    """
    if count_tokens(text) <= max_tokens or "\n" not in text:
        return [text]
    head, _, body = text.partition("\n")
    pieces: list[str] = []
    lines: list[str] = []
    for line in body.split("\n"):
        if lines and count_tokens("\n".join([head, *lines, line])) > max_tokens:
            pieces.append("\n".join([head, *lines]))
            lines = []
        lines.append(line)
    if lines:
        pieces.append("\n".join([head, *lines]))
    return pieces
