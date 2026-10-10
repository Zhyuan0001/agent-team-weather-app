"""架构约束静态测试（SPEC §5）。

core/ 为纯逻辑层：不得 import PyQt5 或 requests；
providers/services 不得 import PyQt5。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "weather_app"


def _imports(path: pathlib.Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def _py_files(subdir: str):
    return sorted((PKG / subdir).glob("*.py"))


@pytest.mark.parametrize("path", _py_files("core"), ids=lambda p: p.name)
def test_core_has_no_gui_or_network_imports(path):
    imported = _imports(path)
    assert "PyQt5" not in imported, f"{path.name} 违规 import PyQt5"
    assert "requests" not in imported, f"{path.name} 违规 import requests"


@pytest.mark.parametrize("subdir", ["providers", "services"])
def test_providers_services_have_no_gui_imports(subdir):
    for path in _py_files(subdir):
        assert "PyQt5" not in _imports(path), f"{subdir}/{path.name} 违规 import PyQt5"
