# Travel Risk Assessment with SEIR Model

An epidemiological modeling tool to assess infection spread risk from inter-state travel in India.

## Key Components

### SEIR Model
- `src/seir_model.py` - Implementation of a Susceptible-Exposed-Infectious-Recovered (SEIR) compartmental model
  - Accounts for state populations and mobility patterns
  - Models latent period (exposure to infectious)
  - Considers pre-symptomatic transmission
  - Projects outcomes over 30 days
  - Adjusts R0 based on mobility data

### Web Interface
- `src/app.py` - Flask web application that provides:
  - State selection for origin and destination
  - Number of travelers input
  - SEIR model state visualization
  - Travel impact projections
- `src/templates/index.html` - Interactive UI with:
  - SEIR compartment visualization
  - Population and mobility statistics
  - 30-day infection projections

### Data Sources
- `data/india_mobility_states.csv` - State-level mobility metrics
- `data/state_populations.csv` - State population data
- Historical death data (used for model training)

## Running Locally (Windows PowerShell)

```powershell
python -m venv venv; .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/app.py
```

Then open http://127.0.0.1:5000 in your browser.

## Model Details

The SEIR model simulates disease spread with four compartments:
- **S**usceptible: Population vulnerable to infection
- **E**xposed: Infected but not yet infectious
- **I**nfectious: Can transmit to others
- **R**ecovered: Immune after recovery

Key parameters:
- R0 (basic reproduction number): Adjusted by mobility data
- Latent period: Time from exposure to infectious
- Infectious period: Duration of infectiousness
- Initial conditions: Calibrated from recent data

The mobility data influences transmission by adjusting R0 - higher mobility leads to increased transmission potential.

## Usage Notes
- The model provides epidemiologically-grounded projections but should not be used as the sole input for policy decisions
- All parameters can be tuned based on specific disease characteristics
- Consider supplementing with:
  - Testing data
  - Vaccination coverage
  - Healthcare capacity
  - Age demographics
