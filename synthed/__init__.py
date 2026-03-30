"""
SynthEd: Agent-Based Synthetic Educational Data Generation Platform

Combines TinyTroupe-inspired persona modeling with MiroFish-inspired
scalable simulation to generate behaviorally coherent synthetic
educational data for Open and Distance Learning (ODL) research.
"""

try:
    from importlib.metadata import version
    __version__ = version("synthed")
except Exception:
    # Fallback for development installs without metadata
    from setuptools_scm import get_version
    try:
        __version__ = get_version(root="..", relative_to=__file__)
    except Exception:
        __version__ = "0.0.0-dev"

__author__ = "Halis Aykut Cosgun"
