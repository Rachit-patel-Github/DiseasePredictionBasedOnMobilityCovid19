import os
import pickle
import pandas as pd
import numpy as np
from flask import Flask, render_template, request, jsonify
try:
    # Preferred package import (works when running via tests or as a package)
    from src.seir_model import compute_traveler_impact
except ModuleNotFoundError:
    # Fallback for executing this file directly: add project root to sys.path
    import sys, os
    this_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(this_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    # Try local import (module visible as seir_model when running as script)
    from seir_model import compute_traveler_impact
import re

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(ROOT, 'data')
MODEL_DIR = os.path.join(ROOT, 'models')
MOBILITY_CSV = os.path.join(DATA_DIR, 'india_mobility_states.csv')
MODEL_PATH = os.path.join(MODEL_DIR, 'random_forest_deaths.pkl')
POP_CSV = os.path.join(DATA_DIR, 'state_populations.csv')

app = Flask(__name__, 
          template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
          static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# Load resources
if os.path.exists(MODEL_PATH):
    with open(MODEL_PATH, 'rb') as f:
        model_bundle = pickle.load(f)
    model = model_bundle['model']
    feature_cols = model_bundle['feature_cols']
else:
    model = None
    feature_cols = []

# Normalize state names to a canonical form used across CSVs and UI
def normalize_state(name: str) -> str:
    if name is None:
        return ''
    s = str(name).strip()
    # common replacements
    s = s.replace('&', 'and')
    s = re.sub(r"\s+", ' ', s)
    s = s.strip().lower()

    # Known aliases mapping (lowercase keys)
    aliases = {
        'aandn islands': 'Andaman and Nicobar Islands',
        'andaman and nicobar islands islands': 'Andaman and Nicobar Islands',
        'jandk (ut)': 'Jammu and Kashmir',
        'jammu & kashmir': 'Jammu and Kashmir',
        'jammu and kashmir': 'Jammu and Kashmir',
        'dadra and nagar haveli & daman and diu': 'Dadra and Nagar Haveli and Daman and Diu',
        'daman and diu': 'Dadra and Nagar Haveli and Daman and Diu',
        'nandk': 'Jammu and Kashmir'
    }

    if s in aliases:
        return aliases[s]

    # Title-case as default canonical form
    return ' '.join([w.capitalize() for w in s.split(' ')])

mob_df = pd.read_csv(MOBILITY_CSV) if os.path.exists(MOBILITY_CSV) else pd.DataFrame()
pop_df = pd.read_csv(POP_CSV) if os.path.exists(POP_CSV) else pd.DataFrame()
pop_map = {}
if not pop_df.empty:
    # normalize state names and build lookup
    pop_df['state'] = pop_df['state'].astype(str).str.strip()
    pop_df['population'] = pd.to_numeric(pop_df['population'], errors='coerce')
    # create a normalized state column for reliable lookups
    pop_df['state_norm'] = pop_df['state'].apply(normalize_state)
    pop_map = dict(zip(pop_df['state_norm'], pop_df['population']))

# Helper: normalize mobility values for prediction (same cleaning used in modeling_pipeline)

def clean_mob_row(row):
    out = {}
    for c in feature_cols:
        val = row.get(c, '')
        if pd.isna(val):
            out[c] = 0.0
        else:
            s = str(val)
            s = re.sub(r"[^0-9\-]", "", s)
            try:
                out[c] = float(s)
            except:
                out[c] = 0.0
    return pd.Series(out)


# normalize_state already defined above; no duplicate here
# Compute risk estimate using SEIR model for travelers from origin->destination
def compute_expected_infections(origin, destination, travelers=1):
    # Find rows
    mob = mob_df.copy()
    # Ensure mobility dataframe has a normalized column
    if 'state_norm' not in mob.columns:
        mob['state_norm'] = mob['state'].astype(str).str.strip().apply(normalize_state)

    origin_norm = normalize_state(origin)
    dest_norm = normalize_state(destination)

    o_row = mob[mob['state_norm'] == origin_norm]
    d_row = mob[mob['state_norm'] == dest_norm]
    if o_row.empty or d_row.empty:
        raise ValueError('Origin or destination not found in mobility dataset')

    o_features = clean_mob_row(o_row.iloc[0])
    d_features = clean_mob_row(d_row.iloc[0])
    
    # Get populations
    # Lookup populations using normalized keys
    pop_o = pop_map.get(origin_norm)
    pop_d = pop_map.get(dest_norm)
    # fallback to mean population if missing
    if pop_o is None or np.isnan(pop_o):
        pop_o = np.nanmean(list(pop_map.values())) if pop_map else 1.0
    if pop_d is None or np.isnan(pop_d):
        pop_d = np.nanmean(list(pop_map.values())) if pop_map else 1.0

    # Get workplace mobility directly from the DataFrame
    origin_mob = float(o_row['workplace_mobility'].iloc[0])
    dest_mob = float(d_row['workplace_mobility'].iloc[0])

    # Use SEIR model to compute impact
    # Allow caller to pass projection days via flask request context if provided
    # Default to 30 days
    projection_days = 30
    try:
        # If used in an API call, request.json may have projection_days; handle safely
        from flask import request as _request
        if _request and _request.is_json:
            pd = _request.get_json().get('projection_days')
            if pd is not None:
                projection_days = int(pd)
    except Exception:
        projection_days = 30

    results = compute_traveler_impact(
        origin_population=int(pop_o),
        origin_mobility=origin_mob,
        dest_population=int(pop_d),
        dest_mobility=dest_mob,
        n_travelers=travelers,
        days_to_simulate=projection_days
    )

    # Format response
    return {
        'population_origin': int(pop_o),
        'population_destination': int(pop_d),
        'origin_state': results['origin_state'],
        'dest_state': results['dest_state'],
        'origin_name': origin,
        'dest_name': destination,
        'p_infectious': results.get('p_infectious', 0.0),
        'p_infectious_pct': results.get('p_infectious_pct', 0.0),
        'projection_days': projection_days,
        'transmission_multiplier_origin': results['origin_mobility_factor'],
        'transmission_multiplier_dest': results['dest_mobility_factor'],
        'expected_infectious_travelers': results['expected_infectious_travelers'],
        'expected_new_infections_30d': results.get('expected_new_infections_30d', 0.0),
        'model_based_new_infections_30d': results.get('model_based_new_infections_30d', 0.0)
    }

@app.route('/', methods=['GET', 'POST'])
def index():
    states = sorted(mob_df['state'].unique()) if not mob_df.empty else []
    result = None
    error = None
    if request.method == 'POST':
        origin = request.form.get('origin')
        destination = request.form.get('destination')
        travelers = int(request.form.get('travelers', '1'))
        try:
            result = compute_expected_infections(origin, destination, travelers)
        except Exception as e:
            error = str(e)
    return render_template('index.html', states=states, result=result, error=error)


@app.route('/dashboard', methods=['GET'])
def dashboard():
    """Render the richer dashboard page that uses the JS visualizations.

    This page expects the `states` list to populate the origin/destination
    selects. It's available at /dashboard for interactive testing.
    """
    states = sorted(mob_df['state'].unique()) if not mob_df.empty else []
    return render_template('dashboard.html', states=states)


@app.route('/mobility-trends/<state>', methods=['GET'])
def mobility_trends(state):
    """Return mobility time-series traces for a given state as Plotly traces (JSON array).

    The front-end calls this and passes the returned array directly to Plotly.newPlot(...).
    """
    df = mob_df.copy()
    if df.empty:
        return jsonify({'error': 'mobility dataset not available'}), 500

    if 'state_norm' not in df.columns:
        df['state_norm'] = df['state'].astype(str).str.strip().apply(normalize_state)

    state_norm = normalize_state(state)
    rows = df[df['state_norm'] == state_norm]
    if rows.empty:
        return jsonify({'error': 'state not found'}), 404

    # ensure date column is parsed and sorted
    if 'date' in rows.columns:
        rows = rows.copy()
        rows['date_parsed'] = pd.to_datetime(rows['date'], errors='coerce')
        rows = rows.sort_values('date_parsed')
        x = rows['date_parsed'].dt.strftime('%Y-%m-%d').tolist()
    else:
        x = list(range(len(rows)))

    traces = []
    for col, name in [('workplace_mobility', 'Workplace'), ('parks_mobility', 'Parks'), ('residential_mobility', 'Residential')]:
        if col in rows.columns:
            y = rows[col].astype(float).fillna(0).tolist()
            traces.append({'x': x, 'y': y, 'type': 'scatter', 'mode': 'lines', 'name': name})

    return jsonify(traces)


@app.route('/risk-heatmap', methods=['GET'])
def risk_heatmap():
    """Return a simple state-to-state risk heatmap as a single Plotly heatmap trace wrapped in an array.

    The heatmap here is a lightweight estimate computed from workplace mobility values.
    """
    df = mob_df.copy()
    if df.empty:
        return jsonify({'error': 'mobility dataset not available'}), 500

    if 'state_norm' not in df.columns:
        df['state_norm'] = df['state'].astype(str).str.strip().apply(normalize_state)

    # pick the latest available entry per state (if date exists)
    if 'date' in df.columns:
        df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
        latest = df.sort_values('date_parsed').groupby('state_norm', as_index=False).last()
    else:
        latest = df.groupby('state_norm', as_index=False).last()

    states = latest['state_norm'].tolist()
    # normalize workplace mobility to [0,1]
    vals = pd.to_numeric(latest['workplace_mobility'], errors='coerce').fillna(0).astype(float)
    maxv = vals.max() if not vals.empty else 1.0
    if maxv == 0:
        maxv = 1.0

    matrix = []
    for vo in vals:
        row = []
        for vd in vals:
            # simple symmetric risk estimate based on product of mobilities
            score = (vo * vd) / (maxv * maxv) * 100.0
            row.append(score)
        matrix.append(row)

    trace = {'z': matrix, 'x': states, 'y': states, 'type': 'heatmap', 'colorscale': 'YlOrRd'}
    return jsonify([trace])
@app.route('/api/predict', methods=['POST'])
def api_predict():
    data = request.get_json()
    origin = data.get('origin')
    destination = data.get('destination')
    travelers = int(data.get('travelers', 1))
    res = compute_expected_infections(origin, destination, travelers)
    return jsonify(res)

if __name__ == '__main__':
    # If run directly, print a sample mapping and a small test
    try:
        print('Available states:', sorted(mob_df['state'].unique()))
    except Exception as e:
        print('Error listing available states:', e)

    # Run Flask app with extra error visibility
    try:
        app.run(host='127.0.0.1', port=5000, debug=True)
    except Exception as e:
        import traceback
        print('Flask failed to start:')
        traceback.print_exc()
        # keep console open to allow user to copy the traceback when running interactively
        try:
            input('Press Enter to exit...')
        except Exception:
            pass