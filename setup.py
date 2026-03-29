from setuptools import setup, find_packages

setup(
    name="synthed",
    version="0.1.0",
    description="Agent-Based Synthetic Educational Data Generation for ODL Research",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Aykut Gençkaptan",
    author_email="theaiagent@gmail.com",
    url="https://github.com/theaiagent/SynthEd",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "openai>=1.0.0",
    ],
    extras_require={
        "dev": ["pytest", "jupyter", "matplotlib", "pandas"],
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
