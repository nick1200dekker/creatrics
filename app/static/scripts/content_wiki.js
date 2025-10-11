// Content Wiki Application - Grid-based Category System
const WikiApp = (function() {
    // State
    let currentCategory = null;
    let currentDocumentId = null;
    let currentContent = [];
    let categories = [];
    let autoSaveTimer = null;
    let viewMode = 'grid';
    let filterMode = 'all';
    let searchDebounceTimer = null;
    
    // Initialize
    function init() {
        console.log('Initializing Content Wiki...');
        loadCategories();
        setupEventListeners();
        showOverview();
    }

    // Setup event listeners
    function setupEventListeners() {
        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            // Ctrl/Cmd + S to save
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                if (currentDocumentId) saveDocument();
            }

            // Escape to go back
            if (e.key === 'Escape') {
                if (currentDocumentId) {
                    closeEditor();
                } else if (currentCategory) {
                    showOverview();
                }
            }
        });

        // Document title auto-save
        const titleInput = document.getElementById('documentTitle');
        if (titleInput) {
            titleInput.addEventListener('input', handleContentChange);
        }

        // Setup editor
        const editor = document.getElementById('wikiEditor');
        if (editor) {
            setupEditor(editor);
        }
    }

    // Setup editor
    function setupEditor(editor) {
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
    async function loadCategories() {
        try {
            const response = await fetch('/api/content-wiki/pages');
            const data = await response.json();

            if (data.success) {
                // Get preset categories
                categories = data.categories || [];
                
                // Count content per category
                const pages = data.pages || [];
                categories.forEach(cat => {
                    cat.documentCount = pages.filter(p => p.category === cat.id && !p.is_file).length;
                    cat.fileCount = pages.filter(p => p.category === cat.id && p.is_file).length;
                });

                displayCategories();
                updateStats(pages);
            }
        } catch (error) {
            console.error('Error loading categories:', error);
            showToast('Failed to load categories', 'error');
        }
    }

    // Display categories in sidebar
    function displayCategories() {
        const categoriesList = document.getElementById('categoriesList');
        if (!categoriesList) return;

        categoriesList.innerHTML = categories.map(cat => `
            <div class="category-item ${cat.id === currentCategory ? 'active' : ''}" 
                 data-category="${cat.id}"
                 onclick="WikiApp.openCategory('${cat.id}')">
                <span class="category-icon">${cat.icon}</span>
                <div class="category-info">
                    <span class="category-name">${cat.name}</span>
                    <span class="category-meta">${cat.documentCount + cat.fileCount} items</span>
                </div>
            </div>
        `).join('');
    }

    // Update stats
    function updateStats(pages) {
        const totalDocs = pages.filter(p => !p.is_file).length;
        const totalFiles = pages.filter(p => p.is_file).length;
        
        document.getElementById('totalDocs').textContent = totalDocs;
        document.getElementById('totalFiles').textContent = totalFiles;
    }

    // Show overview
    function showOverview() {
        currentCategory = null;
        currentDocumentId = null;
        
        // Update sidebar
        document.querySelectorAll('.category-item').forEach(item => {
            item.classList.remove('active');
        });

        // Hide other views
        document.getElementById('categorySpace').style.display = 'none';
        document.getElementById('documentEditor').style.display = 'none';
        
        // Show overview
        const overview = document.getElementById('categoryOverview');
        overview.style.display = 'block';
        
        // Display category cards
        const grid = overview.querySelector('.category-grid');
        grid.innerHTML = categories.map(cat => `
            <div class="category-card" onclick="WikiApp.openCategory('${cat.id}')">
                <span class="category-card-icon">${cat.icon}</span>
                <h3 class="category-card-name">${cat.name}</h3>
                <div class="category-card-stats">
                    <span class="category-card-stat">
                        <i class="ph ph-file-text"></i>
                        ${cat.documentCount}
                    </span>
                    <span class="category-card-stat">
                        <i class="ph ph-paperclip"></i>
                        ${cat.fileCount}
                    </span>
                </div>
            </div>
        `).join('');
    }

    // Open category
    async function openCategory(categoryId) {
        currentCategory = categoryId;
        const category = categories.find(c => c.id === categoryId);
        if (!category) return;

        // Update sidebar
        document.querySelectorAll('.category-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-category="${categoryId}"]`)?.classList.add('active');

        // Hide other views
        document.getElementById('categoryOverview').style.display = 'none';
        document.getElementById('documentEditor').style.display = 'none';
        
        // Show category space
        const categorySpace = document.getElementById('categorySpace');
        categorySpace.style.display = 'flex';

        // Update header
        document.getElementById('spaceIcon').textContent = category.icon;
        document.getElementById('spaceName').textContent = category.name;

        // Load content
        await loadCategoryContent(categoryId);
    }

    // Load category content
    async function loadCategoryContent(categoryId) {
        try {
            const response = await fetch(`/api/content-wiki/pages?category=${categoryId}`);
            const data = await response.json();

            if (data.success) {
                currentContent = data.pages || [];
                
                // Update stats
                const docs = currentContent.filter(c => !c.is_file);
                const files = currentContent.filter(c => c.is_file);
                document.getElementById('spaceDocs').textContent = docs.length;
                document.getElementById('spaceFiles').textContent = files.length;

                displayContent();
            }
        } catch (error) {
            console.error('Error loading content:', error);
            showToast('Failed to load content', 'error');
        }
    }

    // Display content
    function displayContent() {
        const grid = document.getElementById('contentGrid');
        const emptyState = document.getElementById('emptyState');
        
        // Filter content
        let filteredContent = currentContent;
        if (filterMode === 'documents') {
            filteredContent = currentContent.filter(c => !c.is_file);
        } else if (filterMode === 'files') {
            filteredContent = currentContent.filter(c => c.is_file);
        }

        // Show empty state if no content
        if (filteredContent.length === 0) {
            grid.style.display = 'none';
            emptyState.style.display = 'flex';
            return;
        }

        grid.style.display = 'grid';
        emptyState.style.display = 'none';

        // Apply view mode
        if (viewMode === 'list') {
            grid.classList.add('list-view');
        } else {
            grid.classList.remove('list-view');
        }

        // Sort: pinned first, then by date
        filteredContent.sort((a, b) => {
            if (a.is_pinned && !b.is_pinned) return -1;
            if (!a.is_pinned && b.is_pinned) return 1;
            return new Date(b.updated_at) - new Date(a.updated_at);
        });

        // Display cards
        grid.innerHTML = filteredContent.map(item => {
            const isFile = item.is_file || false;
            const isPinned = item.is_pinned || false;
            const icon = getContentIcon(item);
            const date = formatDate(new Date(item.updated_at));
            
            if (viewMode === 'list') {
                return `
                    <div class="content-card ${isFile ? 'file' : 'document'} ${isPinned ? 'pinned' : ''}"
                         onclick="WikiApp.${isFile ? 'previewFile' : 'openDocument'}('${item.id}')">
                        <div class="content-card-icon">
                            <i class="${icon}"></i>
                        </div>
                        <div class="content-card-info">
                            <div class="content-card-title">${escapeHtml(item.title || item.filename || 'Untitled')}</div>
                            <div class="content-card-meta">
                                <span class="content-card-date">
                                    <i class="ph ph-clock"></i>
                                    ${date}
                                </span>
                                ${item.size ? `<span class="content-card-size">${formatFileSize(item.size)}</span>` : ''}
                            </div>
                        </div>
                    </div>
                `;
            } else {
                return `
                    <div class="content-card ${isFile ? 'file' : 'document'} ${isPinned ? 'pinned' : ''}"
                         onclick="WikiApp.${isFile ? 'previewFile' : 'openDocument'}('${item.id}')">
                        <div class="content-card-icon">
                            <i class="${icon}"></i>
                        </div>
                        <div class="content-card-title">${escapeHtml(item.title || item.filename || 'Untitled')}</div>
                        <div class="content-card-meta">
                            <span class="content-card-date">
                                ${date}
                            </span>
                            ${item.size ? `<span class="content-card-size">${formatFileSize(item.size)}</span>` : ''}
                        </div>
                    </div>
                `;
            }
        }).join('');
    }

    // Get content icon
    function getContentIcon(item) {
        if (!item.is_file) return 'ph ph-file-text';
        
        const filename = item.filename || '';
        const ext = filename.split('.').pop().toLowerCase();
        
        if (['jpg', 'jpeg', 'png', 'gif', 'svg'].includes(ext)) {
            return 'ph ph-image';
        } else if (['mp4', 'avi', 'mov', 'wmv'].includes(ext)) {
            return 'ph ph-video';
        } else if (['pdf'].includes(ext)) {
            return 'ph ph-file-pdf';
        } else if (['doc', 'docx'].includes(ext)) {
            return 'ph ph-file-doc';
        } else if (['xls', 'xlsx'].includes(ext)) {
            return 'ph ph-file-xls';
        } else if (['zip', 'rar', '7z'].includes(ext)) {
            return 'ph ph-file-zip';
        } else {
            return 'ph ph-file';
        }
    }

    // Create document
    async function createDocument() {
        if (!currentCategory) {
            showToast('Please select a category first', 'error');
            return;
        }

        try {
            const response = await fetch('/api/content-wiki/pages', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: 'New Document',
                    content: '',
                    category: currentCategory,
                    tags: [],
                    is_file: false
                })
            });

            const data = await response.json();

            if (data.success && data.page) {
                currentDocumentId = data.page.id;
                openDocument(data.page.id);
                showToast('Document created', 'success');
            }
        } catch (error) {
            console.error('Error creating document:', error);
            showToast('Failed to create document', 'error');
        }
    }

    // Open document
    async function openDocument(documentId) {
        try {
            const response = await fetch(`/api/content-wiki/pages/${documentId}`);
            const data = await response.json();

            if (data.success && data.page) {
                currentDocumentId = documentId;
                
                // Hide other views
                document.getElementById('categoryOverview').style.display = 'none';
                document.getElementById('categorySpace').style.display = 'none';
                
                // Show editor
                document.getElementById('documentEditor').style.display = 'flex';
                
                // Load document data
                document.getElementById('documentTitle').value = data.page.title || '';
                document.getElementById('wikiEditor').innerHTML = data.page.content || '';
                
                // Update pin button
                const pinBtn = document.getElementById('pinBtn');
                if (data.page.is_pinned) {
                    pinBtn.classList.add('active');
                } else {
                    pinBtn.classList.remove('active');
                }
                
                // Update info
                document.getElementById('docVersion').textContent = `v${data.page.version || 1}`;
                document.getElementById('lastEdited').textContent = formatDate(new Date(data.page.updated_at));
                
                updateSaveStatus('saved');
            }
        } catch (error) {
            console.error('Error opening document:', error);
            showToast('Failed to open document', 'error');
        }
    }

    // Close editor
    function closeEditor() {
        currentDocumentId = null;
        document.getElementById('documentEditor').style.display = 'none';
        
        if (currentCategory) {
            document.getElementById('categorySpace').style.display = 'flex';
            loadCategoryContent(currentCategory);
        } else {
            showOverview();
        }
    }

    // Save document
    async function saveDocument(silent = false) {
        if (!currentDocumentId) return;

        const title = document.getElementById('documentTitle').value || 'Untitled';
        const content = document.getElementById('wikiEditor').innerHTML;

        updateSaveStatus('saving');

        try {
            const response = await fetch(`/api/content-wiki/pages/${currentDocumentId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, content })
            });

            const data = await response.json();

            if (data.success) {
                updateSaveStatus('saved');
                if (!silent) showToast('Document saved', 'success');
            } else {
                updateSaveStatus('error');
                if (!silent) showToast('Failed to save', 'error');
            }
        } catch (error) {
            console.error('Error saving document:', error);
            updateSaveStatus('error');
            if (!silent) showToast('Failed to save', 'error');
        }
    }

    // Delete document
    async function deleteDocument() {
        if (!currentDocumentId) return;

        if (!confirm('Delete this document? This cannot be undone.')) return;

        try {
            const response = await fetch(`/api/content-wiki/pages/${currentDocumentId}`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                showToast('Document deleted', 'success');
                closeEditor();
            }
        } catch (error) {
            console.error('Error deleting document:', error);
            showToast('Failed to delete', 'error');
        }
    }

    // Duplicate document
    async function duplicateDocument() {
        if (!currentDocumentId) return;

        try {
            const response = await fetch(`/api/content-wiki/pages/${currentDocumentId}/duplicate`, {
                method: 'POST'
            });

            const data = await response.json();

            if (data.success && data.page) {
                openDocument(data.page.id);
                showToast('Document duplicated', 'success');
            }
        } catch (error) {
            console.error('Error duplicating document:', error);
            showToast('Failed to duplicate', 'error');
        }
    }

    // Toggle pin
    async function togglePin() {
        if (!currentDocumentId) return;

        const pinBtn = document.getElementById('pinBtn');
        const isPinned = pinBtn.classList.contains('active');

        try {
            const response = await fetch(`/api/content-wiki/pages/${currentDocumentId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_pinned: !isPinned })
            });

            const data = await response.json();

            if (data.success) {
                if (!isPinned) {
                    pinBtn.classList.add('active');
                    showToast('Document pinned', 'success');
                } else {
                    pinBtn.classList.remove('active');
                    showToast('Document unpinned', 'success');
                }
            }
        } catch (error) {
            console.error('Error toggling pin:', error);
            showToast('Failed to update pin', 'error');
        }
    }

    // Upload file
    function uploadFile() {
        document.getElementById('fileUpload').click();
    }

    // Handle file upload
    async function handleFileUpload(input) {
        const file = input.files[0];
        if (!file) return;

        if (!currentCategory) {
            showToast('Please select a category first', 'error');
            return;
        }

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
                // Create a file entry
                const fileEntry = {
                    title: file.name,
                    filename: file.name,
                    category: currentCategory,
                    is_file: true,
                    url: data.attachment.url,
                    size: data.attachment.size,
                    type: data.attachment.type
                };

                const saveResponse = await fetch('/api/content-wiki/pages', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(fileEntry)
                });

                const saveData = await saveResponse.json();

                if (saveData.success) {
                    showToast('File uploaded', 'success');
                    loadCategoryContent(currentCategory);
                }
            }
        } catch (error) {
            console.error('Error uploading file:', error);
            showToast('Failed to upload file', 'error');
        }

        // Clear input
        input.value = '';
    }

    // Preview file
    async function previewFile(fileId) {
        try {
            const response = await fetch(`/api/content-wiki/pages/${fileId}`);
            const data = await response.json();

            if (data.success && data.page) {
                const modal = document.getElementById('filePreviewModal');
                const title = document.getElementById('filePreviewTitle');
                const content = document.getElementById('filePreviewContent');
                
                title.textContent = data.page.filename || data.page.title;
                
                // Store current file for download
                window.currentFileUrl = data.page.url;
                
                // Display based on file type
                const ext = (data.page.filename || '').split('.').pop().toLowerCase();
                
                if (['jpg', 'jpeg', 'png', 'gif', 'svg'].includes(ext)) {
                    content.innerHTML = `<img src="${data.page.url}" style="max-width: 100%; height: auto;">`;
                } else if (['pdf'].includes(ext)) {
                    content.innerHTML = `<embed src="${data.page.url}" type="application/pdf" width="100%" height="600px">`;
                } else {
                    content.innerHTML = `
                        <div style="text-align: center; padding: 2rem;">
                            <i class="${getContentIcon(data.page)}" style="font-size: 4rem; color: var(--text-tertiary); margin-bottom: 1rem;"></i>
                            <p>${escapeHtml(data.page.filename)}</p>
                            <p style="color: var(--text-tertiary);">Size: ${formatFileSize(data.page.size)}</p>
                        </div>
                    `;
                }
                
                modal.classList.add('active');
            }
        } catch (error) {
            console.error('Error previewing file:', error);
            showToast('Failed to preview file', 'error');
        }
    }

    // Close file preview
    function closeFilePreview() {
        document.getElementById('filePreviewModal').classList.remove('active');
        window.currentFileUrl = null;
    }

    // Download file
    function downloadFile() {
        if (window.currentFileUrl) {
            window.open(window.currentFileUrl, '_blank');
        }
    }

    // Show document info
    function showDocInfo() {
        if (!currentDocumentId) return;

        const modal = document.getElementById('docInfoModal');
        const content = document.getElementById('docInfoContent');
        
        // Get current document from content array
        const doc = currentContent.find(c => c.id === currentDocumentId);
        if (!doc) return;
        
        content.innerHTML = `
            <div style="display: grid; gap: 1rem;">
                <div>
                    <strong>Title:</strong> ${escapeHtml(doc.title)}
                </div>
                <div>
                    <strong>Category:</strong> ${getCategoryName(doc.category)}
                </div>
                <div>
                    <strong>Created:</strong> ${formatFullDate(new Date(doc.created_at))}
                </div>
                <div>
                    <strong>Last Updated:</strong> ${formatFullDate(new Date(doc.updated_at))}
                </div>
                <div>
                    <strong>Version:</strong> ${doc.version || 1}
                </div>
                ${doc.last_edited_by ? `
                    <div>
                        <strong>Last Edited By:</strong> ${doc.last_edited_by}
                    </div>
                ` : ''}
            </div>
        `;
        
        modal.classList.add('active');
    }

    // Close document info
    function closeDocInfo() {
        document.getElementById('docInfoModal').classList.remove('active');
    }

    // Filter content
    function filterContent(mode) {
        filterMode = mode;
        
        // Update UI
        document.querySelectorAll('.filter-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        event.target.closest('.filter-tab').classList.add('active');
        
        displayContent();
    }

    // Set view mode
    function setView(mode) {
        viewMode = mode;
        
        // Update UI
        document.querySelectorAll('.view-toggle').forEach(btn => {
            btn.classList.remove('active');
        });
        event.target.closest('.view-toggle').classList.add('active');
        
        displayContent();
    }

    // Search
    function searchDebounced(query) {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => search(query), 300);
    }

    async function search(query) {
        if (!query) {
            loadCategories();
            return;
        }

        try {
            const response = await fetch(`/api/content-wiki/search?q=${encodeURIComponent(query)}`);
            const data = await response.json();

            if (data.success) {
                // Show search results in current view
                currentContent = data.results.map(r => r.page);
                displayContent();
            }
        } catch (error) {
            console.error('Error searching:', error);
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

    // Insert code block
    function insertCode() {
        const code = '<pre><code>// Your code here</code></pre>';
        document.execCommand('insertHTML', false, code);
        document.getElementById('wikiEditor').focus();
    }

    // Insert table
    function insertTable() {
        const table = `
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr>
                        <th style="border: 1px solid #ddd; padding: 8px;">Column 1</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Column 2</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Column 3</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px;">Data 1</td>
                        <td style="border: 1px solid #ddd; padding: 8px;">Data 2</td>
                        <td style="border: 1px solid #ddd; padding: 8px;">Data 3</td>
                    </tr>
                </tbody>
            </table>
        `;
        document.execCommand('insertHTML', false, table);
        document.getElementById('wikiEditor').focus();
    }

    // Handle content change
    function handleContentChange() {
        if (!currentDocumentId) return;

        clearTimeout(autoSaveTimer);
        updateSaveStatus('typing');

        autoSaveTimer = setTimeout(() => {
            saveDocument(true);
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
        showOverview,
        openCategory,
        createDocument,
        openDocument,
        closeEditor,
        saveDocument,
        deleteDocument,
        duplicateDocument,
        togglePin,
        uploadFile,
        handleFileUpload,
        previewFile,
        closeFilePreview,
        downloadFile,
        showDocInfo,
        closeDocInfo,
        filterContent,
        setView,
        searchDebounced,
        formatText,
        insertLink,
        insertImage,
        handleImageUpload,
        insertCode,
        insertTable
    };
})();

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    WikiApp.init();
});