from setuptools import setup, find_packages

setup(
    name="job-search-tool",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "python-jobspy>=1.1.75",
        "httpx>=0.27.0",
        "anthropic>=0.40.0",
        "click>=8.1.0",
        "thefuzz[speedup]>=0.22.0",
        "python-Levenshtein>=0.25.0",
    ],
    entry_points={
        "console_scripts": [
            "jobsearch=src.cli:cli",
        ],
    },
)
