// Reply Guy Application
(function() {
    'use strict';

    console.log('Reply Guy JS loaded successfully');

    // State management
    const state = {
        currentView: 'replies',
        selectedList: null,
        selectedListType: null,
        currentEditingListId: null,
        currentDeletingListId: null,
        hasBrandVoiceData: false,
        ongoingUpdates: {},
        isInitialized: false
    };

    // Initialize application
    function init() {
        if (state.isInitialized) return;

        console.log('Initializing Reply Guy...');

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
        console.log('Reply Guy initialized');
    }

    // Load initial data from server
    function loadInitialData() {
        // First, load from sessionStorage to persist across page navigation
        try {
            const storedUpdates = sessionStorage.getItem('reply_guy_ongoing_updates');
            if (storedUpdates) {
                const parsed = JSON.parse(storedUpdates);
                // Clean up old updates (older than 5 minutes)
                const fiveMinutesAgo = Date.now() - (5 * 60 * 1000);
                state.ongoingUpdates = {};
                for (const [listId, updateInfo] of Object.entries(parsed)) {
                    if (updateInfo.timestamp && updateInfo.timestamp > fiveMinutesAgo) {
                        state.ongoingUpdates[listId] = updateInfo;
                    }
                }
                console.log('Loaded ongoing updates from session:', state.ongoingUpdates);
            }
        } catch (error) {
            console.error('Error loading from sessionStorage:', error);
            state.ongoingUpdates = {};
        }

        // Then load server data
        const initialDataElement = document.getElementById('initial-data');
        if (initialDataElement) {
            try {
                const initialData = JSON.parse(initialDataElement.textContent);
                // Merge with server data (server data takes precedence)
                state.ongoingUpdates = { ...state.ongoingUpdates, ...(initialData.ongoing_updates || {}) };
            } catch (error) {
                console.error('Error parsing initial data:', error);
            }
        }
    }

    // Save ongoing updates to sessionStorage
    function saveOngoingUpdates() {
        try {
            sessionStorage.setItem('reply_guy_ongoing_updates', JSON.stringify(state.ongoingUpdates));
        } catch (error) {
            console.error('Error saving to sessionStorage:', error);
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

        // If no list is selected on page load, the dropdown text needs to be updated
        // but we don't need to call selectList() since the backend already auto-selected it
        if (!state.selectedList) {
            const firstDefaultList = document.querySelector('.dropdown-option[data-type="default"]');
            if (firstDefaultList) {
                console.log('Auto-selecting first default list UI on page load');
                // Just update the UI, don't make an API call
                const optionText = firstDefaultList.textContent.trim();
                const selectedListText = document.getElementById('selected-list-text');
                const selectedListTextEmpty = document.getElementById('selected-list-text-empty');
                if (selectedListText) selectedListText.textContent = optionText;
                if (selectedListTextEmpty) selectedListTextEmpty.textContent = optionText;

                firstDefaultList.classList.add('selected');
                state.selectedList = firstDefaultList.getAttribute('data-value');
                state.selectedListType = firstDefaultList.getAttribute('data-type');
            } else {
                // If no default lists, try custom lists
                const firstCustomList = document.querySelector('.dropdown-option[data-type="custom"]');
                if (firstCustomList) {
                    console.log('Auto-selecting first custom list on page load');
                    selectListOption(firstCustomList);
                }
            }
        }

        // Check if there are ongoing updates and refresh button state (deferred)
        if (Object.keys(state.ongoingUpdates).length > 0) {
            console.log('Found ongoing updates, checking their status...');
            setTimeout(() => checkOngoingUpdatesStatus(), 500);
        }

        updateButtonVisibility();
    }

    // Check status of ongoing updates
    function checkOngoingUpdatesStatus() {
        const listIds = Object.keys(state.ongoingUpdates);
        if (listIds.length === 0) return;

        // Check each ongoing update
        listIds.forEach(listId => {
            fetch('/reply-guy/check-update-status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ list_id: listId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success && !data.is_updating) {
                    // Update completed, remove from ongoing updates
                    delete state.ongoingUpdates[listId];
                    saveOngoingUpdates();

                    // If this is the currently selected list, refresh the page
                    if (listId === state.selectedList) {
                        showToast('Update completed! Refreshing...', 'success');
                        setTimeout(() => window.location.reload(), 1000);
                    }
                }
                updateButtonVisibility();
            })
            .catch(error => {
                console.error('Error checking update status:', error);
            });
        });

        // Continue checking every 5 seconds if there are still ongoing updates
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
            });
    }

    function setBrandVoiceState(hasData) {
        state.hasBrandVoiceData = hasData;

        console.log('Setting brand voice state:', hasData);

        // Load user preference from localStorage
        const userPrefersBrandVoice = localStorage.getItem('preferBrandVoice');
        const shouldEnableBrandVoice = userPrefersBrandVoice === null ? true : userPrefersBrandVoice === 'true';

        document.querySelectorAll('.brand-voice-checkbox').forEach(checkbox => {
            const wasDisabled = checkbox.disabled;
            checkbox.disabled = !hasData;
            console.log('Checkbox:', checkbox.id, 'disabled:', checkbox.disabled, 'hasData:', hasData, 'was disabled:', wasDisabled);

            // Auto-check if brand voice is available based on user preference
            if (hasData) {
                if (!checkbox.hasAttribute('data-initialized')) {
                    checkbox.checked = shouldEnableBrandVoice;
                    checkbox.setAttribute('data-initialized', 'true');
                    console.log('Initialized checkbox to:', shouldEnableBrandVoice);

                    // Add change listener to save preference (only once)
                    checkbox.addEventListener('change', function(e) {
                        console.log('Brand voice checkbox change event fired! New value:', this.checked);
                        localStorage.setItem('preferBrandVoice', this.checked);
                    }, { once: false });
                }
            } else {
                checkbox.checked = false;
                checkbox.removeAttribute('data-initialized');
            }
        });

        document.querySelectorAll('.brand-voice-toggle').forEach(toggle => {
            // Remove any existing click handler first to prevent duplicates
            const oldHandler = toggle._disabledClickHandler;
            if (oldHandler) {
                toggle.removeEventListener('click', oldHandler, true);
            }

            if (hasData) {
                toggle.classList.remove('disabled');
                toggle.title = '';
                toggle.style.removeProperty('pointer-events'); // Remove any inline style
                console.log('Brand voice toggle enabled');
            } else {
                toggle.classList.add('disabled');
                toggle.title = 'Connect your X account and ensure you have replies on your profile to enable brand voice';
                toggle.style.pointerEvents = 'none'; // Explicitly disable pointer events

                // Create and store the handler so we can remove it later
                const disabledHandler = function(e) {
                    if (this.classList.contains('disabled')) {
                        e.preventDefault();
                        e.stopPropagation();
                        e.stopImmediatePropagation();
                        console.log('Brand voice toggle is disabled - click prevented');
                        return false;
                    }
                };
                toggle._disabledClickHandler = disabledHandler;
                toggle.addEventListener('click', disabledHandler, true);  // Use capture phase
            }
        });

        // Handle global brand voice toggle specifically
        const globalToggle = document.querySelector('.brand-voice-toggle.global-brand-voice');
        const globalCheckbox = document.getElementById('global-brand-voice');

        if (globalToggle && globalCheckbox) {
            if (hasData) {
                globalToggle.classList.remove('disabled');
                globalToggle.title = 'Use your brand voice for all replies';
                // Add click handler for visual feedback
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
        // View toggle buttons
        const repliesViewBtn = document.getElementById('replies-view-btn');
        const listsViewBtn = document.getElementById('lists-view-btn');

        if (repliesViewBtn) {
            repliesViewBtn.onclick = () => switchView('replies');
        }

        if (listsViewBtn) {
            listsViewBtn.onclick = () => switchView('lists');
        }

        // Update buttons (both regular and empty state)
        const updateBtn = document.getElementById('update-btn');
        const updateBtnEmpty = document.getElementById('update-btn-empty');
        if (updateBtn) {
            updateBtn.onclick = handleUpdate;
        }
        if (updateBtnEmpty) {
            updateBtnEmpty.onclick = handleUpdate;
        }

        // Create list button
        const createListBtn = document.getElementById('create-list-btn');
        if (createListBtn) {
            createListBtn.onclick = handleCreateList;
        }

        // List type dropdown
        const newListType = document.getElementById('new-list-type');
        if (newListType) {
            newListType.onchange = handleListTypeChange;
            handleListTypeChange(); // Initialize visibility
        }

        // Simple form buttons
        const simpleCreateBtn = document.getElementById('simple-create-btn');
        if (simpleCreateBtn) {
            simpleCreateBtn.onclick = handleSimpleCreateList;
        }
        const cancelCreateBtn = document.getElementById('cancel-create-btn');
        if (cancelCreateBtn) {
            cancelCreateBtn.onclick = hideCreatePanel;
        }
        const closeCreateModal = document.getElementById('close-create-modal');
        if (closeCreateModal) {
            closeCreateModal.onclick = hideCreatePanel;
        }

        // Direct event listeners for create new list buttons
        const createNewListBtn = document.getElementById('create-new-list');
        const createNewListEmptyBtn = document.getElementById('create-new-list-empty');

        if (createNewListBtn) {
            console.log('Found create-new-list button, adding listener');
            createNewListBtn.onclick = function(e) {
                e.preventDefault();
                console.log('Direct click on create-new-list');
                showCreatePanel();
            };
        }

        if (createNewListEmptyBtn) {
            console.log('Found create-new-list-empty button, adding listener');
            createNewListEmptyBtn.onclick = function(e) {
                e.preventDefault();
                console.log('Direct click on create-new-list-empty');
                showCreatePanel();
            };
        }

        // Delegated event listeners for dynamic content
        document.addEventListener('click', handleDelegatedClicks);
        document.addEventListener('input', handleDelegatedInputs);
        document.addEventListener('change', handleDelegatedInputs);  // Also listen for change events (checkboxes)
    }

    function handleDelegatedClicks(e) {
        console.log('Click detected on:', e.target);
        console.log('Closest create-new:', e.target.closest('.create-new'));

        // Generate reply button
        if (e.target.closest('.generate-reply-btn')) {
            e.preventDefault();
            console.log('Generate reply button clicked');
            const btn = e.target.closest('.generate-reply-btn');
            if (btn.disabled) {
                console.log('Button is disabled, ignoring click');
                return;
            }

            btn.disabled = true;
            const tweetElement = btn.closest('.tweet-opportunity');
            console.log('Tweet element found:', tweetElement);
            generateReply(tweetElement).finally(() => {
                btn.disabled = false;
            });
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

        // Handle brand voice checkbox changes
        if (e.target.classList.contains('brand-voice-checkbox')) {
            const toggle = e.target.closest('.brand-voice-toggle');

            // If the toggle is disabled, prevent the change
            if (toggle && toggle.classList.contains('disabled')) {
                e.preventDefault();
                e.stopPropagation();
                console.log('Brand voice checkbox change prevented - toggle is disabled');
                e.target.checked = !e.target.checked; // Revert the change
                return false;
            }

            if (toggle && !toggle.classList.contains('disabled')) {
                // Allow the checkbox to toggle normally
                console.log('Brand voice toggled:', e.target.checked);
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
    }

    function setupMainDropdown() {
        const dropdownTriggers = ['list-dropdown-trigger', 'list-dropdown-trigger-empty'];

        dropdownTriggers.forEach(triggerId => {
            const dropdownTrigger = document.getElementById(triggerId);
            if (!dropdownTrigger) return;

            const menuId = triggerId === 'list-dropdown-trigger' ? 'list-dropdown-menu' : 'list-dropdown-menu-empty';
            const dropdownMenu = document.getElementById(menuId);

            // Remove old listener if exists
            dropdownTrigger.replaceWith(dropdownTrigger.cloneNode(true));
            const newTrigger = document.getElementById(triggerId);

            newTrigger.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleMainDropdown(triggerId, menuId);
            });
        });

        // Use event delegation for dropdown options
        document.addEventListener('click', (e) => {
            const option = e.target.closest('.dropdown-option:not(.create-new)');
            if (option && (option.closest('#list-dropdown-menu') || option.closest('#list-dropdown-menu-empty'))) {
                selectListOption(option);
                return;
            }

            // Close on outside click
            if (!e.target.closest('.dropdown')) {
                closeDropdowns();
            }
        }, true);
    }

    function toggleMainDropdown(triggerId, menuId) {
        const dropdownTrigger = document.getElementById(triggerId);
        const dropdownMenu = document.getElementById(menuId);

        // Close other dropdown
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

        // Close reply style dropdowns too
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

        console.log('List selected:', {
            listId: state.selectedList,
            listType: state.selectedListType,
            optionElement: option
        });

        // Update both dropdown texts
        const selectedListText = document.getElementById('selected-list-text');
        const selectedListTextEmpty = document.getElementById('selected-list-text-empty');
        // Get text content directly from option (text is no longer wrapped in span)
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

        // Close other reply style dropdowns
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
        // Handle both regular and empty state update buttons
        const updateButtonContainer = document.getElementById('update-button-container');
        const updateBtn = document.getElementById('update-btn');
        const updateButtonContainerEmpty = document.getElementById('update-button-container-empty');
        const updateBtnEmpty = document.getElementById('update-btn-empty');

        console.log('Update button visibility check:', {
            selectedListType: state.selectedListType,
            selectedList: state.selectedList,
            regularContainerExists: !!updateButtonContainer,
            regularButtonExists: !!updateBtn,
            emptyContainerExists: !!updateButtonContainerEmpty,
            emptyButtonExists: !!updateBtnEmpty
        });

        if (state.selectedListType === 'custom' && state.selectedList) {
            // Show the appropriate update button
            if (updateButtonContainer) {
                updateButtonContainer.style.display = 'block';
                console.log('Showing regular update button for custom list');
            }
            if (updateButtonContainerEmpty) {
                updateButtonContainerEmpty.style.display = 'block';
                console.log('Showing empty state update button for custom list');
            }

            const isUpdating = state.selectedList in state.ongoingUpdates;

            // Update both buttons if they exist
            [updateBtn, updateBtnEmpty].forEach(btn => {
                if (btn) {
                    if (isUpdating) {
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
            // Hide both update buttons
            if (updateButtonContainer) {
                updateButtonContainer.style.display = 'none';
                console.log('Hiding regular update button - not a custom list');
            }
            if (updateButtonContainerEmpty) {
                updateButtonContainerEmpty.style.display = 'none';
                console.log('Hiding empty state update button - not a custom list');
            }
        }
    }

    function selectList() {
        if (!state.selectedList) return;

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

                if (data.has_analysis && data.opportunities_count > 0) {
                    showToast(`Found ${data.opportunities_count} opportunities! Refreshing...`, 'success');
                    setTimeout(() => window.location.reload(), 1000);
                } else if (state.selectedListType === 'default') {
                    showToast('Loading default list analysis...', 'info');
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    const emptyMessage = document.getElementById('empty-message');
                    if (emptyMessage) {
                        emptyMessage.textContent = data.is_updating ?
                            'Update in progress for this list...' :
                            'Click "Update" to analyze this custom list.';
                    }
                }
            } else {
                showToast('Error selecting list: ' + data.error, 'error');
            }
        })
        .catch(error => {
            showToast('Network error selecting list', 'error');
        });
    }

    function handleUpdate() {
        if (!state.selectedList || state.selectedListType !== 'custom') {
            return;
        }

        if (state.selectedList in state.ongoingUpdates) {
            showToast('Update already in progress for this list', 'warning');
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
            delete state.ongoingUpdates[state.selectedList];
            saveOngoingUpdates();

            if (data.success) {
                showToast('Analysis completed! Refreshing page...', 'success');
                setTimeout(() => window.location.reload(), 1500);
            } else {
                if (data.is_updating) {
                    state.ongoingUpdates[state.selectedList] = {
                        status: 'running',
                        timestamp: Date.now()
                    };
                    saveOngoingUpdates();
                    showToast('Update already in progress for this list', 'warning');
                } else {
                    showToast('Analysis failed: ' + data.error, 'error');
                }
                updateButtonVisibility();
            }
        })
        .catch(error => {
            delete state.ongoingUpdates[state.selectedList];
            saveOngoingUpdates();
            showToast('Network error during analysis', 'error');
            updateButtonVisibility();
        });
    }

    // Reply Functions
    function generateReply(tweetElement) {
        console.log('generateReply function called with:', tweetElement);
        if (!tweetElement) {
            console.log('No tweet element provided');
            return Promise.resolve();
        }

        const tweetId = tweetElement.getAttribute('data-tweet-id');
        console.log('Tweet ID:', tweetId);
        const tweetTextElement = tweetElement.querySelector('.tweet-text');

        let tweetText = tweetTextElement ? tweetTextElement.innerHTML : '';
        tweetText = tweetText.replace(/<br\s*\/?>/gi, '\n').trim();
        tweetText = tweetText.replace(/<[^>]*>/g, '');
        console.log('Tweet text:', tweetText);

        const authorElement = tweetElement.querySelector('.tweet-author-username');
        const author = authorElement ? authorElement.textContent.replace('@', '') : '';
        const style = getSelectedStyle(tweetElement);
        const useBrandVoice = getBrandVoiceState(tweetElement);
        console.log('Author:', author, 'Style:', style, 'Brand voice:', useBrandVoice);

        const textarea = tweetElement.querySelector('.reply-textarea');
        const generateBtn = tweetElement.querySelector('.generate-reply-btn');

        if (generateBtn) {
            generateBtn.innerHTML = '<div class="loading-spinner"></div>';
            generateBtn.disabled = true;
            generateBtn.classList.add('loading');
        }
        if (textarea) {
            textarea.value = 'Generating reply...';
        }

        console.log('Making API request to generate reply...');
        return fetch('/reply-guy/generate-reply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tweet_text: tweetText,
                author: author,
                style: style,
                use_brand_voice: useBrandVoice
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (textarea) {
                    textarea.value = data.reply;
                    updateCharacterCount(textarea);
                }
                showToast('Reply generated successfully!', 'success');
            } else {
                if (textarea) {
                    textarea.value = data.credits_required ?
                        'Insufficient credits to generate reply.' :
                        'Error generating reply: ' + data.error;
                }
                showToast(data.credits_required ?
                    'Insufficient credits. Please purchase more credits.' :
                    'Error generating reply', 'error');
            }
        })
        .catch(error => {
            if (textarea) {
                textarea.value = 'Network error generating reply.';
            }
            showToast('Network error', 'error');
        })
        .finally(() => {
            if (generateBtn) {
                generateBtn.innerHTML = '<i class="ph ph-sparkle"></i>';
                generateBtn.disabled = false;
                generateBtn.classList.remove('loading');
            }
        });
    }

    function getSelectedStyle(tweetElement) {
        const styleDropdown = tweetElement.querySelector('.dropdown');
        const selectedOption = styleDropdown ? styleDropdown.querySelector('.reply-style-option.selected') : null;
        return selectedOption ? selectedOption.getAttribute('data-value') : 'supportive';
    }

    function getBrandVoiceState(tweetElement) {
        // Check global brand voice toggle first
        const globalCheckbox = document.getElementById('global-brand-voice');
        if (globalCheckbox && !globalCheckbox.disabled) {
            return globalCheckbox.checked;
        }

        // Fallback to individual checkbox (legacy)
        const checkbox = tweetElement.querySelector('.brand-voice-checkbox');
        return checkbox ? checkbox.checked : false;
    }

    function postReply(tweetElement) {
        if (!tweetElement) return;

        const tweetId = tweetElement.getAttribute('data-tweet-id');
        const textarea = tweetElement.querySelector('.reply-textarea');
        const replyText = textarea ? textarea.value.trim() : '';

        if (!replyText || replyText.includes('Error') || replyText.includes('Generating')) {
            showToast('Please generate a valid reply first', 'error');
            return;
        }

        if (replyText.length > 280) {
            showToast('Reply exceeds 280 characters', 'error');
            return;
        }

        const tweetUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(replyText)}&in_reply_to=${tweetId}`;

        // Open window
        window.open(tweetUrl, '_blank', 'noopener,noreferrer');

        // Log the reply
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
                showToast('Reply logged successfully!', 'success');
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

            // Update progress text with motivation
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
            showToast('Please enter a list name', 'error');
            return;
        }

        if (type === 'x_list' && !xListId) {
            showToast('Please enter an X List ID', 'error');
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
                showToast('List created successfully!', 'success');

                // Clear form
                if (nameInput) nameInput.value = '';
                if (xListIdInput) xListIdInput.value = '';

                // Reload page to show new list
                setTimeout(() => window.location.reload(), 1000);
            } else {
                showToast('Error creating list: ' + data.error, 'error');
            }
        })
        .catch(error => {
            hideLoading();
            showToast('Network error creating list', 'error');
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
                showToast(`List refreshed! Found ${data.account_count} accounts.`, 'success');
                setTimeout(() => window.location.reload(), 1000);
            } else {
                showToast('Error refreshing list: ' + data.error, 'error');
            }
        })
        .catch(error => {
            hideLoading();
            showToast('Network error refreshing list', 'error');
        });
    }

    // Modal functions
    function setupModals() {
        // Edit modal handlers
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

        // Delete modal handlers
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

        // Close on outside click
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
                showToast('Error loading list details: ' + data.error, 'error');
            }
        })
        .catch(error => {
            showToast('Network error loading list details', 'error');
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
                showToast('Error removing account: ' + data.error, 'error');
            }
        });
    }

    function addAccountToList() {
        const newAccountInput = document.getElementById('new-account-input');
        const account = newAccountInput ? newAccountInput.value.trim() : '';

        if (!account) {
            showToast('Please enter an account name', 'error');
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

                showToast('Account added successfully', 'success');
            } else {
                showToast('Error adding account: ' + data.error, 'error');
            }
        })
        .catch(error => {
            showToast('Network error adding account', 'error');
        });
    }

    function saveEditChanges() {
        const editListName = document.getElementById('edit-list-name');
        const newName = editListName ? editListName.value.trim() : '';

        if (!newName) {
            showToast('Please enter a list name', 'error');
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
                showToast('List updated successfully!', 'success');
                hideModal('edit-list-modal');
                setTimeout(() => window.location.reload(), 1000);
            } else {
                showToast('Error updating list: ' + data.error, 'error');
            }
        })
        .catch(error => {
            showToast('Network error updating list', 'error');
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
                showToast('List deleted successfully!', 'success');
                hideModal('delete-modal');
                setTimeout(() => window.location.reload(), 1000);
            } else {
                showToast('Error deleting list: ' + data.error, 'error');
            }
        })
        .catch(error => {
            showToast('Network error deleting list', 'error');
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

    function showToast(message, type = 'info') {
        // Remove existing toast
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

        // Show toast
        setTimeout(() => toast.classList.add('show'), 100);

        // Hide toast
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // Functions for managing create list panel
    function showCreatePanel() {
        const modal = document.getElementById('create-list-modal');
        if (modal) {
            modal.classList.add('show');
        }
    }

    function hideCreatePanel() {
        const modal = document.getElementById('create-list-modal');
        if (modal) {
            modal.classList.remove('show');
        }
        // Clear form
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
            showToast('Please enter a list name', 'error');
            return;
        }

        if (!xListId) {
            showToast('Please enter an X List ID', 'error');
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
                // Don't hide loading yet - we're going to run analysis
                showLoading('Running analysis...', 'Finding reply opportunities in your new list...');
                hideCreatePanel();

                // Auto-run analysis on the newly created list
                const listId = data.list.id;
                fetch('/reply-guy/run-analysis', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        list_id: listId,
                        list_type: 'custom',
                        time_range: '24h'
                    })
                })
                .then(response => response.json())
                .then(analysisData => {
                    hideLoading();
                    if (analysisData.success) {
                        showToast('List created and analyzed successfully!', 'success');
                        // Reload to show the new list and its opportunities
                        setTimeout(() => window.location.reload(), 1000);
                    } else {
                        showToast('List created but analysis failed: ' + analysisData.error, 'warning');
                        setTimeout(() => window.location.reload(), 1000);
                    }
                })
                .catch(analysisError => {
                    hideLoading();
                    showToast('List created but analysis failed', 'warning');
                    console.error('Analysis error:', analysisError);
                    setTimeout(() => window.location.reload(), 1000);
                });
            } else {
                hideLoading();
                showToast('Error creating list: ' + data.error, 'error');
            }
        })
        .catch(error => {
            hideLoading();
            showToast('Network error creating list', 'error');
            console.error('Error:', error);
        });
    }

    // Enhanced profile picture consistency handler
    function fixProfilePictureConsistency() {
        const profileMap = new Map();
        const authorNameMap = new Map(); // Track author screen names

        console.log('Starting profile picture consistency fix...');

        // First pass: collect all profile pictures and author data
        document.querySelectorAll('.tweet-opportunity').forEach(tweet => {
            const authorNameEl = tweet.querySelector('.tweet-author-name');
            const authorUsernameEl = tweet.querySelector('.tweet-author-username');
            const img = tweet.querySelector('.tweet-avatar img');

            if (authorNameEl && authorUsernameEl) {
                const displayName = authorNameEl.textContent.trim();
                const username = authorUsernameEl.textContent.replace('@', '').trim();

                // Store mapping between username and display name
                authorNameMap.set(username, displayName);

                if (img && img.src && !img.src.includes('data:') && img.src !== window.location.href) {
                    const profileUrl = img.src;
                    if (!profileMap.has(username) && profileUrl) {
                        profileMap.set(username, profileUrl);
                        console.log(`Stored profile for @${username}:`, profileUrl);
                    }
                }
            }
        });

        console.log(`Found ${profileMap.size} unique profiles`);

        // Second pass: apply consistent profiles and fix missing ones
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
                        // If we have a stored profile URL and the current image is missing/broken
                        if (storedProfileUrl && (!img.src || img.src === window.location.href || img.src.includes('data:'))) {
                            console.log(`Fixing profile for @${username}`);
                            img.src = storedProfileUrl;
                        }

                        // Enhanced image loading handlers
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
                                // Try to generate a better fallback
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

                        // Trigger a recheck if the image seems broken
                        if (img.naturalWidth === 0 && img.complete) {
                            img.onerror();
                        }
                    } else if (!img && fallback) {
                        // No image element at all, just show fallback
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

        console.log('Profile picture consistency fix completed');
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    // Fix profile pictures after content loads - single deferred call
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(fixProfilePictureConsistency, 1000);
    });

    // Also run when new content might be loaded
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        return originalFetch.apply(this, args).then(response => {
            // Run profile fix after any fetch that might load new content
            if (args[0] && (args[0].includes('reply-guy') || args[0].includes('analysis'))) {
                setTimeout(fixProfilePictureConsistency, 1000);
            }
            return response;
        });
    };

    // Debug: Test if buttons are clickable after page load
    setTimeout(() => {
        const generateBtns = document.querySelectorAll('.generate-reply-btn');
        const tweetOpportunities = document.querySelectorAll('.tweet-opportunity');
        const repliesPanel = document.getElementById('replies-panel');
        const emptyState = document.querySelector('.empty-state');

        console.log('=== DEBUG INFO ===');
        console.log('Found generate buttons:', generateBtns.length);
        console.log('Found tweet opportunities:', tweetOpportunities.length);
        console.log('Replies panel visible:', repliesPanel ? !repliesPanel.classList.contains('hidden') : 'not found');
        console.log('Empty state visible:', emptyState ? emptyState.style.display !== 'none' : 'not found');
        console.log('Current selected list:', state.selectedList);

        generateBtns.forEach((btn, index) => {
            console.log(`Button ${index}:`, btn, 'Disabled:', btn.disabled);
            // Test if button is actually clickable
            btn.addEventListener('click', () => {
                console.log(`Direct click on button ${index} detected!`);
            });
        });

        if (generateBtns.length === 0) {
            console.log('❌ No generate buttons found - you may need to select a list first');
        }
    }, 2000);

    // Format tweet timestamps
    function formatTimestamp(dateString) {
        try {
            const tweetDate = new Date(dateString);
            const now = new Date();
            const diffMs = now - tweetDate;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);

            if (diffMins < 1) return 'now';
            if (diffMins < 60) return `${diffMins}m`;
            if (diffHours < 24) return `${diffHours}h`;
            if (diffDays < 7) return `${diffDays}d`;

            // Format as date for older tweets
            return tweetDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        } catch (e) {
            return '';
        }
    }

    // Update all timestamps on page
    function updateTimestamps() {
        const timestamps = document.querySelectorAll('.tweet-timestamp');
        timestamps.forEach(el => {
            const timestamp = el.getAttribute('data-timestamp');
            if (timestamp) {
                el.textContent = formatTimestamp(timestamp);
            }
        });
    }

    // Update timestamps immediately and every minute
    updateTimestamps();
    setInterval(updateTimestamps, 60000);

    // Pagination: Load More functionality with API
    const loadMoreBtn = document.getElementById('load-more-btn');
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', async function() {
            const listId = this.getAttribute('data-list-id');
            const listType = this.getAttribute('data-list-type');
            const loaded = parseInt(this.getAttribute('data-loaded'));
            const total = parseInt(this.getAttribute('data-total'));

            // Disable button while loading
            this.disabled = true;
            this.innerHTML = '<i class="ph ph-spinner"></i> Loading...';

            try {
                const response = await fetch('/reply_guy/get-more-tweets', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        list_id: listId,
                        list_type: listType,
                        offset: loaded,
                        limit: 100
                    })
                });

                const data = await response.json();

                if (data.success && data.tweets) {
                    const container = document.getElementById('tweets-container');

                    // Render new tweets
                    data.tweets.forEach(tweet => {
                        const tweetHtml = renderTweetCard(tweet);
                        container.insertAdjacentHTML('beforeend', tweetHtml);
                    });

                    // Update loaded count
                    const newLoaded = loaded + data.tweets.length;
                    this.setAttribute('data-loaded', newLoaded);

                    // Update timestamps for new tweets
                    updateTimestamps();

                    // Check if more to load
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

    // Helper function to render tweet card HTML
    function renderTweetCard(tweet) {
        // This is a simplified version - you may need to match your exact template structure
        return `
            <div class="tweet-opportunity" data-tweet-id="${tweet.tweet_id}">
                <div class="tweet-grid">
                    <!-- Add full tweet HTML structure here -->
                </div>
            </div>
        `;
    }

})();