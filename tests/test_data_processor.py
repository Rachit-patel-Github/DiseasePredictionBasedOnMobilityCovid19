"""Tests for data processing module."""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from src.data_processor import MobilityDataProcessor

@pytest.fixture
def data_processor():
    """Create a data processor instance for testing."""
    return MobilityDataProcessor()

def test_get_all_states(data_processor):
    """Test retrieval of all states."""
    states = data_processor.get_all_states()
    assert isinstance(states, list)
    assert len(states) > 0
    assert all(isinstance(state, str) for state in states)
    assert 'Maharashtra' in states  # Check for a known state

def test_get_state_population(data_processor):
    """Test state population retrieval."""
    population = data_processor.get_state_population('Maharashtra')
    assert isinstance(population, int)
    assert population > 0
    
    # Test non-existent state
    population = data_processor.get_state_population('NonExistentState')
    assert population == 0

def test_get_latest_mobility(data_processor):
    """Test latest mobility data retrieval."""
    mobility = data_processor.get_latest_mobility('Maharashtra')
    assert isinstance(mobility, dict)
    assert 'workplace_mobility' in mobility
    assert 'residential_mobility' in mobility
    assert 'last_updated' in mobility
    
    # Check value ranges
    assert -100 <= mobility['workplace_mobility'] <= 100
    assert -100 <= mobility['residential_mobility'] <= 100
    
    # Test date format
    datetime.strptime(mobility['last_updated'], '%Y-%m-%d')

def test_get_mobility_trends(data_processor):
    """Test mobility trends retrieval."""
    trends = data_processor.get_mobility_trends('Maharashtra', days=7)
    assert isinstance(trends, dict)
    assert all(key in trends for key in ['dates', 'workplace_mobility', 'residential_mobility'])
    assert len(trends['dates']) <= 7
    assert len(trends['workplace_mobility']) == len(trends['dates'])
    assert len(trends['residential_mobility']) == len(trends['dates'])

def test_update_mobility_data(data_processor):
    """Test mobility data update functionality."""
    # Create test data
    dates = pd.date_range(
        end=datetime.now(),
        periods=5,
        freq='D'
    )
    test_data = pd.DataFrame({
        'date': [d.strftime('%Y-%m-%d') for d in dates],
        'state': ['Maharashtra'] * 5,
        'workplace_mobility': np.random.uniform(-100, 100, 5),
        'residential_mobility': np.random.uniform(-100, 100, 5)
    })
    
    # Test update
    assert data_processor.update_mobility_data(test_data)
    
    # Verify update
    latest = data_processor.get_latest_mobility('Maharashtra')
    assert latest['last_updated'] == dates[-1].strftime('%Y-%m-%d')

def test_invalid_update_data(data_processor):
    """Test handling of invalid update data."""
    # Missing required columns
    invalid_data = pd.DataFrame({
        'date': ['2024-01-01'],
        'state': ['Maharashtra']
    })
    assert not data_processor.update_mobility_data(invalid_data)
    
    # Invalid data type
    assert not data_processor.update_mobility_data("not a dataframe")