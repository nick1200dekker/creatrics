// State management
let currentSpaceId = null;
let statusPollInterval = null;
let isProcessing = false;
let audioEditor = null;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    checkForActiveProcess();
});

// Toggle sections
function toggleHowItWorks() {
    const section = document.getElementById('howItWorksSection');
    section.classList.toggle('show');
}

function toggleHistory() {
    const panel = document.getElementById('historyPanel');
    panel.classList.toggle('show');
}

function toggleTranscript() {
    const content = document.getElementById('transcriptContent');
    const btn = document.getElementById('toggleTranscriptBtn');
    
    if (content.classList.contains('show')) {
        content.classList.remove('show');
        btn.innerHTML = '<i class="ph ph-eye"></i> Show Transcript';
    } else {
        content.classList.add('show');
        btn.innerHTML = '<i class="ph ph-eye-slash"></i> Hide Transcript';
    }
}

// Switch summary tabs
function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.summary-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.getElementById(tabName + 'Tab').classList.add('active');
    
    // Update tab panels
    document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    document.getElementById(tabName + 'Panel').classList.add('active');
}

// Audio Editor Class - Simplified version from original
class AudioEditor {
    constructor(audioUrl, containerId) {
        this.audioUrl = audioUrl;
        this.container = document.getElementById(containerId);
        this.regions = [];
        this.currentRegion = null;
        this.isPlaying = false;
        this.currentTime = 0;
        this.duration = 0;
        
        this.initializeUI();
        this.initializeWaveSurfer();
        this.initializeEventListeners();
    }
    
    initializeUI() {
        // Create the editor container
        this.editorContainer = document.createElement('div');
        this.editorContainer.className = 'audio-editor-container';
        
        // Create current time display
        this.currentTimeDisplay = document.createElement('div');
        this.currentTimeDisplay.className = 'current-time-display';
        this.currentTimeDisplay.innerHTML = '00:00.00 / 00:00.00';
        
        // Create waveform container
        this.waveformContainer = document.createElement('div');
        this.waveformContainer.className = 'waveform-container';
        this.waveformContainer.style.position = 'relative';
        
        // Create loading indicator
        this.loadingIndicator = document.createElement('div');
        this.loadingIndicator.className = 'audio-loading-indicator';
        this.loadingIndicator.innerHTML = `
            <div class="audio-spinner">
                <i class="ph ph-circle-notch ph-spin"></i>
            </div>
            <div class="audio-loading-text">Loading audio...</div>
        `;
        this.waveformContainer.appendChild(this.loadingIndicator);
        
        // Create timeline container
        this.timelineContainer = document.createElement('div');
        this.timelineContainer.className = 'timeline-container';
        
        // Create controls container
        this.controlsContainer = document.createElement('div');
        this.controlsContainer.className = 'editor-controls';
        
        // Play/Pause button
        this.playButton = document.createElement('button');
        this.playButton.className = 'editor-button play-button';
        this.playButton.innerHTML = '<i class="ph ph-play"></i> Play';
        
        // Add region button
        this.addRegionButton = document.createElement('button');
        this.addRegionButton.className = 'editor-button add-region-button';
        this.addRegionButton.innerHTML = '<i class="ph ph-scissors"></i> Select Part';
        
        // Delete region button
        this.deleteRegionButton = document.createElement('button');
        this.deleteRegionButton.className = 'editor-button delete-region-button';
        this.deleteRegionButton.innerHTML = '<i class="ph ph-trash"></i> Delete Part';
        this.deleteRegionButton.disabled = true;
        
        // Export button
        this.exportButton = document.createElement('button');
        this.exportButton.className = 'editor-button secondary-button';
        this.exportButton.innerHTML = '<i class="ph ph-download"></i> Export';
        
        // Create navigation group
        this.navigationGroup = document.createElement('div');
        this.navigationGroup.className = 'navigation-group';
        
        // Navigation buttons
        this.prevRegionButton = document.createElement('button');
        this.prevRegionButton.className = 'editor-button prev-region-button';
        this.prevRegionButton.innerHTML = '<i class="ph ph-caret-left"></i>';
        this.prevRegionButton.disabled = true;
        this.prevRegionButton.title = 'Previous part';
        
        this.partsCounter = document.createElement('span');
        this.partsCounter.className = 'parts-counter';
        this.partsCounter.innerHTML = 'Part 0/0';
        
        this.nextRegionButton = document.createElement('button');
        this.nextRegionButton.className = 'editor-button next-region-button';
        this.nextRegionButton.innerHTML = '<i class="ph ph-caret-right"></i>';
        this.nextRegionButton.disabled = true;
        this.nextRegionButton.title = 'Next part';
        
        this.navigationGroup.appendChild(this.prevRegionButton);
        this.navigationGroup.appendChild(this.partsCounter);
        this.navigationGroup.appendChild(this.nextRegionButton);
        
        // Add controls to container
        this.controlsContainer.appendChild(this.playButton);
        this.controlsContainer.appendChild(this.addRegionButton);
        this.controlsContainer.appendChild(this.deleteRegionButton);
        this.controlsContainer.appendChild(this.exportButton);
        this.controlsContainer.appendChild(this.navigationGroup);
        
        // Add all elements to editor container
        this.editorContainer.appendChild(this.currentTimeDisplay);
        this.editorContainer.appendChild(this.waveformContainer);
        this.editorContainer.appendChild(this.timelineContainer);
        this.editorContainer.appendChild(this.controlsContainer);
        
        // Add editor to main container
        this.container.appendChild(this.editorContainer);
    }
    
    initializeWaveSurfer() {
        // Create unique IDs to prevent conflicts
        this.waveformId = 'waveform-' + Math.random().toString(36).substring(2, 9);
        this.timelineId = 'timeline-' + Math.random().toString(36).substring(2, 9);
        
        // Set unique IDs for the containers
        this.waveformContainer.id = this.waveformId;
        this.timelineContainer.id = this.timelineId;
        
        // Create a hidden audio element for better streaming support
        this.audioElement = document.createElement('audio');
        this.audioElement.crossOrigin = 'anonymous';
        this.audioElement.preload = 'metadata';
        this.audioElement.style.display = 'none';
        document.body.appendChild(this.audioElement);
        
        // Create WaveSurfer instance
        this.wavesurfer = WaveSurfer.create({
            container: '#' + this.waveformId,
            waveColor: '#4ad7d7',
            progressColor: '#20D7D7',
            cursorColor: '#ffffff',
            barWidth: 2,
            barRadius: 3,
            cursorWidth: 1,
            height: 80,
            barGap: 2,
            responsive: true,
            normalize: true,
            backend: 'MediaElement',
            mediaElement: this.audioElement,
            plugins: [
                WaveSurfer.timeline.create({
                    container: '#' + this.timelineId,
                    primaryColor: '#20D7D7',
                    secondaryColor: '#128c8c',
                    primaryFontColor: '#ffffff',
                    secondaryFontColor: '#e2e8f0',
                    fontSize: 12,
                }),
                WaveSurfer.regions.create({
                    regions: [],
                    dragSelection: true,
                    color: 'rgba(32, 215, 215, 0.3)',
                    slop: 5
                })
            ]
        });
        
        // Initialize regions array
        this.regions = [];
        
        // Show loading indicator
        this.showLoading();
        
        // Load audio
        this.wavesurfer.load(this.audioUrl);
        
        // Set up WaveSurfer events
        this.wavesurfer.on('ready', () => {
            console.log('WaveSurfer is ready');
            this.duration = this.wavesurfer.getDuration();
            
            // Hide loading indicator
            this.hideLoading();
            
            // Configure timeline intervals based on duration
            this.configureTimelineIntervals();
            
            // Update time display
            this.updateTimeDisplay();
            
            this.wavesurfer.enableDragSelection({
                color: 'rgba(32, 215, 215, 0.3)'
            });
            
            // Show toast when ready
            showToast('Audio loaded. Click and drag to select parts.', 'success', 5000);
        });
        
        // Update time display during playback
        this.wavesurfer.on('audioprocess', () => {
            this.currentTime = this.wavesurfer.getCurrentTime();
            this.updateTimeDisplay();
        });
        
        this.wavesurfer.on('seek', () => {
            this.currentTime = this.wavesurfer.getCurrentTime();
            this.updateTimeDisplay();
        });
        
        // Handle region creation
        this.wavesurfer.on('region-created', (region) => {
            console.log('Region created:', region);
            
            // Make sure the region isn't already in our array
            const exists = this.regions.some(r => r.id === region.id);
            if (!exists) {
                this.regions.push(region);
                console.log(`Added region ${region.id}, total regions: ${this.regions.length}`);
            }
            
            this.selectRegion(region);
            this.updateNavigationButtons();
        });
        
        this.wavesurfer.on('region-clicked', (region, e) => {
            e.stopPropagation();
            this.selectRegion(region);
            this.wavesurfer.seekTo(region.start / this.duration);
        });
        
        this.wavesurfer.on('play', () => {
            this.isPlaying = true;
            this.playButton.innerHTML = '<i class="ph ph-pause"></i> Pause';
        });
        
        this.wavesurfer.on('pause', () => {
            this.isPlaying = false;
            this.playButton.innerHTML = '<i class="ph ph-play"></i> Play';
        });
        
        this.wavesurfer.on('error', (error) => {
            console.error('WaveSurfer error:', error);
            this.hideLoading();
            showToast('Error loading audio. Please try again.', 'error');
        });
    }
    
    configureTimelineIntervals() {
        // Configure timeline intervals based on duration
        const durationMinutes = this.duration / 60;
        let timeInterval;
        
        if (durationMinutes <= 5) {
            timeInterval = 30;
        } else if (durationMinutes <= 15) {
            timeInterval = 60;
        } else if (durationMinutes <= 30) {
            timeInterval = 120;
        } else if (durationMinutes <= 60) {
            timeInterval = 300;
        } else if (durationMinutes <= 120) {
            timeInterval = 600;
        } else {
            timeInterval = 900;
        }
        
        // Update the timeline plugin with the calculated interval
        if (this.wavesurfer.timeline) {
            this.wavesurfer.timeline.params.timeInterval = timeInterval;
            this.wavesurfer.timeline.render();
        }
    }
    
    updateTimeDisplay() {
        const current = this.formatTime(this.currentTime);
        const total = this.formatTime(this.duration);
        this.currentTimeDisplay.innerHTML = `${current} / ${total}`;
    }
    
    initializeEventListeners() {
        // Play/Pause button
        this.playButton.addEventListener('click', () => {
            this.wavesurfer.playPause();
        });
        
        // Add region button
        this.addRegionButton.addEventListener('click', () => {
            const region = this.wavesurfer.addRegion({
                start: this.wavesurfer.getCurrentTime(),
                end: Math.min(this.wavesurfer.getCurrentTime() + 30, this.duration),
                color: 'rgba(32, 215, 215, 0.3)',
                drag: true,
                resize: true
            });
            
            this.wavesurfer.seekTo(region.start / this.duration);
        });
        
        // Previous region button
        this.prevRegionButton.addEventListener('click', () => {
            if (this.regions.length <= 1) return;
            
            const currentIndex = this.regions.findIndex(r => r.id === this.currentRegion?.id);
            
            if (currentIndex > 0) {
                const prevRegion = this.regions[currentIndex - 1];
                this.selectRegion(prevRegion);
            }
        });
        
        // Next region button
        this.nextRegionButton.addEventListener('click', () => {
            if (this.regions.length <= 1) return;
            
            const currentIndex = this.regions.findIndex(r => r.id === this.currentRegion?.id);
            
            if (currentIndex < this.regions.length - 1) {
                const nextRegion = this.regions[currentIndex + 1];
                this.selectRegion(nextRegion);
            }
        });
        
        // Delete region button
        this.deleteRegionButton.addEventListener('click', () => {
            if (this.currentRegion) {
                const currentIndex = this.regions.findIndex(r => r.id === this.currentRegion.id);
                this.currentRegion.remove();
                this.regions = this.regions.filter(r => r.id !== this.currentRegion.id);
                
                if (this.regions.length > 0) {
                    const nextIndex = Math.min(currentIndex, this.regions.length - 1);
                    this.selectRegion(this.regions[nextIndex]);
                } else {
                    this.currentRegion = null;
                    this.deleteRegionButton.disabled = true;
                    this.updatePartsCounter();
                    this.updateNavigationButtons();
                }
            }
        });
        
        // Export button
        this.exportButton.addEventListener('click', () => {
            if (this.regions.length === 0) {
                showToast('Please select at least one part to export', 'error');
                return;
            }
            
            if (this.currentRegion) {
                this.exportRegion(this.currentRegion);
            } else {
                showToast('Please select a region to export', 'error');
            }
        });
    }
    
    selectRegion(region) {
        // Deselect previous region
        if (this.currentRegion) {
            this.currentRegion.element.classList.remove('selected-region');
        }
        
        // Select new region
        this.currentRegion = region;
        region.element.classList.add('selected-region');
        this.deleteRegionButton.disabled = false;
        
        // Position cursor at start of region
        this.wavesurfer.seekTo(region.start / this.duration);
        
        // Update the parts counter
        this.updatePartsCounter();
        
        // Enable/disable navigation buttons
        this.updateNavigationButtons();
    }
    
    updatePartsCounter() {
        if (!this.regions || this.regions.length === 0) {
            this.partsCounter.innerHTML = `Part 0/0`;
            return;
        }
        
        if (!this.currentRegion) {
            this.partsCounter.innerHTML = `Part -/${this.regions.length}`;
            return;
        }
        
        // Find the current region's index
        const currentIndex = this.regions.findIndex(r => r.id === this.currentRegion.id);
        
        if (currentIndex !== -1) {
            this.partsCounter.innerHTML = `Part ${currentIndex + 1}/${this.regions.length}`;
        } else {
            this.partsCounter.innerHTML = `Part ?/${this.regions.length}`;
        }
    }
    
    updateNavigationButtons() {
        // Disable both buttons if there are no regions or only one region
        if (!this.regions || this.regions.length <= 1) {
            this.prevRegionButton.disabled = true;
            this.nextRegionButton.disabled = true;
            return;
        }
        
        // If no region is selected, disable both
        if (!this.currentRegion) {
            this.prevRegionButton.disabled = true;
            this.nextRegionButton.disabled = true;
            return;
        }
        
        // Get the current index
        const currentIndex = this.regions.findIndex(r => r.id === this.currentRegion.id);
        
        // If region not found in array, disable both
        if (currentIndex === -1) {
            this.prevRegionButton.disabled = true;
            this.nextRegionButton.disabled = true;
            return;
        }
        
        // Enable/disable based on position
        this.prevRegionButton.disabled = currentIndex === 0;
        this.nextRegionButton.disabled = currentIndex >= this.regions.length - 1;
    }
    
    formatTime(seconds) {
        if (!seconds || isNaN(seconds)) return '00:00.00';
        
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        
        return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toFixed(2).padStart(5, '0')}`;
    }
    
    exportRegion(region) {
        // Show processing indicator
        showToast('Processing your request...', 'info');
        
        // Get the space ID from the URL or container
        const spaceId = this.getSpaceIdFromUrl();
        if (!spaceId) {
            showToast('Could not determine Space ID', 'error');
            return;
        }
        
        // Prepare request data
        const requestData = {
            space_id: spaceId,
            start: region.start,
            end: region.end,
            filename: `twitter_space_${spaceId}_trim_${Math.floor(region.start)}_${Math.floor(region.end)}.mp3`
        };
        
        // Send request to backend
        fetch('/clip-spaces/trim', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Failed to trim audio');
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Create a temporary link to ensure cookies are sent
                const link = document.createElement('a');
                link.href = data.download_url;
                link.download = data.filename || 'download';
                link.target = '_blank';
                link.style.display = 'none';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                showToast('Audio trimmed and download started!', 'success');
            } else {
                throw new Error(data.error || 'Failed to trim audio');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast(error.message || 'Error trimming audio', 'error');
        });
    }
    
    getSpaceIdFromUrl() {
        // Try to get from the audio editor container data attribute
        const container = document.getElementById('audioEditorContainer');
        if (container) {
            const spaceId = container.getAttribute('data-space-id');
            if (spaceId) return spaceId;
        }
        
        // Try to get from URL parameter
        const urlParams = new URLSearchParams(window.location.search);
        const spaceId = urlParams.get('space_id');
        if (spaceId) return spaceId;
        
        // Try to get from the audio URL path
        const match = this.audioUrl.match(/\/clip-spaces\/audio\/([^\/\?]+)/);
        if (match && match[1]) return match[1];
        
        // Check if it's in the current path
        const pathMatch = window.location.pathname.match(/\/clip-spaces\/info\/([^\/]+)/);
        if (pathMatch && pathMatch[1]) return pathMatch[1];
        
        // If all else fails, try to find it in the page content
        const spaceIdElement = document.querySelector('[data-space-id]');
        if (spaceIdElement) return spaceIdElement.getAttribute('data-space-id');
        
        return null;
    }
    
    showLoading() {
        if (this.loadingIndicator) {
            this.loadingIndicator.style.display = 'flex';
            // Disable controls while loading
            this.playButton.disabled = true;
            this.addRegionButton.disabled = true;
            this.exportButton.disabled = true;
        }
    }
    
    hideLoading() {
        if (this.loadingIndicator) {
            this.loadingIndicator.style.display = 'none';
            // Enable controls
            this.playButton.disabled = false;
            this.addRegionButton.disabled = false;
            this.exportButton.disabled = false;
        }
    }
    
    destroy() {
        // Clean up WaveSurfer instance
        if (this.wavesurfer) {
            this.wavesurfer.destroy();
        }
        
        // Remove the audio element
        if (this.audioElement && this.audioElement.parentNode) {
            this.audioElement.parentNode.removeChild(this.audioElement);
        }
        
        // Remove the editor container
        if (this.editorContainer && this.editorContainer.parentNode) {
            this.editorContainer.parentNode.removeChild(this.editorContainer);
        }
    }
}

// Process space
async function processSpace() {
    const spaceId = document.getElementById('spaceId').value.trim();
    
    if (!spaceId) {
        showToast('Please enter a Space ID', 'error');
        return;
    }
    
    if (isProcessing) return;
    
    // Check for active process first
    try {
        const checkResponse = await fetch('/clip-spaces/check_processing');
        const checkData = await checkResponse.json();
        
        if (checkData.has_active_process && checkData.space_id !== spaceId) {
            showToast('Another space is already being processed. Please wait for it to complete.', 'error');
            return;
        }
    } catch (error) {
        console.warn('Could not check for active processes:', error);
    }
    
    isProcessing = true;
    currentSpaceId = spaceId;
    
    // Update UI to processing state
    hideAllSections();
    showSection('loadingSection');
    updateProcessButton(true);
    updateLoadingStatus('Starting processing...', 5);
    
    try {
        const formData = new FormData();
        formData.append('space_id', spaceId);
        
        const response = await fetch('/clip-spaces/process', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            startStatusPolling(spaceId);
        } else {
            // Check if it's an insufficient credits error
            if (data.error_type === 'insufficient_credits') {
                hideAllSections();
                showSection('insufficientCreditsSection');
                document.getElementById('creditsDescription').innerHTML = `
                    You need <strong>${data.required_credits?.toFixed(2) || '0.00'}</strong> credits but only have
                    <strong>${data.current_credits?.toFixed(2) || '0.00'}</strong> credits.
                `;
            } else {
                throw new Error(data.error || 'Failed to start processing');
            }
        }
    } catch (error) {
        console.error('Error processing space:', error);
        isProcessing = false;
        updateProcessButton(false);
        hideAllSections();
        showSection('errorSection');
        document.getElementById('errorText').textContent = error.message;
        showToast('Failed to start processing', 'error');
    }
}

// Check for active process on page load
async function checkForActiveProcess() {
    try {
        const response = await fetch('/clip-spaces/check_processing');
        const data = await response.json();
        
        if (data.has_active_process) {
            const spaceId = data.space_id;
            currentSpaceId = spaceId;
            isProcessing = true;
            
            // Set space ID in input
            document.getElementById('spaceId').value = spaceId;
            
            // Show loading state
            hideAllSections();
            showSection('loadingSection');
            updateProcessButton(true);
            updateLoadingStatus(data.status.message || 'Processing in progress...', data.status.progress || 10);
            
            // Start polling
            startStatusPolling(spaceId);
        }
    } catch (error) {
        console.log('No active processes found');
    }
}

// Start status polling
function startStatusPolling(spaceId) {
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
    }
    
    statusPollInterval = setInterval(async function() {
        try {
            const response = await fetch('/clip-spaces/status/' + spaceId);
            const status = await response.json();
            
            updateLoadingStatus(status.message, status.progress);
            
            if (status.status === 'completed') {
                clearInterval(statusPollInterval);
                statusPollInterval = null;
                isProcessing = false;
                updateProcessButton(false);
                loadSpaceData(spaceId);
            } else if (status.status === 'error') {
                clearInterval(statusPollInterval);
                statusPollInterval = null;
                isProcessing = false;
                updateProcessButton(false);
                hideAllSections();
                showSection('errorSection');
                document.getElementById('errorText').textContent = status.error || 'Processing failed';
                showToast('Processing failed', 'error');
            }
        } catch (error) {
            console.error('Status polling error:', error);
        }
    }, 2000);
}

// Load space data
async function loadSpaceData(spaceId) {
    try {
        updateLoadingStatus('Loading space data...', 95);
        
        const response = await fetch('/clip-spaces/info/' + spaceId);
        const data = await response.json();
        
        if (data.success) {
            populateSpaceData(data);
            hideAllSections();
            showSection('resultsSection');
            showToast('Space processed successfully!', 'success');
        } else {
            throw new Error(data.error || 'Failed to load space data');
        }
    } catch (error) {
        console.error('Error loading space data:', error);
        hideAllSections();
        showSection('errorSection');
        document.getElementById('errorText').textContent = error.message;
        showToast('Failed to load space data', 'error');
    }
}

// Load existing space from history
window.loadSpace = function(spaceId) {
    // Hide history panel
    document.getElementById('historyPanel').classList.remove('show');
    
    // Set space ID and load
    document.getElementById('spaceId').value = spaceId;
    currentSpaceId = spaceId;
    
    // Show loading
    hideAllSections();
    showSection('loadingSection');
    updateLoadingStatus('Loading space data...', 50);
    
    loadSpaceData(spaceId);
};

// Populate space data
function populateSpaceData(data) {
    const spaceInfo = data.space_info;
    
    // Format date
    function formatDate(timestamp) {
        const date = new Date(parseInt(timestamp));
        return date.toLocaleString();
    }
    
    // Update space details
    document.getElementById('spaceTitle').textContent = spaceInfo.creator?.display_name || 'Twitter Space';
    document.getElementById('spaceCreator').textContent = 'Creator: ' + (spaceInfo.creator?.display_name || 'Unknown') + ' (@' + (spaceInfo.creator?.screenname || 'unknown') + ')';
    document.getElementById('spaceDate').textContent = 'Started: ' + formatDate(spaceInfo.started);
    document.getElementById('spaceListeners').textContent = 'Listeners: ' + (spaceInfo.total_live_listeners || 0) + ' live, ' + (spaceInfo.total_replay_watched || 0) + ' replay';
    
    // Populate participants
    const participantsList = document.getElementById('participantsList');
    participantsList.innerHTML = '';
    
    function addParticipants(role, participants) {
        if (participants && participants.length > 0) {
            participants.forEach(participant => {
                const item = document.createElement('div');
                item.className = 'participant-item';
                item.innerHTML = `
                    <img src="${participant.avatar || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png'}" 
                         alt="${participant.display_name || 'User'}" 
                         class="participant-avatar">
                    <span class="participant-name">${(participant.display_name || 'User')} (@${participant.screenname || 'unknown'}) - ${role}</span>
                `;
                participantsList.appendChild(item);
            });
        }
    }
    
    if (spaceInfo.participants) {
        addParticipants('Host', spaceInfo.participants.admins);
        addParticipants('Speaker', spaceInfo.participants.speakers);
    }
    
    // Initialize audio editor
    if (data.audio_url) {
        initializeAudioEditor(data.audio_url, data.space_id);
    } else {
        document.getElementById('audioEditorContainer').innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 2rem;">No audio available for this space</div>';
    }
    
    // Handle summary
    if (data.summary) {
        handleSummaryContent(data.summary);
    } else {
        document.getElementById('overviewContent').innerHTML = '<p style="color: var(--text-secondary);">No summary was generated for this space.</p>';
        document.getElementById('quotesContent').innerHTML = '<p style="color: var(--text-secondary);">No highlights were generated for this space.</p>';
    }
    
    // Handle transcript
    if (data.transcript) {
        formatTranscript(data.transcript);
        document.getElementById('transcriptInfo').textContent = data.transcript.length.toLocaleString() + ' characters';
        document.getElementById('toggleTranscriptBtn').disabled = false;
    } else {
        document.getElementById('transcriptContent').innerHTML = '<p style="color: var(--text-secondary); padding: 1rem;">No transcript was generated for this space.</p>';
        document.getElementById('transcriptInfo').textContent = '0 characters';
        document.getElementById('toggleTranscriptBtn').disabled = true;
    }
}

// Initialize audio editor
function initializeAudioEditor(audioUrl, spaceId) {
    const container = document.getElementById('audioEditorContainer');
    container.setAttribute('data-space-id', spaceId);
    
    // Clear previous editor if exists
    container.innerHTML = '';
    
    // Destroy previous editor instance
    if (audioEditor) {
        try {
            audioEditor.destroy();
        } catch (e) {
            console.error("Error destroying previous audio editor:", e);
        }
        audioEditor = null;
    }
    
    // Wait a bit for the container to be ready, then create new editor
    setTimeout(function() {
        try {
            audioEditor = new AudioEditor(audioUrl, 'audioEditorContainer');
            console.log("Audio editor created successfully");
        } catch (error) {
            console.error("Error creating audio editor:", error);
            container.innerHTML = `
                <div style="text-align: center; color: var(--text-secondary); padding: 2rem;">
                    <div style="margin-bottom: 1rem;">Audio editor failed to load</div>
                    <audio controls style="width: 100%; max-width: 400px;">
                        <source src="${audioUrl}" type="audio/mpeg">
                        Your browser does not support the audio element.
                    </audio>
                </div>
            `;
            showToast('Audio editor failed to load, using fallback player', 'error');
        }
    }, 500);
}

// Handle summary content
function handleSummaryContent(summary) {
    if (summary.includes("## Overview") && summary.includes("## Key Highlights and Quotes")) {
        const overviewSection = summary.split("## Key Highlights and Quotes")[0]
            .replace("# Twitter Space Summary", "")
            .replace("## Overview", "")
            .trim();
        const quotesSection = summary.split("## Key Highlights and Quotes")[1].trim();
        
        // Use marked.js if available, otherwise simple formatting
        if (typeof marked !== 'undefined') {
            document.getElementById('overviewContent').innerHTML = marked.parse(overviewSection);
        } else {
            document.getElementById('overviewContent').innerHTML = formatMarkdown(overviewSection);
        }
        formatKeyQuotes(quotesSection);
    } else {
        // If different format, put everything in overview
        if (typeof marked !== 'undefined') {
            document.getElementById('overviewContent').innerHTML = marked.parse(summary);
        } else {
            document.getElementById('overviewContent').innerHTML = formatMarkdown(summary);
        }
        document.getElementById('quotesContent').innerHTML = '<p style="color: var(--text-secondary);">No detailed highlights available for this Space.</p>';
    }
}

// Simple markdown formatter
function formatMarkdown(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/^/, '<p>')
        .replace(/$/, '</p>');
}

// Format key quotes
function formatKeyQuotes(quotesText) {
    const container = document.getElementById('quotesContent');
    container.innerHTML = '';
    
    // Parse quotes format: **[MM:SS.MS - MM:SS.MS] speaker_name: "quote text"**
    const quotePattern = /\*\*\[(\d{2}:\d{2}\.\d{2})\s*-\s*(\d{2}:\d{2}\.\d{2})\]\s+([^:]+):\s*"([^"]+)"\*\*/g;
    let matches = [];
    let match;
    
    while ((match = quotePattern.exec(quotesText)) !== null) {
        matches.push({
            startTime: match[1].trim(),
            endTime: match[2].trim(),
            speaker: match[3].trim(),
            text: match[4].trim()
        });
    }
    
    if (matches.length > 0) {
        matches.forEach(quote => {
            const quoteEl = document.createElement('div');
            quoteEl.className = 'quote-item';
            quoteEl.innerHTML = `
                <div class="quote-speaker">${escapeHtml(quote.speaker)}</div>
                <div class="quote-timestamp">${quote.startTime} - ${quote.endTime}</div>
                <div class="quote-text">"${escapeHtml(quote.text)}"</div>
                <div class="quote-actions">
                    <button class="quote-btn" onclick="playQuote('${quote.startTime}')">
                        <i class="ph ph-play"></i> Play
                    </button>
                    <button class="quote-btn" onclick="downloadQuote('${quote.startTime}', '${quote.endTime}', '${escapeHtml(quote.speaker)}')">
                        <i class="ph ph-download"></i> Download
                    </button>
                </div>
            `;
            container.appendChild(quoteEl);
        });
    } else {
        container.innerHTML = '<p style="color: var(--text-secondary);">No detailed highlights could be parsed from this Space.</p>';
    }
}

// Format transcript
function formatTranscript(transcript) {
    const container = document.getElementById('transcriptContent');
    container.innerHTML = '';
    
    // Parse transcript format
    const segmentPattern = /(\d{2}:\d{2}\.\d{2})\s*-\s*(\d{2}:\d{2}\.\d{2})\s*\n\*\*([^*:]+):\*\*\s*\n([\s\S]*?)(?=\n\d{2}:\d{2}\.\d{2}|\n\n\d{2}:\d{2}\.\d{2}|$)/g;
    let matches = [];
    let match;
    
    while ((match = segmentPattern.exec(transcript)) !== null) {
        matches.push({
            startTime: match[1],
            endTime: match[2],
            speaker: match[3].trim(),
            text: match[4].trim()
        });
    }
    
    // Try alternative parsing if first method fails
    if (matches.length === 0) {
        const segments = transcript.split('\n\n');
        
        segments.forEach(function(segment) {
            if (!segment.trim()) return;
            
            const lines = segment.split('\n');
            if (lines.length >= 3) {
                const timestampMatch = lines[0].match(/(\d{2}:\d{2}\.\d{2})\s*-\s*(\d{2}:\d{2}\.\d{2})/);
                if (timestampMatch) {
                    const speakerMatch = lines[1].match(/\*\*([^*:]+):\*\*/);
                    if (speakerMatch) {
                        matches.push({
                            startTime: timestampMatch[1],
                            endTime: timestampMatch[2],
                            speaker: speakerMatch[1].trim(),
                            text: lines.slice(2).join('\n').trim()
                        });
                    }
                }
            }
        });
    }
    
    if (matches.length > 0) {
        matches.forEach(segment => {
            if (segment.text && segment.text.trim()) {
                const segmentEl = document.createElement('div');
                segmentEl.className = 'transcript-segment';
                segmentEl.innerHTML = `
                    <div class="transcript-timestamp">${segment.startTime} - ${segment.endTime}</div>
                    <div class="transcript-speaker">${escapeHtml(segment.speaker)}:</div>
                    <div class="transcript-text">${escapeHtml(segment.text)}</div>
                `;
                container.appendChild(segmentEl);
            }
        });
    } else {
        container.innerHTML = '<p style="color: var(--text-secondary);">Could not parse transcript format.</p>';
    }
}

// Play quote function
function playQuote(startTime) {
    if (audioEditor && audioEditor.wavesurfer) {
        // Convert time string to seconds
        const timeInSeconds = convertTimeToSeconds(startTime);
        const seekPosition = timeInSeconds / audioEditor.duration;
        audioEditor.wavesurfer.seekTo(seekPosition);
        audioEditor.wavesurfer.play();
    } else {
        showToast('Audio player not ready', 'error');
    }
}

// Download quote function  
function downloadQuote(startTime, endTime, speaker) {
    // Get space ID from the audio editor container
    const spaceId = getSpaceIdFromContainer();
    if (!spaceId) {
        showToast('Could not determine Space ID', 'error');
        return;
    }
    
    showToast('Processing quote download...', 'info');
    
    // Sanitize speaker name for filename
    const sanitizedSpeaker = speaker.replace(/[^a-zA-Z0-9_]/g, '');
    
    // Convert time strings to seconds
    const startTimeSeconds = convertTimeToSeconds(startTime);
    const endTimeSeconds = convertTimeToSeconds(endTime);
    
    // Prepare request data
    const requestData = {
        space_id: spaceId,
        start: startTimeSeconds,
        end: endTimeSeconds,
        filename: 'quote_' + sanitizedSpeaker + '_' + Math.floor(startTimeSeconds) + '_' + Math.floor(endTimeSeconds) + '.mp3'
    };
    
    // Send request to backend
    fetch('/clip-spaces/trim', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Failed to download quote');
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            const link = document.createElement('a');
            link.href = data.download_url;
            link.download = data.filename || 'quote.mp3';
            link.target = '_blank';
            link.style.display = 'none';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            showToast('Quote download started!', 'success');
        } else {
            throw new Error(data.error || 'Failed to download quote');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast(error.message || 'Error downloading quote', 'error');
    });
}

// Helper function to convert MM:SS.MS to seconds
function convertTimeToSeconds(timeStr) {
    if (!timeStr) return 0;
    
    const parts = timeStr.split(':');
    if (parts.length !== 2) return 0;
    
    const minutes = parseInt(parts[0]) || 0;
    const secondsPart = parseFloat(parts[1]) || 0;
    
    return minutes * 60 + secondsPart;
}

// Helper function to get space ID from container
function getSpaceIdFromContainer() {
    const container = document.getElementById('audioEditorContainer');
    if (container) {
        const spaceId = container.getAttribute('data-space-id');
        if (spaceId) return spaceId;
    }
    
    const urlParams = new URLSearchParams(window.location.search);
    const spaceId = urlParams.get('space_id');
    if (spaceId) return spaceId;
    
    const pathMatch = window.location.pathname.match(/\/spaces\/info\/([^\/]+)/);
    if (pathMatch && pathMatch[1]) return pathMatch[1];
    
    return null;
}

// Utility functions
function hideAllSections() {
    document.querySelectorAll('.loading-section, .error-section, .insufficient-credits-section, .results-section').forEach(section => {
        section.classList.remove('show');
    });
}

function showSection(sectionId) {
    document.getElementById(sectionId).classList.add('show');
}

function updateProcessButton(processing) {
    const btn = document.getElementById('processBtn');
    if (processing) {
        btn.disabled = true;
        btn.classList.add('processing');
        btn.innerHTML = '<i class="ph ph-spinner"></i> Processing...';
    } else {
        btn.disabled = false;
        btn.classList.remove('processing');
        btn.innerHTML = '<i class="ph ph-sparkle"></i> Process Space';
    }
}

function updateLoadingStatus(message, progress) {
    document.getElementById('loadingStatus').textContent = message;
    document.getElementById('loadingProgress').style.width = progress + '%';
}

function showToast(message, type = 'success', duration = 3000) {
    // Remove existing toast
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'ph-check-circle';
    if (type === 'error') icon = 'ph-x-circle';
    else if (type === 'info') icon = 'ph-info';
    
    toast.innerHTML = `
        <i class="ph ${icon}"></i>
        <span class="toast-text">${message}</span>
    `;
    
    document.body.appendChild(toast);
    
    // Show toast
    setTimeout(() => toast.classList.add('show'), 100);
    
    // Hide toast
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
    }
    
    if (audioEditor) {
        try {
            audioEditor.destroy();
        } catch (e) {
            console.error('Error destroying audio editor:', e);
        }
    }
});
