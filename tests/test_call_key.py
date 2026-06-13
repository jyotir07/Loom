"""Cache/dedup key derivation must be stable and order-insensitive on params."""

from loom._call_key import call_key


def _k(**kw):
    base = dict(provider="openai", modality="text", model="gpt-4o-mini", prompt="hi", params=None)
    base.update(kw)
    return call_key(**base)


def test_same_inputs_same_key():
    assert _k() == _k()


def test_param_order_does_not_change_key():
    a = _k(params={"a": 1, "b": 2, "c": 3})
    b = _k(params={"c": 3, "b": 2, "a": 1})
    assert a == b


def test_nested_param_order_does_not_change_key():
    a = _k(params={"nested": {"a": 1, "b": 2}})
    b = _k(params={"nested": {"b": 2, "a": 1}})
    assert a == b


def test_different_prompts_different_keys():
    assert _k(prompt="a") != _k(prompt="b")


def test_different_models_different_keys():
    assert _k(model="m1") != _k(model="m2")


def test_different_providers_different_keys():
    assert _k(provider="openai") != _k(provider="anthropic")


def test_param_value_changes_key():
    assert _k(params={"x": 1}) != _k(params={"x": 2})


def test_empty_and_none_params_match():
    assert _k(params=None) == _k(params={})
