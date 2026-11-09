"""llm.py のテスト。本物の AI は呼ばず、偽物の会社を使う。"""

import pytest

from app.llm import LLMUnavailableError, RetryableError, generate, get_provider


class FakeProvider:
    """モデルごとに決めた答えかエラーを返す、偽物の会社。"""

    name = "fake"
    models = ["first", "second"]

    def __init__(self, results: dict):
        self.results = results
        self.called = []

    def complete(self, model, prompt):
        self.called.append(model)
        result = self.results[model]
        if isinstance(result, Exception):
            raise result
        return result


def test_first_model_answers_and_second_is_not_tried():
    p = FakeProvider({"first": "答え1", "second": "答え2"})
    assert generate("質問", provider=p) == ("答え1", "first")
    assert p.called == ["first"]


def test_retryable_error_moves_to_next_model():
    p = FakeProvider({"first": RetryableError("first: 503"), "second": "答え2"})
    assert generate("質問", provider=p) == ("答え2", "second")
    assert p.called == ["first", "second"]


def test_all_models_busy_raises_unavailable():
    p = FakeProvider({"first": RetryableError("first: 503"), "second": RetryableError("second: 429")})
    with pytest.raises(LLMUnavailableError, match="first: 503、second: 429"):
        generate("質問", provider=p)


def test_other_errors_are_raised_without_trying_next_model():
    p = FakeProvider({"first": ValueError("キーが正しくない"), "second": "答え2"})
    with pytest.raises(ValueError):
        generate("質問", provider=p)
    assert p.called == ["first"]


def test_models_argument_overrides_provider_models():
    p = FakeProvider({"first": "答え1", "second": "答え2"})
    assert generate("質問", models=["second"], provider=p) == ("答え2", "second")
    assert p.called == ["second"]


def test_unknown_provider_name_is_error():
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        get_provider("unknown")