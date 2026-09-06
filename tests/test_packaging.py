"""
The packaging metadata points at things that exist.

``[project.scripts]`` named ``src.server.main:run_server``; there is no
``src/server/main.py``, so the installed ``legal-assistant-server`` command
raised ``ModuleNotFoundError`` on first use.
"""

from __future__ import annotations

import importlib
import pathlib

import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _scripts() -> dict[str, str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["scripts"]


class TestConsoleScripts:
    def test_every_script_target_imports_and_is_callable(self):
        for name, target in _scripts().items():
            module_name, _, attr = target.partition(":")
            module = importlib.import_module(module_name)
            assert callable(getattr(module, attr)), f"{name} -> {target}"


class TestDeclaredDependencies:
    def test_no_dependency_that_nothing_imports(self):
        """
        Every runtime dependency in pyproject is imported somewhere under src/ or
        main.py. Stripe, Twilio, python-jose, passlib, jinja2 and python-dateutil
        were declared and never imported; this keeps the list honest.
        """
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        # distribution name -> import name(s)
        import_names = {
            "langgraph": ["langgraph"],
            "langchain-core": ["langchain_core"],
            "langchain-openai": ["langchain_openai"],
            "langchain-anthropic": ["langchain_anthropic"],
            "mcp": ["mcp"],
            "fastapi": ["fastapi"],
            "uvicorn": ["uvicorn"],
            "pydantic": ["pydantic"],
            "pydantic-settings": ["pydantic_settings"],
            "pinecone-client": ["pinecone"],
            "pdfplumber": ["pdfplumber"],
            "PyMuPDF": ["fitz"],
            "python-docx": ["docx"],
            "sqlalchemy": ["sqlalchemy"],
            "asyncpg": ["asyncpg", "postgresql+asyncpg"],
            "httpx": ["httpx", "TestClient"],  # used by the FastAPI/Starlette test client
            "python-dotenv": ["dotenv", "env_file"],  # pydantic-settings reads .env
            "click": ["click"],
        }
        source = "\n".join(
            p.read_text(encoding="utf-8")
            for p in [
                *(ROOT / "src").rglob("*.py"),
                ROOT / "main.py",
                *(ROOT / "tests").rglob("*.py"),
            ]
        )
        for dep in data["project"]["dependencies"]:
            dist = dep.split(">")[0].split("[")[0].split("=")[0].strip()
            assert dist in import_names, f"{dist}: add its import name to this test"
            assert any(n in source for n in import_names[dist]), (
                f"{dist} is declared but never used"
            )
