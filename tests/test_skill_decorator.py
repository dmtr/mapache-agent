"""Tests for the @target decorator and ToolMeta/ParamMeta introspection."""

from __future__ import annotations

import sys
import types

import pytest

from mapache_agent.skill import ParamMeta, ToolMeta, target


# ── helpers ───────────────────────────────────────────────────────────────────


def _fresh_module(name: str = "_test_skill") -> types.ModuleType:
    """Return a fresh module with no _TARGETS so tests don't bleed into each other."""
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


# ── basic registration ────────────────────────────────────────────────────────


def test_target_registers_in_module():
    mod = _fresh_module()

    def greet(name: str) -> str:
        """Say hello."""
        return f"Hello, {name}"

    greet.__module__ = mod.__name__
    target(greet)

    assert hasattr(mod, "_TARGETS")
    assert "greet" in mod._TARGETS


def test_target_returns_function_unmodified():
    def my_fn(x: int) -> int:
        """Double x."""
        return x * 2

    result = target(my_fn)
    assert result is my_fn
    assert result(3) == 6


# ── ToolMeta fields ───────────────────────────────────────────────────────────


def test_tool_meta_name():
    mod = _fresh_module("_tm_name")

    def do_thing() -> str:
        """Do the thing."""
        return "done"

    do_thing.__module__ = mod.__name__
    target(do_thing)
    assert mod._TARGETS["do_thing"].name == "do_thing"


def test_tool_meta_description_first_line():
    mod = _fresh_module("_tm_desc")

    def do_thing() -> str:
        """First line description.

        Second paragraph ignored.
        """
        return "done"

    do_thing.__module__ = mod.__name__
    target(do_thing)
    assert mod._TARGETS["do_thing"].description == "First line description."


def test_tool_meta_no_docstring():
    mod = _fresh_module("_tm_nodoc")

    def no_doc():
        pass

    no_doc.__module__ = mod.__name__
    target(no_doc)
    assert mod._TARGETS["no_doc"].description == ""


# ── ParamMeta fields ──────────────────────────────────────────────────────────


def test_param_required_and_type():
    mod = _fresh_module("_pm_req")

    def fn(file: str, count: int) -> str:
        """A function.

        :param file: The file path
        :param count: How many times
        """
        return ""

    fn.__module__ = mod.__name__
    target(fn)
    params = mod._TARGETS["fn"].params
    assert len(params) == 2

    file_p = params[0]
    assert file_p.name == "file"
    assert file_p.json_type == "string"
    assert file_p.required is True
    assert file_p.description == "The file path"

    count_p = params[1]
    assert count_p.name == "count"
    assert count_p.json_type == "integer"
    assert count_p.required is True
    assert count_p.description == "How many times"


def test_param_optional_with_default():
    mod = _fresh_module("_pm_opt")

    def fn(path: str, encoding: str = "utf-8") -> str:
        """Read file.

        :param path: File path
        :param encoding: File encoding
        """
        return ""

    fn.__module__ = mod.__name__
    target(fn)
    params = mod._TARGETS["fn"].params

    enc = params[1]
    assert enc.name == "encoding"
    assert enc.required is False
    assert enc.default == "utf-8"


def test_param_no_annotation_defaults_to_string():
    mod = _fresh_module("_pm_notype")

    def fn(x) -> str:
        """Fn."""
        return ""

    fn.__module__ = mod.__name__
    target(fn)
    assert mod._TARGETS["fn"].params[0].json_type == "string"


@pytest.mark.parametrize(
    "annotation, expected",
    [
        (str, "string"),
        (int, "integer"),
        (float, "number"),
        (bool, "boolean"),
    ],
)
def test_annotation_mapping(annotation, expected):
    mod = _fresh_module(f"_pm_ann_{expected}")

    def fn(x) -> str:
        """Fn."""
        return ""

    import inspect

    fn.__module__ = mod.__name__
    fn.__annotations__ = {"x": annotation}
    target(fn)
    assert mod._TARGETS["fn"].params[0].json_type == expected


# ── fn stored correctly ───────────────────────────────────────────────────────


def test_tool_meta_stores_callable():
    mod = _fresh_module("_tm_callable")

    def multiply(a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b

    multiply.__module__ = mod.__name__
    target(multiply)
    meta = mod._TARGETS["multiply"]
    assert isinstance(meta, ToolMeta)
    assert meta.fn(3, 4) == 12


# ── multiple targets in one module ───────────────────────────────────────────


def test_multiple_targets_accumulate():
    mod = _fresh_module("_mt_multi")

    def alpha() -> str:
        """Alpha."""
        return "a"

    def beta() -> str:
        """Beta."""
        return "b"

    alpha.__module__ = mod.__name__
    beta.__module__ = mod.__name__
    target(alpha)
    target(beta)
    assert set(mod._TARGETS.keys()) == {"alpha", "beta"}
