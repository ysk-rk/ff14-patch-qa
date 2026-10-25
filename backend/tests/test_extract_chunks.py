"""scripts/extract_chunks.py のテスト。"""

from bs4 import BeautifulSoup

from extract_chunks import MAX_CHARS, Walker, heading_level, split_table, table_to_markdown


def tag(html: str):
    return BeautifulSoup(html, "html.parser").find()


def walk(html: str) -> Walker:
    walker = Walker()
    walker.walk(tag(f"<div>{html}</div>"))
    walker.finish()
    return walker


class TestHeadingLevel:
    def test_classの付いたh3は大分類(self):
        assert heading_level(tag('<h3 class="mdl-title__ancher">バトル関連</h3>')) == 0

    def test_h2は中分類(self):
        assert heading_level(tag("<h2>PvP全般</h2>")) == 1

    def test_classのないh3は項目(self):
        assert heading_level(tag("<h3>アクション／特性において…</h3>")) == 2

    def test_h4はジョブ名など(self):
        assert heading_level(tag("<h4>モンク</h4>")) == 3

    def test_見出しでなければNone(self):
        assert heading_level(tag("<p>本文</p>")) is None


class TestTableToMarkdown:
    def test_すべての行が空の列は消す(self):
        # 矢印の画像だけが入った列
        html = (
            "<table>"
            "<tr><th>変更前</th><th></th><th>変更後</th></tr>"
            "<tr><td>Lv51-79</td><td><img></td><td>Lv51-59</td></tr>"
            "</table>"
        )
        assert table_to_markdown(tag(html)) == "\n".join(
            ["| 変更前 | 変更後 |", "| --- | --- |", "| Lv51-79 | Lv51-59 |"]
        )


class TestSplitTable:
    def test_分けたそれぞれに見出しの行を付け直す(self):
        header = "| 名称 | 変更点 |\n| --- | --- |"
        rows = [f"| スキル{i} | {'あ' * 100} |" for i in range(30)]
        parts = split_table("\n".join([header, *rows]))
        assert len(parts) > 1
        for part in parts:
            assert part.startswith(header)
            assert len(part) <= MAX_CHARS


class TestWalker:
    def test_見出しの階層を記録する(self):
        walker = walk(
            '<h3 class="mdl-title__ancher">バトル関連</h3>'
            "<h3>アクション／特性において、以下の調整が行われます。</h3>"
            "<h4>モンク</h4><p>本文</p>"
        )
        assert walker.blocks[-1].headings == (
            "バトル関連",
            "アクション／特性において、以下の調整が行われます。",
            "モンク",
        )

    def test_大分類が変わったら前の中分類は消える(self):
        # 「バトル関連」の PvE の調整に、前の大分類の「その他」が残っていた不具合
        walker = walk(
            '<h3 class="mdl-title__ancher">イベント関連</h3><h2>その他</h2><p>A</p>'
            '<h3 class="mdl-title__ancher">バトル関連</h3><h3>項目</h3><p>B</p>'
        )
        assert walker.blocks[-1].headings == ("バトル関連", "項目")

    def test_見出しだけの項目も残す(self):
        # 「分解スキルの上限値が…」が消えていた不具合
        walker = walk(
            '<h3 class="mdl-title__ancher">アイテム関連</h3>'
            "<h3>分解スキルの上限値が 720 → 740 に引き上げられます。</h3>"
            "<h3>次の項目</h3><p>本文</p>"
        )
        contents = [b.content for b in walker.blocks]
        assert "分解スキルの上限値が 720 → 740 に引き上げられます。" in contents

    def test_最後の見出しだけの項目も残す(self):
        walker = walk('<h3 class="mdl-title__ancher">アイテム関連</h3><h3>最後の項目</h3>')
        assert [b.content for b in walker.blocks] == ["最後の項目"]

    def test_大分類と中分類だけの見出しは残さない(self):
        walker = walk('<h3 class="mdl-title__ancher">システム関連</h3><h2>システム全般</h2><h3>項目</h3><p>本文</p>')
        contents = [b.content for b in walker.blocks]
        assert "システム関連" not in contents
        assert "システム全般" not in contents