from setuptools import setup, find_packages

setup(
    name="langchain_summarizer",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "langchain",
        "langchain-community",
        "openai",
        "python-dotenv",
        "tiktoken",
        "rouge-score"
    ]
) 