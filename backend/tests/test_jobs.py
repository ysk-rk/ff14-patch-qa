"""ジョブの名前の集め方、ジョブの判定、順位の合わせ方のテスト。"""

from app.rules import (
    boosted_chunks,
    fuse_ranks,
    job_names_from_headings,
    job_of,
    jobs_in,
    label_role_heading,
    role_jobs_from_headings,
    skill_names_in,
    skills_in,
)

ACTION = "アクション／特性において、以下の調整が行われます。"
PVP_ACTION = "PvPアクションにおいて、以下の調整が行われます。"

HEADINGS = [
    ["バトル関連", ACTION, "格闘士／モンク"],
    ["バトル関連", ACTION, "暗黒騎士"],
    [PVP_ACTION, "ナイト"],
    # ジョブの調整の見出しの下にある、ロールと共通の調整
    ["バトル関連", ACTION, "ヒーラー"],
    [PVP_ACTION, "近接物理DPS"],
    [PVP_ACTION, "HEALER"],
    [PVP_ACTION, "共通"],
    # 「において」がない、ジョブではないアクションの見出し
    ["システム関連", "アクションやアイテムの整理に役立つ新機能「クイックパネル」が追加されます。", "マウス操作の場合"],
    ["バトル関連", "ヴァリアントダンジョンに新たなヴァリアントアクションが追加されます。", "TANK"],
    # 新しいジョブの見出し
    ["バトル関連", "新たなジョブ「魔獣使い」が実装されます。", "≪開放条件≫"],
    ["イベント関連", "クエスト関連", "凄腕の狩人"],
]
NAMES = job_names_from_headings(HEADINGS)


def test_names_exclude_roles_common_and_ui_headings():
    assert NAMES == {"格闘士", "モンク", "暗黒騎士", "ナイト", "魔獣使い", "青魔道士"}


def test_new_job_in_adjustment_heading_is_added_without_code_change():
    names = job_names_from_headings([["バトル関連", ACTION, "新しいジョブ"]])
    assert "新しいジョブ" in names


def test_new_job_introduction_heading_is_added_without_code_change():
    names = job_names_from_headings([["バトル関連", "新たなジョブ「未来のジョブ」が実装されます。"]])
    assert "未来のジョブ" in names


def test_job_of_finds_single_job():
    assert job_of("PvPのナイトのホーリースピリットの最大チャージ数は？", NAMES) == "ナイト"
    assert job_of("魔獣使いのペットの呼び出し方は？", NAMES) == "魔獣使い"


def test_job_of_none_or_multiple_is_none():
    assert job_of("分解スキルの上限値はいくつ？", NAMES) is None
    assert job_of("ナイトと暗黒騎士", NAMES) is None


def test_jobs_in_heading_with_class_name():
    assert jobs_in("格闘士／モンク", NAMES) == {"格闘士", "モンク"}


def test_jobs_in_drops_name_inside_longer_name():
    assert jobs_in("暗黒騎士", {"騎士", "暗黒騎士"}) == {"暗黒騎士"}


def test_fuse_ranks_without_bonus_is_plain_rrf():
    # a: 1/61+1/63、b: 1/62+1/61、c: 1/63+1/62
    assert fuse_ranks([["a", "b", "c"], ["b", "c", "a"]], k=60) == ["b", "a", "c"]


def test_fuse_ranks_bonus_moves_up_without_removing_others():
    out = fuse_ranks([["a", "b", "c"], ["a", "b", "c"]], k=60, boosted={"c"}, bonus=1.0)
    assert out[0] == "c"
    assert sorted(out) == ["a", "b", "c"]


def test_fuse_ranks_bonus_does_not_add_new_candidates():
    out = fuse_ranks([["a"], ["b"]], k=60, boosted={"z"}, bonus=1.0)
    assert "z" not in out


# 改善12: ロールや共通のチャンクのスキル名

ROLE_TABLE = """[パッチ7.31] バトル関連 > PvP全般 > PvPアクションにおいて、以下の調整が行われます。 > 共通
| 名称 | 詳細 |
| --- | --- |
| 浄化 | ・消費MPが 2,500 → 2,000 に変更されます。 |
| 快気 | ・消費MPが 2,500 → 2,000 に変更されます。 |"""

# 7.16-0021 の形（表がなく、箇条書きだけ）
ROLE_BULLETS = """[パッチ7.16] バトル関連 > PvP全般 > 以下のPvPアクションにおいて、実行から効果が発揮されるまでの時間が短縮されます。 > 共通
- 快気

- 浄化"""

ALL_SKILLS = {"浄化", "快気", "防御", "スマイト", "シールドスマイト", "ヒール", "ホーリースピリット"}
CHUNK_JOBS = {"knight": {"ナイト"}, "monk": {"格闘士", "モンク"}}
ROLE_CHUNK_SKILLS = {"common": {"浄化", "快気", "防御"}, "melee": {"スマイト"}, "healer": {"ヒール"}}


def test_skill_names_from_table_rows():
    assert skill_names_in(ROLE_TABLE) == {"浄化", "快気"}


def test_skill_names_from_bullets_without_table():
    assert skill_names_in(ROLE_BULLETS) == {"快気", "浄化"}


def test_skill_names_skip_sentence_bullets():
    text = "見出し\n- 「エスナ」を実行すると、カットシーンが再生されない。\n- 浄化"
    assert skill_names_in(text) == {"浄化"}


def test_skills_in_drops_name_inside_longer_name():
    assert skills_in("PvPのナイトのシールドスマイトの威力は？", ALL_SKILLS) == {"シールドスマイト"}


def test_skills_in_keeps_two_letter_names():
    assert skills_in("PvPのナイトの浄化と防御は何が変わった？", ALL_SKILLS) == {"浄化", "防御"}


def test_boosted_chunks_adds_role_chunk_with_skill_in_question():
    q = "PvPのナイトの浄化は何が変わった？"
    assert boosted_chunks(q, "ナイト", CHUNK_JOBS, ROLE_CHUNK_SKILLS, ALL_SKILLS) == {"knight", "common"}


def test_boosted_chunks_skips_role_chunk_without_skill_in_question():
    q = "PvPのナイトのホーリースピリットの威力は？"
    assert boosted_chunks(q, "ナイト", CHUNK_JOBS, ROLE_CHUNK_SKILLS, ALL_SKILLS) == {"knight"}


def test_boosted_chunks_skips_shorter_name_inside_longer_name():
    q = "PvPのナイトのシールドスマイトの威力は？"
    assert boosted_chunks(q, "ナイト", CHUNK_JOBS, ROLE_CHUNK_SKILLS, ALL_SKILLS) == {"knight"}


def test_boosted_chunks_empty_when_job_is_none():
    # クラフターはジョブの一覧にないので、job_of は None になる
    roles = {"crafter": {"真価", "上級加工"}}
    q = "木工師の真価は？"
    assert job_of(q, NAMES) is None
    assert boosted_chunks(q, None, CHUNK_JOBS, roles, ALL_SKILLS | {"真価", "上級加工"}) == set()


# 改善13: ロールや共通の資料の見出しに、ジョブ名を書き足す

ROLE_QUEST_HEADINGS = [
    ["イベント関連", "クエスト関連", "新たなロールクエストが追加されます。", "≪タンク（ナイト／戦士／暗黒騎士／ガンブレイカー）≫"],
    ["イベント関連", "クエスト関連", "新たなロールクエストが追加されます。", "≪ヒーラー（白魔道士／学者／占星術師／賢者）≫"],
    # ジョブの一覧にない名前は入れない
    ["イベント関連", "クエスト関連", "新たなロールクエストが追加されます。", "≪近接物理DPS（モンク／まだないジョブ）≫"],
]
ROLE_NAMES = {"ナイト", "戦士", "暗黒騎士", "ガンブレイカー", "白魔道士", "学者", "占星術師", "賢者", "モンク"}
ROLES = role_jobs_from_headings(ROLE_QUEST_HEADINGS, ROLE_NAMES)
HEALERS = "白魔道士／学者／占星術師／賢者"


def test_role_jobs_from_role_quest_headings():
    assert ROLES == {
        "タンク": ["ナイト", "戦士", "暗黒騎士", "ガンブレイカー"],
        "ヒーラー": ["白魔道士", "学者", "占星術師", "賢者"],
        "近接物理DPS": ["モンク"],
    }


def test_label_role_heading_adds_jobs():
    line = f"[パッチ7.1] バトル関連 > {ACTION} > ヒーラー"
    assert label_role_heading(line, ROLES) == f"[パッチ7.1] バトル関連 > {ACTION} > ヒーラー（{HEALERS}）"


def test_label_role_heading_reads_healer_in_english():
    line = f"[パッチ7.25] バトル関連 > PvP全般 > {PVP_ACTION} > HEALER"
    assert label_role_heading(line, ROLES) == f"[パッチ7.25] バトル関連 > PvP全般 > {PVP_ACTION} > HEALER（{HEALERS}）"


def test_label_role_heading_common_only_when_exact():
    line = f"[パッチ7.3] バトル関連 > PvP全般 > {PVP_ACTION} > 共通"
    assert label_role_heading(line, ROLES) == f"[パッチ7.3] バトル関連 > PvP全般 > {PVP_ACTION} > 共通（すべてのジョブ）"
    crafter = "[パッチ7.0] アイテム関連 > クラフターアクションにおいて、以下の調整が行われます。 > 全クラフタークラス共通"
    assert label_role_heading(crafter, ROLES) == crafter


def test_label_role_heading_keeps_job_heading():
    line = f"[パッチ7.1] バトル関連 > {ACTION} > 白魔道士"
    assert label_role_heading(line, ROLES) == line
