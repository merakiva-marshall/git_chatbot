from setuptools import setup, find_packages

setup(
    name="git_chatbot",
    version="0.1",
    packages=find_packages(),
    package_dir={"": "src"},
    python_requires=">=3.10",
    install_requires=[
        'streamlit',
        'anthropic',
        'python-dotenv',
        'qdrant-client',
        'plotly',
        'pandas',
        'networkx>=3.1',
        'astroid>=3.0.1',
        'libcst>=1.1.0',
        'tree-sitter>=0.20.1',
        'pydantic>=2.5.2',
        'scipy>=1.11.4',
        'numpy>=1.24.0',
        'spacy>=3.7.2',
        'joblib>=1.3.2',
        'typing-extensions>=4.8.0'
    ]
)