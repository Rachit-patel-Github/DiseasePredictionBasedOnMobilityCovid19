"""SEIR model implementation for state-level COVID transmission predictions.

This module provides a deterministic SEIR model and helper functions used by
the dashboard. The `compute_traveler_impact` function computes travel-related
metrics using these formulas:

- Probability of Infectious Traveler (percent):
    (Infected_origin / Population_origin) * Mobility_factor_origin * 100
- Expected Infectious Travelers:
    Number_of_travelers * (Probability_of_Infectious_Traveler / 100)
- Projected New Infections (30 days):
    Expected_Infectious_Travelers * (INFECTION_RATE_PER_DAY * 30) * dest_mobility_factor

All outputs are rounded to 3 decimals and probability values are capped to
logical bounds (≤ 100%).
"""

import numpy as np
import math
from dataclasses import dataclass
from typing import Dict, Optional

# Constants
INFECTION_RATE_PER_DAY = 0.008  # 0.8% per day

def cap(x, min_val=0.0, max_val=1e12):
    """Clamp x between min_val and max_val."""
    return max(min(x, max_val), min_val)

@dataclass
class SEIRParams:
    """SEIR model parameters"""
    # Basic reproduction number (R0) - adjusted by mobility
    r0_base: float = 3.5  # Higher R0 for more aggressive spread
    # Latent period (1/alpha) - days from exposure to infectious
    latent_period: float = 2.0  # Shorter latent period for faster spread
    # Infectious period (1/gamma) - days infectious
    infectious_period: float = 10.0  # Longer infectious period
    # Initial conditions as fractions of N
    initial_exposed_fraction: float = 0.03  # 3% initial exposure
    initial_infected_fraction: float = 0.02  # 2% initial infection
    initial_recovered_fraction: float = 0.40  # Lower immunity level (40%)

    @property
    def alpha(self) -> float:
        """Rate of progression from exposed to infectious"""
        return 1.0 / self.latent_period

    @property
    def gamma(self) -> float:
        """Recovery rate"""
        return 1.0 / self.infectious_period

class SEIRModel:
    """Simple SEIR model implementation."""
    
    def __init__(
        self,
        population: int,
        params: Optional[SEIRParams] = None,
        mobility_factor: float = 1.0
    ):
        self.N = population
        self.params = params or SEIRParams()
        self.mobility_factor = mobility_factor
        
        # Compute initial state
        # Use floats for compartments to avoid truncation errors
        self.I = float(self.N * self.params.initial_infected_fraction)
        self.E = float(self.N * self.params.initial_exposed_fraction)
        self.R = float(self.N * self.params.initial_recovered_fraction)
        self.S = float(self.N) - self.I - self.E - self.R
        
        # Effective R0 adjusted by mobility
        self.r0_effective = self.params.r0_base * self.mobility_factor
        
        # Derived transmission rate beta = R0 * gamma
        self.beta = self.r0_effective * self.params.gamma
    
    def step(self, day: int = 0, dt: float = 1.0):
        """Advance the model by dt time units (default 1 day).

        day: integer day index used for seasonal forcing.
        """
        S, E, I, R = self.S, self.E, self.I, self.R
        N = float(self.N)
        beta, alpha, gamma = self.beta, self.params.alpha, self.params.gamma

        # Enhanced seasonal variation with stronger effect
        day_of_year = day % 365
        # Stronger seasonal effect during winter months (assuming day 0 is January 1)
        winter_boost = 1.5 if (day_of_year < 90 or day_of_year > 270) else 1.0
        seasonal_factor = (1.0 + 0.6 * np.cos(2 * np.pi * day_of_year / 365)) * winter_boost
        beta_seasonal = beta * seasonal_factor

        # Dynamic immunity waning based on time since recovery
        base_waning_rate = 0.005  # Base rate 0.5% per day
        waning_rate = base_waning_rate * (1.0 + 0.5 * np.sin(2 * np.pi * day_of_year / 365))

        # Population density effect
        density_factor = min(2.0, math.sqrt(N / 1000000.0))  # Increases with sqrt of population in millions
        
        # Enhanced SEIR dynamics with density-dependent transmission
        contact_rate = beta_seasonal * density_factor * S * I / N if N > 0 else 0.0
        
        # Note: removed stochastic superspreader factor for deterministic behavior
        # (keeps model deterministic for testing and reproducibility)
        
        # Modified SEIR equations with enhanced dynamics
        dSdt = -contact_rate + waning_rate * R
        dEdt = contact_rate - alpha * E
        dIdt = alpha * E - gamma * I
        dRdt = gamma * I - waning_rate * R

        # Update state with Euler integration (floats)
        self.S = max(0.0, S + dSdt * dt)
        self.E = max(0.0, E + dEdt * dt)
        self.I = max(0.0, I + dIdt * dt)
        self.R = max(0.0, R + dRdt * dt)

        # Ensure conservation of population by scaling if small numerical drift
        total = self.S + self.E + self.I + self.R
        if total <= 0:
            # reset to initial proportions if degenerate
            self.S = N
            self.E = 0.0
            self.I = 0.0
            self.R = 0.0
        elif abs(total - N) > 1e-6:
            scale = N / total
            self.S *= scale
            self.E *= scale
            self.I *= scale
            self.R *= scale
    
    def run(self, days: int = 30) -> Dict[str, np.ndarray]:
        """Run model for specified number of days"""
        S = np.zeros(days, dtype=float)
        E = np.zeros(days, dtype=float)
        I = np.zeros(days, dtype=float)
        R = np.zeros(days, dtype=float)

        for t in range(days):
            S[t] = self.S
            E[t] = self.E
            I[t] = self.I
            R[t] = self.R
            # pass current day to step for seasonal forcing
            self.step(day=t, dt=1.0)
        
        return {
            'S': S,
            'E': E,
            'I': I,
            'R': R,
            'total': S + E + I + R
        }
    
    def get_state(self) -> Dict[str, int]:
        """Get current state as a dict"""
        return {
            'susceptible': self.S,
            'exposed': self.E,
            'infected': self.I,
            'recovered': self.R,
            'total': self.N
        }

def compute_traveler_impact(
    origin_population: int,
    origin_mobility: float,  # Workplace mobility percentage from CSV
    dest_population: int,
    dest_mobility: float,    # Workplace mobility percentage from CSV
    n_travelers: int = 1,
    death_rate_proxy: float = 0.01,
    days_to_simulate: int = 30
) -> Dict:
    """Compute travel-impact metrics using explicit formulas.

    Formulas implemented:
    - Probability of Infectious Traveler (percent) =
        (Infected_origin / Population_origin) * Mobility_factor_origin * 100
    - Expected Infectious Travelers =
        Number_of_travelers * (Probability_of_Infectious_Traveler / 100)
    - Projected New Infections (30 days) =
        Expected_Infectious_Travelers * (INFECTION_RATE_PER_DAY * 30) * dest_mobility_factor

    Returns a dictionary with these keys (rounded to 3 decimals):
    - origin_state: {susceptible, exposed, infected, recovered, population}
    - dest_state: {susceptible, exposed, infected, recovered, population}
    - p_infectious: probability as fraction (0-1)
    - p_infectious_pct: probability as percent (0-100)
    - expected_infectious_travelers: count
    - expected_new_infections_30d: rule-based projection
    - model_based_new_infections_30d: simulation-based sanity check
    - origin_mobility_factor, dest_mobility_factor, population_origin, population_destination
    """
    # Calculate mobility factor directly from workplace mobility percentage
    def calculate_mobility_factor(workplace_mobility: float) -> float:
        # workplace_mobility is percentage change from baseline
        # Convert to decimal: e.g., 110% -> 1.1, -20% -> 0.8
        return cap(1.0 + (workplace_mobility / 100.0), min_val=0.1, max_val=2.0)
    
    # Apply mobility factors from CSV data
    origin_factor = calculate_mobility_factor(origin_mobility)
    dest_factor = calculate_mobility_factor(dest_mobility)

    # Create and run origin SEIR model to estimate prevalence
    origin_model = SEIRModel(population=origin_population, mobility_factor=origin_factor)
    origin_results = origin_model.run(days_to_simulate)
    origin_state = origin_model.get_state()

    # Ensure compartment conservation at origin (S+E+I+R == population)
    origin_S = float(origin_state['susceptible'])
    origin_E = float(origin_state['exposed'])
    origin_I = float(origin_state['infected'])
    origin_R = float(origin_state['recovered'])
    total_origin = origin_S + origin_E + origin_I + origin_R
    if origin_population > 0 and abs(total_origin - origin_population) > 1e-6:
        origin_S += (origin_population - total_origin)

    # Compute Probability of Infectious Traveler (percentage)
    # Formula: (Infected_origin / Population_origin) * Mobility_factor_origin * 100
    prob_infectious_pct = 0.0
    if origin_population > 0:
        prob_infectious_pct = (origin_I / float(origin_population)) * origin_factor * 100.0
    # Cap at 100%
    prob_infectious_pct = cap(prob_infectious_pct, min_val=0.0, max_val=100.0)

    # Expected Infectious Travelers = Number_of_travelers * (Probability_of_Infectious_Traveler / 100)
    expected_infectious_travelers = float(n_travelers) * (prob_infectious_pct / 100.0)

    # Projected New Infections (30 days)
    # Formula: Expected_Infectious_Travelers * (Infection_Rate_per_day * 30) * dest_factor
    projected_new_infections_30d = expected_infectious_travelers * (INFECTION_RATE_PER_DAY * 30.0) * dest_factor

    # Ensure projected infections do not exceed destination population
    projected_new_infections_30d = max(0.0, min(float(dest_population), projected_new_infections_30d))

    # Run baseline and seeded destination simulations for optional comparison (keep deterministic)
    dest_model_base = SEIRModel(population=dest_population, mobility_factor=dest_factor)
    dest_results_base = dest_model_base.run(days_to_simulate)

    # Seed destination with expected infectious travelers (fractional allowed)
    dest_model_seeded = SEIRModel(population=dest_population, mobility_factor=dest_factor)
    seed_cases = max(0.0, min(float(expected_infectious_travelers), dest_model_seeded.S))
    dest_model_seeded.I += seed_cases
    dest_model_seeded.S -= seed_cases
    dest_results_seeded = dest_model_seeded.run(days_to_simulate)

    # Calculate new infections from model difference as a sanity check
    def calc_total_new_infections_from_models(base, seeded):
        base_total = float(base['I'][-1] + base['R'][-1])
        seeded_total = float(seeded['I'][-1] + seeded['R'][-1])
        return max(0.0, seeded_total - base_total)

    model_based_new_infections = calc_total_new_infections_from_models(dest_results_base, dest_results_seeded)

    # Final result values (rounded to 3 decimals for display consistency)
    prob_infectious_pct = round(prob_infectious_pct, 3)
    p_infectious = round(prob_infectious_pct / 100.0, 3)
    expected_infectious_travelers = round(expected_infectious_travelers, 3)
    projected_new_infections_30d = round(projected_new_infections_30d, 3)
    model_based_new_infections = round(float(model_based_new_infections), 3)
    
    return {
        # Current compartment states (floats)
        'origin_state': {
            'susceptible': round(origin_S, 3),
            'exposed': round(origin_E, 3),
            'infected': round(origin_I, 3),
            'recovered': round(origin_R, 3),
            'population': int(origin_population)
        },
        'dest_state': {
            'susceptible': round(dest_model_seeded.S, 3),
            'exposed': round(dest_model_seeded.E, 3),
            'infected': round(dest_model_seeded.I, 3),
            'recovered': round(dest_model_seeded.R, 3),
            'population': int(dest_population)
        },
        # Probability as fraction (0-1) and as percent for display
    'p_infectious': float(p_infectious),
    'p_infectious_pct': float(prob_infectious_pct),
    # Expected infectious travelers (count)
    'expected_infectious_travelers': float(expected_infectious_travelers),
    # Projected new infections for 30 days (rule-based) and model-based sanity check
    'expected_new_infections_30d': float(projected_new_infections_30d),
    'model_based_new_infections_30d': float(model_based_new_infections),
        # Mobility factors
        'origin_mobility_factor': float(origin_factor),
        'dest_mobility_factor': float(dest_factor),
        'population_origin': int(origin_population),
        'population_destination': int(dest_population),
        'transmission_multiplier_origin': origin_factor,
        'transmission_multiplier_dest': dest_factor
    }


def compute_traveler_time_series(
    origin_population: int,
    origin_mobility: float,
    dest_population: int,
    dest_mobility: float,
    infected_travelers: float = 1.0,
    days_checkpoints: Optional[list] = None,
    days_to_simulate: int = 30,
) -> Dict:
    """Simulate destination epidemic with and without a specified number of infected travelers

    Returns incremental new infections caused by the seeded infected travelers at the
    requested checkpoint days. Uses deterministic SEIR runs (float compartments).
    """
    if days_checkpoints is None:
        days_checkpoints = [5, 10, 15, 20, 25, 30]

    # Use the same mobility factor calculation as in compute_traveler_impact
    def calculate_mobility_factor(workplace_mobility: float) -> float:
        return max(0.1, min(2.0, 1.0 + (workplace_mobility / 100.0)))
    
    origin_factor = calculate_mobility_factor(origin_mobility)
    dest_factor = calculate_mobility_factor(dest_mobility)

    # Run baseline dest model
    dest_base = SEIRModel(population=dest_population, mobility_factor=dest_factor)
    base_results = dest_base.run(days_to_simulate)

    # Run seeded model
    dest_seeded = SEIRModel(population=dest_population, mobility_factor=dest_factor)
    seed = max(0.0, min(float(infected_travelers), dest_seeded.S))
    dest_seeded.I += seed
    dest_seeded.S -= seed
    seeded_results = dest_seeded.run(days_to_simulate)

    # Compute cumulative infected (I + R) at each day and delta
    checkpoints = {}
    max_day = days_to_simulate
    for d in sorted(set(days_checkpoints)):
        if d <= 0:
            checkpoints[d] = 0.0
            continue
        idx = min(d - 1, max_day - 1)
        base_cum = float(base_results['I'][idx] + base_results['R'][idx])
        seeded_cum = float(seeded_results['I'][idx] + seeded_results['R'][idx])
        checkpoints[d] = max(0.0, seeded_cum - base_cum)

    return {
        'origin_population': origin_population,
        'dest_population': dest_population,
        'infected_travelers_seeded': float(infected_travelers),
        'checkpoints_new_infections': checkpoints,
        'dest_mobility_factor': dest_factor,
        'origin_mobility_factor': origin_factor
    }