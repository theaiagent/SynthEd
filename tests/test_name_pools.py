"""Tests for name_pools module."""

import numpy as np
import pytest

from synthed.agents.name_pools import (
    select_name, select_country_context, _POOLS, _COUNTRY_CONTEXTS,
)


class TestNamePoolConstants:
    def test_all_country_contexts_have_pools(self):
        """Every country_context in _COUNTRY_CONTEXTS has a non-empty pool."""
        for ctx in _COUNTRY_CONTEXTS:
            assert ctx in _POOLS
            assert len(_POOLS[ctx]) > 0

    def test_all_pools_have_sufficient_names(self):
        """Each NamePool has at least 20 names per category."""
        for ctx, pools in _POOLS.items():
            for pool in pools:
                assert len(pool.male_first) >= 20, f"{pool.region_label} male_first too small"
                assert len(pool.female_first) >= 20, f"{pool.region_label} female_first too small"
                assert len(pool.last_names) >= 20, f"{pool.region_label} last_names too small"

    def test_name_pool_is_frozen(self):
        """NamePool instances are immutable."""
        pool = _POOLS[_COUNTRY_CONTEXTS[0]][0]
        with pytest.raises(AttributeError):
            pool.region_label = "modified"

    def test_four_country_contexts(self):
        """Exactly 4 country contexts exist."""
        assert len(_COUNTRY_CONTEXTS) == 4


class TestSelectName:
    def test_returns_string_pair(self):
        rng = np.random.default_rng(42)
        first, last = select_name(rng, "male", "developed_economy")
        assert isinstance(first, str) and len(first) > 0
        assert isinstance(last, str) and len(last) > 0

    def test_deterministic_with_seed(self):
        r1 = select_name(np.random.default_rng(42), "female", "developing_economy")
        r2 = select_name(np.random.default_rng(42), "female", "developing_economy")
        assert r1 == r2

    def test_all_contexts_work(self):
        rng = np.random.default_rng(42)
        for ctx in _COUNTRY_CONTEXTS:
            first, last = select_name(rng, "male", ctx)
            assert isinstance(first, str) and len(first) > 0

    def test_unknown_context_falls_back(self):
        """Unknown country_context falls back gracefully, not crash."""
        rng = np.random.default_rng(42)
        first, last = select_name(rng, "male", "unknown_context")
        assert isinstance(first, str) and len(first) > 0

    def test_both_genders(self):
        rng = np.random.default_rng(42)
        m_first, _ = select_name(rng, "male", "developed_economy")
        f_first, _ = select_name(np.random.default_rng(42), "female", "developed_economy")
        # Both should return valid strings (may or may not be different)
        assert isinstance(m_first, str) and isinstance(f_first, str)


class TestSelectCountryContext:
    def test_returns_valid_context(self):
        rng = np.random.default_rng(42)
        ctx = select_country_context(rng)
        assert ctx in _COUNTRY_CONTEXTS

    def test_deterministic(self):
        c1 = select_country_context(np.random.default_rng(99))
        c2 = select_country_context(np.random.default_rng(99))
        assert c1 == c2

