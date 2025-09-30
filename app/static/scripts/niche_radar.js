// Niche Radar JavaScript - Consistent with reply guy style
(function() {
    'use strict';

    // Store references to event handlers for cleanup
    let eventHandlers = {
        delegatedClick: null,
        modalClick: null,
        formKey: null,
        cleanup: null
    };

    // Wait for ApexCharts to be available
    function waitForApexCharts(callback) {
        if (typeof ApexCharts !== 'undefined') {
            callback();
        } else {
            setTimeout(() => waitForApexCharts(callback), 50);
        }
    }

    // Initialize niche radar functionality
    function initializeNicheRadar() {
        console.log('Niche Radar: Starting initialization');

        // Global state
        window.NicheRadarState = {
            isAnalyzing: false,
            statusCheckInterval: null,
            charts: {},
            currentEditingList: null,
            currentDeletingList: null,
            selectedList: null,
            selectedTimeRange: '24h'
        };

        // State manager
        if (!window.CreatorPal) window.CreatorPal = {};
        if (!window.CreatorPal.NicheRadar) window.CreatorPal.NicheRadar = {};

        if (!window.CreatorPal.NicheRadar.StateManager) {
            window.CreatorPal.NicheRadar.StateManager = {
                getProcessingState: function() {
                    try {
                        const state = sessionStorage.getItem('niche_radar_processing_state');
                        return state ? JSON.parse(state) : null;
                    } catch (e) {
                        return null;
                    }
                },

                setProcessingState: function(listName, isProcessing, statusMessage = '', progress = 0) {
                    const state = {
                        listName: listName,
                        isProcessing: isProcessing,
                        statusMessage: statusMessage,
                        progress: progress,
                        timestamp: Date.now()
                    };
                    try {
                        sessionStorage.setItem('niche_radar_processing_state', JSON.stringify(state));
                    } catch (e) {
                        console.error('Failed to save processing state:', e);
                    }
                },

                clearProcessingState: function() {
                    try {
                        sessionStorage.removeItem('niche_radar_processing_state');
                    } catch (e) {
                        console.error('Failed to clear processing state:', e);
                    }
                },

                isStateExpired: function(state) {
                    if (!state || !state.timestamp) return true;
                    const thirtyMinutes = 30 * 60 * 1000;
                    return (Date.now() - state.timestamp) > thirtyMinutes;
                }
            };
        }

        // Initialize all components
        init();

        function init() {
            console.log('Niche Radar: Initializing');
            restoreProcessingState();
            defineEventHandlers(); // Define handlers FIRST
            setupEventListeners();  // Then attach them
            setupViewToggle();
            setupDropdowns();
            setupListTypeToggle();

            // Initialize selected list from default
            const defaultListOption = document.querySelector('.dropdown-option.selected');
            if (defaultListOption) {
                const value = defaultListOption.dataset.value;
                if (value) {
                    window.NicheRadarState.selectedList = value;
                    console.log('Initialized with default list:', value);
                }
            }

            // Wait for ApexCharts before setting up charts
            waitForApexCharts(() => {
                console.log('ApexCharts loaded, setting up charts');
                setupCharts();
            });

            console.log('Niche Radar: Initialization complete');
        }

        function restoreProcessingState() {
            const savedState = window.CreatorPal.NicheRadar.StateManager.getProcessingState();
            if (savedState && savedState.isProcessing && !window.CreatorPal.NicheRadar.StateManager.isStateExpired(savedState)) {
                console.log('Restoring processing state for list:', savedState.listName);
                setAnalyzingState(true, savedState.statusMessage);
                validateSavedProcessingState(savedState.listName);
            } else {
                setTimeout(checkForActiveProcessOnLoad, 100);
            }
        }

        function validateSavedProcessingState(listName) {
            console.log('Validating saved processing state for list:', listName);

            fetch('/niche/get-status')
                .then(response => response.json())
                .then(data => {
                    if (data.running && data.status === 'processing') {
                        console.log('Server confirms process is active');
                        startStatusPolling();
                    } else {
                        console.log('Server says no active process - clearing stale saved state');
                        window.CreatorPal.NicheRadar.StateManager.clearProcessingState();
                        setAnalyzingState(false);

                        if (data.running) {
                            console.log('Found different active process');
                            const cleanMessage = data.step || 'Processing in progress...';
                            window.CreatorPal.NicheRadar.StateManager.setProcessingState('unknown', true, cleanMessage, data.progress || 10);
                            setAnalyzingState(true, cleanMessage);
                            startStatusPolling();
                            showToast('Found active analysis process, monitoring it', 'info');
                        } else {
                            setTimeout(checkForActiveProcessOnLoad, 100);
                        }
                    }
                })
                .catch(error => {
                    console.error('Error validating saved state:', error);
                    console.log('Clearing saved state due to validation error');
                    window.CreatorPal.NicheRadar.StateManager.clearProcessingState();
                    setAnalyzingState(false);
                });
        }

        function checkForActiveProcessOnLoad() {
            fetch('/niche/get-status')
                .then(response => response.json())
                .then(data => {
                    if (data.running && data.status === 'processing') {
                        console.log('Found active process on load');
                        const cleanStatusMessage = data.step || 'Processing in progress...';
                        window.CreatorPal.NicheRadar.StateManager.setProcessingState('unknown', true, cleanStatusMessage, data.progress || 10);
                        setAnalyzingState(true, cleanStatusMessage);
                        startStatusPolling();
                        console.log('Resumed monitoring active process silently');
                    } else {
                        console.log('No active processes found');
                    }
                })
                .catch(error => {
                    console.log('No active processes found or connection error');
                });
        }

        function setAnalyzingState(analyzing, statusMessage = '') {
            // Update all analyze buttons
            document.querySelectorAll('[id^="analyze-button"]').forEach(button => {
                window.NicheRadarState.isAnalyzing = analyzing;

                if (analyzing) {
                    button.classList.add('processing');
                    button.disabled = true;
                    button.innerHTML = '<div class="loading-spinner"></div><span>Analyzing...</span>';
                } else {
                    button.classList.remove('processing');
                    button.disabled = false;
                    button.innerHTML = '<i class="ph ph-arrows-clockwise"></i><span>Analyze</span>';
                }
            });
            console.log('Button state updated:', analyzing ? 'analyzing' : 'normal');
        }

        // Define all event handlers
        function defineEventHandlers() {
            console.log('Defining event handlers...');

            eventHandlers.delegatedClick = function(e) {
            console.log('Click event:', e.target);

            // Handle list action buttons
            const listActionBtn = e.target.closest('.list-action-btn');
            if (listActionBtn) {
                console.log('List action button clicked');
                const listName = listActionBtn.dataset.listName;

                if (listActionBtn.classList.contains('edit')) {
                    editList(listName);
                } else if (listActionBtn.classList.contains('refresh')) {
                    updateXList(listName);
                } else if (listActionBtn.classList.contains('delete')) {
                    confirmDeleteList(listName);
                }
                return;
            }

            // Handle analyze buttons
            const analyzeBtn = e.target.closest('[id^="analyze-button"]');
            if (analyzeBtn) {
                console.log('Analyze button clicked:', analyzeBtn.id, 'disabled:', analyzeBtn.disabled);
                if (analyzeBtn.disabled) {
                    console.log('Button is disabled, ignoring');
                    showToast('Please add an X List first', 'warning');
                    return;
                }
                handleAnalyze();
                return;
            }

            // Handle create list button (modal)
            if (e.target.closest('#simple-create-btn')) {
                console.log('Create button clicked');
                handleSimpleCreateList();
                return;
            }

            // Handle cancel create button
            if (e.target.closest('#cancel-create-btn')) {
                console.log('Cancel button clicked');
                hideModal('create-list-modal');
                return;
            }

            // Handle close create modal
            if (e.target.closest('#close-create-modal')) {
                console.log('Close modal clicked');
                hideModal('create-list-modal');
                return;
            }

            // Handle modal close buttons
            if (e.target.closest('#close-edit-modal, #close-edit-modal-btn')) {
                hideModal('edit-list-modal');
                return;
            }

            if (e.target.closest('#close-delete-modal')) {
                hideModal('delete-modal');
                return;
            }

            if (e.target.closest('#cancel-delete')) {
                hideModal('delete-modal');
                return;
            }

            if (e.target.closest('#confirm-delete')) {
                deleteList();
                return;
            }

            if (e.target.closest('#add-creator-btn')) {
                addCreator();
                return;
            }
        };

        eventHandlers.modalClick = function(e) {
            if (e.target.classList.contains('modal')) {
                hideModal(e.target.id);
            }
        };

        eventHandlers.formKey = function(e) {
            if (e.key === 'Enter') {
                if (e.target.id === 'new-creator-handle-input') {
                    addCreator();
                } else if (e.target.id === 'simple-list-name' || e.target.id === 'simple-x-list-id') {
                    handleSimpleCreateList();
                }
            }
        };

            console.log('Event handlers defined successfully');
        }

        function setupEventListeners() {
            console.log('Setting up event listeners');

            // Remove old event listeners first
            document.removeEventListener('click', eventHandlers.delegatedClick);
            document.removeEventListener('click', eventHandlers.modalClick);
            document.removeEventListener('keydown', eventHandlers.formKey);

            // Add new event listeners
            document.addEventListener('click', eventHandlers.delegatedClick);
            document.addEventListener('click', eventHandlers.modalClick);
            document.addEventListener('keydown', eventHandlers.formKey);

            console.log('Event listeners setup complete');
            console.log('Delegated click handler:', eventHandlers.delegatedClick);
            console.log('Testing click detection...');

            // Test if clicks are being captured
            setTimeout(() => {
                console.log('Please click anywhere on the page now to test event capture');
            }, 1000);
        }

        function setupViewToggle() {
            const analyticsBtn = document.getElementById('analytics-view-btn');
            const listsBtn = document.getElementById('lists-view-btn');

            if (analyticsBtn) {
                analyticsBtn.addEventListener('click', () => switchView('analytics'));
            }

            if (listsBtn) {
                listsBtn.addEventListener('click', () => switchView('lists'));
            }
        }

        function switchView(view) {
            const analyticsViewBtn = document.getElementById('analytics-view-btn');
            const listsViewBtn = document.getElementById('lists-view-btn');
            const analyticsPanel = document.getElementById('analytics-panel');
            const listsPanel = document.getElementById('lists-panel');

            if (view === 'analytics') {
                analyticsViewBtn?.classList.add('active');
                listsViewBtn?.classList.remove('active');
                analyticsPanel?.classList.remove('hidden');
                listsPanel?.classList.remove('active');
            } else {
                listsViewBtn?.classList.add('active');
                analyticsViewBtn?.classList.remove('active');
                analyticsPanel?.classList.add('hidden');
                listsPanel?.classList.add('active');
            }
        }

        function setupDropdowns() {
            // Setup all dropdown functionality
            document.querySelectorAll('.dropdown').forEach(dropdown => {
                const trigger = dropdown.querySelector('.dropdown-trigger');
                const menu = dropdown.querySelector('.dropdown-menu');
                const options = dropdown.querySelectorAll('.dropdown-option');

                if (!trigger || !menu) return;

                trigger.addEventListener('click', (e) => {
                    e.stopPropagation();
                    
                    // Close other dropdowns
                    document.querySelectorAll('.dropdown-menu.active').forEach(otherMenu => {
                        if (otherMenu !== menu) {
                            otherMenu.classList.remove('active');
                            otherMenu.parentElement.querySelector('.dropdown-trigger').classList.remove('active');
                        }
                    });
                    
                    // Toggle this dropdown
                    menu.classList.toggle('active');
                    trigger.classList.toggle('active');
                });

                options.forEach(option => {
                    option.addEventListener('click', (e) => {
                        e.stopPropagation();

                        // Handle "Add X List" option
                        if (option.classList.contains('create-new')) {
                            console.log('Create new list clicked');
                            menu.classList.remove('active');
                            trigger.classList.remove('active');
                            scrollToCreateForm();
                            return;
                        }

                        const value = option.dataset.value;
                        const text = option.textContent.trim();

                        // Update trigger text
                        const textElement = trigger.querySelector('span');
                        if (textElement) {
                            textElement.textContent = text;
                        }

                        // Update selected state
                        options.forEach(opt => opt.classList.remove('selected'));
                        option.classList.add('selected');

                        // Store selection based on dropdown type
                        if (dropdown.querySelector('#list-dropdown-trigger, #list-dropdown-trigger-empty, #list-dropdown-trigger-default')) {
                            window.NicheRadarState.selectedList = value;
                            console.log('Selected list:', value);
                        } else if (dropdown.querySelector('#time-range-dropdown-trigger, #time-range-dropdown-trigger-empty, #time-range-dropdown-trigger-default')) {
                            window.NicheRadarState.selectedTimeRange = value;
                            console.log('Selected time range:', value);
                        }

                        // Close dropdown
                        menu.classList.remove('active');
                        trigger.classList.remove('active');
                    });
                });
            });

            // Close dropdowns when clicking outside
            document.addEventListener('click', () => {
                document.querySelectorAll('.dropdown-menu.active').forEach(menu => {
                    menu.classList.remove('active');
                    menu.parentElement.querySelector('.dropdown-trigger').classList.remove('active');
                });
            });
        }

        function setupListTypeToggle() {
            // No longer needed - always X List
        }

        function setupCharts() {
            const chartDataElement = document.getElementById('chart-data');
            if (!chartDataElement) {
                console.log('No chart data found');
                return;
            }

            let chartData;
            try {
                chartData = JSON.parse(chartDataElement.textContent);
            } catch (error) {
                console.error('Error parsing chart data:', error);
                return;
            }

            console.log('Setting up charts with data:', chartData);

            // Destroy existing charts first
            Object.values(window.NicheRadarState.charts).forEach(chart => {
                if (chart && chart.destroy) {
                    chart.destroy();
                }
            });
            window.NicheRadarState.charts = {};

            const chartOptions = {
                chart: {
                    type: 'bar',
                    height: '100%',
                    toolbar: { show: false },
                    background: 'transparent',
                    fontFamily: 'Inter, sans-serif',
                    foreColor: '#a0aec0',
                    animations: {
                        enabled: true,
                        easing: 'easeinout',
                        speed: 400
                    }
                },
                theme: { mode: 'dark' },
                grid: {
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    strokeDashArray: 3,
                    xaxis: { lines: { show: false } },
                    yaxis: { lines: { show: true } }
                },
                colors: ['#3B82F6'],
                plotOptions: {
                    bar: {
                        borderRadius: 8,
                        columnWidth: '60%',
                        dataLabels: {
                            position: 'top'
                        }
                    }
                },
                xaxis: {
                    labels: {
                        style: {
                            colors: '#a0aec0',
                            fontSize: '12px'
                        },
                        rotate: -45,
                        rotateAlways: true,
                        trim: true,
                        maxHeight: 100
                    },
                    axisBorder: { color: 'rgba(255, 255, 255, 0.1)' },
                    axisTicks: { color: 'rgba(255, 255, 255, 0.1)' }
                },
                yaxis: {
                    labels: {
                        style: { colors: '#a0aec0', fontSize: '12px' },
                        formatter: function(val) {
                            const rounded = Math.round(val);
                            if (rounded >= 1000000) {
                                return Math.round(rounded / 1000000) + 'M';
                            } else if (rounded >= 1000) {
                                return Math.round(rounded / 1000) + 'K';
                            }
                            return rounded.toString();
                        }
                    }
                },
                dataLabels: { enabled: false },
                tooltip: {
                    theme: 'dark',
                    x: {
                        show: true
                    }
                }
            };

            // Initialize each chart with a slight delay to ensure proper rendering
            setTimeout(() => {
                initChart('tweets-chart', chartOptions, chartData.tweets_count, 'Tweets');
            }, 100);

            setTimeout(() => {
                initChart('likes-chart', chartOptions, chartData.likes_count, 'Likes');
            }, 200);

            setTimeout(() => {
                initChart('views-chart', chartOptions, chartData.views_count, 'Views');
            }, 300);

            setTimeout(() => {
                initEngagementChart(chartData.engagement_rate);
            }, 400);
        }

        function initChart(elementId, baseOptions, data, seriesName) {
            const element = document.getElementById(elementId);
            if (!element || !data) return;

            // Clear any existing content
            element.innerHTML = '';

            const config = {
                ...baseOptions,
                series: [{
                    name: seriesName,
                    data: data.values.map(v => Math.round(v))
                }],
                xaxis: {
                    ...baseOptions.xaxis,
                    categories: data.creators,
                    labels: {
                        ...baseOptions.xaxis.labels,
                        formatter: function(value) {
                            return String(value);
                        }
                    }
                }
            };

            try {
                const chart = new ApexCharts(element, config);
                window.NicheRadarState.charts[elementId] = chart;
                chart.render();
            } catch (error) {
                console.error('Error creating chart:', elementId, error);
            }
        }

        function initEngagementChart(data) {
            const element = document.getElementById('engagement-chart');
            if (!element || !data) return;

            // Clear any existing content
            element.innerHTML = '';

            const config = {
                chart: {
                    type: 'bar',
                    height: '100%',
                    toolbar: { show: false },
                    background: 'transparent',
                    fontFamily: 'Inter, sans-serif',
                    foreColor: '#a0aec0',
                    animations: {
                        enabled: true,
                        easing: 'easeinout',
                        speed: 400
                    }
                },
                theme: { mode: 'dark' },
                grid: {
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    strokeDashArray: 3,
                    xaxis: { lines: { show: false } },
                    yaxis: { lines: { show: true } }
                },
                colors: ['#3B82F6'],
                plotOptions: {
                    bar: {
                        borderRadius: 8,
                        columnWidth: '60%',
                        dataLabels: {
                            position: 'top'
                        }
                    }
                },
                xaxis: {
                    labels: {
                        style: {
                            colors: '#a0aec0',
                            fontSize: '12px'
                        },
                        rotate: -45,
                        rotateAlways: true,
                        trim: true,
                        maxHeight: 100,
                        formatter: function(value) {
                            return String(value);
                        }
                    },
                    categories: data.creators
                },
                yaxis: {
                    labels: {
                        style: { colors: '#a0aec0', fontSize: '12px' },
                        formatter: function(val) { return val.toFixed(1) + '%'; }
                    }
                },
                dataLabels: { enabled: false },
                tooltip: {
                    theme: 'dark',
                    x: {
                        show: true
                    },
                    y: { formatter: function(val) { return val.toFixed(1) + '%'; } }
                },
                series: [{
                    name: 'Engagement Rate (%)',
                    data: data.values.map(v => parseFloat(v.toFixed(1)))
                }]
            };

            try {
                const chart = new ApexCharts(element, config);
                window.NicheRadarState.charts['engagement-chart'] = chart;
                chart.render();
            } catch (error) {
                console.error('Error creating engagement chart:', error);
            }
        }

        function handleAnalyze() {
            console.log('Analyze button clicked');

            if (window.NicheRadarState.isAnalyzing) {
                console.log('Already analyzing, ignoring click');
                return;
            }

            const selectedList = window.NicheRadarState.selectedList;
            const selectedTimeRange = window.NicheRadarState.selectedTimeRange || '24h';

            if (!selectedList) {
                showToast('Please select a list to analyze', 'error');
                return;
            }

            console.log('Starting analysis for list:', selectedList, 'time range:', selectedTimeRange);

            window.CreatorPal.NicheRadar.StateManager.setProcessingState(selectedList, true, 'Starting analysis...', 5);
            setAnalyzingState(true);

            fetch('/niche/analyze-creators', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    list_name: selectedList,
                    time_range: selectedTimeRange
                })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Analysis response:', data);

                if (data.success) {
                    showToast('Analysis started! This will take a few minutes.', 'success');
                    startStatusPolling();
                } else {
                    console.log('Analysis failed to start:', data.error);
                    setAnalyzingState(false);
                    window.CreatorPal.NicheRadar.StateManager.clearProcessingState();
                    showToast(data.error || 'Error starting analysis', 'error');
                }
            })
            .catch(error => {
                console.error('Analysis start error:', error);
                setAnalyzingState(false);
                window.CreatorPal.NicheRadar.StateManager.clearProcessingState();
                showToast('Network error: ' + error.message, 'error');
            });
        }

        function startStatusPolling() {
            console.log('Starting status polling');

            if (window.NicheRadarState.statusCheckInterval) {
                clearInterval(window.NicheRadarState.statusCheckInterval);
            }

            let pollCount = 0;
            const maxPolls = 150;

            window.NicheRadarState.statusCheckInterval = setInterval(function() {
                pollCount++;

                fetch('/niche/get-status')
                .then(response => response.json())
                .then(data => {
                    console.log('Status poll:', data.status, 'running:', data.running);

                    const currentState = window.CreatorPal.NicheRadar.StateManager.getProcessingState();
                    if (currentState && currentState.isProcessing) {
                        window.CreatorPal.NicheRadar.StateManager.setProcessingState(
                            currentState.listName,
                            true,
                            data.step || 'Processing...',
                            data.progress || 10
                        );
                    }

                    if (data.status === 'completed') {
                        console.log('Analysis completed!');
                        stopStatusPolling();
                        window.CreatorPal.NicheRadar.StateManager.clearProcessingState();
                        setAnalyzingState(false);
                        showToast('Analysis completed! Refreshing page...', 'success');
                        setTimeout(() => window.location.reload(), 1000);
                    } else if (data.status === 'error') {
                        console.log('Analysis error:', data.error);
                        stopStatusPolling();
                        window.CreatorPal.NicheRadar.StateManager.clearProcessingState();
                        setAnalyzingState(false);
                        showToast('Analysis failed: ' + (data.error || 'Unknown error'), 'error');
                    } else if (!data.running && data.status !== 'processing') {
                        console.log('Analysis stopped unexpectedly');
                        stopStatusPolling();
                        window.CreatorPal.NicheRadar.StateManager.clearProcessingState();
                        setAnalyzingState(false);
                        showToast('Analysis stopped. Please try again.', 'warning');
                    }

                    if (pollCount >= maxPolls) {
                        console.log('Max polling duration reached');
                        stopStatusPolling();
                        window.CreatorPal.NicheRadar.StateManager.clearProcessingState();
                        setAnalyzingState(false);
                        showToast('Analysis taking longer than expected. Please check back later.', 'warning');
                    }
                })
                .catch(error => {
                    console.error('Error checking status:', error);
                    if (pollCount >= maxPolls) {
                        stopStatusPolling();
                        window.CreatorPal.NicheRadar.StateManager.clearProcessingState();
                        setAnalyzingState(false);
                        showToast('Connection lost. Please refresh the page.', 'error');
                    }
                });
            }, 2000);
        }

        function stopStatusPolling() {
            console.log('Stopping status polling');
            if (window.NicheRadarState.statusCheckInterval) {
                clearInterval(window.NicheRadarState.statusCheckInterval);
                window.NicheRadarState.statusCheckInterval = null;
            }
        }

        // API Functions
        async function handleSimpleCreateList() {
            const listName = document.getElementById('simple-list-name')?.value?.trim();
            const xListId = document.getElementById('simple-x-list-id')?.value?.trim();

            if (!listName) {
                showToast('Please enter a list name', 'error');
                return;
            }

            if (!xListId) {
                showToast('Please enter an X List ID', 'error');
                return;
            }

            const createBtn = document.getElementById('simple-create-btn');
            setButtonLoading(createBtn, true);

            try {
                const data = {
                    list_name: listName,
                    list_type: 'x_list',
                    x_list_id: xListId
                };

                const response = await fetch('/niche/create-list', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                const result = await response.json();

                if (result.success) {
                    showToast('X List created! Starting analysis...', 'success');
                    hideModal('create-list-modal');

                    // Clear form
                    document.getElementById('simple-list-name').value = '';
                    document.getElementById('simple-x-list-id').value = '';

                    // Update dropdown text to show the new list
                    updateDropdownText(listName);

                    // Auto-start analysis
                    setTimeout(() => {
                        autoStartAnalysis(listName);
                    }, 500);
                } else {
                    showToast(result.message || 'Error adding X List', 'error');
                }
            } catch (error) {
                showToast('Network error: ' + error.message, 'error');
            } finally {
                setButtonLoading(createBtn, false);
            }
        }

        // Auto-start analysis after creating list
        async function autoStartAnalysis(listName) {
            console.log('Auto-starting analysis for list:', listName);

            window.NicheRadarState.selectedList = listName;
            window.CreatorPal.NicheRadar.StateManager.setProcessingState(listName, true, 'Starting analysis...', 5);
            setAnalyzingState(true);

            try {
                const response = await fetch('/niche/analyze-creators', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        list_name: listName,
                        time_range: '24h'
                    })
                });

                const data = await response.json();

                if (data.success) {
                    showToast('Analysis started! This will take a few minutes.', 'success');
                    startStatusPolling();
                } else {
                    console.log('Analysis failed to start:', data.error);
                    setAnalyzingState(false);
                    window.CreatorPal.NicheRadar.StateManager.clearProcessingState();
                    showToast(data.error || 'Error starting analysis', 'error');
                }
            } catch (error) {
                console.error('Analysis start error:', error);
                setAnalyzingState(false);
                window.CreatorPal.NicheRadar.StateManager.clearProcessingState();
                showToast('Network error: ' + error.message, 'error');
            }
        }

        async function editList(listName) {
            window.NicheRadarState.currentEditingList = listName;

            try {
                const response = await fetch(`/niche/get-creators?list_name=${encodeURIComponent(listName)}`);
                const data = await response.json();

                if (data.success) {
                    displayCreatorsInModal(data.creators);
                    showModal('edit-list-modal');
                } else {
                    showToast('Error loading list creators', 'error');
                }
            } catch (error) {
                showToast('Network error', 'error');
            }
        }

        async function addCreator() {
            const creatorHandle = document.getElementById('new-creator-handle-input')?.value?.trim();

            if (!creatorHandle) {
                showToast('Please enter a creator handle', 'error');
                return;
            }

            if (!window.NicheRadarState.currentEditingList) {
                showToast('No list selected', 'error');
                return;
            }

            const addBtn = document.getElementById('add-creator-btn');
            setButtonLoading(addBtn, true);

            try {
                const response = await fetch('/niche/add-creator', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        list_name: window.NicheRadarState.currentEditingList,
                        creator_handle: creatorHandle
                    })
                });

                const data = await response.json();

                if (data.success) {
                    showToast('Creator added successfully!', 'success');
                    document.getElementById('new-creator-handle-input').value = '';
                    displayCreatorsInModal(data.creators);
                } else {
                    showToast(data.message || 'Error adding creator', 'error');
                }
            } catch (error) {
                showToast('Network error', 'error');
            } finally {
                setButtonLoading(addBtn, false);
            }
        }

        async function removeCreator(creatorHandle) {
            if (!window.NicheRadarState.currentEditingList) return;

            try {
                const response = await fetch('/niche/remove-creator', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        list_name: window.NicheRadarState.currentEditingList,
                        creator_handle: creatorHandle
                    })
                });

                const data = await response.json();

                if (data.success) {
                    showToast('Creator removed successfully!', 'success');
                    displayCreatorsInModal(data.creators);
                } else {
                    showToast(data.error || 'Error removing creator', 'error');
                }
            } catch (error) {
                showToast('Network error', 'error');
            }
        }

        async function updateXList(listName) {
            const button = document.querySelector(`[data-list-name="${listName}"].refresh`);
            if (button) setButtonLoading(button, true);

            try {
                const response = await fetch('/niche/update-x-list', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ list_name: listName })
                });

                const data = await response.json();

                if (data.success) {
                    showToast('X list updated successfully!', 'success');
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    showToast(data.message || 'Error updating X list', 'error');
                }
            } catch (error) {
                showToast('Network error', 'error');
            } finally {
                if (button) setButtonLoading(button, false);
            }
        }

        function confirmDeleteList(listName) {
            window.NicheRadarState.currentDeletingList = listName;
            document.getElementById('delete-list-name').textContent = `List: ${listName}`;
            showModal('delete-modal');
        }

        async function deleteList() {
            if (!window.NicheRadarState.currentDeletingList) return;

            const confirmBtn = document.getElementById('confirm-delete');
            setButtonLoading(confirmBtn, true);

            try {
                const response = await fetch('/niche/delete-list', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ list_name: window.NicheRadarState.currentDeletingList })
                });

                const data = await response.json();

                if (data.success) {
                    showToast('List deleted successfully!', 'success');
                    hideModal('delete-modal');
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    showToast(data.error || 'Error deleting list', 'error');
                }
            } catch (error) {
                showToast('Network error', 'error');
            } finally {
                setButtonLoading(confirmBtn, false);
            }
        }

        async function setDefaultList(listName) {
            try {
                const response = await fetch('/niche/set-default-list', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ list_name: listName })
                });

                const data = await response.json();

                if (data.success) {
                    showToast('Default list updated!', 'success');
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    showToast(data.message || 'Error setting default list', 'error');
                }
            } catch (error) {
                showToast('Network error', 'error');
            }
        }

        // Show create list modal
        function scrollToCreateForm() {
            showModal('create-list-modal');

            // Focus on the list name input
            setTimeout(() => {
                const nameInput = document.getElementById('simple-list-name');
                if (nameInput) {
                    nameInput.focus();
                }
            }, 100);
        }

        // Update dropdown text after creating list
        function updateDropdownText(listName) {
            const dropdownTexts = [
                'selected-list-text',
                'selected-list-text-empty',
                'selected-list-text-default'
            ];

            dropdownTexts.forEach(id => {
                const element = document.getElementById(id);
                if (element) {
                    element.textContent = listName;
                }
            });
        }

        // Helper Functions
        function displayCreatorsInModal(creators) {
            const creatorsList = document.getElementById('creators-list');
            if (!creatorsList) return;

            creatorsList.innerHTML = '';

            creators.forEach(creator => {
                const creatorCard = document.createElement('div');
                creatorCard.className = 'creator-card';
                creatorCard.innerHTML = `
                    <div class="creator-info">
                        <div class="creator-handle">@${creator}</div>
                    </div>
                    <button class="list-action-btn delete" onclick="removeCreator('${creator}')">
                        <i class="ph ph-trash"></i>
                    </button>
                `;
                creatorsList.appendChild(creatorCard);
            });
        }


        function showModal(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.style.display = 'flex';
                modal.classList.add('show');
            }
        }

        function hideModal(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.remove('show');
                setTimeout(() => {
                    modal.style.display = 'none';
                }, 300);
            }
        }

        function setButtonLoading(button, loading) {
            if (!button) return;

            if (loading) {
                button.setAttribute('data-original-content', button.innerHTML);
                button.innerHTML = '<div class="loading-spinner"></div> Loading...';
                button.disabled = true;
            } else {
                const originalContent = button.getAttribute('data-original-content');
                if (originalContent) {
                    button.innerHTML = originalContent;
                }
                button.disabled = false;
                button.removeAttribute('data-original-content');
            }
        }

        function showToast(message, type = 'info') {
            const toast = document.createElement('div');
            let icon = 'info';

            if (type === 'success') icon = 'check-circle';
            else if (type === 'error') icon = 'warning-circle';
            else if (type === 'warning') icon = 'warning';

            toast.className = `toast ${type}`;
            toast.innerHTML = `
                <i class="ph ph-${icon}"></i>
                <span class="toast-text">${message}</span>
            `;

            document.body.appendChild(toast);

            setTimeout(() => toast.classList.add('show'), 100);

            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            }, 4000);
        }

        // Expose functions globally for onclick handlers
        window.removeCreator = removeCreator;
        window.setDefaultList = setDefaultList;

        // Store cleanup function
        eventHandlers.cleanup = function() {
            console.log('Cleaning up niche radar event listeners and state');

            // Stop polling
            stopStatusPolling();

            // Destroy charts
            if (window.NicheRadarState && window.NicheRadarState.charts) {
                Object.values(window.NicheRadarState.charts).forEach(chart => {
                    if (chart && chart.destroy) {
                        chart.destroy();
                    }
                });
                window.NicheRadarState.charts = {};
            }

            // Remove event listeners
            document.removeEventListener('click', eventHandlers.delegatedClick);
            document.removeEventListener('click', eventHandlers.modalClick);
            document.removeEventListener('keydown', eventHandlers.formKey);
        };
    }

    // Initialize on DOMContentLoaded
    document.addEventListener('DOMContentLoaded', function() {
        if (document.getElementById('analytics-panel') || document.getElementById('lists-panel')) {
            initializeNicheRadar();
        }
    });

    // Expose for external initialization
    window.initializeNicheRadar = initializeNicheRadar;
})();