// Reply Guy Application - Complete with GIF Suggestions
(function() {
    'use strict';

    

    // State management
    const state = {
        currentView: 'replies',
        selectedList: null,
        selectedListType: null,
        currentEditingListId: null,
        currentDeletingListId: null,
        hasBrandVoiceData: false,
        ongoingUpdates: {},
        isInitialized: false,
        gifCache: new Map(), // Cache GIF search results by query
        defaultLists: [] // Store default lists loaded from server
    };

    // Initialize application
    function init() {
        if (state.isInitialized) return;

        // Load ongoing updates from sessionStorage FIRST
        loadOngoingUpdates();

        // Load initial data
        loadInitialData();

        // Initialize components immediately (no blocking calls)
        initializeView();
        setupEventListeners();
        setupDropdowns();
        setupModals();

        // Defer non-critical operations
        setTimeout(() => {
            checkBrandVoice();
        }, 100);

        state.isInitialized = true;
    }

    // Load initial data from server via API
    async function loadInitialData() {
        const tweetsSection = document.getElementById('tweets-section');

        try {
            console.log('🔄 Loading initial data...');
            // Keep section visible but dimmed during load
            if (tweetsSection) {
                tweetsSection.style.opacity = '0.5';
                tweetsSection.style.pointerEvents = 'none';
            }

            // Fetch initial data from API
            const response = await fetch('/reply-guy/get-initial-data', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error('Failed to load initial data');
            }

            const data = await response.json();
            console.log('✅ Data loaded:', data);

            if (!data.success) {
                throw new Error(data.error || 'Failed to load data');
            }

            // Merge server ongoing updates with sessionStorage (sessionStorage takes precedence)
            // This allows updates to persist across page navigation
            const serverUpdates = data.ongoing_updates || {};
            state.ongoingUpdates = { ...serverUpdates, ...state.ongoingUpdates };
            console.log('🔄 Merged ongoing updates:', state.ongoingUpdates);

            // Update progress card with reply stats
            updateProgressCard(data.reply_stats);

            // Store default lists in state
            if (data.default_lists && data.default_lists.length > 0) {
                state.defaultLists = data.default_lists;
                console.log('✅ Stored', data.default_lists.length, 'default lists');
            }

            // Populate custom lists dropdown
            if (data.custom_lists && data.custom_lists.length > 0) {
                populateCustomListsDropdown(data.custom_lists);
            }

            // Set current selection
            if (data.current_selection) {
                state.selectedList = data.current_selection.list_id;
                state.selectedListType = data.current_selection.list_type;

                // Update mode tabs to match current selection
                const modeTabs = document.querySelectorAll('.mode-tab-compact');
                modeTabs.forEach(tab => {
                    if (tab.dataset.mode === data.current_selection.list_type) {
                        tab.classList.add('active');
                    } else {
                        tab.classList.remove('active');
                    }
                });

                // Show/hide custom list container based on mode
                const container = document.querySelector('.custom-list-container');
                if (data.current_selection.list_type === 'custom') {
                    if (container) container.style.display = 'flex';

                    // Update dropdown text with selected list name
                    if (data.list_name) {
                        const selectedListText = document.getElementById('selected-list-text');
                        if (selectedListText) {
                            selectedListText.textContent = data.list_name;
                            console.log('✅ Set dropdown text to:', data.list_name);
                        }
                    }

                    // Show update button for custom lists
                    updateButtonVisibility();
                } else {
                    if (container) container.style.display = 'none';
                }
            }

            // Update panel title with list name
            if (data.list_name) {
                const panelTitle = document.querySelector('.panel-title');
                if (panelTitle) {
                    panelTitle.innerHTML = `<i class="ph ph-chat-dots"></i> Reply Opportunities - ${data.list_name}`;
                }
            }

            // Add/update last refresh indicator
            if (data.timestamp) {
                updateLastRefreshIndicator(data.timestamp);
            }

            // Inject tweets HTML
            if (data.has_tweets && data.tweets_html) {
                console.log('💬 Injecting tweets HTML...');

                // 1. Inject HTML into DOM
                tweetsSection.innerHTML = data.tweets_html;

                // 2. Show tweets section first
                tweetsSection.style.display = 'block';

                // 3. Wait for Twitter widgets to be ready, then load each blockquote individually
                setTimeout(async () => {
                    console.log('🐦 Waiting for Twitter widgets...');
                    const widgetsReady = await waitForTwitterWidgets();

                    if (widgetsReady) {
                        // Validate blockquotes before loading
                        const blockquotes = Array.from(tweetsSection.querySelectorAll('blockquote.twitter-tweet'));
                        console.log(`Found ${blockquotes.length} tweet blockquotes`);

                        // Load each widget individually with error handling
                        if (blockquotes.length > 0) {
                            let successCount = 0;
                            for (const blockquote of blockquotes) {
                                try {
                                    // Check if blockquote is still in DOM and has valid structure
                                    if (blockquote.isConnected && blockquote.querySelector('a')) {
                                        await window.twttr.widgets.createTweet(
                                            blockquote.querySelector('a').href.split('/').pop(),
                                            blockquote.parentElement,
                                            { theme: 'dark', dnt: true }
                                        );
                                        // Remove original blockquote after widget loads
                                        blockquote.remove();
                                        successCount++;
                                    }
                                } catch (err) {
                                    // Silently continue - some tweets may fail to load
                                }
                            }
                            console.log(`✅ Loaded ${successCount}/${blockquotes.length} Twitter widgets`);
                        }
                    }
                }, 200);

                console.log('📝 Waiting for images and content to load...');

                // 4. Wait for all images in tweets to load
                const images = tweetsSection.querySelectorAll('img');
                const imagePromises = Array.from(images).map(img => {
                    if (img.complete) return Promise.resolve();
                    return new Promise(resolve => {
                        img.onload = resolve;
                        img.onerror = resolve; // Continue even if image fails
                        setTimeout(resolve, 2000); // Timeout after 2s
                    });
                });

                Promise.all(imagePromises).then(() => {
                    console.log('🖼️ Images loaded, initializing interactions...');

                    // 5. Initialize event listeners for dynamically loaded content
                    setupReplyStyleDropdowns();

                    console.log('✅ Everything ready, enabling section...');

                    // 6. Enable the section - everything is ready
                    if (tweetsSection) {
                        tweetsSection.style.opacity = '1';
                        tweetsSection.style.pointerEvents = 'auto';
                    }
                });

            } else {
                console.log('ℹ️ No tweets to display');

                // Show empty state for lists with 0 opportunities
                if (tweetsSection) {
                    tweetsSection.innerHTML = `
                        <div class="empty-state">
                            <i class="ph ph-chat-circle-text empty-icon"></i>
                            <h3 class="empty-title">No Reply Opportunities</h3>
                            <p class="empty-text">No suitable tweets found in this list. Try updating to analyze recent tweets.</p>
                        </div>
                    `;
                    tweetsSection.style.display = 'block';
                    tweetsSection.style.opacity = '1';
                    tweetsSection.style.pointerEvents = 'auto';
                }

                // Hide loading spinner
                if (tweetsLoadingSection) {
                    tweetsLoadingSection.style.display = 'none';
                }
            }

        } catch (error) {
            console.error('❌ Error loading initial data:', error);
            showToast('Failed to load data. Please refresh the page.', 'error');

            // Enable section even on error
            if (tweetsSection) {
                tweetsSection.style.opacity = '1';
                tweetsSection.style.pointerEvents = 'auto';
            }
        }
    }

    // Update progress card with reply stats
    function updateProgressCard(replyStats) {
        if (!replyStats) return;

        const progressFill = document.querySelector('.progress-fill');
        const progressPercentage = document.querySelector('.progress-percentage');
        const progressText = document.querySelector('.progress-text');

        if (progressFill) {
            progressFill.style.width = `${replyStats.progress_percentage || 0}%`;
        }
        if (progressPercentage) {
            progressPercentage.textContent = `${replyStats.progress_percentage || 0}%`;
        }
        if (progressText) {
            const total = replyStats.total_replies || 0;
            const target = replyStats.target || 50;
            let message = `You've posted <strong>${total}</strong> out of <strong>${target}</strong> replies today. `;

            if (replyStats.progress_percentage >= 100) {
                message += "Congratulations! You've reached your daily goal!";
            } else if (replyStats.progress_percentage >= 75) {
                message += "You're almost there! Keep it up!";
            } else if (replyStats.progress_percentage >= 50) {
                message += "Great progress! You're halfway to your goal.";
            } else {
                message += "Let's get started on your reply goals for today.";
            }
            progressText.innerHTML = message;
        }
    }

    // Update or create last refresh indicator
    function updateLastRefreshIndicator(timestamp) {
        // Find or create the indicator element
        let indicator = document.querySelector('.last-refresh-indicator');
        const panelContent = document.getElementById('tweets-container');

        if (!indicator && panelContent) {
            // Create the indicator if it doesn't exist
            indicator = document.createElement('div');
            indicator.className = 'last-refresh-indicator';
            indicator.innerHTML = `
                <i class="ph ph-clock-clockwise"></i>
                <span class="refresh-label">Last refreshed:</span>
                <span class="refresh-time" id="lastRefreshTime"></span>
                <span class="refresh-note">· Engagement stats are from this snapshot</span>
            `;
            // Insert before tweets container
            panelContent.parentElement.insertBefore(indicator, panelContent);
        }

        if (indicator) {
            indicator.setAttribute('data-timestamp', timestamp);

            // Update the time display
            const timeElement = indicator.querySelector('.refresh-time') || indicator.querySelector('#lastRefreshTime');
            if (timeElement) {
                // Format the timestamp
                const date = new Date(timestamp);
                const now = new Date();
                const diff = now - date;
                const minutes = Math.floor(diff / 60000);
                const hours = Math.floor(minutes / 60);
                const days = Math.floor(hours / 24);

                let timeText = '';
                if (days > 0) {
                    timeText = `${days} day${days > 1 ? 's' : ''} ago`;
                } else if (hours > 0) {
                    timeText = `${hours} hour${hours > 1 ? 's' : ''} ago`;
                } else if (minutes > 0) {
                    timeText = `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
                } else {
                    timeText = 'just now';
                }

                timeElement.textContent = timeText;
            }
        }
    }

    // Populate custom lists dropdown
    function populateCustomListsDropdown(customLists) {
        console.log('📋 populateCustomListsDropdown called with:', customLists);
        const dropdownMenu = document.getElementById('list-dropdown-menu');
        if (!dropdownMenu) {
            console.error('❌ Dropdown menu not found');
            return;
        }

        // Find the existing custom list options container
        const existingOptions = dropdownMenu.querySelectorAll('.dropdown-option[data-type="custom"]');
        const emptyMessage = dropdownMenu.querySelector('.dropdown-empty');

        console.log('🔍 Found', existingOptions.length, 'existing options');
        console.log('🔍 Empty message exists:', !!emptyMessage);

        // Remove empty message if it exists
        if (emptyMessage) {
            emptyMessage.remove();
            console.log('🗑️ Removed empty message');
        }

        // Remove existing custom list options (but keep the "Add New" button)
        existingOptions.forEach(option => {
            if (!option.classList.contains('create-new')) {
                option.remove();
            }
        });

        // Find the divider and "Add New" button
        const divider = dropdownMenu.querySelector('.dropdown-divider');
        console.log('🔍 Divider found:', !!divider);

        // Add custom lists before the divider
        customLists.forEach(list => {
            const option = document.createElement('div');
            option.className = 'dropdown-option';
            option.setAttribute('data-value', list.id);
            option.setAttribute('data-type', 'custom');
            option.innerHTML = `
                <i class="ph ph-user-circle option-icon"></i>
                ${list.name}
            `;

            if (divider) {
                dropdownMenu.insertBefore(option, divider);
            } else {
                dropdownMenu.appendChild(option);
            }
            console.log('➕ Added custom list:', list.name, 'with id:', list.id);
        });

        console.log(`✅ Populated ${customLists.length} custom lists in dropdown`);
    }

    // Render tweets in the tweets container
    function renderTweets(analysisData) {
        if (!analysisData || !analysisData.tweet_opportunities) return;

        const tweetsContainer = document.getElementById('tweets-container');
        const tweetsSection = document.getElementById('tweets-section');

        if (!tweetsContainer || !tweetsSection) return;

        // For now, since tweets are server-rendered in the template,
        // we just need to show the section. In a full rewrite, we'd
        // dynamically create tweet elements here.

        // TODO: Full dynamic rendering of tweets
        // For now, just ensure the section is visible
    }

    // Save ongoing updates to sessionStorage
    function saveOngoingUpdates() {
        try {
            sessionStorage.setItem('reply_guy_ongoing_updates', JSON.stringify(state.ongoingUpdates));
            console.log('💾 Saved ongoing updates:', state.ongoingUpdates);
        } catch (error) {
            console.error('Error saving to sessionStorage:', error);
        }
    }

    // Load ongoing updates from sessionStorage
    function loadOngoingUpdates() {
        try {
            const saved = sessionStorage.getItem('reply_guy_ongoing_updates');
            if (saved) {
                state.ongoingUpdates = JSON.parse(saved);
                console.log('📂 Loaded ongoing updates from sessionStorage:', state.ongoingUpdates);
            }
        } catch (error) {
            console.error('Error loading from sessionStorage:', error);
            state.ongoingUpdates = {};
        }
    }

    // Initialize view state
    function initializeView() {
        // Check for initial selection data attribute on page
        const pageData = document.getElementById('reply-guy-data');
        if (pageData) {
            const selectedListId = pageData.dataset.selectedListId;
            const selectedListType = pageData.dataset.selectedListType;

            if (selectedListId) {
                state.selectedList = selectedListId;
                state.selectedListType = selectedListType;

                const selectedOption = document.querySelector(`[data-value="${state.selectedList}"]`);
                if (selectedOption) {
                    const selectedListText = document.getElementById('selected-list-text');
                    const selectedListTextEmpty = document.getElementById('selected-list-text-empty');
                    const optionText = selectedOption.textContent.trim();
                    if (selectedListText) {
                        selectedListText.textContent = optionText;
                    }
                    if (selectedListTextEmpty) {
                        selectedListTextEmpty.textContent = optionText;
                    }
                    selectedOption.classList.add('selected');
                }
            }
        }

        // If no list is selected on page load, auto-select the first default list
        if (!state.selectedList) {
            if (state.defaultLists && state.defaultLists.length > 0) {
                // Select first default list
                const firstDefaultList = state.defaultLists[0];
                state.selectedList = firstDefaultList.id;
                state.selectedListType = 'default';
                console.log('✅ Auto-selected default list:', firstDefaultList.name);
            } else {
                // Only fall back to custom list if no default lists exist
                const firstCustomList = document.querySelector('.dropdown-option[data-type="custom"]');
                if (firstCustomList) {
                    const optionText = firstCustomList.textContent.trim();
                    const selectedListText = document.getElementById('selected-list-text');
                    if (selectedListText) selectedListText.textContent = optionText;

                    firstCustomList.classList.add('selected');
                    state.selectedList = firstCustomList.getAttribute('data-value');
                    state.selectedListType = 'custom';
                    console.log('✅ Auto-selected custom list:', optionText);
                }
            }
        }

        // Check if there are ongoing updates and refresh button state
        if (Object.keys(state.ongoingUpdates).length > 0) {
            setTimeout(() => checkOngoingUpdatesStatus(), 500);
        }

        updateButtonVisibility();
    }

    // Check status of ongoing updates
    function checkOngoingUpdatesStatus() {
        const listIds = Object.keys(state.ongoingUpdates);
        if (listIds.length === 0) return;

        listIds.forEach(listId => {
            fetch('/reply-guy/check-update-status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ list_id: listId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success && !data.is_updating) {
                    delete state.ongoingUpdates[listId];
                    saveOngoingUpdates();

                    if (listId === state.selectedList) {
                        // showToast('Update completed! Refreshing...', 'success');
                        setTimeout(() => window.location.reload(), 1000);
                    }
                }
                updateButtonVisibility();
            })
            .catch(error => {
                console.error('Error checking update status:', error);
            });
        });

        if (Object.keys(state.ongoingUpdates).length > 0) {
            setTimeout(checkOngoingUpdatesStatus, 5000);
        }
    }

    // Check brand voice availability
    function checkBrandVoice() {
        fetch('/reply-guy/check-brand-voice')
            .then(response => response.json())
            .then(data => {
                const hasData = data.success && data.has_brand_voice_data;
                setBrandVoiceState(hasData);
            })
            .catch(error => {
                console.error('Brand voice check failed:', error);
                setBrandVoiceState(false);
            })
            .finally(() => {
                const loadingSection = document.getElementById('tweets-loading-section');
                const tweetsSection = document.getElementById('tweets-section');

                if (loadingSection) {
                    loadingSection.style.display = 'none';
                }
                if (tweetsSection) {
                    tweetsSection.style.display = 'block';
                }
            });
    }

    function setBrandVoiceState(hasData) {
        state.hasBrandVoiceData = hasData;


        const userPrefersBrandVoice = localStorage.getItem('preferBrandVoice');
        const shouldEnableBrandVoice = userPrefersBrandVoice === null ? true : userPrefersBrandVoice === 'true';

        document.querySelectorAll('.brand-voice-checkbox').forEach(checkbox => {
            const wasDisabled = checkbox.disabled;
            checkbox.disabled = !hasData;

            if (hasData) {
                if (!checkbox.hasAttribute('data-initialized')) {
                    checkbox.checked = shouldEnableBrandVoice;
                    checkbox.setAttribute('data-initialized', 'true');

                    checkbox.addEventListener('change', function(e) {
                        localStorage.setItem('preferBrandVoice', this.checked);
                    }, { once: false });
                }
            } else {
                // Force uncheck and ensure it stays that way
                checkbox.checked = false;
                checkbox.removeAttribute('data-initialized');

                // Clear localStorage preference when no brand voice data
                localStorage.removeItem('preferBrandVoice');

                // Prevent any interaction with disabled checkbox
                checkbox.onclick = function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    this.checked = false;
                    return false;
                };
            }
        });

        document.querySelectorAll('.brand-voice-toggle').forEach(toggle => {
            const oldHandler = toggle._disabledClickHandler;
            if (oldHandler) {
                toggle.removeEventListener('click', oldHandler, true);
            }

            if (hasData) {
                toggle.classList.remove('disabled');
                toggle.title = '';
                toggle.style.removeProperty('pointer-events');
            } else {
                toggle.classList.add('disabled');
                toggle.title = 'Connect your X account and ensure you have replies on your profile to enable brand voice';
                toggle.style.pointerEvents = 'none';

                const disabledHandler = function(e) {
                    if (this.classList.contains('disabled')) {
                        e.preventDefault();
                        e.stopPropagation();
                        e.stopImmediatePropagation();
                        return false;
                    }
                };
                toggle._disabledClickHandler = disabledHandler;
                toggle.addEventListener('click', disabledHandler, true);
            }
        });

        const globalToggle = document.querySelector('.brand-voice-toggle.global-brand-voice');
        const globalCheckbox = document.getElementById('global-brand-voice');

        if (globalToggle && globalCheckbox) {
            if (hasData) {
                globalToggle.classList.remove('disabled');
                globalToggle.title = 'Use your brand voice for all replies';
                globalCheckbox.addEventListener('change', function() {
                    if (this.checked) {
                        globalToggle.classList.add('active');
                    } else {
                        globalToggle.classList.remove('active');
                    }
                });
            } else {
                globalToggle.classList.add('disabled');
                globalToggle.title = 'Connect your Twitter account to enable brand voice';
                globalCheckbox.checked = false;
                globalToggle.classList.remove('active');
            }
        }
    }

    // Setup event listeners
    function setupEventListeners() {
        const repliesViewBtn = document.getElementById('replies-view-btn');
        const listsViewBtn = document.getElementById('lists-view-btn');

        if (repliesViewBtn) {
            repliesViewBtn.onclick = () => switchView('replies');
        }

        if (listsViewBtn) {
            listsViewBtn.onclick = () => switchView('lists');
        }

        // Global brand voice checkbox guard - catch any change events
        document.addEventListener('change', function(e) {
            if (e.target.classList.contains('brand-voice-checkbox')) {
                // If no brand voice data, force uncheck
                if (!state.hasBrandVoiceData) {
                    e.preventDefault();
                    e.target.checked = false;
                    console.log('Brand voice change blocked - no data available');
                }
            }
        }, true); // Use capture phase to catch early

        const updateBtn = document.getElementById('update-btn');
        const updateBtnEmpty = document.getElementById('update-btn-empty');
        if (updateBtn) {
            updateBtn.onclick = handleUpdate;
        }
        if (updateBtnEmpty) {
            updateBtnEmpty.onclick = handleUpdate;
        }

        const createListBtn = document.getElementById('create-list-btn');
        if (createListBtn) {
            createListBtn.onclick = handleCreateList;
        }

        const newListType = document.getElementById('new-list-type');
        if (newListType) {
            newListType.onchange = handleListTypeChange;
            handleListTypeChange();
        }

        const simpleCreateBtn = document.getElementById('simple-create-btn');
        if (simpleCreateBtn) {
            simpleCreateBtn.onclick = handleSimpleCreateList;
        }
        const cancelCreateBtn = document.getElementById('cancel-create-btn');
        if (cancelCreateBtn) {
            cancelCreateBtn.onclick = hideCreateModal;
        }
        const closeCreateModal = document.getElementById('close-create-modal');
        if (closeCreateModal) {
            closeCreateModal.onclick = hideCreateModal;
        }

        const createNewListBtn = document.getElementById('create-new-list');
        const createNewListEmptyBtn = document.getElementById('create-new-list-empty');

        if (createNewListBtn) {
            createNewListBtn.onclick = function(e) {
                e.preventDefault();
                e.stopPropagation();
                showInlineCreateForm();
            };
        }

        if (createNewListEmptyBtn) {
            createNewListEmptyBtn.onclick = function(e) {
                e.preventDefault();
                showInlineCreateForm();
            };
        }

        // Panel form controls
        const closePanelBtn = document.getElementById('close-create-panel');
        const cancelPanelCreate = document.getElementById('cancel-panel-create');
        const panelCreateBtn = document.getElementById('panel-create-btn');

        if (closePanelBtn) {
            closePanelBtn.onclick = hideCreatePanel;
        }
        if (cancelPanelCreate) {
            cancelPanelCreate.onclick = hideCreatePanel;
        }
        if (panelCreateBtn) {
            panelCreateBtn.onclick = handlePanelCreateList;
        }

        document.addEventListener('click', handleDelegatedClicks);
        document.addEventListener('input', handleDelegatedInputs);
        document.addEventListener('change', handleDelegatedInputs);
    }

    function handleDelegatedClicks(e) {

        // Generate reply button
        if (e.target.closest('.generate-reply-btn')) {
            console.log('🔘 Generate reply button clicked');
            e.preventDefault();
            const btn = e.target.closest('.generate-reply-btn');
            if (btn.disabled) {
                console.log('⚠️ Button is disabled, ignoring click');
                return;
            }

            btn.disabled = true;
            const tweetElement = btn.closest('.tweet-opportunity');
            console.log('📝 Tweet element found:', !!tweetElement);
            console.log('Tweet data:', {
                id: tweetElement?.getAttribute('data-tweet-id'),
                text: tweetElement?.getAttribute('data-tweet-text')?.substring(0, 50) + '...',
                author: tweetElement?.getAttribute('data-tweet-author')
            });
            generateReply(tweetElement).finally(() => {
                btn.disabled = false;
            });
            return;
        }

        // GIF suggest button removed - GIFs show automatically

        // GIF item selection - Download immediately on click
        if (e.target.closest('.gif-item-reply')) {
            e.preventDefault();
            const gifItem = e.target.closest('.gif-item-reply');
            const tweetElement = gifItem.closest('.tweet-opportunity');

            // Download GIF immediately
            const gifData = {
                id: gifItem.getAttribute('data-gif-id'),
                url: gifItem.getAttribute('data-gif-url'),
                title: gifItem.getAttribute('data-gif-title')
            };

            // Download the GIF
            downloadGif(gifData);

            // Optional: Close the panel after download
            const panel = tweetElement.querySelector('.gif-suggestion-panel');
            if (panel) {
                panel.classList.remove('show');
            }
            return;
        }

        // GIF download button - NEW
        if (e.target.closest('.gif-download-btn')) {
            e.preventDefault();
            const btn = e.target.closest('.gif-download-btn');
            const tweetElement = btn.closest('.tweet-opportunity');
            downloadSelectedGif(tweetElement);
            return;
        }

        // GIF change button - NEW
        if (e.target.closest('.gif-change-btn')) {
            e.preventDefault();
            const btn = e.target.closest('.gif-change-btn');
            const tweetElement = btn.closest('.tweet-opportunity');
            showGifGrid(tweetElement);
            return;
        }

        // GIF panel close - NEW
        if (e.target.closest('.gif-panel-close')) {
            e.preventDefault();
            const btn = e.target.closest('.gif-panel-close');
            const tweetElement = btn.closest('.tweet-opportunity');
            hideGifPanel(tweetElement);
            return;
        }

        // GIF query navigation - Previous
        if (e.target.closest('.gif-query-prev')) {
            e.preventDefault();
            const btn = e.target.closest('.gif-query-prev');
            const tweetElement = btn.closest('.tweet-opportunity');
            navigateGifQuery(tweetElement, -1);
            return;
        }

        // GIF query navigation - Next
        if (e.target.closest('.gif-query-next')) {
            e.preventDefault();
            const btn = e.target.closest('.gif-query-next');
            const tweetElement = btn.closest('.tweet-opportunity');
            navigateGifQuery(tweetElement, 1);
            return;
        }

        // Post reply button
        if (e.target.closest('.post-reply-btn')) {
            e.preventDefault();
            const btn = e.target.closest('.post-reply-btn');
            if (btn.disabled) return;

            btn.disabled = true;
            const tweetElement = btn.closest('.tweet-opportunity');
            postReply(tweetElement);
            setTimeout(() => {
                btn.disabled = false;
            }, 1000);
            return;
        }

        // List management buttons
        if (e.target.closest('.edit-list-btn')) {
            const listId = e.target.closest('.edit-list-btn').getAttribute('data-list-id');
            openEditModal(listId);
        } else if (e.target.closest('.delete-list-btn')) {
            const listId = e.target.closest('.delete-list-btn').getAttribute('data-list-id');
            openDeleteModal(listId);
        } else if (e.target.closest('.refresh-list-btn')) {
            const listId = e.target.closest('.refresh-list-btn').getAttribute('data-list-id');
            refreshXList(listId);
        } else if (e.target.closest('.create-new')) {
            e.preventDefault();
            closeDropdowns();
            showCreatePanel();
        }
    }

    function handleDelegatedInputs(e) {
        if (e.target.classList.contains('reply-textarea')) {
            updateCharacterCount(e.target);
        }

        if (e.target.classList.contains('brand-voice-checkbox')) {
            const toggle = e.target.closest('.brand-voice-toggle');

            // STRICT: Check if brand voice data is available before allowing interaction
            if (!state.hasBrandVoiceData) {
                e.preventDefault();
                e.stopPropagation();
                e.target.checked = false;
                console.log('Brand voice interaction blocked - no data available');
                return false;
            }

            // Prevent interaction if toggle is disabled or checkbox is disabled
            if ((toggle && toggle.classList.contains('disabled')) || e.target.disabled) {
                e.preventDefault();
                e.stopPropagation();
                // Force checkbox back to unchecked
                setTimeout(() => {
                    e.target.checked = false;
                }, 0);
                return false;
            }

            if (toggle && !toggle.classList.contains('disabled') && !e.target.disabled) {
                const newState = e.target.checked;

                document.querySelectorAll('.brand-voice-checkbox').forEach(checkbox => {
                    if (!checkbox.disabled) {
                        checkbox.checked = newState;
                    }
                });

                localStorage.setItem('preferBrandVoice', newState.toString());
            }
        }
    }

    function switchView(view) {
        state.currentView = view;

        const repliesViewBtn = document.getElementById('replies-view-btn');
        const listsViewBtn = document.getElementById('lists-view-btn');
        const repliesPanel = document.getElementById('replies-panel');
        const listsPanel = document.getElementById('lists-panel');

        if (view === 'replies') {
            if (repliesViewBtn) repliesViewBtn.classList.add('active');
            if (listsViewBtn) listsViewBtn.classList.remove('active');
            if (repliesPanel) repliesPanel.classList.remove('hidden');
            if (listsPanel) listsPanel.classList.remove('active');
        } else {
            if (listsViewBtn) listsViewBtn.classList.add('active');
            if (repliesViewBtn) repliesViewBtn.classList.remove('active');
            if (repliesPanel) repliesPanel.classList.add('hidden');
            if (listsPanel) listsPanel.classList.add('active');
        }
    }

    function handleListTypeChange() {
        const newListType = document.getElementById('new-list-type');
        const xListIdInput = document.getElementById('x-list-id');

        if (newListType && xListIdInput) {
            if (newListType.value === 'x_list') {
                xListIdInput.style.display = 'block';
                xListIdInput.required = true;
            } else {
                xListIdInput.style.display = 'none';
                xListIdInput.required = false;
            }
        }
    }

    // Setup dropdowns
    function setupDropdowns() {
        setupMainDropdown();
        setupReplyStyleDropdowns();
        setupModeTabsAndListSelection();
    }

    // Setup mode tabs and list selection (compact interface)
    function setupModeTabsAndListSelection() {
        // Compact mode tab switching
        const modeTabs = document.querySelectorAll('.mode-tab-compact');

        if (modeTabs.length === 0) {
            return;
        }


        // Function to handle mode switching
        function switchMode(mode) {
            const container = document.querySelector('.custom-list-container');
            const updateBtnContainer = document.getElementById('update-button-container');

            if (mode === 'default') {
                // Hide container and update button for default mode
                if (container) container.style.display = 'none';
                if (updateBtnContainer) updateBtnContainer.style.display = 'none';

                // Auto-select first default list from state
                if (state.defaultLists && state.defaultLists.length > 0) {
                    const firstDefaultList = state.defaultLists[0];
                    const listId = firstDefaultList.id;

                    console.log('🔄 Switching to default list:', firstDefaultList.name, listId);

                    state.selectedList = listId;
                    state.selectedListType = 'default';

                    // Small delay before API call
                    setTimeout(() => selectList(), 100);
                } else {
                    console.error('❌ No default lists available');
                }
            } else {
                // Show container for custom mode
                if (container) container.style.display = 'flex';

                // Auto-select first custom list
                const firstCustomList = document.querySelector('.dropdown-option[data-type="custom"]');
                if (firstCustomList) {
                    const optionText = firstCustomList.textContent.trim();
                    const selectedListText = document.getElementById('selected-list-text');
                    if (selectedListText) selectedListText.textContent = optionText;

                    // Clear any dropdown selections
                    document.querySelectorAll('.dropdown-option').forEach(opt => {
                        opt.classList.remove('selected');
                    });

                    state.selectedList = firstCustomList.getAttribute('data-value');
                    state.selectedListType = 'custom';
                    firstCustomList.classList.add('selected');

                    // Small delay before API call
                    setTimeout(() => selectList(), 100);
                }

                // Update button visibility is handled by updateButtonVisibility()
                updateButtonVisibility();
            }
        }

        modeTabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();

                const mode = tab.dataset.mode;

                // Remove active from all tabs
                modeTabs.forEach(t => t.classList.remove('active'));
                // Add active to clicked tab
                tab.classList.add('active');

                // Switch mode
                switchMode(mode);
            });
        });

        // Initialize based on current state or default to 'default' mode
        const initialMode = state.selectedListType || 'default';

        // Set the correct tab as active
        modeTabs.forEach(t => {
            if (t.dataset.mode === initialMode) {
                t.classList.add('active');
            } else {
                t.classList.remove('active');
            }
        });

        // Show/hide UI elements based on initial mode
        const container = document.querySelector('.custom-list-container');
        const updateBtnContainer = document.getElementById('update-button-container');

        if (initialMode === 'default') {
            if (container) container.style.display = 'none';
            if (updateBtnContainer) updateBtnContainer.style.display = 'none';
        } else {
            if (container) container.style.display = 'flex';
            updateButtonVisibility();
        }
    }

    function setupMainDropdown() {
        const dropdownTriggers = ['list-dropdown-trigger', 'list-dropdown-trigger-empty'];

        dropdownTriggers.forEach(triggerId => {
            const dropdownTrigger = document.getElementById(triggerId);
            if (!dropdownTrigger) return;

            const menuId = triggerId === 'list-dropdown-trigger' ? 'list-dropdown-menu' : 'list-dropdown-menu-empty';
            const dropdownMenu = document.getElementById(menuId);

            dropdownTrigger.replaceWith(dropdownTrigger.cloneNode(true));
            const newTrigger = document.getElementById(triggerId);

            newTrigger.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleMainDropdown(triggerId, menuId);
            });
        });

        document.addEventListener('click', (e) => {
            const option = e.target.closest('.dropdown-option:not(.create-new)');
            if (option && (option.closest('#list-dropdown-menu') || option.closest('#list-dropdown-menu-empty'))) {
                selectListOption(option);
                return;
            }

            if (!e.target.closest('.dropdown')) {
                closeDropdowns();
            }
        }, true);
    }

    function toggleMainDropdown(triggerId, menuId) {
        const dropdownTrigger = document.getElementById(triggerId);
        const dropdownMenu = document.getElementById(menuId);

        const otherTriggerId = triggerId === 'list-dropdown-trigger' ? 'list-dropdown-trigger-empty' : 'list-dropdown-trigger';
        const otherMenuId = otherTriggerId === 'list-dropdown-trigger' ? 'list-dropdown-menu' : 'list-dropdown-menu-empty';
        const otherTrigger = document.getElementById(otherTriggerId);
        const otherMenu = document.getElementById(otherMenuId);

        if (otherTrigger) otherTrigger.classList.remove('active');
        if (otherMenu) otherMenu.classList.remove('active');

        const isOpen = dropdownTrigger.classList.contains('active');

        if (!isOpen) {
            dropdownTrigger.classList.add('active');
            if (dropdownMenu) dropdownMenu.classList.add('active');
        } else {
            closeDropdowns();
        }
    }

    function closeDropdowns() {
        const triggers = ['list-dropdown-trigger', 'list-dropdown-trigger-empty'];
        const menus = ['list-dropdown-menu', 'list-dropdown-menu-empty'];

        triggers.forEach(triggerId => {
            const trigger = document.getElementById(triggerId);
            if (trigger) trigger.classList.remove('active');
        });

        menus.forEach(menuId => {
            const menu = document.getElementById(menuId);
            if (menu) menu.classList.remove('active');
        });

        document.querySelectorAll('.reply-style-trigger').forEach(trigger => {
            trigger.classList.remove('active');
        });
        document.querySelectorAll('.reply-style-menu').forEach(menu => {
            menu.classList.remove('active');
        });
    }

    function selectListOption(option) {
        document.querySelectorAll('.dropdown-option').forEach(opt => {
            opt.classList.remove('selected');
        });

        option.classList.add('selected');
        state.selectedList = option.getAttribute('data-value');
        state.selectedListType = option.getAttribute('data-type');

        const selectedListText = document.getElementById('selected-list-text');
        const selectedListTextEmpty = document.getElementById('selected-list-text-empty');
        const optionText = option.textContent.trim();

        if (selectedListText) selectedListText.textContent = optionText;
        if (selectedListTextEmpty) selectedListTextEmpty.textContent = optionText;

        closeDropdowns();
        updateButtonVisibility();
        selectList();
    }

    function setupReplyStyleDropdowns() {
        document.querySelectorAll('.reply-style-trigger').forEach(trigger => {
            trigger.onclick = (e) => {
                e.stopPropagation();
                const dropdown = trigger.closest('.dropdown');
                toggleReplyStyleDropdown(dropdown);
            };
        });

        document.querySelectorAll('.reply-style-option').forEach(option => {
            option.onclick = () => {
                const dropdown = option.closest('.dropdown');
                selectReplyStyleOption(dropdown, option);
            };
        });
    }

    function toggleReplyStyleDropdown(dropdown) {
        const trigger = dropdown.querySelector('.reply-style-trigger');
        const menu = dropdown.querySelector('.reply-style-menu');

        document.querySelectorAll('.dropdown').forEach(otherDropdown => {
            if (otherDropdown !== dropdown) {
                const otherTrigger = otherDropdown.querySelector('.reply-style-trigger');
                const otherMenu = otherDropdown.querySelector('.reply-style-menu');
                if (otherTrigger) otherTrigger.classList.remove('active');
                if (otherMenu) otherMenu.classList.remove('active');
            }
        });

        const isOpen = trigger.classList.contains('active');

        if (!isOpen) {
            trigger.classList.add('active');
            if (menu) menu.classList.add('active');
        } else {
            trigger.classList.remove('active');
            if (menu) menu.classList.remove('active');
        }
    }

    function selectReplyStyleOption(dropdown, option) {
        const trigger = dropdown.querySelector('.reply-style-trigger');
        const menu = dropdown.querySelector('.reply-style-menu');
        const selectedText = dropdown.querySelector('.selected-style-text');

        dropdown.querySelectorAll('.reply-style-option').forEach(opt => {
            opt.classList.remove('selected');
        });

        option.classList.add('selected');
        if (selectedText) {
            selectedText.textContent = option.textContent;
        }

        if (trigger) trigger.classList.remove('active');
        if (menu) menu.classList.remove('active');
    }

    // API Functions
    function updateButtonVisibility() {
        const updateButtonContainer = document.getElementById('update-button-container');
        const updateBtn = document.getElementById('update-btn');
        const updateButtonContainerEmpty = document.getElementById('update-button-container-empty');
        const updateBtnEmpty = document.getElementById('update-btn-empty');

        console.log('🔘 updateButtonVisibility - selectedList:', state.selectedList, 'type:', state.selectedListType, 'ongoingUpdates:', state.ongoingUpdates);

        if (state.selectedListType === 'custom' && state.selectedList) {
            // Check if THIS list is updating
            const isThisListUpdating = state.selectedList in state.ongoingUpdates;
            console.log('🔘 isThisListUpdating:', isThisListUpdating);

            // Check if ANY OTHER list is updating
            const otherListUpdating = Object.keys(state.ongoingUpdates).find(id => id !== state.selectedList);
            const hasOtherListUpdating = !!otherListUpdating;

            // If another list is updating, hide the button completely
            if (hasOtherListUpdating) {
                if (updateButtonContainer) {
                    updateButtonContainer.style.display = 'none';
                }
                if (updateButtonContainerEmpty) {
                    updateButtonContainerEmpty.style.display = 'none';
                }
                return;
            }

            // Show button containers
            if (updateButtonContainer) {
                updateButtonContainer.style.display = 'block';
            }
            if (updateButtonContainerEmpty) {
                updateButtonContainerEmpty.style.display = 'block';
            }

            // Update button state based on whether THIS list is updating
            [updateBtn, updateBtnEmpty].forEach(btn => {
                if (btn) {
                    if (isThisListUpdating) {
                        btn.disabled = true;
                        btn.classList.add('processing');
                        btn.innerHTML = '<span class="loading-spinner"></span>Updating...';
                    } else {
                        btn.disabled = false;
                        btn.classList.remove('processing');
                        btn.innerHTML = '<i class="ph ph-arrows-clockwise"></i>Update';
                    }
                }
            });
        } else {
            // Not a custom list, hide buttons
            if (updateButtonContainer) {
                updateButtonContainer.style.display = 'none';
            }
            if (updateButtonContainerEmpty) {
                updateButtonContainerEmpty.style.display = 'none';
            }
        }
    }

    function selectList() {
        if (!state.selectedList) return;

        console.log('🔄 Selecting list:', state.selectedList, 'type:', state.selectedListType);

        fetch('/reply-guy/select-list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                list_id: state.selectedList,
                list_type: state.selectedListType
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('✅ List selected, has_analysis:', data.has_analysis, 'is_updating:', data.is_updating);

                if (data.is_updating) {
                    state.ongoingUpdates[state.selectedList] = {
                        ...data.update_info,
                        timestamp: Date.now()
                    };
                    saveOngoingUpdates();
                } else {
                    delete state.ongoingUpdates[state.selectedList];
                    saveOngoingUpdates();
                }

                updateButtonVisibility();

                if (data.has_analysis) {
                    // Load the analysis data without reloading the page
                    console.log('📊 Loading analysis data...');
                    loadInitialData();
                } else if (state.selectedListType === 'default') {
                    // For default lists, load data (should always have analysis)
                    console.log('📊 Loading default list data...');
                    loadInitialData();
                } else {
                    // Custom list with no analysis - show empty state first
                    console.log('📭 Custom list has no analysis');
                    const tweetsContainer = document.getElementById('tweets-section');
                    const tweetsLoadingSection = document.getElementById('tweets-loading-section');

                    // Hide loading spinner
                    if (tweetsLoadingSection) {
                        tweetsLoadingSection.style.display = 'none';
                    }

                    // Show empty state
                    if (tweetsContainer) {
                        tweetsContainer.innerHTML = `
                            <div class="empty-state">
                                <i class="ph ph-chat-circle-text empty-icon"></i>
                                <h3 class="empty-title">No Reply Opportunities Yet</h3>
                                <p class="empty-text">Click "Update" to analyze this list and find reply opportunities.</p>
                            </div>
                        `;
                        tweetsContainer.style.display = 'block';
                    }

                    // Check if we can auto-trigger
                    const hasAnyUpdating = Object.keys(state.ongoingUpdates).length > 0;

                    if (hasAnyUpdating) {
                        console.log('⚠️ Cannot auto-trigger update - another list is updating');
                        return;
                    }

                    console.log('🔄 No analysis for custom list, auto-triggering update...');

                    // Mark as updating to show spinner on button
                    state.ongoingUpdates[state.selectedList] = {
                        status: 'running',
                        started_at: new Date().toISOString(),
                        timestamp: Date.now()
                    };
                    saveOngoingUpdates();
                    updateButtonVisibility();

                    // Trigger analysis
                    fetch('/reply-guy/analyze', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            list_id: state.selectedList,
                            list_type: 'custom',
                            time_range: '24h'
                        })
                    })
                    .then(response => response.json())
                    .then(analysisData => {
                        delete state.ongoingUpdates[state.selectedList];
                        saveOngoingUpdates();
                        updateButtonVisibility();

                        if (analysisData.success) {
                            console.log('✅ Analysis completed');
                            loadInitialData();
                        } else {
                            console.error('❌ Analysis failed:', analysisData.error);
                            if (tweetsContainer) {
                                tweetsContainer.innerHTML = `
                                    <div class="empty-state">
                                        <i class="ph ph-warning-circle empty-icon"></i>
                                        <h3 class="empty-title">Analysis Failed</h3>
                                        <p class="empty-text">Failed to analyze this list. Please try clicking "Update" manually.</p>
                                    </div>
                                `;
                            }
                        }
                    })
                    .catch(analysisError => {
                        delete state.ongoingUpdates[state.selectedList];
                        saveOngoingUpdates();
                        updateButtonVisibility();
                        console.error('❌ Analysis error:', analysisError);
                    });
                }
            } else {
                console.error('❌ Error selecting list:', data.error);
            }
        })
        .catch(error => {
            console.error('❌ Network error selecting list:', error);
        });
    }

    function handleUpdate() {
        if (!state.selectedList || state.selectedListType !== 'custom') {
            return;
        }

        // Prevent starting multiple updates - check if ANY list is updating
        const hasAnyUpdating = Object.keys(state.ongoingUpdates).length > 0;
        if (hasAnyUpdating) {
            console.log('⚠️ Cannot start update - another list is already updating');
            // showToast('Please wait for the current update to finish', 'warning');
            return;
        }

        state.ongoingUpdates[state.selectedList] = {
            status: 'running',
            started_at: new Date().toISOString(),
            timestamp: Date.now()
        };
        saveOngoingUpdates();
        updateButtonVisibility();

        fetch('/reply-guy/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                list_id: state.selectedList,
                list_type: state.selectedListType,
                time_range: '24h'
            })
        })
        .then(response => response.json())
        .then(data => {
            const listIdBeingUpdated = state.selectedList;
            delete state.ongoingUpdates[listIdBeingUpdated];
            saveOngoingUpdates();

            if (data.success) {
                // showToast('Analysis completed!', 'success');
                console.log('✅ Update completed, reloading data...');
                loadInitialData(); // Reload data instead of page reload
                updateButtonVisibility();
            } else {
                if (data.is_updating) {
                    state.ongoingUpdates[state.selectedList] = {
                        status: 'running',
                        timestamp: Date.now()
                    };
                    saveOngoingUpdates();
                    // showToast('Update already in progress for this list', 'warning');
                } else {
                    // showToast('Analysis failed: ' + data.error, 'error');
                }
                updateButtonVisibility();
            }
        })
        .catch(error => {
            delete state.ongoingUpdates[state.selectedList];
            saveOngoingUpdates();
            // showToast('Network error during analysis', 'error');
            updateButtonVisibility();
        });
    }

    // Reply Functions - ENHANCED with GIF support
    function generateReply(tweetElement) {
        if (!tweetElement) {
            return Promise.resolve();
        }

        const tweetId = tweetElement.getAttribute('data-tweet-id');

        // Get tweet data from data attributes (since tweet is in iframe)
        let tweetText = tweetElement.getAttribute('data-tweet-text') || '';
        const author = tweetElement.getAttribute('data-tweet-author') || '';

        const style = getSelectedStyle(tweetElement);
        const useBrandVoice = getBrandVoiceState(tweetElement);

        // Extract image URLs from data attribute if available
        let imageUrls = [];
        try {
            const imageUrlsData = tweetElement.getAttribute('data-image-urls');
            if (imageUrlsData) {
                imageUrls = JSON.parse(imageUrlsData);
                console.log('📷 Found', imageUrls.length, 'image(s) in tweet');
            }
        } catch (e) {
            console.error('Error parsing image URLs:', e);
            imageUrls = [];
        }


        const textarea = tweetElement.querySelector('.reply-textarea');
        const generateBtn = tweetElement.querySelector('.generate-reply-btn');
        const gifBtn = tweetElement.querySelector('.gif-suggest-btn');

        if (generateBtn) {
            generateBtn.innerHTML = '<div class="loading-spinner"></div>';
            generateBtn.disabled = true;
            generateBtn.classList.add('loading');
        }
        if (textarea) {
            textarea.value = imageUrls.length > 0 ? 'Analyzing images and generating reply...' : 'Generating reply...';
        }

        return fetch('/reply-guy/generate-reply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tweet_text: tweetText,
                author: author,
                style: style,
                use_brand_voice: useBrandVoice,
                image_urls: imageUrls
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (textarea) {
                    textarea.value = data.reply;
                    updateCharacterCount(textarea);
                }

                // Store GIF queries for this tweet (now multiple)
                if (data.gif_queries && data.gif_queries.length > 0) {
                    tweetElement.setAttribute('data-gif-queries', JSON.stringify(data.gif_queries));
                    tweetElement.setAttribute('data-current-query-index', '0');

                    // Add indicator to GIF button
                    if (gifBtn) {
                        gifBtn.classList.add('has-gif');
                    }

                    // Auto-load GIFs for first query and show panel immediately
                    const firstQuery = data.gif_queries[0];
                    loadGifsForTweet(tweetElement, firstQuery).then(gifs => {
                        if (gifs && gifs.length > 0) {
                            // Automatically show the GIF panel with results
                            const panel = getOrCreateGifPanel(tweetElement);
                            panel.classList.add('show');
                            displayGifsInPanel(tweetElement, gifs);
                            updateGifPanelNavigation(tweetElement, 0, data.gif_queries);
                        }
                    });
                } else if (data.gif_query) {
                    // Fallback for single query (backward compatibility)
                    tweetElement.setAttribute('data-gif-queries', JSON.stringify([data.gif_query]));
                    tweetElement.setAttribute('data-current-query-index', '0');

                    if (gifBtn) {
                        gifBtn.classList.add('has-gif');
                    }

                    loadGifsForTweet(tweetElement, data.gif_query).then(gifs => {
                        if (gifs && gifs.length > 0) {
                            const panel = getOrCreateGifPanel(tweetElement);
                            panel.classList.add('show');
                            displayGifsInPanel(tweetElement, gifs);
                            updateGifPanelNavigation(tweetElement, 0, [data.gif_query]);
                        }
                    });
                }

                // showToast('Reply generated successfully!', 'success');
            } else {
                if (textarea) {
                    if (data.credits_required) {
                        textarea.value = 'Insufficient credits to generate reply.';
                    } else if (data.error_type === 'brand_voice_unavailable') {
                        textarea.value = 'Brand voice is not available. Please connect your X account and ensure you have reply data in analytics.';
                        // Auto-disable brand voice checkbox
                        const checkbox = tweetElement.querySelector('.brand-voice-checkbox');
                        if (checkbox) {
                            checkbox.checked = false;
                        }
                    } else {
                        textarea.value = 'Error generating reply: ' + data.error;
                    }
                }
                // showToast(data.credits_required ?
                //     'Insufficient credits. Please purchase more credits.' :
                //     'Error generating reply', 'error');
            }
        })
        .catch(error => {
            if (textarea) {
                textarea.value = 'Network error generating reply.';
            }
            // showToast('Network error', 'error');
        })
        .finally(() => {
            if (generateBtn) {
                generateBtn.innerHTML = '<i class="ph ph-sparkle"></i>';
                generateBtn.disabled = false;
                generateBtn.classList.remove('loading');
            }
        });
    }

    // NEW: Load GIFs for a tweet
    function loadGifsForTweet(tweetElement, query) {
        if (!query) return;

        // Check cache first
        if (state.gifCache.has(query)) {
            const cachedGifs = state.gifCache.get(query);
            tweetElement.setAttribute('data-gifs', JSON.stringify(cachedGifs));
            return Promise.resolve(cachedGifs);
        }

        return fetch('/reply-guy/search-gifs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query, limit: 8 })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.gifs) {
                // Cache the results
                state.gifCache.set(query, data.gifs);
                tweetElement.setAttribute('data-gifs', JSON.stringify(data.gifs));
                return data.gifs;
            }
            return [];
        })
        .catch(error => {
            console.error('Error loading GIFs:', error);
            return [];
        });
    }

    // NEW: Toggle GIF panel
    function toggleGifPanel(tweetElement) {
        const panel = getOrCreateGifPanel(tweetElement);
        
        if (panel.classList.contains('show')) {
            hideGifPanel(tweetElement);
        } else {
            showGifPanel(tweetElement);
        }
    }

    // NEW: Show GIF panel
    function showGifPanel(tweetElement) {
        const panel = getOrCreateGifPanel(tweetElement);
        const query = tweetElement.getAttribute('data-gif-query');
        
        if (!query) {
            // showToast('Generate a reply first to get GIF suggestions', 'info');
            return;
        }

        panel.classList.add('show');
        
        // Check if we have cached GIFs
        const cachedGifsJson = tweetElement.getAttribute('data-gifs');
        if (cachedGifsJson) {
            const gifs = JSON.parse(cachedGifsJson);
            displayGifsInPanel(tweetElement, gifs);
        } else {
            // Load GIFs
            showGifLoading(tweetElement);
            loadGifsForTweet(tweetElement, query).then(gifs => {
                if (gifs && gifs.length > 0) {
                    displayGifsInPanel(tweetElement, gifs);
                } else {
                    showGifEmpty(tweetElement);
                }
            });
        }
    }

    // NEW: Hide GIF panel
    function hideGifPanel(tweetElement) {
        const panel = tweetElement.querySelector('.gif-suggestion-panel');
        if (panel) {
            panel.classList.remove('show');
        }
    }

    // NEW: Get or create GIF panel
    function getOrCreateGifPanel(tweetElement) {
        let panel = tweetElement.querySelector('.gif-suggestion-panel');
        
        if (!panel) {
            const replyPanel = tweetElement.querySelector('.reply-panel');
            panel = document.createElement('div');
            panel.className = 'gif-suggestion-panel';
            panel.innerHTML = `
                <div class="gif-panel-header">
                    <div class="gif-panel-title">
                        <i class="ph ph-gif"></i>
                        Suggested GIFs
                    </div>
                    <div class="gif-query-navigation" style="display: none;">
                        <button class="gif-query-prev" title="Previous suggestion">
                            <i class="ph ph-caret-left"></i>
                        </button>
                        <span class="gif-query-text"></span>
                        <button class="gif-query-next" title="Next suggestion">
                            <i class="ph ph-caret-right"></i>
                        </button>
                    </div>
                    <button class="gif-panel-close">
                        <i class="ph ph-x"></i>
                    </button>
                </div>
                <div class="gif-grid-container"></div>
                <div class="gif-panel-footer">
                    <a href="https://tenor.com" target="_blank" rel="noopener" class="tenor-attribution">
                        <img src="https://www.gstatic.com/tenor/web/attribution/PB_tenor_logo_blue_horizontal.svg" alt="Powered by Tenor" height="16">
                    </a>
                </div>
                <div class="gif-selected-info">
                    <div class="gif-selected-preview">
                        <img src="" alt="Selected GIF">
                    </div>
                    <div class="gif-selected-details">
                        <div class="gif-selected-label">Selected GIF</div>
                        <div class="gif-selected-title"></div>
                    </div>
                    <div class="gif-selected-actions">
                        <button class="gif-change-btn">
                            <i class="ph ph-arrows-clockwise"></i>
                        </button>
                        <button class="gif-download-btn">
                            <i class="ph ph-download"></i>
                            Download
                        </button>
                    </div>
                </div>
            `;
            replyPanel.appendChild(panel);
        }
        
        return panel;
    }

    // NEW: Display GIFs in panel
    function displayGifsInPanel(tweetElement, gifs) {
        const panel = tweetElement.querySelector('.gif-suggestion-panel');
        const gridContainer = panel.querySelector('.gif-grid-container');
        
        gridContainer.innerHTML = gifs.map(gif => `
            <div class="gif-item-reply" data-gif-id="${gif.id}" data-gif-url="${gif.url}" data-gif-preview="${gif.preview_url}" data-gif-title="${gif.title || 'GIF'}">
                <img src="${gif.preview_url}" alt="${gif.title || 'GIF'}" loading="lazy">
            </div>
        `).join('');
    }

    // NEW: Show GIF loading state
    function showGifLoading(tweetElement) {
        const panel = tweetElement.querySelector('.gif-suggestion-panel');
        const gridContainer = panel.querySelector('.gif-grid-container');
        
        gridContainer.innerHTML = `
            <div class="gif-loading" style="grid-column: 1 / -1;">
                <i class="ph ph-spinner"></i>
                Loading GIFs...
            </div>
        `;
    }

    // NEW: Show GIF empty state
    function showGifEmpty(tweetElement) {
        const panel = tweetElement.querySelector('.gif-suggestion-panel');
        const gridContainer = panel.querySelector('.gif-grid-container');
        
        gridContainer.innerHTML = `
            <div class="gif-empty" style="grid-column: 1 / -1;">
                <i class="ph ph-image" style="font-size: 2rem; opacity: 0.3; display: block; margin-bottom: 0.5rem;"></i>
                No GIFs found for this query
            </div>
        `;
    }

    // NEW: Select a GIF
    function selectGif(tweetElement, gifItem) {
        // Remove selection from all GIF items in this tweet
        tweetElement.querySelectorAll('.gif-item-reply').forEach(item => {
            item.classList.remove('selected');
        });
        
        // Mark this GIF as selected
        gifItem.classList.add('selected');
        
        // Store selected GIF data
        const gifData = {
            id: gifItem.getAttribute('data-gif-id'),
            url: gifItem.getAttribute('data-gif-url'),
            preview_url: gifItem.getAttribute('data-gif-preview'),
            title: gifItem.getAttribute('data-gif-title')
        };
        
        tweetElement.setAttribute('data-selected-gif', JSON.stringify(gifData));
        
        // Show selected GIF info and hide grid
        showSelectedGifInfo(tweetElement, gifData);
    }

    // NEW: Show selected GIF info
    function showSelectedGifInfo(tweetElement, gifData) {
        const panel = tweetElement.querySelector('.gif-suggestion-panel');
        const gridContainer = panel.querySelector('.gif-grid-container');
        const selectedInfo = panel.querySelector('.gif-selected-info');
        
        // Hide grid, show selected info
        gridContainer.style.display = 'none';
        selectedInfo.classList.add('show');
        
        // Update selected info
        const preview = selectedInfo.querySelector('.gif-selected-preview img');
        const title = selectedInfo.querySelector('.gif-selected-title');
        
        preview.src = gifData.preview_url;
        title.textContent = gifData.title || 'GIF';
    }

    // NEW: Show GIF grid again (after selection)
    function showGifGrid(tweetElement) {
        const panel = tweetElement.querySelector('.gif-suggestion-panel');
        const gridContainer = panel.querySelector('.gif-grid-container');
        const selectedInfo = panel.querySelector('.gif-selected-info');
        
        // Show grid, hide selected info
        gridContainer.style.display = 'grid';
        selectedInfo.classList.remove('show');
        
        // Clear selection
        tweetElement.removeAttribute('data-selected-gif');
        tweetElement.querySelectorAll('.gif-item-reply').forEach(item => {
            item.classList.remove('selected');
        });
    }

    // Update GIF panel navigation display
    function updateGifPanelNavigation(tweetElement, currentIndex, queries) {
        const panel = tweetElement.querySelector('.gif-suggestion-panel');
        if (!panel) return;

        const nav = panel.querySelector('.gif-query-navigation');
        const queryText = panel.querySelector('.gif-query-text');
        const prevBtn = panel.querySelector('.gif-query-prev');
        const nextBtn = panel.querySelector('.gif-query-next');

        if (queries.length > 1) {
            nav.style.display = 'flex';
            queryText.textContent = queries[currentIndex];
            prevBtn.disabled = currentIndex === 0;
            nextBtn.disabled = currentIndex === queries.length - 1;
        } else {
            nav.style.display = 'none';
        }
    }

    // Navigate between GIF queries
    function navigateGifQuery(tweetElement, direction) {
        const queriesJson = tweetElement.getAttribute('data-gif-queries');
        if (!queriesJson) return;

        const queries = JSON.parse(queriesJson);
        const currentIndex = parseInt(tweetElement.getAttribute('data-current-query-index') || '0');
        const newIndex = Math.max(0, Math.min(queries.length - 1, currentIndex + direction));

        if (newIndex !== currentIndex) {
            tweetElement.setAttribute('data-current-query-index', newIndex.toString());
            const newQuery = queries[newIndex];

            // Show loading state
            showGifLoading(tweetElement);

            // Load GIFs for new query (with rate limiting consideration)
            setTimeout(() => {
                loadGifsForTweet(tweetElement, newQuery).then(gifs => {
                    if (gifs && gifs.length > 0) {
                        displayGifsInPanel(tweetElement, gifs);
                    } else {
                        showGifEmpty(tweetElement);
                    }
                    updateGifPanelNavigation(tweetElement, newIndex, queries);
                });
            }, 200); // Small delay to respect Tenor's 1 RPS limit
        }
    }

    // Download GIF directly
    function downloadGif(gifData) {
        // Register share with Tenor
        fetch('/gifs/api/register-share', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ gif_id: gifData.id })
        }).catch(err => console.error('Error registering share:', err));

        // Download the GIF
        fetch(gifData.url)
            .then(response => response.blob())
            .then(blob => {
                const blobUrl = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = blobUrl;
                link.download = `${gifData.title || 'gif'}-${gifData.id}.gif`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                setTimeout(() => URL.revokeObjectURL(blobUrl), 100);

                // showToast('GIF downloaded! You can now add it to your reply.', 'success');
            })
            .catch(error => {
                console.error('Download error:', error);
                window.open(gifData.url, '_blank');
                // showToast('Opening GIF in new tab...', 'info');
            });
    }

    // NEW: Download selected GIF
    function downloadSelectedGif(tweetElement) {
        const selectedGifJson = tweetElement.getAttribute('data-selected-gif');
        
        if (!selectedGifJson) {
            // showToast('No GIF selected', 'error');
            return;
        }
        
        const gifData = JSON.parse(selectedGifJson);
        
        // Register share with Tenor
        fetch('/gifs/api/register-share', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ gif_id: gifData.id })
        }).catch(err => console.error('Error registering share:', err));
        
        // Download the GIF
        fetch(gifData.url)
            .then(response => response.blob())
            .then(blob => {
                const blobUrl = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = blobUrl;
                link.download = `${gifData.title || 'gif'}-${gifData.id}.gif`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                setTimeout(() => URL.revokeObjectURL(blobUrl), 100);
                
                // showToast('GIF downloaded! You can now add it to your reply.', 'success');
            })
            .catch(error => {
                console.error('Download error:', error);
                window.open(gifData.url, '_blank');
                // showToast('Opening GIF in new tab...', 'info');
            });
    }

    function getSelectedStyle(tweetElement) {
        const styleDropdown = tweetElement.querySelector('.dropdown');
        const selectedOption = styleDropdown ? styleDropdown.querySelector('.reply-style-option.selected') : null;
        return selectedOption ? selectedOption.getAttribute('data-value') : 'supportive';
    }

    function getBrandVoiceState(tweetElement) {
        const globalCheckbox = document.getElementById('global-brand-voice');
        if (globalCheckbox && !globalCheckbox.disabled) {
            return globalCheckbox.checked;
        }

        const checkbox = tweetElement.querySelector('.brand-voice-checkbox');
        return checkbox ? checkbox.checked : false;
    }

    function postReply(tweetElement) {
        if (!tweetElement) return;

        const tweetId = tweetElement.getAttribute('data-tweet-id');
        const textarea = tweetElement.querySelector('.reply-textarea');
        const replyText = textarea ? textarea.value.trim() : '';

        if (!replyText || replyText.includes('Error') || replyText.includes('Generating')) {
            // showToast('Please generate a valid reply first', 'error');
            return;
        }

        if (replyText.length > 280) {
            // showToast('Reply exceeds 280 characters', 'error');
            return;
        }

        const tweetUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(replyText)}&in_reply_to=${tweetId}`;

        window.open(tweetUrl, '_blank', 'noopener,noreferrer');

        fetch('/reply-guy/log-reply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tweet_id: tweetId,
                reply_text: replyText
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.stats) {
                updateProgressBar(data.stats);
                // showToast('Reply logged successfully!', 'success');
            }
        })
        .catch(error => {
            console.error('Error logging reply:', error);
        });
    }

    function updateCharacterCount(textarea) {
        if (!textarea) return;

        const count = textarea.value.length;
        const counter = textarea.closest('.reply-panel')?.querySelector('.character-count');
        if (counter) {
            counter.textContent = `${count}/280`;
            if (count > 280) {
                counter.classList.add('over-limit');
            } else {
                counter.classList.remove('over-limit');
            }
        }
    }

    function updateProgressBar(stats) {
        const progressFill = document.querySelector('.progress-fill');
        const progressPercentage = document.querySelector('.progress-percentage');
        const progressText = document.querySelector('.progress-text');

        if (progressFill && progressPercentage && progressText) {
            const newPercentage = Math.min(Math.round(stats.progress_percentage), 100);

            progressFill.style.width = newPercentage + '%';
            progressPercentage.textContent = newPercentage + '%';

            const newProgressText = `You've posted <strong>${stats.total_replies}</strong> out of <strong>${stats.target}</strong> replies today. `;
            let motivationalText = '';

            if (newPercentage >= 100) {
                motivationalText = 'Congratulations! You\'ve reached your daily goal!';
            } else if (newPercentage >= 75) {
                motivationalText = 'You\'re almost there! Keep it up!';
            } else if (newPercentage >= 50) {
                motivationalText = 'Great progress! You\'re halfway to your goal.';
            } else {
                motivationalText = 'Let\'s get started on your reply goals for today.';
            }

            progressText.innerHTML = newProgressText + motivationalText;
        }
    }

    // List Management Functions
    function handleCreateList() {
        const nameInput = document.getElementById('new-list-name');
        const typeInput = document.getElementById('new-list-type');
        const xListIdInput = document.getElementById('x-list-id');

        const name = nameInput ? nameInput.value.trim() : '';
        const type = typeInput ? typeInput.value : 'x_list';
        const xListId = xListIdInput ? xListIdInput.value.trim() : '';

        if (!name) {
            // showToast('Please enter a list name', 'error');
            return;
        }

        if (type === 'x_list' && !xListId) {
            // showToast('Please enter an X List ID', 'error');
            return;
        }

        showLoading('Creating your custom list...', 'Creating your custom list...');

        fetch('/reply-guy/create-custom-list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                type: type,
                x_list_id: type === 'x_list' ? xListId : null
            })
        })
        .then(response => response.json())
        .then(data => {
            hideLoading();
            if (data.success) {
                // showToast('List created successfully!', 'success');

                if (nameInput) nameInput.value = '';
                if (xListIdInput) xListIdInput.value = '';

                setTimeout(() => window.location.reload(), 1000);
            } else {
                // showToast('Error creating list: ' + data.error, 'error');
            }
        })
        .catch(error => {
            hideLoading();
            // showToast('Network error creating list', 'error');
        });
    }

    function refreshXList(listId) {
        showLoading('Refreshing X List', 'Fetching latest accounts from X...');

        fetch('/reply-guy/update-custom-list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                list_id: listId,
                action: 'refresh'
            })
        })
        .then(response => response.json())
        .then(data => {
            hideLoading();

            if (data.success) {
                // showToast(`List refreshed! Found ${data.account_count} accounts.`, 'success');
                setTimeout(() => window.location.reload(), 1000);
            } else {
                // showToast('Error refreshing list: ' + data.error, 'error');
            }
        })
        .catch(error => {
            hideLoading();
            // showToast('Network error refreshing list', 'error');
        });
    }

    // Modal functions
    function setupModals() {
        const closeEditModal = document.getElementById('close-edit-modal');
        if (closeEditModal) {
            closeEditModal.onclick = () => hideModal('edit-list-modal');
        }

        const cancelEditBtn = document.getElementById('cancel-edit-btn');
        if (cancelEditBtn) {
            cancelEditBtn.onclick = () => hideModal('edit-list-modal');
        }

        const saveEditBtn = document.getElementById('save-edit-btn');
        if (saveEditBtn) {
            saveEditBtn.onclick = saveEditChanges;
        }

        const addAccountBtn = document.getElementById('add-account-btn');
        if (addAccountBtn) {
            addAccountBtn.onclick = addAccountToList;
        }

        const closeDeleteModal = document.getElementById('close-delete-modal');
        if (closeDeleteModal) {
            closeDeleteModal.onclick = () => hideModal('delete-modal');
        }

        const cancelDeleteBtn = document.getElementById('cancel-delete-btn');
        if (cancelDeleteBtn) {
            cancelDeleteBtn.onclick = () => hideModal('delete-modal');
        }

        const confirmDeleteBtn = document.getElementById('confirm-delete-btn');
        if (confirmDeleteBtn) {
            confirmDeleteBtn.onclick = confirmDelete;
        }

        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                hideModal(e.target.id);
            }
        });
    }

    function showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('show');
        }
    }

    function hideModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('show');
        }
    }

    function openEditModal(listId) {
        state.currentEditingListId = listId;

        fetch('/reply-guy/get-custom-list-details', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ list_id: listId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const list = data.list;
                const editListName = document.getElementById('edit-list-name');
                if (editListName) {
                    editListName.value = list.name;
                }

                const accountsSection = document.getElementById('accounts-section');
                if (accountsSection) {
                    if (list.type === 'x_list') {
                        accountsSection.style.display = 'none';
                    } else {
                        accountsSection.style.display = 'block';

                        const tagsContainer = document.getElementById('edit-account-tags');
                        if (tagsContainer) {
                            tagsContainer.innerHTML = '';

                            list.accounts.forEach(account => {
                                const tag = createAccountTag(account);
                                tagsContainer.appendChild(tag);
                            });
                        }
                    }
                }

                showModal('edit-list-modal');
            } else {
                // showToast('Error loading list details: ' + data.error, 'error');
            }
        })
        .catch(error => {
            // showToast('Network error loading list details', 'error');
        });
    }

    function createAccountTag(account) {
        const tag = document.createElement('div');
        tag.style.cssText = `
            background: rgba(59, 130, 246, 0.1);
            color: #3B82F6;
            padding: 0.5rem 0.75rem;
            border-radius: 8px;
            font-size: 0.875rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-weight: 500;
            border: 1px solid rgba(59, 130, 246, 0.3);
        `;
        tag.innerHTML = `
            @${account}
            <button style="background: none; border: none; color: #EF4444; cursor: pointer; padding: 0; font-size: 0.875rem;" data-account="${account}">×</button>
        `;

        const removeBtn = tag.querySelector('button');
        if (removeBtn) {
            removeBtn.onclick = function() {
                const accountToRemove = this.getAttribute('data-account');
                removeAccountFromEdit(accountToRemove);
                tag.remove();
            };
        }

        return tag;
    }

    function removeAccountFromEdit(account) {
        fetch('/reply-guy/update-custom-list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                list_id: state.currentEditingListId,
                action: 'remove_account',
                account: account
            })
        })
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                // showToast('Error removing account: ' + data.error, 'error');
            }
        });
    }

    function addAccountToList() {
        const newAccountInput = document.getElementById('new-account-input');
        const account = newAccountInput ? newAccountInput.value.trim() : '';

        if (!account) {
            // showToast('Please enter an account name', 'error');
            return;
        }

        const cleanAccount = account.startsWith('@') ? account.slice(1) : account;

        fetch('/reply-guy/update-custom-list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                list_id: state.currentEditingListId,
                action: 'add_account',
                account: cleanAccount
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const tag = createAccountTag(cleanAccount);
                const editAccountTags = document.getElementById('edit-account-tags');
                if (editAccountTags) {
                    editAccountTags.appendChild(tag);
                }
                if (newAccountInput) {
                    newAccountInput.value = '';
                }

                // showToast('Account added successfully', 'success');
            } else {
                // showToast('Error adding account: ' + data.error, 'error');
            }
        })
        .catch(error => {
            // showToast('Network error adding account', 'error');
        });
    }

    function saveEditChanges() {
        const editListName = document.getElementById('edit-list-name');
        const newName = editListName ? editListName.value.trim() : '';

        if (!newName) {
            // showToast('Please enter a list name', 'error');
            return;
        }

        fetch('/reply-guy/update-custom-list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                list_id: state.currentEditingListId,
                action: 'update_name',
                name: newName
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // showToast('List updated successfully!', 'success');
                hideModal('edit-list-modal');
                setTimeout(() => window.location.reload(), 1000);
            } else {
                // showToast('Error updating list: ' + data.error, 'error');
            }
        })
        .catch(error => {
            // showToast('Network error updating list', 'error');
        });
    }

    function openDeleteModal(listId) {
        state.currentDeletingListId = listId;

        const listItem = document.querySelector(`[data-list-id="${listId}"]`);
        const listName = listItem ? listItem.querySelector('.list-name').textContent : 'Unknown List';

        const deleteListName = document.getElementById('delete-list-name');
        if (deleteListName) {
            deleteListName.textContent = `List: ${listName}`;
        }

        showModal('delete-modal');
    }

    function confirmDelete() {
        fetch('/reply-guy/delete-custom-list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ list_id: state.currentDeletingListId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // showToast('List deleted successfully!', 'success');
                hideModal('delete-modal');
                setTimeout(() => window.location.reload(), 1000);
            } else {
                // showToast('Error deleting list: ' + data.error, 'error');
            }
        })
        .catch(error => {
            // showToast('Network error deleting list', 'error');
        });
    }

    // Utility functions
    function showLoading(title, description) {
        const loadingText = document.getElementById('loading-text');
        const loadingDescription = document.getElementById('loading-description');

        if (loadingText) loadingText.textContent = title;
        if (loadingDescription) loadingDescription.textContent = description;

        showModal('loading-modal');
    }

    function hideLoading() {
        hideModal('loading-modal');
    }

    // Commented out toast functionality
    function showToast(message, type = 'info') {
        return; // Toast messages disabled
        const existingToast = document.querySelector('.toast');
        if (existingToast) {
            existingToast.remove();
        }

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        let icon = 'ph-info';
        if (type === 'success') icon = 'ph-check-circle';
        else if (type === 'error') icon = 'ph-x-circle';
        else if (type === 'warning') icon = 'ph-warning';

        toast.innerHTML = `
            <i class="ph ${icon}"></i>
            <span class="toast-text">${message}</span>
        `;

        document.body.appendChild(toast);

        setTimeout(() => toast.classList.add('show'), 100);

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // Functions for managing create list modal
    function showInlineCreateForm() {
        const modal = document.getElementById('create-list-panel');
        if (modal) {
            modal.style.display = 'flex';
            // Close dropdown
            closeDropdowns();
        }
    }

    function hideCreatePanel() {
        const modal = document.getElementById('create-list-panel');
        if (modal) {
            modal.style.display = 'none';
            // Clear inputs
            const nameInput = document.getElementById('panel-list-name');
            const idInput = document.getElementById('panel-x-list-id');
            if (nameInput) nameInput.value = '';
            if (idInput) idInput.value = '';
        }
    }

    // Close modal when clicking outside
    document.addEventListener('click', function(e) {
        const modal = document.getElementById('create-list-panel');
        if (modal && e.target === modal) {
            hideCreatePanel();
        }
    });

    function handlePanelCreateList() {
        const nameInput = document.getElementById('panel-list-name');
        const idInput = document.getElementById('panel-x-list-id');
        const btn = document.getElementById('panel-create-btn');

        if (!nameInput || !idInput) return;

        const name = nameInput.value.trim();
        const xListId = idInput.value.trim();

        if (!name) {
            alert('Please enter a list name');
            return;
        }

        if (!xListId) {
            alert('Please enter an X List ID');
            return;
        }

        // Show loading state on button
        if (btn) {
            btn.disabled = true;
            btn.classList.add('loading');
            const icon = btn.querySelector('i');
            if (icon) {
                icon.className = 'ph ph-spinner';
            }
            const span = btn.querySelector('span');
            if (span) {
                span.textContent = 'Adding...';
            }
        }

        fetch('/reply-guy/create-custom-list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                type: 'x_list',
                x_list_id: xListId
            })
        })
        .then(response => response.json())
        .then(data => {
            // Reset button state
            if (btn) {
                btn.disabled = false;
                btn.classList.remove('loading');
                const icon = btn.querySelector('i');
                if (icon) {
                    icon.className = 'ph ph-plus';
                }
                const span = btn.querySelector('span');
                if (span) {
                    span.textContent = 'Add List';
                }
            }

            if (data.success) {
                console.log('✅ List created:', data.list);
                hideCreatePanel();

                // Clear form
                if (nameInput) nameInput.value = '';
                if (idInput) idInput.value = '';

                // Add the new list to the dropdown dynamically
                const newList = data.list;
                const dropdownMenu = document.getElementById('list-dropdown-menu');
                if (dropdownMenu) {
                    const divider = dropdownMenu.querySelector('.dropdown-divider');
                    const option = document.createElement('div');
                    option.className = 'dropdown-option';
                    option.setAttribute('data-value', newList.id);
                    option.setAttribute('data-type', 'custom');
                    option.innerHTML = `
                        <i class="ph ph-user-circle option-icon"></i>
                        ${newList.name}
                    `;

                    if (divider) {
                        dropdownMenu.insertBefore(option, divider);
                    } else {
                        dropdownMenu.appendChild(option);
                    }

                    // Remove "No custom lists yet" message if present
                    const emptyMessage = dropdownMenu.querySelector('.dropdown-empty');
                    if (emptyMessage) emptyMessage.remove();

                    console.log('✅ Added list to dropdown');
                }

                // Select the newly created list
                setTimeout(() => {
                    state.selectedList = newList.id;
                    state.selectedListType = 'custom';

                    const selectedListText = document.getElementById('selected-list-text');
                    if (selectedListText) selectedListText.textContent = newList.name;

                    // Mark as updating to show spinner on button
                    state.ongoingUpdates[newList.id] = {
                        status: 'running',
                        started_at: new Date().toISOString(),
                        timestamp: Date.now()
                    };
                    saveOngoingUpdates();
                    updateButtonVisibility();

                    fetch('/reply-guy/analyze', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            list_id: newList.id,
                            list_type: 'custom',
                            time_range: '24h'
                        })
                    })
                    .then(response => response.json())
                    .then(analysisData => {
                        delete state.ongoingUpdates[newList.id];
                        saveOngoingUpdates();
                        updateButtonVisibility();

                        if (analysisData.success) {
                            console.log('✅ Analysis completed');
                            loadInitialData();
                        } else {
                            console.error('❌ Analysis failed:', analysisData.error);
                            loadInitialData();
                        }
                    })
                    .catch(analysisError => {
                        delete state.ongoingUpdates[newList.id];
                        saveOngoingUpdates();
                        updateButtonVisibility();
                        console.error('❌ Analysis error:', analysisError);
                        loadInitialData();
                    });
                }, 500);
            } else {
                console.error('❌ Error creating list:', data.error);
                alert('Error creating list: ' + data.error);
            }
        })
        .catch(error => {
            // Reset button state on error
            if (btn) {
                btn.disabled = false;
                btn.classList.remove('loading');
                const icon = btn.querySelector('i');
                if (icon) {
                    icon.className = 'ph ph-plus';
                }
                const span = btn.querySelector('span');
                if (span) {
                    span.textContent = 'Add List';
                }
            }
            console.error('❌ Network error creating list:', error);
            alert('Network error creating list');
        });
    }

    // Functions for managing create list modal (deprecated - modal version)
    function showCreateModal() {
        const modal = document.getElementById('create-list-modal');
        if (modal) {
            modal.classList.add('show');

            modal.setAttribute('style', `
                display: flex !important;
                align-items: flex-start !important;
                justify-content: center !important;
                padding-top: 5rem !important;
                padding-bottom: 0 !important;
                padding-left: 0 !important;
                padding-right: 0 !important;
                position: fixed !important;
                top: 0 !important;
                left: 0 !important;
                right: 0 !important;
                bottom: 0 !important;
                width: 100% !important;
                height: 100% !important;
                background: rgba(0, 0, 0, 0.5) !important;
                z-index: 10000 !important;
                opacity: 1 !important;
                visibility: visible !important;
                overflow-y: auto !important;
            `);

            const modalContent = modal.querySelector('.modal-content');
            if (modalContent) {
                modalContent.setAttribute('style', `
                    margin-top: 0 !important;
                    margin-bottom: auto !important;
                    position: relative !important;
                    transform: none !important;
                    max-height: calc(100vh - 10rem) !important;
                    overflow-y: auto !important;
                `);
            }

            setTimeout(() => {
                const computed = window.getComputedStyle(modal);
                const modalContent = modal.querySelector('.modal-content');
                const contentComputed = modalContent ? window.getComputedStyle(modalContent) : null;

                if (contentComputed) {
                }

                const rect = modal.getBoundingClientRect();
                const contentRect = modalContent ? modalContent.getBoundingClientRect() : null;
                if (contentRect) {
                }
            }, 100);
        } else {
        }
    }

    function hideCreateModal() {
        const modal = document.getElementById('create-list-modal');
        if (modal) {
            modal.classList.remove('show');
            modal.removeAttribute('style');
        }
        const nameInput = document.getElementById('simple-list-name');
        const idInput = document.getElementById('simple-x-list-id');
        if (nameInput) nameInput.value = '';
        if (idInput) idInput.value = '';
    }

    function handleSimpleCreateList() {
        const nameInput = document.getElementById('simple-list-name');
        const idInput = document.getElementById('simple-x-list-id');

        if (!nameInput || !idInput) return;

        const name = nameInput.value.trim();
        const xListId = idInput.value.trim();

        if (!name) {
            // showToast('Please enter a list name', 'error');
            return;
        }

        if (!xListId) {
            // showToast('Please enter an X List ID', 'error');
            return;
        }

        showLoading('Creating your custom list...', 'Please wait while we fetch the list accounts...');

        fetch('/reply-guy/create-custom-list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                type: 'x_list',
                x_list_id: xListId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('✅ List created:', data.list);
                hideCreateModal();

                // Clear form
                if (nameInput) nameInput.value = '';
                if (idInput) idInput.value = '';

                // Add the new list to the dropdown dynamically
                const newList = data.list;
                const dropdownMenu = document.getElementById('list-dropdown-menu');
                if (dropdownMenu) {
                    const divider = dropdownMenu.querySelector('.dropdown-divider');
                    const option = document.createElement('div');
                    option.className = 'dropdown-option';
                    option.setAttribute('data-value', newList.id);
                    option.setAttribute('data-type', 'custom');
                    option.innerHTML = `
                        <i class="ph ph-user-circle option-icon"></i>
                        ${newList.name}
                    `;

                    if (divider) {
                        dropdownMenu.insertBefore(option, divider);
                    } else {
                        dropdownMenu.appendChild(option);
                    }

                    // Remove "No custom lists yet" message if present
                    const emptyMessage = dropdownMenu.querySelector('.dropdown-empty');
                    if (emptyMessage) emptyMessage.remove();

                    console.log('✅ Added list to dropdown');
                }

                // Switch to custom mode and select the new list
                const customTab = document.querySelector('.mode-tab-compact[data-mode="custom"]');
                if (customTab) {
                    customTab.click();
                }

                // Select the newly created list after a short delay
                setTimeout(() => {
                    state.selectedList = newList.id;
                    state.selectedListType = 'custom';

                    const selectedListText = document.getElementById('selected-list-text');
                    if (selectedListText) selectedListText.textContent = newList.name;

                    // Mark as updating to show spinner on button
                    state.ongoingUpdates[newList.id] = {
                        status: 'running',
                        started_at: new Date().toISOString(),
                        timestamp: Date.now()
                    };
                    saveOngoingUpdates();
                    updateButtonVisibility();

                    fetch('/reply-guy/analyze', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            list_id: newList.id,
                            list_type: 'custom',
                            time_range: '24h'
                        })
                    })
                    .then(response => response.json())
                    .then(analysisData => {
                        delete state.ongoingUpdates[newList.id];
                        saveOngoingUpdates();
                        updateButtonVisibility();

                        if (analysisData.success) {
                            console.log('✅ Analysis completed');
                            loadInitialData();
                        } else {
                            console.error('❌ Analysis failed:', analysisData.error);
                            loadInitialData();
                        }
                    })
                    .catch(analysisError => {
                        delete state.ongoingUpdates[newList.id];
                        saveOngoingUpdates();
                        updateButtonVisibility();
                        console.error('❌ Analysis error:', analysisError);
                        loadInitialData();
                    });
                }, 500);
            } else {
                hideLoading();
                console.error('❌ Error creating list:', data.error);
            }
        })
        .catch(error => {
            hideLoading();
            console.error('❌ Network error creating list:', error);
        });
    }

    // Enhanced profile picture consistency handler
    function fixProfilePictureConsistency() {
        const profileMap = new Map();
        const authorNameMap = new Map();


        document.querySelectorAll('.tweet-opportunity').forEach(tweet => {
            const authorNameEl = tweet.querySelector('.tweet-author-name');
            const authorUsernameEl = tweet.querySelector('.tweet-author-username');
            const img = tweet.querySelector('.tweet-avatar img');

            if (authorNameEl && authorUsernameEl) {
                const displayName = authorNameEl.textContent.trim();
                const username = authorUsernameEl.textContent.replace('@', '').trim();

                authorNameMap.set(username, displayName);

                if (img && img.src && !img.src.includes('data:') && img.src !== window.location.href) {
                    const profileUrl = img.src;
                    if (!profileMap.has(username) && profileUrl) {
                        profileMap.set(username, profileUrl);
                    }
                }
            }
        });


        document.querySelectorAll('.tweet-avatar').forEach(avatar => {
            const img = avatar.querySelector('img');
            const fallback = avatar.querySelector('.fallback-avatar');
            const tweet = avatar.closest('.tweet-opportunity');

            if (tweet) {
                const authorUsernameEl = tweet.querySelector('.tweet-author-username');

                if (authorUsernameEl) {
                    const username = authorUsernameEl.textContent.replace('@', '').trim();
                    const storedProfileUrl = profileMap.get(username);

                    if (img) {
                        if (storedProfileUrl && (!img.src || img.src === window.location.href || img.src.includes('data:'))) {
                            console.log(`Fixing profile for @${username}`);
                            img.src = storedProfileUrl;
                        }

                        img.onload = function() {
                            this.style.display = 'block';
                            this.classList.remove('error');
                            if (fallback) fallback.style.display = 'none';
                        };

                        img.onerror = function() {
                            console.log(`Image failed for @${username}, showing fallback`);
                            this.style.display = 'none';
                            this.classList.add('error');
                            if (fallback) {
                                fallback.style.display = 'flex';
                                const firstLetter = username.charAt(0).toUpperCase();
                                const icon = fallback.querySelector('i');
                                if (icon) {
                                    icon.textContent = firstLetter;
                                    icon.style.fontSize = '1.2rem';
                                    icon.style.fontWeight = 'bold';
                                    icon.style.fontFamily = 'system-ui, sans-serif';
                                }
                            }
                        };

                        if (img.naturalWidth === 0 && img.complete) {
                            img.onerror();
                        }
                    } else if (!img && fallback) {
                        fallback.style.display = 'flex';
                        const firstLetter = username.charAt(0).toUpperCase();
                        const icon = fallback.querySelector('i');
                        if (icon) {
                            icon.textContent = firstLetter;
                            icon.style.fontSize = '1.2rem';
                            icon.style.fontWeight = 'bold';
                            icon.style.fontFamily = 'system-ui, sans-serif';
                        }
                    }
                }
            }
        });

    }

    // Format tweet timestamps - Full format for X brand compliance
    function formatFullTimestamp(dateString) {
        try {
            const tweetDate = new Date(dateString);
            const hours = tweetDate.getHours();
            const minutes = tweetDate.getMinutes();
            const ampm = hours >= 12 ? 'PM' : 'AM';
            const displayHours = hours % 12 || 12;
            const displayMinutes = minutes.toString().padStart(2, '0');

            const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            const month = monthNames[tweetDate.getMonth()];
            const day = tweetDate.getDate();
            const year = tweetDate.getFullYear();

            return `${displayHours}:${displayMinutes} ${ampm} · ${month} ${day}, ${year}`;
        } catch (e) {
            return '';
        }
    }

    // Format numbers with commas (e.g., 3819 -> 3,819)
    function formatNumber(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }

    // Format numbers with K/M abbreviation for large numbers (X style)
    function formatNumberAbbreviated(num) {
        const absNum = Math.abs(num);

        if (absNum >= 1000000) {
            // Millions: 9930000 -> 9.9M
            const millions = num / 1000000;
            return millions.toFixed(1).replace(/\.0$/, '') + 'M';
        } else if (absNum >= 10000) {
            // Ten thousands and above: 99300 -> 99.3K
            const thousands = num / 1000;
            return thousands.toFixed(1).replace(/\.0$/, '') + 'K';
        } else if (absNum >= 1000) {
            // Thousands: 9930 -> 9,930 (keep with commas)
            return formatNumber(num);
        }

        return num.toString();
    }

    // Format tweet text by converting \n\n to <br><br>
    function formatTweetText(text) {
        if (!text) return '';
        return text.replace(/\\n\\n/g, '<br><br>').replace(/\\n/g, '<br>');
    }

    function updateTimestamps() {
        // Update full timestamps and format view counts
        document.querySelectorAll('.tweet-timestamp-full').forEach(el => {
            const timestamp = el.getAttribute('data-timestamp');
            const timeSpan = el.querySelector('.tweet-time');
            if (timestamp && timeSpan) {
                timeSpan.textContent = formatFullTimestamp(timestamp);
            }

            // Format view count with K/M abbreviation
            const viewsCount = el.querySelector('.tweet-views-count');
            if (viewsCount) {
                const rawViews = viewsCount.textContent.trim();
                if (rawViews && !isNaN(rawViews)) {
                    viewsCount.textContent = formatNumberAbbreviated(parseInt(rawViews));
                }
            }
        });

        // Format all engagement stats with K/M abbreviation
        document.querySelectorAll('.engagement-stat').forEach(stat => {
            const textNode = Array.from(stat.childNodes).find(node => node.nodeType === Node.TEXT_NODE);
            if (textNode) {
                const rawNumber = textNode.textContent.trim();
                if (rawNumber && !isNaN(rawNumber)) {
                    textNode.textContent = formatNumberAbbreviated(parseInt(rawNumber));
                }
            }
        });
    }

    // Format last refresh timestamp with color coding
    function formatLastRefresh() {
        const indicator = document.querySelector('.last-refresh-indicator');
        if (!indicator) {
            console.log('No last-refresh-indicator found');
            return;
        }

        const timestampStr = indicator.getAttribute('data-timestamp');
        if (!timestampStr || timestampStr === 'None' || timestampStr === '') {
            console.log('No valid timestamp, hiding indicator');
            indicator.style.display = 'none';
            return;
        }


        try {
            // Parse timestamp - handle multiple formats
            let timestamp;

            // Handle ISO format with microseconds: "2025-11-02 17:33:58.191744+00:00"
            // Or standard ISO: "2025-11-02T17:33:58Z"
            // Or simple format: "2025-01-11 14:30:45"

            if (timestampStr.includes('T')) {
                // ISO format with T separator
                timestamp = new Date(timestampStr);
            } else if (timestampStr.includes('+') || timestampStr.includes('Z')) {
                // Space-separated with timezone - replace space with T
                timestamp = new Date(timestampStr.replace(' ', 'T'));
            } else {
                // Simple format without timezone - add Z for UTC
                timestamp = new Date(timestampStr.replace(' ', 'T') + 'Z');
            }

            // Validate timestamp
            if (isNaN(timestamp.getTime())) {
                console.error('Invalid timestamp format:', timestampStr);
                indicator.style.display = 'none';
                return;
            }

            const now = new Date();
            const diffMs = now - timestamp;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);

            let timeText = '';
            let freshnessClass = '';

            // Clear and simple time display
            if (diffMins < 1) {
                timeText = 'just now';
                freshnessClass = 'fresh';
            } else if (diffMins < 60) {
                timeText = diffMins === 1 ? '1 min ago' : `${diffMins} mins ago`;
                freshnessClass = diffMins < 15 ? 'fresh' : (diffMins < 30 ? 'recent' : 'stale');
            } else if (diffHours < 24) {
                timeText = diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
                freshnessClass = 'old';
            } else {
                timeText = diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;
                freshnessClass = 'old';
            }


            // Update the time text
            const timeEl = document.getElementById('lastRefreshTime');
            if (timeEl) {
                timeEl.textContent = timeText;
            }

            // Add freshness class
            indicator.classList.add(freshnessClass);

        } catch (e) {
            console.error('Error formatting last refresh time:', e);
        }
    }

    // Helper to wait for Twitter widgets to be ready
    function waitForTwitterWidgets(maxWait = 5000) {
        return new Promise((resolve) => {
            const startTime = Date.now();
            const checkInterval = setInterval(() => {
                if (window.twttr && window.twttr.widgets) {
                    clearInterval(checkInterval);
                    resolve(true);
                } else if (Date.now() - startTime > maxWait) {
                    clearInterval(checkInterval);
                    console.warn('Twitter widgets script not loaded after timeout');
                    resolve(false);
                }
            }, 100);
        });
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    // Fix profile pictures after content loads
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(fixProfilePictureConsistency, 1000);
        formatLastRefresh();
    });

    // Timestamps are now handled by X embed widgets
    // updateTimestamps();

    // Pagination: Load More functionality with API
    const loadMoreBtn = document.getElementById('load-more-btn');
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', async function() {
            const listId = this.getAttribute('data-list-id');
            const listType = this.getAttribute('data-list-type');
            const loaded = parseInt(this.getAttribute('data-loaded'));
            const total = parseInt(this.getAttribute('data-total'));

            this.disabled = true;
            this.innerHTML = '<i class="ph ph-spinner"></i> Loading...';

            try {
                const response = await fetch('/reply-guy/get-more-tweets', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        list_id: listId,
                        list_type: listType,
                        offset: loaded,
                        limit: 50
                    })
                });

                const data = await response.json();

                if (data.success && data.tweets) {
                    const tweetsSection = document.getElementById('tweets-section');
                    const loadMoreContainer = this.parentElement;

                    data.tweets.forEach(tweet => {
                        const tweetHtml = renderTweetCard(tweet);
                        // Insert before the load more button container
                        loadMoreContainer.insertAdjacentHTML('beforebegin', tweetHtml);
                    });

                    // Reload X (Twitter) embed widgets for new tweets
                    if (window.twttr && window.twttr.widgets) {
                        window.twttr.widgets.load();
                    }

                    const newLoaded = loaded + data.tweets.length;
                    this.setAttribute('data-loaded', newLoaded);

                    // Timestamps are handled by X embed widgets
                    // updateTimestamps();

                    // Re-setup reply style dropdowns for new tweets
                    setupReplyStyleDropdowns();

                    // Re-apply brand voice state for new tweets
                    setBrandVoiceState(state.hasBrandVoiceData);

                    // Fix profile pictures for new tweets
                    setTimeout(fixProfilePictureConsistency, 500);

                    if (data.has_more) {
                        const remaining = total - newLoaded;
                        this.innerHTML = `<i class="ph ph-arrow-down"></i> Load More (${remaining} remaining)`;
                        this.disabled = false;
                    } else {
                        this.parentElement.style.display = 'none';
                    }

                    console.log(`Loaded ${data.tweets.length} more tweets`);
                } else {
                    throw new Error(data.error || 'Failed to load tweets');
                }
            } catch (error) {
                console.error('Error loading more tweets:', error);
                this.innerHTML = '<i class="ph ph-warning"></i> Error - Try again';
                this.disabled = false;
            }
        });
    }

    function renderTweetCard(tweet) {
        const replyStyles = [
            {id: "creatrics", name: "Creatrics"},
            {id: "supportive", name: "Supportive"},
            {id: "questioning", name: "Questioning"},
            {id: "valueadd", name: "Value-Add"},
            {id: "humorous", name: "Humorous"},
            {id: "contrarian", name: "Contrarian"}
        ];

        // Render reply style options
        const replyStyleOptionsHtml = replyStyles.map((style, index) => `
            <div class="dropdown-option reply-style-option ${index === 0 ? 'selected' : ''}" data-value="${style.id}">
                ${style.name}
            </div>
        `).join('');

        return `
            <div class="tweet-opportunity" data-tweet-id="${tweet.tweet_id}">
                <div class="tweet-grid">
                    <!-- Tweet Content - Official X Embed -->
                    <div class="tweet-content-section">
                        <blockquote class="twitter-tweet" data-theme="dark" data-dnt="true">
                            <a href="https://twitter.com/${tweet.author}/status/${tweet.tweet_id}"></a>
                        </blockquote>
                    </div>

                    <!-- Reply Panel with GIF Support -->
                    <div class="reply-panel">
                        <div class="reply-panel-header">
                            <div class="style-selector">
                                <div class="dropdown">
                                    <div class="dropdown-trigger reply-style-trigger">
                                        <span class="selected-style-text">Creatrics</span>
                                        <i class="ph ph-caret-down dropdown-arrow"></i>
                                    </div>
                                    <div class="dropdown-menu reply-style-menu">
                                        ${replyStyleOptionsHtml}
                                    </div>
                                </div>
                            </div>

                            <label for="brand-voice-tweet-${tweet.tweet_id}" class="brand-voice-toggle">
                                <input type="checkbox" id="brand-voice-tweet-${tweet.tweet_id}" class="brand-voice-checkbox">
                                <span class="toggle-slider"></span>
                                <span class="toggle-label">Brand Voice</span>
                            </label>
                        </div>

                        <textarea id="reply-textarea-tweet-${tweet.tweet_id}" class="reply-textarea"
                                  placeholder="Click generate to create a response..."></textarea>

                        <div class="reply-footer">
                            <div class="character-count">0/280</div>
                            <div class="reply-actions">
                                <button class="action-btn post post-reply-btn" title="Post reply">
                                    <i class="ph ph-paper-plane-right"></i>
                                </button>
                                <button class="action-btn generate generate-reply-btn" title="Generate AI reply">
                                    <i class="ph ph-sparkle"></i>
                                </button>
                            </div>
                        </div>

                        <!-- GIF Panel will be dynamically created by JS -->
                    </div>
                </div>
            </div>
        `;
    }

    // Debug info
    setTimeout(() => {
        const generateBtns = document.querySelectorAll('.generate-reply-btn');
        const tweetOpportunities = document.querySelectorAll('.tweet-opportunity');
        const repliesPanel = document.getElementById('replies-panel');
        const emptyState = document.querySelector('.empty-state');


        generateBtns.forEach((btn, index) => {
            console.log(`Button ${index}:`, btn, 'Disabled:', btn.disabled);
            btn.addEventListener('click', () => {
                console.log(`Direct click on button ${index} detected!`);
            });
        });

        if (generateBtns.length === 0) {
            console.log('❌ No generate buttons found - you may need to select a list first');
        }
    }, 2000);

    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        return originalFetch.apply(this, args).then(response => {
            if (args[0] && (args[0].includes('reply-guy') || args[0].includes('analysis'))) {
                setTimeout(fixProfilePictureConsistency, 1000);
            }
            return response;
        });
    };

    // Add spin animation style
    const style = document.createElement('style');
    style.textContent = `
    .ph-spin {
        animation: spin 1s linear infinite;
    }
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    `;
    document.head.appendChild(style);

})();