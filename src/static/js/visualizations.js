// Visualization handling for disease prediction dashboard

// Plot objects for updating
let plots = {
    predictionSummary: null,
    originSeirPlot: null,
    destSeirPlot: null,
    originMobilityPlot: null,
    destMobilityPlot: null,
    riskHeatmap: null
};

// Initialize dashboard
// Helper to load Plotly dynamically if it's not already present (robust against CDN blocking)
function ensurePlotly() {
    return new Promise((resolve) => {
        if (window.Plotly) return resolve(window.Plotly);
        const script = document.createElement('script');
        script.src = 'https://cdn.plot.ly/plotly-2.24.1.min.js';
        script.onload = () => resolve(window.Plotly);
        script.onerror = (e) => {
            console.error('Failed to load Plotly library', e);
            resolve(null);
        };
        document.head.appendChild(script);
    });
}

// Initialize dashboard once DOM is ready and Plotly is available
document.addEventListener('DOMContentLoaded', function() {
    ensurePlotly().then(() => {
        // Load initial heatmap
        fetchRiskHeatmap();

        // Setup form handler
        const form = document.getElementById('predictionForm');
    if (form) {
        form.addEventListener('submit', handlePredictionSubmit);

        // Inject projection period dropdown above submit button (if not present)
        if (!document.getElementById('projectionDays')) {
            const projectionWrapper = document.createElement('div');
            projectionWrapper.className = 'mb-3';
            projectionWrapper.innerHTML = `\
                <label for="projectionDays" class="block text-sm font-medium text-gray-700 mb-1">Projection Period (Days)</label>\
                <select id="projectionDays" class="block w-full rounded-md border-gray-300 shadow-sm">\
                    <option value="5">5</option>\
                    <option value="10">10</option>\
                    <option value="15">15</option>\
                    <option value="20">20</option>\
                    <option value="25">25</option>\
                    <option value="30" selected>30</option>\
                </select>`;
            // find submit button and insert before it
            const submit = form.querySelector('button[type="submit"]');
            if (submit && submit.parentNode) {
                submit.parentNode.insertBefore(projectionWrapper, submit);
            } else {
                form.appendChild(projectionWrapper);
            }
        }
    }
    
    // Setup state change handlers
    ['originState', 'destState'].forEach(id => {
        const select = document.getElementById(id);
        if (select) {
            select.addEventListener('change', () => {
                updateMobilityPlots(id);
                // Auto-fetch new results when state changes
                fetchPredictionData();
            });
        }
    });
    // React to travelers and projection changes to auto-update results
    const travelersInput = document.getElementById('travelers');
    if (travelersInput) {
        travelersInput.addEventListener('input', () => {
            // debounce small inputs
            clearTimeout(travelersInput._timer);
            travelersInput._timer = setTimeout(() => fetchPredictionData(), 250);
        });
    }
    const projectionSelect = document.getElementById('projectionDays');
    if (projectionSelect) {
        projectionSelect.addEventListener('change', () => fetchPredictionData());
    }
    // Auto-initialize selections and plots so the dashboard shows graphs immediately
    try {
        const originSelect = document.getElementById('originState');
        const destSelect = document.getElementById('destState');
        // If selects exist but no value chosen, pick the first real option (skip empty placeholder)
        if (originSelect && !originSelect.value && originSelect.options.length > 1) {
            originSelect.selectedIndex = 1;
        }
        if (destSelect && !destSelect.value && destSelect.options.length > 1) {
            // pick second option if different from origin when possible
            destSelect.selectedIndex = (originSelect && originSelect.selectedIndex === 1 && destSelect.options.length > 2) ? 2 : 1;
        }

        if (originSelect && destSelect && originSelect.value && destSelect.value) {
            // draw mobility plots and fetch prediction to populate all charts
            updateMobilityPlots('originState');
            updateMobilityPlots('destState');
            // small delay to allow plots to initialize
            setTimeout(() => {
                try { fetchPredictionData(); } catch (e) { console.error('Auto fetch failed', e); }
            }, 350);
        }
    } catch (e) {
        console.error('Auto-init failed', e);
    }
    });
});

async function handlePredictionSubmit(e) {
    e.preventDefault();
    
    const originState = document.getElementById('originState').value;
    const destState = document.getElementById('destState').value;
    const travelers = document.getElementById('travelers').value;
    
    if (!originState || !destState) {
        showError('Please select both origin and destination states.');
        return;
    }
    
    try {
        // Show loading state
        document.getElementById('results').style.display = 'none';
        showLoading(true);
        const projectionDays = document.getElementById('projectionDays') ? parseInt(document.getElementById('projectionDays').value) : 30;
        
        const response = await fetch('/api/predict', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                origin: originState,
                destination: destState,
                travelers: parseInt(travelers),
                projection_days: projectionDays
            })
        });
        
        const data = await response.json();
        if (data.error) {
            showError(data.error);
        } else {
            updateVisualizations(data);
            document.getElementById('results').style.display = 'block';
        }
    } catch (error) {
        showError('Failed to get prediction results.');
        console.error('Prediction error:', error);
    } finally {
        showLoading(false);
    }
}

// Centralized fetcher used by change handlers and form submit
async function fetchPredictionData() {
    const originState = document.getElementById('originState') ? document.getElementById('originState').value : '';
    const destState = document.getElementById('destState') ? document.getElementById('destState').value : '';
    const travelers = document.getElementById('travelers') ? document.getElementById('travelers').value : 1;
    if (!originState || !destState) return;
    try {
        showLoading(true);
        const projectionDays = document.getElementById('projectionDays') ? parseInt(document.getElementById('projectionDays').value) : 30;
        const resp = await fetch('/api/predict', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ origin: originState, destination: destState, travelers: parseInt(travelers), projection_days: projectionDays })
        });
        const data = await resp.json();
        if (data.error) showError(data.error);
        else updateVisualizations(data);
    } catch (err) {
        console.error('Auto-fetch error', err);
    } finally {
        showLoading(false);
    }
}

function updateVisualizations(data) {
    // Ensure results container is visible before attempting to draw plots.
    const resultsDiv = document.getElementById('results');
    if (resultsDiv) resultsDiv.style.display = 'block';

    // Update prediction summary div with formatted and responsive Tailwind layout
    const summaryDiv = document.getElementById('predictionSummary');
    const projDays = data.projection_days || data.projection_days === 0 ? data.projection_days : 30;
    const format = (v) => (typeof v === 'number' ? v.toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 }) : v);

    // Create infection projection graph
    const baseValue = data.expected_new_infections_30d || 0;
    const timePoints = [5, 10, 15, 20, 25, 30];
    const projectedValues = timePoints.map(days => baseValue * (days/30));
    
    Plotly.newPlot('infectionProjectionPlot', [{
        x: timePoints,
        y: projectedValues,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'Projected Infections',
        line: {
            color: '#ff0000',
            width: 3,
            shape: 'spline'
        },
        marker: {
            size: 10,
            color: '#ff0000',
            symbol: 'circle'
        }
    }], {
        title: {
            text: 'Projected New Infections Over Time',
            font: { 
                size: 18,
                color: '#111827'
            }
        },
        xaxis: {
            title: 'Projection Period (Days)',
            tickmode: 'array',
            tickvals: timePoints,
            ticktext: timePoints.map(d => d + ' days'),
            gridcolor: '#E5E7EB',
            linecolor: '#D1D5DB'
        },
        yaxis: {
            title: 'Number of New Infections',
            gridcolor: '#E5E7EB',
            linecolor: '#D1D5DB',
            tickformat: '.3f'
        },
        height: 500,
        margin: { t: 50, r: 30, l: 80, b: 50 },
        paper_bgcolor: 'white',
        plot_bgcolor: 'white',
        hovermode: 'x unified',
        hoverlabel: {
            bgcolor: 'white',
            font: { size: 14 }
        },
        showlegend: false
    });

    // Try to resize/relayout plots after drawing to ensure they appear
    try {
        if (window.Plotly && Plotly.Plots && typeof Plotly.Plots.resize === 'function') {
            ['infectionProjectionPlot','originSeirPlot','destSeirPlot','originMobilityPlot','destMobilityPlot','riskHeatmap']
                .forEach(id => {
                    const el = document.getElementById(id);
                    if (el) {
                        try { Plotly.Plots.resize(el); } catch(e) { /* ignore */ }
                    }
                });
        }
    } catch (e) {
        console.warn('Plotly resize failed', e);
    }

    // Determine probability color
    const p = Number(data.p_infectious_pct || data.p_infectious * 100 || 0);
    let pClass = 'text-green-600';
    if (p > 20.0) pClass = 'text-red-600';
    else if (p >= 5.0) pClass = 'text-yellow-500';

    if (summaryDiv) {
        summaryDiv.innerHTML = `
            <div class="grid gap-4 grid-cols-1 lg:grid-cols-3">
                <div class="shadow-md rounded-2xl p-4 bg-white transition-all duration-300">
                    <h6 class="text-sm font-semibold mb-2">Origin State</h6>
                    <div class="text-xs text-gray-500 mb-2">${data.origin_name || 'Origin'}</div>
                    <div class="text-sm">Population: <span class="font-medium">${format(data.population_origin)}</span></div>
                    <div class="text-sm">Mobility Factor: <span class="font-medium">${Number(data.transmission_multiplier_origin).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}</span></div>
                </div>
                <div class="shadow-md rounded-2xl p-4 bg-white transition-all duration-300">
                    <h6 class="text-sm font-semibold mb-2">Destination State</h6>
                    <div class="text-xs text-gray-500 mb-2">${data.dest_name || 'Destination'}</div>
                    <div class="text-sm">Population: <span class="font-medium">${format(data.population_destination)}</span></div>
                    <div class="text-sm">Mobility Factor: <span class="font-medium">${Number(data.transmission_multiplier_dest).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}</span></div>
                </div>
                <div id="impactCard" class="shadow-md rounded-2xl p-4 bg-white transition-all duration-300 opacity-0 transform translate-y-2">
                    <h6 class="text-sm font-semibold mb-2">Travel Impact Assessment</h6>
                    <div class="text-sm mb-2">Probability of Infectious Traveler: <span id="probText" class="font-bold ${pClass}">${format(p)}%</span></div>
                    <div class="text-sm mb-2">Expected Infectious Travelers: <span class="font-bold">${format(data.expected_infectious_travelers)}</span></div>
                    <div class="text-sm">Projected New Infections (${projDays} days): <span class="font-bold">${format(data.expected_new_infections_30d)}</span></div>
                </div>
            </div>
        `;

        // Trigger smooth reveal
        const card = document.getElementById('impactCard');
        if (card) {
            requestAnimationFrame(() => {
                card.classList.remove('opacity-0', 'translate-y-2');
                card.classList.add('opacity-100');
            });
        }
    }
    
    // Update SEIR plots
    if (data.originSeir) {
        // ensure container visible then plot
        const osp = document.getElementById('originSeirPlot'); if (osp) osp.style.display = 'block';
        Plotly.newPlot('originSeirPlot', data.originSeir);
    }
    if (data.destSeir) {
        const dsp = document.getElementById('destSeirPlot'); if (dsp) dsp.style.display = 'block';
        Plotly.newPlot('destSeirPlot', data.destSeir);
    }
    
    // Update mobility plots
    if (data.originMobility) {
        const omp = document.getElementById('originMobilityPlot'); if (omp) omp.style.display = 'block';
        Plotly.newPlot('originMobilityPlot', data.originMobility);
    }
    if (data.destMobility) {
        const dmp = document.getElementById('destMobilityPlot'); if (dmp) dmp.style.display = 'block';
        Plotly.newPlot('destMobilityPlot', data.destMobility);
    }
}

async function updateMobilityPlots(stateType) {
    const state = document.getElementById(stateType).value;
    if (!state) return;
    
    try {
        const response = await fetch(`/mobility-trends/${state}`);
        const data = await response.json();
        
        if (data.error) {
            console.error('Error fetching mobility data:', data.error);
            return;
        }
        
        const plotId = `${stateType.replace('State', '')}MobilityPlot`;
        // Always attempt to (re)draw the mobility plot for the given element.
        // Some callers previously relied on `plots[plotId]` truthiness which
        // prevented the first draw because `plots` entries were initialized to null.
        // Draw and then store the plot data for future reference.
        try {
            Plotly.newPlot(plotId, data);
            plots[plotId] = data;
        } catch (err) {
            console.error('Plotly failed to render mobility plot', plotId, err);
        }
    } catch (error) {
        console.error('Failed to update mobility plot:', error);
    }
}

async function fetchRiskHeatmap() {
    try {
        const response = await fetch('/risk-heatmap');
        // Only try to parse JSON when response is ok and content-type is JSON
        if (!response.ok) {
            console.warn('Risk heatmap endpoint returned', response.status);
            return;
        }
        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
            console.warn('Risk heatmap did not return JSON, skipping plot');
            return;
        }
        const data = await response.json();
        if (data.error) {
            console.error('Error fetching heatmap data:', data.error);
            return;
        }
        try {
            Plotly.newPlot('riskHeatmap', data);
            plots.riskHeatmap = data;
        } catch (err) {
            console.error('Failed to render risk heatmap', err);
        }
    } catch (error) {
        console.error('Failed to load risk heatmap:', error);
    }
}

function showLoading(isLoading) {
    // Implementation of loading state visualization
    const buttons = document.querySelectorAll('button[type="submit"]');
    buttons.forEach(button => {
        button.disabled = isLoading;
        if (isLoading) {
            button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';
        } else {
            button.innerHTML = 'Analyze Risk';
        }
    });
}

function showError(message) {
    const resultsDiv = document.getElementById('results');
    if (resultsDiv) {
        resultsDiv.style.display = 'block';
        resultsDiv.innerHTML = `
            <div class="alert alert-danger" role="alert">
                <h4 class="alert-heading">Error</h4>
                <p>${message}</p>
            </div>
        `;
    } else {
        alert(message);
    }
}