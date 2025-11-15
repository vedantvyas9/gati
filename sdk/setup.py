"""Setup configuration for GATI SDK."""
from setuptools import setup, find_packages

# Read version from gati/version.py
import re
from pathlib import Path

version_file = Path(__file__).parent / "gati" / "version.py"
version_content = version_file.read_text() if version_file.exists() else ""
version_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', version_content)
__version__ = version_match.group(1) if version_match else "0.1.0"

setup(
    name="gati",
    version=__version__,
    description="SDK for tracking AI agent executions (LLM calls, tool usage, state) and sending events to a local backend",
    long_description=open("README.md").read() if Path("README.md").exists() else "",
    long_description_content_type="text/markdown",
    author="GATI Team",
    author_email="",
    url="https://github.com/gati/gati-sdk",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "requests",
        "typing-extensions",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)













