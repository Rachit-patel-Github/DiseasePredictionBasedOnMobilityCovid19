import math
import pytest

from src import seir_model


def test_probability_cap():
    """Probability of infectious traveler must not exceed 100% or 1.0 fraction."""
    # Create scenario where infected > population via monkeypatching SEIRModel
    class StubExtreme:
        def __init__(self, population, mobility_factor=1.0):
            self.N = population
            self.I = float(population * 2)  # more infected than population
            self.E = 0.0
            self.R = 0.0
            self.S = float(population) - self.I
        def run(self, days):
            return {'S':[self.S]*days,'E':[self.E]*days,'I':[self.I]*days,'R':[self.R]*days}
        def get_state(self):
            return {'susceptible': self.S, 'exposed': self.E, 'infected': self.I, 'recovered': self.R, 'total': self.N}

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(seir_model, 'SEIRModel', StubExtreme)
    try:
        res = seir_model.compute_traveler_impact(origin_population=1000, origin_mobility=50, dest_population=1000, dest_mobility=50, n_travelers=100)
        assert res['p_infectious_pct'] <= 100.0
        assert res['p_infectious'] <= 1.0
        assert math.isclose(res['p_infectious'], res['p_infectious_pct'] / 100.0, rel_tol=1e-9)
    finally:
        monkeypatch.undo()


def test_infection_cap():
    """Projected infections must not exceed destination population."""
    res = seir_model.compute_traveler_impact(origin_population=10000, origin_mobility=20, dest_population=5000, dest_mobility=10, n_travelers=1000000)
    assert res['expected_new_infections_30d'] <= res['population_destination']


def test_population_conservation():
    """Check S+E+I+R ≈ population in returned origin_state."""
    res = seir_model.compute_traveler_impact(origin_population=50000, origin_mobility=10, dest_population=100000, dest_mobility=10, n_travelers=1000)
    origin = res['origin_state']
    total = origin['susceptible'] + origin['exposed'] + origin['infected'] + origin['recovered']
    assert pytest.approx(total, rel=1e-6) == origin['population']


def test_edge_cases_zero_values():
    """Edge cases: zero infected origin, zero travelers, extremely high infected count."""
    # origin population zero
    res_zero_origin = seir_model.compute_traveler_impact(origin_population=0, origin_mobility=0, dest_population=1000, dest_mobility=0, n_travelers=100)
    assert res_zero_origin['p_infectious_pct'] == 0.0
    assert res_zero_origin['expected_infectious_travelers'] == 0.0

    # zero travelers
    res_zero_travelers = seir_model.compute_traveler_impact(origin_population=1000, origin_mobility=0, dest_population=1000, dest_mobility=0, n_travelers=0)
    assert res_zero_travelers['expected_infectious_travelers'] == 0.0
    assert res_zero_travelers['expected_new_infections_30d'] == 0.0

    # extremely high infected count handled by cap
    class StubExtreme2:
        def __init__(self, population, mobility_factor=1.0):
            self.N = population
            self.I = float(population * 10)
            self.E = 0.0
            self.R = 0.0
            self.S = float(population) - self.I
        def run(self, days):
            return {'S':[self.S]*days,'E':[self.E]*days,'I':[self.I]*days,'R':[self.R]*days}
        def get_state(self):
            return {'susceptible': self.S, 'exposed': self.E, 'infected': self.I, 'recovered': self.R, 'total': self.N}

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(seir_model, 'SEIRModel', StubExtreme2)
    try:
        res_extreme = seir_model.compute_traveler_impact(origin_population=1000, origin_mobility=100, dest_population=1000, dest_mobility=100, n_travelers=1000)
        assert res_extreme['p_infectious_pct'] <= 100.0
        assert res_extreme['expected_infectious_travelers'] <= 1000.0
    finally:
        monkeypatch.undo()