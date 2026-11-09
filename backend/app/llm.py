"""AI（LLM）を呼ぶ部分。会社ごとの呼び方の違いを、ここに閉じ込める。

使う会社は .env の LLM_PROVIDER で決める（書かなければ gemini）。
別の会社を足すときは、GeminiProvider と同じ形（name、models、complete）のクラスを作り、PROVIDERS に足す。
"""

import os

# 答えのランダムさ。0 にすると、同じ質問には毎回なるべく同じ答えを返す
TEMPERATURE = 0

# 混雑や回数制限など、別のモデルなら通る可能性があるエラーのコード
RETRYABLE_CODES = {429, 500, 503}

# LLM_PROVIDER が書かれていないときに使う会社
DEFAULT_PROVIDER = "gemini"


class LLMUnavailableError(Exception):
    """すべてのモデルが混雑などで使えなかったときのエラー。"""


class RetryableError(Exception):
    """別のモデルなら通る可能性があるエラー。各社のクラスが、自分の会社のエラーをこれに直して出す。"""


class GeminiProvider:
    """Gemini API。無料枠で使えるモデルを、先頭から順に試す。"""

    name = "gemini"
    models = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]

    def __init__(self) -> None:
        # Gemini のライブラリは、使うときに初めて読み込む（自動テストでは入れていないため）
        from google import genai
        from google.genai import errors, types

        self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self._errors = errors
        self._types = types

    def complete(self, model: str, prompt: str) -> str:
        try:
            response = self._client.models.generate_content(
                model=model,
                contents=prompt,
                config=self._types.GenerateContentConfig(temperature=TEMPERATURE),
            )
        except self._errors.APIError as e:
            if e.code in RETRYABLE_CODES:
                raise RetryableError(f"{model}: {e.code}") from e
            raise
        return response.text


PROVIDERS = {GeminiProvider.name: GeminiProvider}

# 一度作った会社のクラスを使い回す
_providers: dict = {}


def get_provider(name: str | None = None):
    """会社の名前（省略時は LLM_PROVIDER）から、その会社のクラスを作って返す。"""
    name = name or os.environ.get("LLM_PROVIDER", DEFAULT_PROVIDER)
    if name not in PROVIDERS:
        raise ValueError(f"LLM_PROVIDER が正しくありません: {name}（使えるもの: {', '.join(PROVIDERS)}）")
    if name not in _providers:
        _providers[name] = PROVIDERS[name]()
    return _providers[name]


def generate(prompt: str, models: list[str] | None = None, provider=None) -> tuple[str, str]:
    """models（省略時はその会社の models）を先頭から順に試し、(回答, 使ったモデル名) を返す。"""
    provider = provider or get_provider()
    failures = []
    for model in models or provider.models:
        try:
            return provider.complete(model, prompt), model
        except RetryableError as e:
            failures.append(str(e))
    raise LLMUnavailableError("、".join(failures))