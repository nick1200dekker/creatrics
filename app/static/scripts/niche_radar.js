// FIXED Creator Tracker JavaScript - Proper scope management and ApexCharts handling
(function() {
    'use strict';

    // Store references to event handlers at module level for cleanup
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

    // Initialize tracker functionality
    function initializeTracker() {
        console.log('Creator Tracker: Starting initialization');

        // Global state - reset on each initialization
        window.TrackerState = {
            isAnalyzing: false,
            statusCheckInterval: null,
            charts: {},
            currentEditingList: null,
            currentDeletingList: null
        };

        // State manager
        if (!window.CreatorPal) window.CreatorPal = {};
        if (!window.CreatorPal.Tracker) window.CreatorPal.Tracker = {};

        if (!window.CreatorPal.Tracker.StateManager) {
            window.CreatorPal.Tracker.StateManager = {
                getProcessingState: function() {
                    try {
                        const state = sessionStorage.getItem('tracker_processing_state');
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
                        sessionStorage.setItem('tracker_processing_state', JSON.stringify(state));
                    } catch (e) {
                        console.error('Failed to save processing state:', e);
                    }
                },

                clearProcessingState: function() {
                    try {
                        sessionStorage.removeItem('tracker_processing_state');
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
            console.log('Creator Tracker: Initializing');
            restoreProcessingState();
            setupEventListeners();
            setupViewToggle();
            setupListTypeToggle();

            // Wait for ApexCharts before setting up charts
            waitForApexCharts(() => {
                console.log('ApexCharts loaded, setting up charts');
                setupCharts();
            });

            console.log('Creator Tracker: Initialization complete');
        }

        function restoreProcessingState() {
            const savedState = window.CreatorPal.Tracker.StateManager.getProcessingState();
            if (savedState && savedState.isProcessing && !window.CreatorPal.Tracker.StateManager.isStateExpired(savedState)) {
                console.log('Restoring processing state for list:', savedState.listName);

                // Update all list selects
                document.querySelectorAll('[id^="list-select"]').forEach(select => {
                    for (let i = 0; i < select.options.length; i++) {
                        if (select.options[i].value === savedState.listName) {
                            select.selectedIndex = i;
                            break;
                        }
                    }
                });

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
                        window.CreatorPal.Tracker.StateManager.clearProcessingState();
                        setAnalyzingState(false);

                        if (data.running) {
                            console.log('Found different active process');
                            const cleanMessage = data.step || 'Processing in progress...';
                            window.CreatorPal.Tracker.StateManager.setProcessingState('unknown', true, cleanMessage, data.progress || 10);
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
                    window.CreatorPal.Tracker.StateManager.clearProcessingState();
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
                        window.CreatorPal.Tracker.StateManager.setProcessingState('unknown', true, cleanStatusMessage, data.progress || 10);
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
                window.TrackerState.isAnalyzing = analyzing;

                if (analyzing) {
                    button.classList.add('analyzing');
                    button.disabled = true;
                    button.innerHTML = '<div class="tracker-loading-spinner"></div><span>Analyzing...</span>';
                } else {
                    button.classList.remove('analyzing');
                    button.disabled = false;
                    button.innerHTML = '<i class="ph ph-arrows-clockwise"></i><span>Analyze</span>';
                }
            });
            console.log('Button state updated:', analyzing ? 'analyzing' : 'normal');
        }

        // Define event handlers at module level
        eventHandlers.delegatedClick = function(e) {
            const target = e.target.closest('[data-list-name]');
            if (!target) return;

            const listName = target.dataset.listName;

            if (target.classList.contains('set-default-btn')) {
                setDefaultList(listName);
            } else if (target.classList.contains('edit-list-btn')) {
                editList(listName);
            } else if (target.classList.contains('update-x-list-btn')) {
                updateXList(listName);
            } else if (target.classList.contains('delete-list-btn')) {
                confirmDeleteList(listName);
            }
        };

        eventHandlers.modalClick = function(e) {
            if (e.target.classList.contains('tracker-modal')) {
                hideModal(e.target.id);
            }
        };

        eventHandlers.formKey = function(e) {
            if (e.key === 'Enter') {
                if (e.target.id === 'new-creator-handle-input') {
                    addCreator();
                } else if (e.target.closest('.tracker-creation-form')) {
                    createList();
                }
            }
        };

        function setupEventListeners() {
            console.log('Setting up event listeners');

            // Remove old event listeners first
            document.removeEventListener('click', eventHandlers.delegatedClick);
            document.removeEventListener('click', eventHandlers.modalClick);
            document.removeEventListener('keydown', eventHandlers.formKey);

            // Handle all analyze buttons
            document.querySelectorAll('[id^="analyze-button"]').forEach(button => {
                button.removeEventListener('click', handleAnalyze);
                button.addEventListener('click', handleAnalyze);
            });

            const createListBtn = document.getElementById('create-list-btn');
            if (createListBtn) {
                createListBtn.removeEventListener('click', createList);
                createListBtn.addEventListener('click', createList);
            }

            const closeEditModal = document.getElementById('close-edit-modal');
            if (closeEditModal) {
                closeEditModal.removeEventListener('click', closeEditModalHandler);
                closeEditModal.addEventListener('click', closeEditModalHandler);
            }

            const addCreatorBtn = document.getElementById('add-creator-btn');
            if (addCreatorBtn) {
                addCreatorBtn.removeEventListener('click', addCreator);
                addCreatorBtn.addEventListener('click', addCreator);
            }

            const cancelDelete = document.getElementById('cancel-delete');
            if (cancelDelete) {
                cancelDelete.removeEventListener('click', cancelDeleteHandler);
                cancelDelete.addEventListener('click', cancelDeleteHandler);
            }

            const confirmDelete = document.getElementById('confirm-delete');
            if (confirmDelete) {
                confirmDelete.removeEventListener('click', deleteList);
                confirmDelete.addEventListener('click', deleteList);
            }

            // Add new event listeners
            document.addEventListener('click', eventHandlers.delegatedClick);
            document.addEventListener('click', eventHandlers.modalClick);
            document.addEventListener('keydown', eventHandlers.formKey);

            console.log('Event listeners setup complete');
        }

        // Event handler functions
        function closeEditModalHandler() {
            hideModal('edit-list-modal');
        }

        function cancelDeleteHandler() {
            hideModal('delete-modal');
        }

        function handleAnalyze() {
            console.log('Analyze button clicked');

            if (window.TrackerState.isAnalyzing) {
                console.log('Already analyzing, ignoring click');
                return;
            }

            // Get the first available select values (they should all be synced)
            const listSelect = document.querySelector('[id^="list-select"]');
            const timeRange = document.querySelector('[id^="time-range-select"]');

            const selectedList = listSelect?.value;
            const selectedTimeRange = timeRange?.value || '24h';

            if (!selectedList) {
                showToast('Please select a list to analyze', 'error');
                return;
            }

            console.log('Starting analysis for list:', selectedList, 'time range:', selectedTimeRange);

            window.CreatorPal.Tracker.StateManager.setProcessingState(selectedList, true, 'Starting analysis...', 5);
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
                    window.CreatorPal.Tracker.StateManager.clearProcessingState();
                    showToast(data.error || 'Error starting analysis', 'error');
                }
            })
            .catch(error => {
                console.error('Analysis start error:', error);
                setAnalyzingState(false);
                window.CreatorPal.Tracker.StateManager.clearProcessingState();
                showToast('Network error: ' + error.message, 'error');
            });
        }

        function startStatusPolling() {
            console.log('Starting status polling');

            if (window.TrackerState.statusCheckInterval) {
                clearInterval(window.TrackerState.statusCheckInterval);
            }

            let pollCount = 0;
            const maxPolls = 150;

            window.TrackerState.statusCheckInterval = setInterval(function() {
                pollCount++;

                fetch('/niche/get-status')
                .then(response => response.json())
                .then(data => {
                    console.log('Status poll:', data.status, 'running:', data.running);

                    const currentState = window.CreatorPal.Tracker.StateManager.getProcessingState();
                    if (currentState && currentState.isProcessing) {
                        window.CreatorPal.Tracker.StateManager.setProcessingState(
                            currentState.listName,
                            true,
                            data.step || 'Processing...',
                            data.progress || 10
                        );
                    }

                    if (data.status === 'completed') {
                        console.log('Analysis completed!');
                        stopStatusPolling();
                        window.CreatorPal.Tracker.StateManager.clearProcessingState();
                        setAnalyzingState(false);
                        showToast('Analysis completed! Refreshing page...', 'success');
                        setTimeout(() => window.location.reload(), 1000);
                    } else if (data.status === 'error') {
                        console.log('Analysis error:', data.error);
                        stopStatusPolling();
                        window.CreatorPal.Tracker.StateManager.clearProcessingState();
                        setAnalyzingState(false);
                        showToast('Analysis failed: ' + (data.error || 'Unknown error'), 'error');
                    } else if (!data.running && data.status !== 'processing') {
                        console.log('Analysis stopped unexpectedly');
                        stopStatusPolling();
                        window.CreatorPal.Tracker.StateManager.clearProcessingState();
                        setAnalyzingState(false);
                        showToast('Analysis stopped. Please try again.', 'warning');
                    }

                    if (pollCount >= maxPolls) {
                        console.log('Max polling duration reached');
                        stopStatusPolling();
                        window.CreatorPal.Tracker.StateManager.clearProcessingState();
                        setAnalyzingState(false);
                        showToast('Analysis taking longer than expected. Please check back later.', 'warning');
                    }
                })
                .catch(error => {
                    console.error('Error checking status:', error);
                    if (pollCount >= maxPolls) {
                        stopStatusPolling();
                        window.CreatorPal.Tracker.StateManager.clearProcessingState();
                        setAnalyzingState(false);
                        showToast('Connection lost. Please refresh the page.', 'error');
                    }
                });
            }, 2000);
        }

        function stopStatusPolling() {
            console.log('Stopping status polling');
            if (window.TrackerState.statusCheckInterval) {
                clearInterval(window.TrackerState.statusCheckInterval);
                window.TrackerState.statusCheckInterval = null;
            }
        }

        function setupViewToggle() {
            const analyticsBtn = document.getElementById('analytics-view-btn');
            const listsBtn = document.getElementById('lists-view-btn');

            if (analyticsBtn) {
                analyticsBtn.removeEventListener('click', analyticsClickHandler);
                analyticsBtn.addEventListener('click', analyticsClickHandler);
            }

            if (listsBtn) {
                listsBtn.removeEventListener('click', listsClickHandler);
                listsBtn.addEventListener('click', listsClickHandler);
            }
        }

        function analyticsClickHandler() {
            switchView('analytics');
        }

        function listsClickHandler() {
            switchView('lists');
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

        function setupListTypeToggle() {
            const newListType = document.getElementById('new-list-type-select');
            const xListIdContainer = document.getElementById('x-list-id-container');
            const xListHelpContainer = document.getElementById('x-list-help-container');

            if (newListType && xListIdContainer && xListHelpContainer) {
                newListType.removeEventListener('change', listTypeChangeHandler);
                newListType.addEventListener('change', listTypeChangeHandler);
                listTypeChangeHandler.call(newListType);
            }
        }

        function listTypeChangeHandler() {
            const xListIdContainer = document.getElementById('x-list-id-container');
            const xListHelpContainer = document.getElementById('x-list-help-container');

            if (this.value === 'x_list') {
                if (xListIdContainer) xListIdContainer.classList.add('show');
                if (xListHelpContainer) xListHelpContainer.classList.add('show');
            } else {
                if (xListIdContainer) xListIdContainer.classList.remove('show');
                if (xListHelpContainer) xListHelpContainer.classList.remove('show');
            }
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
            Object.values(window.TrackerState.charts).forEach(chart => {
                if (chart && chart.destroy) {
                    chart.destroy();
                }
            });
            window.TrackerState.charts = {};

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
                colors: ['#20D7D7'],
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
                            // Ensure the value is treated as a string
                            return String(value);
                        }
                    }
                }
            };

            try {
                const chart = new ApexCharts(element, config);
                window.TrackerState.charts[elementId] = chart;
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
                colors: ['#20D7D7'],
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
                            // Ensure the value is treated as a string
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
                window.TrackerState.charts['engagement-chart'] = chart;
                chart.render();
            } catch (error) {
                console.error('Error creating engagement chart:', error);
            }
        }

        // API Functions
        async function createList() {
            const listType = document.getElementById('new-list-type-select')?.value;
            const listName = document.getElementById('new-list-name-input')?.value?.trim();
            const xListId = document.getElementById('x-list-id-input')?.value?.trim();

            if (!listName) {
                showToast('Please enter a list name', 'error');
                return;
            }

            if (listType === 'x_list' && !xListId) {
                showToast('Please enter an X List ID', 'error');
                return;
            }

            const createBtn = document.getElementById('create-list-btn');
            setButtonLoading(createBtn, true);

            try {
                const data = { list_name: listName, list_type: listType };
                if (listType === 'x_list') {
                    data.x_list_id = xListId;
                }

                const response = await fetch('/niche/create-list', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                const result = await response.json();

                if (result.success) {
                    showToast('List created successfully!', 'success');
                    clearCreateForm();
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    showToast(result.message || 'Error creating list', 'error');
                }
            } catch (error) {
                showToast('Network error: ' + error.message, 'error');
            } finally {
                setButtonLoading(createBtn, false);
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

        async function editList(listName) {
            window.TrackerState.currentEditingList = listName;

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

            if (!window.TrackerState.currentEditingList) {
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
                        list_name: window.TrackerState.currentEditingList,
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
            if (!window.TrackerState.currentEditingList) return;

            try {
                const response = await fetch('/niche/remove-creator', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        list_name: window.TrackerState.currentEditingList,
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
            const button = document.querySelector(`[data-list-name="${listName}"].update-x-list-btn`);
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
            window.TrackerState.currentDeletingList = listName;
            document.getElementById('delete-list-name').textContent = `List: ${listName}`;
            showModal('delete-modal');
        }

        async function deleteList() {
            if (!window.TrackerState.currentDeletingList) return;

            const confirmBtn = document.getElementById('confirm-delete');
            setButtonLoading(confirmBtn, true);

            try {
                const response = await fetch('/niche/delete-list', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ list_name: window.TrackerState.currentDeletingList })
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
                    <button class="tracker-list-action-btn delete" onclick="removeCreator('${creator}')">
                        <i class="ph ph-trash"></i>
                    </button>
                `;
                creatorsList.appendChild(creatorCard);
            });
        }

        function clearCreateForm() {
            const inputs = ['new-list-name-input', 'x-list-id-input'];
            inputs.forEach(id => {
                const element = document.getElementById(id);
                if (element) element.value = '';
            });
        }

        function showModal(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) modal.style.display = 'flex';
        }

        function hideModal(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) modal.style.display = 'none';
        }

        function setButtonLoading(button, loading) {
            if (!button) return;

            if (loading) {
                button.setAttribute('data-original-content', button.innerHTML);
                button.innerHTML = '<div class="tracker-loading-spinner"></div> Loading...';
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
            let toastContainer = document.getElementById('tracker-toast-container');
            if (!toastContainer) {
                toastContainer = document.createElement('div');
                toastContainer.className = 'tracker-toast-container';
                toastContainer.id = 'tracker-toast-container';
                document.body.appendChild(toastContainer);
            }

            const toast = document.createElement('div');
            let icon = 'info';

            if (type === 'success') icon = 'check-circle';
            else if (type === 'error') icon = 'warning-circle';
            else if (type === 'warning') icon = 'warning';

            toast.className = `tracker-toast ${type}`;
            toast.innerHTML = `
                <i class="ph ph-${icon}" style="font-size: 1.25rem;"></i>
                <span>${message}</span>
            `;

            toastContainer.appendChild(toast);

            setTimeout(() => toast.classList.add('show'), 100);

            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            }, 4000);
        }

        // Expose removeCreator function globally for onclick handlers
        window.removeCreator = removeCreator;

        // Store cleanup function
        eventHandlers.cleanup = function() {
            console.log('Cleaning up tracker event listeners and state');

            // Stop polling
            stopStatusPolling();

            // Destroy charts
            if (window.TrackerState && window.TrackerState.charts) {
                Object.values(window.TrackerState.charts).forEach(chart => {
                    if (chart && chart.destroy) {
                        chart.destroy();
                    }
                });
                window.TrackerState.charts = {};
            }

            // Remove event listeners
            document.removeEventListener('click', eventHandlers.delegatedClick);
            document.removeEventListener('click', eventHandlers.modalClick);
            document.removeEventListener('keydown', eventHandlers.formKey);
        };
    }

    // Initialize on DOMContentLoaded
    document.addEventListener('DOMContentLoaded', function() {
        if (document.getElementById('analytics-panel')) {
            initializeTracker();
        }
    });

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', function() {
        if (document.getElementById('analytics-panel')) {
            console.log('DOM ready, initializing tracker');
            initializeTracker();
        }
    });
})();