(function() {
    // Global variables for map and interactions
    var map = null;
    var mapTileLayer = null;
    var marker = null;
    var polyline = null;
    var animationFrameId = null;
    var resizeObserver = null;

    // Initialize map with optimized settings
    function initMap() {
        try {
            // Create map with options
            map = L.map('map', {
                preferCanvas: true,
                wheelPxPerZoomLevel: 100,
                maxBoundsViscosity: 1.0,
                minZoom: 4,
                maxZoom: 8,
                bounceAtZoomLimits: true,
                maxBounds: [
                    [6.2325, 68.1766],  // Southwest
                    [35.6745, 97.4025]  // Northeast
                ],
                fadeAnimation: true,
                zoomAnimation: true,
                markerZoomAnimation: true,
                trackResize: true,
                renderer: L.canvas()
            });

            map.setView([20.5937, 78.9629], 5);

            // Add tile layer
            mapTileLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
                subdomains: 'abcd',
                maxZoom: 8,
                minZoom: 4,
                keepBuffer: 8,
                updateWhenIdle: true,
                updateWhenZooming: true,
                noWrap: true,
                className: 'map-tile'
            });

            mapTileLayer.addTo(map);

            // Setup map components
            setupMapListeners();
            loadStateMarkers();
            setupResizeObserver();
            handleLoadingOverlay();

            return map;
        } catch (error) {
            console.error('Error initializing map:', error);
            return null;
        }
    }

    function setupMapListeners() {
        mapTileLayer.on('loading', function() {
            var debugEl = document.getElementById('map-debug');
            if (debugEl) debugEl.innerText = 'Loading tiles...';
        });
        
        mapTileLayer.on('load', function() {
            var debugEl = document.getElementById('map-debug');
            if (debugEl) debugEl.innerText = 'All tiles loaded';
            if (map) map.invalidateSize();
        });
    }

    function loadStateMarkers() {
        fetch('/static/india_states.geojson')
            .then(function(response) { return response.json(); })
            .then(function(data) {
                data.features.forEach(function(state) {
                    var coords = state.properties.center;
                    var stateMarker = L.marker([coords[1], coords[0]], {
                        icon: L.divIcon({
                            html: '<div style="background-color: #d9534f; width: 10px; height: 10px; border-radius: 50%; border: 2px solid white;"></div>',
                            className: 'state-marker',
                            iconSize: [14, 14]
                        })
                    });
                    stateMarker.bindTooltip(state.properties.name);
                    stateMarker.addTo(map);
                });
            })
            .catch(function(error) { console.error('Error loading state data:', error); });
    }

    function setupResizeObserver() {
        var container = document.querySelector('.map-container');
        if (container && window.ResizeObserver) {
            resizeObserver = new ResizeObserver(function() {
                if (map) map.invalidateSize();
            });
            resizeObserver.observe(container);
        }
    }

    function handleLoadingOverlay() {
        var loadingOverlay = document.getElementById('map-loading');
        if (loadingOverlay) {
            setTimeout(function() {
                loadingOverlay.classList.add('hidden');
            }, 2000);
        }
    }

    async function getStateCoords(stateName) {
        try {
            var response = await fetch('/static/india_states.geojson');
            var data = await response.json();
            var state = data.features.find(function(f) { 
                return f.properties.name === stateName; 
            });
            return state ? state.properties.center : null;
        } catch (error) {
            console.error('Error getting state coordinates:', error);
            return null;
        }
    }

    async function animateTravel(origin, destination) {
        // Clear previous animation
        if (animationFrameId) {
            window.cancelAnimationFrame(animationFrameId);
            animationFrameId = null;
        }
        if (polyline && map) {
            map.removeLayer(polyline);
            polyline = null;
        }

        // Get coordinates
        var originCoords = await getStateCoords(origin);
        var destCoords = await getStateCoords(destination);

        if (!originCoords || !destCoords || !map) {
            console.error('Could not animate travel: missing coordinates or map');
            return;
        }

        // Create path line
        polyline = L.polyline([
            [originCoords[1], originCoords[0]],
            [destCoords[1], destCoords[0]]
        ], {
            color: '#FF4444',
            weight: 2,
            opacity: 0.8,
            dashArray: '10, 10'
        });
        polyline.addTo(map);

        // Create or update marker
        if (!marker) {
            marker = L.marker([originCoords[1], originCoords[0]], {
                icon: L.divIcon({
                    html: '<div style="background-color: #2b8cbe; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white;"></div>',
                    className: 'traveler-marker',
                    iconSize: [16, 16]
                })
            });
            marker.addTo(map);
        } else {
            marker.setLatLng([originCoords[1], originCoords[0]]);
        }

        // Animation setup
        var duration = 2000;
        var start = window.performance.now();

        // Animate marker
        function animate(currentTime) {
            var elapsed = currentTime - start;
            var progress = Math.min(elapsed / duration, 1);

            var lat = originCoords[1] + (destCoords[1] - originCoords[1]) * progress;
            var lng = originCoords[0] + (destCoords[0] - originCoords[0]) * progress;
            
            marker.setLatLng([lat, lng]);

            if (progress < 1) {
                animationFrameId = window.requestAnimationFrame(animate);
            }
        }

        // Fit map view
        map.fitBounds([
            [originCoords[1], originCoords[0]],
            [destCoords[1], destCoords[0]]
        ], { padding: [50, 50] });

        // Start animation
        animationFrameId = window.requestAnimationFrame(animate);
    }

    function updateResults(data) {
        var container = document.getElementById('result-container');
        if (!container) return;

        // Use the form values as titles (server does not return state names inside origin_state)
        var originName = (document.getElementById('origin') && document.getElementById('origin').value) || 'Origin';
        var destName = (document.getElementById('destination') && document.getElementById('destination').value) || 'Destination';

        // Defensive access to nested fields
        var o = data.origin_state || {};
        var d = data.dest_state || {};

        // Map server fields to UI
        var pInfectious = typeof data.p_infectious !== 'undefined' ? data.p_infectious : null;
        var expectedInfectious = typeof data.expected_infectious_travelers !== 'undefined' ? data.expected_infectious_travelers : null;
        var newInfections = typeof data.expected_new_infections_30d !== 'undefined' ? data.expected_new_infections_30d : null;
        var transMultO = typeof data.transmission_multiplier_origin !== 'undefined' ? data.transmission_multiplier_origin : data.origin_mobility_factor;
        var transMultD = typeof data.transmission_multiplier_dest !== 'undefined' ? data.transmission_multiplier_dest : data.dest_mobility_factor;

        container.innerHTML = `
            <div class="result">
                <div class="stats">
                    <div class="stat-box">
                        <h4>Origin State: ${originName}</h4>
                        <div class="metrics-grid">
                            <div class="metric">
                                <div class="metric-value">${Number(o.susceptible || 0).toLocaleString()}</div>
                                <div class="metric-label">Susceptible</div>
                            </div>
                            <div class="metric">
                                <div class="metric-value">${Number(o.exposed || 0).toLocaleString()}</div>
                                <div class="metric-label">Exposed</div>
                            </div>
                            <div class="metric">
                                <div class="metric-value">${Number(o.infected || 0).toLocaleString()}</div>
                                <div class="metric-label">Infected</div>
                            </div>
                            <div class="metric">
                                <div class="metric-value">${Number(o.recovered || 0).toLocaleString()}</div>
                                <div class="metric-label">Recovered</div>
                            </div>
                        </div>
                        <div class="population-info">
                            <span class="label">Population</span>
                            <span class="value">${data.population_origin ? Number(data.population_origin).toLocaleString() : 'n/a'}</span>
                        </div>
                        <div class="population-info">
                            <span class="label">Mobility Factor</span>
                            <span class="value">${transMultO !== undefined ? Number(transMultO).toFixed(2) : 'n/a'}</span>
                        </div>
                    </div>
                    <div class="stat-box">
                        <h4>Destination State: ${destName}</h4>
                        <div class="metrics-grid">
                            <div class="metric">
                                <div class="metric-value">${Number(d.susceptible || 0).toLocaleString()}</div>
                                <div class="metric-label">Susceptible</div>
                            </div>
                            <div class="metric">
                                <div class="metric-value">${Number(d.exposed || 0).toLocaleString()}</div>
                                <div class="metric-label">Exposed</div>
                            </div>
                            <div class="metric">
                                <div class="metric-value">${Number(d.infected || 0).toLocaleString()}</div>
                                <div class="metric-label">Infected</div>
                            </div>
                            <div class="metric">
                                <div class="metric-value">${Number(d.recovered || 0).toLocaleString()}</div>
                                <div class="metric-label">Recovered</div>
                            </div>
                        </div>
                        <div class="population-info">
                            <span class="label">Population</span>
                            <span class="value">${data.population_destination ? Number(data.population_destination).toLocaleString() : 'n/a'}</span>
                        </div>
                        <div class="population-info">
                            <span class="label">Mobility Factor</span>
                            <span class="value">${transMultD !== undefined ? Number(transMultD).toFixed(2) : 'n/a'}</span>
                        </div>
                    </div>
                    <div class="stat-box">
                        <h4>Travel Impact Assessment</h4>
                        <div class="impact-metric">
                            <div class="label">Probability of Infectious Traveler</div>
                            <div class="value">${pInfectious !== null ? (pInfectious * 100).toFixed(2) + '%' : 'n/a'}</div>
                        </div>
                        <div class="impact-metric">
                            <div class="label">Expected Infectious Travelers</div>
                            <div class="value">${expectedInfectious !== null ? Number(expectedInfectious).toFixed(2) : 'n/a'}</div>
                        </div>
                        <div class="impact-metric">
                            <div class="label">Projected New Infections (30 days)</div>
                            <div class="value">${newInfections !== null ? Number(newInfections).toLocaleString() : 'n/a'}</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    async function submitTravelForm(event) {
        var origin = document.getElementById('origin').value;
        var destination = document.getElementById('destination').value;
        var travelers = document.getElementById('travelers').value;

        console.log('Form submitted with values:', {origin, destination, travelers});

        // Start travel animation
        await animateTravel(origin, destination);

        // Fetch risk prediction
        try {
            var response = await fetch('/api/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ origin, destination, travelers })
            });

                if (response.ok) {
                    var data = await response.json();
                    console.log('API response data:', data);
                    updateResults(data);
                    
                    // Scroll to results
                    var resultContainer = document.getElementById('result-container');
                    if (resultContainer) {
                        resultContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                    
                    // Update charts with new data (renderCharts is defined in index.html)
                    console.log('Re-rendering charts with selected states:', origin, '->', destination);
                    try {
                        renderCharts();
                    } catch(err) {
                        console.error('Error calling renderCharts:', err);
                    }
                } else {
                    var text = await response.text();
                    var container = document.getElementById('result-container');
                    if (container) container.innerHTML = '<div class="error">Server error: ' + (text || response.status) + '</div>';
                }
        } catch (error) {
                console.error('Failed to fetch prediction:', error);
                var container = document.getElementById('result-container');
                if (container) container.innerHTML = '<div class="error">Request failed: ' + (error && error.message ? error.message : error) + '</div>';
        }
    }

    // Initialize map when document loads
    document.addEventListener('DOMContentLoaded', function() {
        // Initialize map
        initMap();
        
        // Set up form submission handling
        var form = document.getElementById('travel-form');
        if (form) {
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                submitTravelForm(e);
            });
        }
    });
})();