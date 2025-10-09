// Content Wiki Application
const WikiApp = (function() {
    // State
    let currentPageId = null;
    let pages = [];
    let categories = [];
    let autoSaveTimer = null;
    let isEditing = false;
    let currentAttachments = [];
    let searchDebounceTimer = null;
    
    // Initialize
    function init() {
        console.log('Initializing Content Wiki...');
        loadCategories();
        loadPages();
        setupEventListeners();
        setupEditor();
    }

    // Setup event listeners
    function setupEventListeners() {
        // Page title auto-save
        const titleInput = document.getElementById('pageTitle');
        if (titleInput) {
            titleInput.addEventListener('input', handleContentChange);
        }

        // Category and tags change
        const categorySelect = document.getElementById('pageCategory');
        const tagsInput = document.getElementById('pageTags');
        if (categorySelect) {
            categorySelect.addEventListener('change', handleContentChange);
        }
        if (tagsInput) {
            tagsInput.addEventListener('input', handleContentChange);
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            // Ctrl/Cmd + S to save
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                if (currentPageId) savePage();
            }

            // Ctrl/Cmd + N for new page
            if ((e.ctrlKey || e.metaKey) && e.key === 'n' && !e.shiftKey) {
                e.preventDefault();
                createNewPage();
            }
        });
    }

    // Setup editor
    function setupEditor() {
        const editor = document.getElementById('wikiEditor');
        if (!editor) return;

        // Handle paste to preserve formatting
        editor.addEventListener('paste', function(e) {
            e.preventDefault();
            const html = (e.clipboardData || window.clipboardData).getData('text/html');
            const text = (e.clipboardData || window.clipboardData).getData('text/plain');

            if (html) {
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = html;
                
                // Remove scripts and styles
                tempDiv.querySelectorAll('script, style').forEach(el => el.remove());
                
                document.execCommand('insertHTML', false, tempDiv.innerHTML);
            } else {
                document.execCommand('insertText', false, text);
            }
        });

        // Auto-save on content change
        editor.addEventListener('input', handleContentChange);

        // Handle link clicks
        editor.addEventListener('click', function(e) {
            if (e.target.tagName === 'A' && e.target.href) {
                e.preventDefault();
                e.stopPropagation();
                window.open(e.target.href, e.target.target || '_blank');
            }
        });
    }

    // Load categories
    function loadCategories() {
        const categoriesList = document.getElementById('categoriesList');
        const categorySelect = document.getElementById('pageCategory');
        
        // Default categories
        categories = [
            { id: 'brand', name: 'Brand Guidelines', icon: '🎨', color: '#8B5CF6', count: 0 },
            { id: 'content', name: 'Content Standards', icon: '📝', color: '#3B82F6', count: 0 },
            { id: 'visual', name: 'Visual Assets', icon: '🖼️', color: '#EC4899', count: 0 },
            { id: 'templates', name: 'Templates', icon: '📋', color: '#F59E0B', count: 0 },
            { id: 'processes', name: 'Processes', icon: '⚙️', color: '#10B981', count: 0 },
            { id: 'team', name: 'Team Resources', icon: '👥', color: '#06B6D4', count: 0 },
            { id: 'legal', name: 'Legal & Compliance', icon: '⚖️', color: '#EF4444', count: 0 },
            { id: 'reference', name: 'Reference Materials', icon: '📚', color: '#84CC16', count: 0 }
        ];

        if (categoriesList) {
            categoriesList.innerHTML = categories.map(cat => `
                <div class="category-item" data-category="${cat.id}" onclick="WikiApp.filterByCategory('${cat.id}')">
                    <span class="category-icon">${cat.icon}</span>
                    <span class="category-name">${cat.name}</span>
                    <span class="category-count">${cat.count}</span>
                </div>
            `).join('');
        }

        if (categorySelect) {
            categorySelect.innerHTML = categories.map(cat => 
                `<option value="${cat.id}">${cat.icon} ${cat.name}</option>`
            ).join('');
        }
    }

    // Load pages
    async function loadPages(category = null) {
        try {
            let url = '/api/content-wiki/pages';
            if (category) {
                url += `?category=${category}`;
            }

            const response = await fetch(url);
            const data = await response.json();

            if (data.success) {
                pages = data.pages || [];
                displayPages(pages);
                updateCategoryCounts();
                
                // Show pinned section if there are pinned pages
                const pinnedPages = pages.filter(p => p.is_pinned);
                if (pinnedPages.length > 0) {
                    displayPinnedPages(pinnedPages);
                }
            }
        } catch (error) {
            console.error('Error loading pages:', error);
            showToast('Failed to load pages', 'error');
        }
    }

    // Display pages
    function displayPages(pagesToShow) {
        const pagesList = document.getElementById('pagesList');
        const pagesCount = document.getElementById('pagesCount');
        
        if (pagesCount) {
            pagesCount.textContent = pagesToShow.length;
        }

        if (!pagesList) return;

        if (pagesToShow.length === 0) {
            pagesList.innerHTML = `
                <div style="text-align: center; padding: 2rem; color: var(--text-tertiary);">
                    <i class="ph ph-file-dashed" style="font-size: 2rem; margin-bottom: 0.5rem; display: block;"></i>
                    <p style="font-size: 0.875rem;">No pages yet</p>
                </div>
            `;
            return;
        }

        pagesList.innerHTML = pagesToShow.map(page => {
            const isPinned = page.is_pinned ? '<i class="ph ph-push-pin"></i>' : '';
            const date = formatDate(new Date(page.updated_at));
            
            return `
                <div class="page-item ${page.id === currentPageId ? 'active' : ''} ${page.is_pinned ? 'pinned' : ''}"
                     data-page-id="${page.id}"
                     onclick="WikiApp.selectPage('${page.id}')">
                    <div class="page-item-title">
                        ${isPinned}
                        <span>${escapeHtml(page.title || 'Untitled')}</span>
                    </div>
                    <div class="page-item-meta">
                        ${getCategoryIcon(page.category)} • ${date}
                    </div>
                </div>
            `;
        }).join('');
    }

    // Display pinned pages
    function displayPinnedPages(pinnedPages) {
        const pinnedSection = document.getElementById('pinnedSection');
        const pinnedList = document.getElementById('pinnedList');
        
        if (!pinnedSection || !pinnedList) return;

        if (pinnedPages.length > 0) {
            pinnedSection.style.display = 'block';
            pinnedList.innerHTML = pinnedPages.map(page => `
                <div class="pinned-item" onclick="WikiApp.selectPage('${page.id}')">
                    <i class="ph ph-push-pin"></i>
                    <span>${escapeHtml(page.title)}</span>
                </div>
            `).join('');
        } else {
            pinnedSection.style.display = 'none';
        }
    }

    // Update category counts
    function updateCategoryCounts() {
        // Reset counts
        categories.forEach(cat => cat.count = 0);
        
        // Count pages per category
        pages.forEach(page => {
            const cat = categories.find(c => c.id === page.category);
            if (cat) cat.count++;
        });

        // Update UI
        document.querySelectorAll('.category-item').forEach(item => {
            const categoryId = item.getAttribute('data-category');
            const cat = categories.find(c => c.id === categoryId);
            if (cat) {
                const countEl = item.querySelector('.category-count');
                if (countEl) countEl.textContent = cat.count;
            }
        });
    }

    // Create new page
    async function createNewPage(templateId = null) {
        try {
            let pageData = {
                title: 'New Page',
                content: '',
                category: 'brand',
                tags: []
            };

            // Load template if specified
            if (templateId) {
                const template = await loadTemplate(templateId);
                if (template) {
                    pageData = {
                        title: template.title,
                        content: template.content,
                        category: template.category || 'brand',
                        tags: template.tags || []
                    };
                }
            }

            const response = await fetch('/api/content-wiki/pages', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(pageData)
            });

            const data = await response.json();

            if (data.success && data.page) {
                currentPageId = data.page.id;
                pages.unshift(data.page);
                displayPages(pages);
                selectPage(data.page.id);
                showToast('Page created successfully', 'success');
            }
        } catch (error) {
            console.error('Error creating page:', error);
            showToast('Failed to create page', 'error');
        }
    }

    // Create from template
    async function createFromTemplate(templateId) {
        createNewPage(templateId);
    }

    // Load template
    async function loadTemplate(templateId) {
        // For system templates, return hardcoded content
        const systemTemplates = {
            'brand-guidelines': {
                title: 'Brand Guidelines',
                category: 'brand',
                content: `
                    <h2>Brand Identity</h2>
                    <h3>Mission Statement</h3>
                    <p>[Your mission statement here]</p>
                    
                    <h3>Brand Values</h3>
                    <ul>
                        <li>Value 1: [Description]</li>
                        <li>Value 2: [Description]</li>
                        <li>Value 3: [Description]</li>
                    </ul>
                    
                    <h2>Visual Identity</h2>
                    <h3>Logo Usage</h3>
                    <p>[Logo guidelines and rules]</p>
                    
                    <h3>Color Palette</h3>
                    <ul>
                        <li>Primary Color: #[HEX]</li>
                        <li>Secondary Color: #[HEX]</li>
                        <li>Accent Color: #[HEX]</li>
                    </ul>
                    
                    <h3>Typography</h3>
                    <p>Primary Font: [Font Name]</p>
                    <p>Secondary Font: [Font Name]</p>
                    
                    <h2>Voice & Tone</h2>
                    <p>[Brand voice description]</p>
                `
            },
            'content-standards': {
                title: 'Content Standards',
                category: 'content',
                content: `
                    <h2>Content Guidelines</h2>
                    
                    <h3>Writing Style</h3>
                    <ul>
                        <li>Tone: [Professional/Casual/Friendly]</li>
                        <li>Voice: [First person/Third person]</li>
                        <li>Language: [Simple/Technical]</li>
                    </ul>
                    
                    <h3>Video Standards</h3>
                    <ul>
                        <li>Resolution: [1080p/4K]</li>
                        <li>Frame Rate: [24/30/60 fps]</li>
                        <li>Aspect Ratio: [16:9/9:16]</li>
                        <li>Duration: [Target length]</li>
                    </ul>
                    
                    <h3>Thumbnail Guidelines</h3>
                    <ul>
                        <li>Dimensions: 1280x720px</li>
                        <li>File Format: JPG/PNG</li>
                        <li>Text Size: [Minimum size]</li>
                    </ul>
                `
            },
            'editor-letter': {
                title: 'Letter to Editors',
                category: 'team',
                content: `
                    <h2>Letter to Video Editors</h2>
                    
                    <h3>Project Overview</h3>
                    <p>[Brief description of your content and channel]</p>
                    
                    <h3>Editing Style Guidelines</h3>
                    <ul>
                        <li>Pacing: [Fast/Medium/Slow]</li>
                        <li>Transitions: [Types to use]</li>
                        <li>Music: [Style preferences]</li>
                        <li>Effects: [Guidelines for effects usage]</li>
                    </ul>
                    
                    <h3>Brand Elements to Include</h3>
                    <ul>
                        <li>Intro: [Description]</li>
                        <li>Outro: [Description]</li>
                        <li>Lower Thirds: [Style guide]</li>
                        <li>Watermark: [Position and opacity]</li>
                    </ul>
                `
            }
        };

        return systemTemplates[templateId] || null;
    }

    // Select page
    async function selectPage(pageId) {
        const page = pages.find(p => p.id === pageId);
        if (!page) return;

        currentPageId = pageId;
        isEditing = true;

        // Show editor
        document.getElementById('emptyState').style.display = 'none';
        document.getElementById('pageEditor').style.display = 'flex';

        // Update editor
        document.getElementById('pageTitle').value = page.title || '';
        document.getElementById('wikiEditor').innerHTML = page.content || '';
        document.getElementById('pageCategory').value = page.category || 'brand';
        document.getElementById('pageTags').value = (page.tags || []).join(', ');

        // Update pin button
        const pinBtn = document.getElementById('pinBtn');
        if (page.is_pinned) {
            pinBtn.classList.add('active');
        } else {
            pinBtn.classList.remove('active');
        }

        // Update page info
        document.getElementById('pageVersion').textContent = `v${page.version || 1}`;
        document.getElementById('lastEdited').textContent = formatDate(new Date(page.updated_at));

        // Update attachments
        if (page.attachments && page.attachments.length > 0) {
            currentAttachments = page.attachments;
            displayAttachments();
        } else {
            currentAttachments = [];
            document.getElementById('attachmentsSection').style.display = 'none';
        }

        // Update sidebar selection
        document.querySelectorAll('.page-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-page-id="${pageId}"]`)?.classList.add('active');

        updateSaveStatus('saved');
    }

    // Save page
    async function savePage(silent = false) {
        if (!currentPageId) return;

        const title = document.getElementById('pageTitle').value || 'Untitled';
        const content = document.getElementById('wikiEditor').innerHTML;
        const category = document.getElementById('pageCategory').value;
        const tagsValue = document.getElementById('pageTags').value;
        const tags = tagsValue ? tagsValue.split(',').map(t => t.trim()).filter(Boolean) : [];

        updateSaveStatus('saving');

        try {
            const response = await fetch(`/api/content-wiki/pages/${currentPageId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    title, 
                    content, 
                    category, 
                    tags,
                    attachments: currentAttachments
                })
            });

            const data = await response.json();

            if (data.success) {
                // Update local page
                const pageIndex = pages.findIndex(p => p.id === currentPageId);
                if (pageIndex !== -1 && data.page) {
                    pages[pageIndex] = data.page;
                    displayPages(pages);
                }

                updateSaveStatus('saved');
                
                if (!silent) {
                    showToast('Page saved', 'success');
                }
            } else {
                updateSaveStatus('error');
                if (!silent) {
                    showToast('Failed to save', 'error');
                }
            }
        } catch (error) {
            console.error('Error saving page:', error);
            updateSaveStatus('error');
            if (!silent) {
                showToast('Failed to save', 'error');
            }
        }
    }

    // Delete page
    async function deletePage() {
        if (!currentPageId) return;

        const page = pages.find(p => p.id === currentPageId);
        const pageTitle = page ? page.title : 'this page';

        if (!confirm(`Delete "${pageTitle}"? This cannot be undone.`)) return;

        try {
            const response = await fetch(`/api/content-wiki/pages/${currentPageId}`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                pages = pages.filter(p => p.id !== currentPageId);
                displayPages(pages);
                
                // Reset editor
                currentPageId = null;
                document.getElementById('pageEditor').style.display = 'none';
                document.getElementById('emptyState').style.display = 'flex';

                showToast('Page deleted', 'success');
            }
        } catch (error) {
            console.error('Error deleting page:', error);
            showToast('Failed to delete', 'error');
        }
    }

    // Duplicate page
    async function duplicatePage() {
        if (!currentPageId) return;

        try {
            const response = await fetch(`/api/content-wiki/pages/${currentPageId}/duplicate`, {
                method: 'POST'
            });

            const data = await response.json();

            if (data.success && data.page) {
                pages.unshift(data.page);
                displayPages(pages);
                selectPage(data.page.id);
                showToast('Page duplicated', 'success');
            }
        } catch (error) {
            console.error('Error duplicating page:', error);
            showToast('Failed to duplicate page', 'error');
        }
    }

    // Toggle page pin
    async function togglePagePin() {
        if (!currentPageId) return;

        const page = pages.find(p => p.id === currentPageId);
        if (!page) return;

        const newPinState = !page.is_pinned;

        try {
            const response = await fetch(`/api/content-wiki/pages/${currentPageId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_pinned: newPinState })
            });

            const data = await response.json();

            if (data.success) {
                page.is_pinned = newPinState;
                
                // Update UI
                const pinBtn = document.getElementById('pinBtn');
                if (newPinState) {
                    pinBtn.classList.add('active');
                } else {
                    pinBtn.classList.remove('active');
                }

                // Refresh pages list
                displayPages(pages);
                
                // Update pinned section
                const pinnedPages = pages.filter(p => p.is_pinned);
                displayPinnedPages(pinnedPages);

                showToast(newPinState ? 'Page pinned' : 'Page unpinned', 'success');
            }
        } catch (error) {
            console.error('Error toggling pin:', error);
            showToast('Failed to update pin', 'error');
        }
    }

    // Filter by category
    function filterByCategory(categoryId) {
        // Update UI
        document.querySelectorAll('.category-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-category="${categoryId}"]`)?.classList.add('active');

        // Update title
        const category = categories.find(c => c.id === categoryId);
        document.getElementById('pagesTitle').textContent = category ? category.name : 'All Pages';

        // Load filtered pages
        loadPages(categoryId);
    }

    // Show all pages
    function showAllPages() {
        // Update UI
        document.querySelectorAll('.category-item').forEach(item => {
            item.classList.remove('active');
        });
        document.getElementById('pagesTitle').textContent = 'All Pages';

        // Load all pages
        loadPages();
    }

    // Search pages
    function searchDebounced(query) {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => searchPages(query), 300);
    }

    async function searchPages(query) {
        if (!query) {
            loadPages();
            return;
        }

        try {
            const response = await fetch(`/api/content-wiki/search?q=${encodeURIComponent(query)}`);
            const data = await response.json();

            if (data.success) {
                const searchResults = data.results.map(r => r.page);
                displayPages(searchResults);
                document.getElementById('pagesTitle').textContent = 'Search Results';
            }
        } catch (error) {
            console.error('Error searching pages:', error);
        }
    }

    // Format text
    function formatText(command, value = null) {
        document.execCommand(command, false, value);
        document.getElementById('wikiEditor').focus();
    }

    // Insert link
    function insertLink() {
        const url = prompt('Enter URL:', 'https://');
        if (url && url !== 'https://') {
            document.execCommand('createLink', false, url);
        }
        document.getElementById('wikiEditor').focus();
    }

    // Insert image
    function insertImage() {
        document.getElementById('imageUpload').click();
    }

    // Handle image upload
    async function handleImageUpload(input) {
        const file = input.files[0];
        if (!file) return;

        // Validate file size
        if (file.size > 10 * 1024 * 1024) {
            showToast('Image too large. Maximum size is 10MB', 'error');
            return;
        }

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/api/content-wiki/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success && data.attachment) {
                // Insert image into editor
                const img = `<img src="${data.attachment.url}" alt="${data.attachment.filename}" style="max-width: 100%;">`;
                document.execCommand('insertHTML', false, img);
                
                showToast('Image uploaded', 'success');
            }
        } catch (error) {
            console.error('Error uploading image:', error);
            showToast('Failed to upload image', 'error');
        }

        // Clear input
        input.value = '';
    }

    // Upload attachment
    function uploadAttachment() {
        document.getElementById('fileUpload').click();
    }

    // Handle file upload
    async function handleFileUpload(input) {
        const file = input.files[0];
        if (!file) return;

        // Validate file size
        if (file.size > 10 * 1024 * 1024) {
            showToast('File too large. Maximum size is 10MB', 'error');
            return;
        }

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/api/content-wiki/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success && data.attachment) {
                // Add to current attachments
                currentAttachments.push(data.attachment);
                displayAttachments();
                
                // Auto-save
                handleContentChange();
                
                showToast('File uploaded', 'success');
            }
        } catch (error) {
            console.error('Error uploading file:', error);
            showToast('Failed to upload file', 'error');
        }

        // Clear input
        input.value = '';
    }

    // Display attachments
    function displayAttachments() {
        const section = document.getElementById('attachmentsSection');
        const list = document.getElementById('attachmentsList');
        
        if (!section || !list) return;

        if (currentAttachments.length > 0) {
            section.style.display = 'block';
            list.innerHTML = currentAttachments.map((att, index) => `
                <div class="attachment-item" data-index="${index}">
                    <i class="ph ph-file"></i>
                    <span class="attachment-name">${escapeHtml(att.filename)}</span>
                    <span class="attachment-size">${formatFileSize(att.size)}</span>
                    <button class="attachment-remove" onclick="WikiApp.removeAttachment(${index})">
                        <i class="ph ph-x"></i>
                    </button>
                </div>
            `).join('');
        } else {
            section.style.display = 'none';
        }
    }

    // Remove attachment
    function removeAttachment(index) {
        currentAttachments.splice(index, 1);
        displayAttachments();
        handleContentChange();
    }

    // Insert code block
    function insertCode() {
        const code = '<pre><code>// Your code here</code></pre>';
        document.execCommand('insertHTML', false, code);
        document.getElementById('wikiEditor').focus();
    }

    // Insert table
    function insertTable() {
        const table = `
            <table>
                <thead>
                    <tr>
                        <th>Column 1</th>
                        <th>Column 2</th>
                        <th>Column 3</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Data 1</td>
                        <td>Data 2</td>
                        <td>Data 3</td>
                    </tr>
                </tbody>
            </table>
        `;
        document.execCommand('insertHTML', false, table);
        document.getElementById('wikiEditor').focus();
    }

    // Insert callout
    function insertCallout(type) {
        const callout = `<div class="callout callout-${type}"><p>${type === 'info' ? 'Information' : 'Warning'}: Your text here</p></div>`;
        document.execCommand('insertHTML', false, callout);
        document.getElementById('wikiEditor').focus();
    }

    // Change text color
    function changeTextColor(color) {
        document.execCommand('foreColor', false, color);
        document.getElementById('wikiEditor').focus();
    }

    // Change background color
    function changeBgColor(color) {
        document.execCommand('hiliteColor', false, color);
        document.getElementById('wikiEditor').focus();
    }

    // Show page info
    function showPageInfo() {
        if (!currentPageId) return;

        const page = pages.find(p => p.id === currentPageId);
        if (!page) return;

        const modal = document.getElementById('pageInfoModal');
        const content = document.getElementById('pageInfoContent');
        
        content.innerHTML = `
            <div style="display: grid; gap: 1rem;">
                <div>
                    <strong>Title:</strong> ${escapeHtml(page.title)}
                </div>
                <div>
                    <strong>Category:</strong> ${getCategoryName(page.category)}
                </div>
                <div>
                    <strong>Tags:</strong> ${(page.tags || []).join(', ') || 'None'}
                </div>
                <div>
                    <strong>Created:</strong> ${formatFullDate(new Date(page.created_at))}
                </div>
                <div>
                    <strong>Last Updated:</strong> ${formatFullDate(new Date(page.updated_at))}
                </div>
                <div>
                    <strong>Version:</strong> ${page.version || 1}
                </div>
                <div>
                    <strong>Last Edited By:</strong> ${page.last_edited_by || 'Unknown'}
                </div>
                ${page.attachments && page.attachments.length > 0 ? `
                    <div>
                        <strong>Attachments:</strong> ${page.attachments.length} file(s)
                    </div>
                ` : ''}
            </div>
        `;
        
        modal.classList.add('active');
    }

    // Close page info
    function closePageInfo() {
        document.getElementById('pageInfoModal').classList.remove('active');
    }

    // Handle content change
    function handleContentChange() {
        if (!currentPageId) return;

        clearTimeout(autoSaveTimer);
        updateSaveStatus('typing');

        autoSaveTimer = setTimeout(() => {
            savePage(true);
        }, 1000);
    }

    // Update save status
    function updateSaveStatus(status) {
        const statusEl = document.getElementById('saveStatus');
        if (!statusEl) return;

        const statusText = statusEl.querySelector('span');
        const statusIcon = statusEl.querySelector('i');

        statusEl.className = 'save-status ' + status;

        switch(status) {
            case 'typing':
                statusIcon.className = 'ph ph-circle';
                statusText.textContent = 'Typing...';
                break;
            case 'saving':
                statusIcon.className = 'ph ph-circle-notch';
                statusText.textContent = 'Saving...';
                break;
            case 'saved':
                statusIcon.className = 'ph ph-check-circle';
                statusText.textContent = 'Saved';
                break;
            case 'error':
                statusIcon.className = 'ph ph-warning-circle';
                statusText.textContent = 'Error';
                break;
        }
    }

    // Utility functions
    function getCategoryIcon(categoryId) {
        const cat = categories.find(c => c.id === categoryId);
        return cat ? cat.icon : '📄';
    }

    function getCategoryName(categoryId) {
        const cat = categories.find(c => c.id === categoryId);
        return cat ? `${cat.icon} ${cat.name}` : categoryId;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    function formatDate(date) {
        const now = new Date();
        const diff = now - date;
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        
        if (seconds < 60) return 'Just now';
        if (minutes < 60) return `${minutes}m ago`;
        if (hours < 24) return `${hours}h ago`;
        if (days < 7) return `${days}d ago`;
        
        return date.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric'
        });
    }

    function formatFullDate(date) {
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    function showToast(message, type = 'success') {
        // Use the base template's toast function if available
        if (window.showToast) {
            window.showToast(message, type);
        } else {
            console.log(`Toast: ${type} - ${message}`);
        }
    }

    // Public API
    return {
        init,
        createNewPage,
        createFromTemplate,
        selectPage,
        savePage,
        deletePage,
        duplicatePage,
        togglePagePin,
        filterByCategory,
        showAllPages,
        searchDebounced,
        formatText,
        insertLink,
        insertImage,
        handleImageUpload,
        uploadAttachment,
        handleFileUpload,
        removeAttachment,
        insertCode,
        insertTable,
        insertCallout,
        changeTextColor,
        changeBgColor,
        showPageInfo,
        closePageInfo
    };
})();

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    WikiApp.init();
});