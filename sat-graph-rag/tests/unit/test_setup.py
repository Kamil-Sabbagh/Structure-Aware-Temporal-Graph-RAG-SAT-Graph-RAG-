"""Tests to validate the project setup."""

import sys
import importlib


def test_python_version():
    """Ensure Python 3.10+ is being used."""
    assert sys.version_info >= (3, 10), "Python 3.10+ required"


def test_dependencies_installed():
    """Ensure all required packages are installed."""
    required = [
        "requests",
        "bs4",
        "neo4j",
        "pydantic",
        "fastapi",
        "openai",
    ]
    missing = []
    for pkg in required:
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing.append(pkg)
    
    if missing:
        raise AssertionError(f"Missing packages: {', '.join(missing)}")

