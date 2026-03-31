from setuptools import setup, find_packages

setup(
    name="synthed",
    use_scm_version={
        "fallback_version": "0.0.0-dev",
        "version_scheme": "guess-next-dev",
        "local_scheme": "node-and-date",
    },
    setup_requires=["setuptools_scm"],
    description="Agent-Based Synthetic Educational Data Generation for ODL Research",
    long_description=open("README.md", encoding="utf-8").read(),
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
        "uuid_utils>=0.9.0,<1.0.0",
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
