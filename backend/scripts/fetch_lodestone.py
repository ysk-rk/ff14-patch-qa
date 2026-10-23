"""ロードストーンから FF14 黄金のレガシー（7.x）のパッチノートを取得して HTML のまま保存する。"""

import time
from pathlib import Path

import requests

BASE_URL = "https://jp.finalfantasyxiv.com"

# パッチノート一覧ページ（/lodestone/special/patchnote_log/）に載っている 7.x のパッチノート
PATCH_NOTES = {
    "7.0": "/lodestone/topics/detail/1e6473f5a6210bc7f81a6f41507095e2b939fa5d/",
    "7.01": "/lodestone/topics/detail/a82bc67258479464c0faaff9985eebf1397d0140/",
    "7.05": "/lodestone/topics/detail/686ea89c48ef4339ac88e91400b2376c41f027d0/",
    "7.1": "/lodestone/topics/detail/323be12f6a94adb359375e016130e9e1a200e753/",
    "7.11": "/lodestone/topics/detail/657c541763dae98d262d5646d006fc3fa013e296/",
    "7.15": "/lodestone/topics/detail/dfbc510152d601b725c4fbeab61e5fe71dc025d9/",
    "7.16": "/lodestone/topics/detail/3b18b92b9567ead9ddc8106e52578876e702585f/",
    "7.18": "/lodestone/topics/detail/f380ffbdbf05f89f175d9f09c7c5b4ba53e5c2bc/",
    "7.2": "/lodestone/topics/detail/272e3ae76b2663ef84b4d5833441597813e29d75/",
    "7.21": "/lodestone/topics/detail/e03febd75af40827183323fa1f290ec463e3fe7f/",
    "7.25": "/lodestone/topics/detail/19d958632633fb19a71fa75d67326a743e050453/",
    "7.3": "/lodestone/topics/detail/46aaec3b778d1f8382ea83fd5c7bf090c5d79d7d/",
    "7.31": "/lodestone/topics/detail/0a8b8b687d7cf216f6e5dc7ef4f17e55c65458f5/",
    "7.35": "/lodestone/topics/detail/b9a065a686da7f371c82365151861aded5ef3ccf/",
    "7.38": "/lodestone/topics/detail/0a73edcd0a99bf4881f7cb75f41c86f47fb882b8/",
    "7.4": "/lodestone/topics/detail/93e0209ee311f3a2ea55d605c2c8b447e9637bad/",
    "7.41": "/lodestone/topics/detail/97d89805adac177c2fc5e8fcbaf19778f53bd639/",
    "7.45": "/lodestone/topics/detail/bec3740cb24eaaa05a2779dfb32f5e8d472930e3/",
    "7.5": "/lodestone/topics/detail/072b03a01b057707a9b9b6476c898c9ed3c7c4a4/",
    "7.51": "/lodestone/topics/detail/786582567848b6373ddd0063aab675bd63e4f4ff/",
    "7.55": "/lodestone/topics/detail/dfb99538aaee5e47079411b07356ef3c4a820486/",
    "7.56": "/lodestone/topics/detail/67caf3b6b5e0ee7569afb5ec8bdcae5113f9df49/",
    "7.57": "/lodestone/topics/detail/a2f39b00b7c38bee37fb169ac916f8e70c5b3dea/",
}

# サイトに負荷をかけないよう、1ページごとにあける秒数
WAIT_SECONDS = 5

# 誰がアクセスしているか分かるようにする（ポートフォリオ用の個人プロジェクト）
HEADERS = {"User-Agent": "ff14-patch-qa (personal portfolio project; one-time fetch)"}

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "lodestone"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for version, path in PATCH_NOTES.items():
        output = OUTPUT_DIR / f"{version}.html"

        # 一度保存したページは二度と取りに行かない
        if output.exists():
            print(f"  {version:<5}  保存済みのためスキップ")
            continue

        res = requests.get(BASE_URL + path, headers=HEADERS, timeout=30)
        res.raise_for_status()
        res.encoding = "utf-8"
        output.write_text(res.text, encoding="utf-8")

        print(f"  {version:<5}  {len(res.text):>8} 文字  保存しました")
        time.sleep(WAIT_SECONDS)

    print(f"完了: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()