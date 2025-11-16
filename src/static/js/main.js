// Main JavaScript file for disease prediction app

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('predictionForm');
    const resultsDiv = document.getElementById('results');
    const mobilityDiv = document.getElementById('mobilityData');
    let mobilityData = {};

    // Load initial mobility data
    fetchMobilityData();

    // Form submission handler
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const originState = document.getElementById('originState').value;
        const destState = document.getElementById('destState').value;
        const travelers = document.getElementById('travelers').value;

        if (!originState || !destState) {
            showError('Please select both origin and destination states.');
            return;
        }

        const originMobility = mobilityData[originState]?.workplace_mobility || 0;
        const destMobility = mobilityData[destState]?.workplace_mobility || 0;

        try {
            const response = await fetch('/predict', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    originState,
                    destState,
                    travelers: parseInt(travelers),
                    originMobility,
                    destMobility
                })
            });

            const data = await response.json();

            if (data.error) {
                showError(data.error);
            } else {
                showResults(data);
            }
        } catch (error) {
            showError('Failed to get prediction. Please try again.');
            console.error('Prediction error:', error);
        }
    });

    // State selection change handlers
    ['originState', 'destState'].forEach(id => {
        document.getElementById(id).addEventListener('change', updateMobilityDisplay);
    });

    async function fetchMobilityData() {
        try {
            const response = await fetch('/mobility-data');
            mobilityData = await response.json();
            updateMobilityDisplay();
        } catch (error) {
            console.error('Failed to fetch mobility data:', error);
            showError('Failed to load mobility data. Please refresh the page.');
        }
    }

    function updateMobilityDisplay() {
        const originState = document.getElementById('originState').value;
        const destState = document.getElementById('destState').value;

        let html = '<h5 class="mb-3">Current Mobility Data</h5>';

        if (originState) {
            const originData = mobilityData[originState] || {};
            html += createMobilityInfo('Origin', originState, originData);
        }

        if (destState) {
            const destData = mobilityData[destState] || {};
            html += createMobilityInfo('Destination', destState, destData);
        }

        mobilityDiv.innerHTML = html;
    }

    function createMobilityInfo(label, state, data) {
        return `
            <div class="mobility-info">
                <h5>${label}: ${state}</h5>
                <div>Workplace Mobility: 
                    <span class="mobility-value">${data.workplace_mobility?.toFixed(1) || 'N/A'}%</span>
                </div>
                <div>Last Updated: 
                    <span class="mobility-value">${data.last_updated || 'N/A'}</span>
                </div>
            </div>
        `;
    }

    function showResults(data) {
        const infections = Math.round(data.prediction.new_infections_30d);
        let riskLevel, alertClass;

        if (infections < 100) {
            riskLevel = 'Low';
            alertClass = 'alert-success';
        } else if (infections < 1000) {
            riskLevel = 'Moderate';
            alertClass = 'alert-warning';
        } else {
            riskLevel = 'High';
            alertClass = 'alert-danger';
        }

        // Show prediction summary
        const summaryDiv = document.getElementById('predictionSummary');
        summaryDiv.innerHTML = `
            <div class="alert ${alertClass} mb-4">
                <h4 class="alert-heading">Risk Assessment</h4>
                <p class="mb-1">Risk Level: <strong>${riskLevel}</strong></p>
                <p class="mb-1">Estimated new infections over 30 days: <strong>${infections.toLocaleString()}</strong></p>
                <p class="mb-0">Expected infectious travelers: <strong>${Math.round(data.prediction.expected_infectious_travelers).toLocaleString()}</strong></p>
            </div>
        `;

        // Show all visualization sections
        document.getElementById('results').style.display = 'block';
        
        // Update visualizations with the new data
        if (typeof updateVisualizations === 'function') {
            updateVisualizations(data.prediction);
        }
    }

    function showError(message) {
        resultsDiv.innerHTML = `<strong>Error:</strong> ${message}`;
        resultsDiv.className = 'alert alert-danger';
        resultsDiv.style.display = 'block';
    }
});