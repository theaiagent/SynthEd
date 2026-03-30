from setuptools import setup, find_packages

# Read version from single source of truth
version = {}
with open("synthed/__init__.py") as f:
    for line in f:
        if line.startswith("__version__"):
            exec(line, version)
            break

setup(
    name="synthed",
    version=version["__version__"],
    description="Agent-Based Synthetic Educational Data Generation for ODL Research",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Halis Aykut Cosgun",
    author_email="h.aykut.cosgun@gmail.com",
    url="https://github.com/theaiagent/SynthEd",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "openai>=1.0.0",
    ],
    extras_require={
        "dev": ["pytest", "pytest-cov", "ruff"],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
    ],
)
