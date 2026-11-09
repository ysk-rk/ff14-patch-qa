"""ジョブの名前の集め方、ジョブの判定、順位の合わせ方のテスト。"""

from app.rules import fuse_ranks, job_names_from_headings, job_of, jobs_in

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