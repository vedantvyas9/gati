"""
GATI - Local-first observability for AI agents

This setup.py packages the GATI SDK for tracking AI agent executions.

When installed via pip, users get:
- Python SDK with @observe() decorator
- Auto-instrumentation for LangChain/LangGraph
- CLI tool for setup instructions
- Anonymous telemetry (installation ID, event counts only)

Dashboard requires cloning the GitHub repo and running docker-compose.
"""
from setuptools import setup, find_packages
from pathlib import Path
import re

# Read version from sdk/gati/version.py
version_file = Path(__file__).parent / "sdk" / "gati" / "version.py"
version_content = version_file.read_text() if version_file.exists() else ""
version_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', version_content)
__version__ = version_match.group(1) if version_match else "0.1.1"

# Read the root README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="gati",
    version=__version__,
    description="Local-first observability for AI agents. Track LLM calls, tool usage, and agent state.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Vedant Vyas",
    author_email="vedant.p.vyas@gmail.com",
    url="https://github.com/vedantvyas9/gati",
    project_urls={
        "Documentation": "https://github.com/vedantvyas9/gati#readme",
        "Source": "https://github.com/vedantvyas9/gati",
        "Tracker": "https://github.com/vedantvyas9/gati/issues",
    },

    # Package discovery - find all packages in sdk/
    packages=find_packages(where="sdk"),
    package_dir={"": "sdk"},

    # Include package data
    include_package_data=True,
    package_data={
        "gati": [
            "py.typed",
            "docker-compose.yml",
        ],
    },

    # Python version requirement
    python_requires=">=3.9",

    # Core dependencies
    install_requires=[
        "requests>=2.31.0",
        "typing-extensions>=4.7.0",
    ],

    # Optional dependencies
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.7.0",
            "mypy>=1.5.0",
            "ruff>=0.0.280",
            "types-requests>=2.31.0",
        ],
        "langchain": [
            "langchain>=0.1.0",
            "langchain-core>=0.1.0",
        ],
        "langgraph": [
            "langgraph>=0.0.1",
        ],
        "backend": [
            "fastapi>=0.109.0",
            "uvicorn[standard]>=0.27.0",
            "psycopg2-binary>=2.9.9",
            "sqlalchemy>=2.0.25",
            "python-dotenv>=1.0.0",
        ],
    },

    # CLI entry point
    entry_points={
        "console_scripts": [
            "gati=gati.cli.main:main",
        ],
    },

    # PyPI classifiers
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Framework :: FastAPI",
        "Framework :: AsyncIO",
    ],

    keywords="ai agents llm observability tracing langchain langgraph monitoring dashboard",
    license="MIT",

    zip_safe=False,
)
