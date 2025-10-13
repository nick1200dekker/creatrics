// Content Wiki Application - Grid-based Category System with Folders
const WikiApp = (function() {
    // State
    let currentCategory = null;
    let currentDocumentId = null;
    let currentFolder = null;
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
                    const categoryContent = pages.filter(p => p.category === cat.id);
                    cat.documentCount = categoryContent.filter(p => !p.is_file && !p.is_folder).length;
                    cat.fileCount = categoryContent.filter(p => p.is_file).length;
                    cat.folderCount = categoryContent.filter(p => p.is_folder).length;
                });

                displayCategories();
                showOverview(); // Show the overview with categories
                loadStorageUsage(); // Load storage usage
            }
        } catch (error) {
            console.error('Error loading categories:', error);
        }
    }

    // Load storage usage
    async function loadStorageUsage() {
        try {
            const response = await fetch('/api/content-wiki/storage');
            const data = await response.json();

            if (data.success && data.storage) {
                const { used_mb, max_mb, percentage } = data.storage;

                // Update display
                document.getElementById('storageUsedMB').textContent = used_mb;
                const fillEl = document.getElementById('storageUsageFill');
                fillEl.style.width = `${Math.min(percentage, 100)}%`;

                // Color coding based on usage
                fillEl.classList.remove('warning', 'danger');
                if (percentage >= 90) {
                    fillEl.classList.add('danger');
                } else if (percentage >= 70) {
                    fillEl.classList.add('warning');
                }

                // Show storage container after loading
                document.getElementById('storageUsageContainer').style.display = 'block';
            }
        } catch (error) {
            console.error('Error loading storage usage:', error);
        }
    }

    // Display categories (no sidebar, just prepare data)
    function displayCategories() {
        // Categories will be displayed in showOverview()
    }

    // Update stats (not needed in header anymore)
    function updateStats(pages) {
        // Stats are now shown per-category in the space view
    }

    // Show overview
    function showOverview() {
        // If we're in a folder, go back to the category root
        if (currentFolder) {
            currentFolder = null;
            loadCategoryContent(currentCategory, null);
            return;
        }

        // Otherwise go back to wiki home
        currentCategory = null;
        currentDocumentId = null;
        currentFolder = null;

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
                <i class="category-card-icon ph ${cat.icon}" style="color: ${cat.color}"></i>
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
        currentFolder = null;
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

        // Update header (no icon in title)
        document.getElementById('spaceName').textContent = category.name;

        // Load content
        await loadCategoryContent(categoryId);
    }

    // Load category content
    async function loadCategoryContent(categoryId, folderId = null) {
        try {
            // Show loading spinner and hide content
            showContentLoading();

            let url = `/api/content-wiki/pages?category=${categoryId}`;
            if (folderId) {
                url += `&folder=${folderId}`;
            }

            const response = await fetch(url);
            const data = await response.json();

            if (data.success) {
                currentContent = data.pages || [];

                // Update stats
                const docs = currentContent.filter(c => !c.is_file && !c.is_folder);
                const files = currentContent.filter(c => c.is_file);
                const folders = currentContent.filter(c => c.is_folder);

                document.getElementById('spaceDocs').textContent = docs.length;
                document.getElementById('spaceFiles').textContent = files.length;

                // Check if spaceFolders element exists
                const spaceFoldersEl = document.getElementById('spaceFolders');
                if (spaceFoldersEl) {
                    spaceFoldersEl.textContent = folders.length;
                }

                displayContent();
                hideContentLoading();
            }
        } catch (error) {
            console.error('Error loading content:', error);
            showToast('Failed to load content', 'error');
            hideContentLoading();
        }
    }

    // Show content loading spinner
    function showContentLoading() {
        const loading = document.getElementById('contentLoading');
        const grid = document.getElementById('contentGrid');
        const emptyState = document.getElementById('emptyState');

        // Clear current content immediately
        grid.innerHTML = '';
        grid.style.display = 'none';
        emptyState.style.display = 'none';
        loading.style.display = 'flex';
    }

    // Hide content loading spinner
    function hideContentLoading() {
        const loading = document.getElementById('contentLoading');
        loading.style.display = 'none';
    }

    // Display content
    function displayContent() {
        const grid = document.getElementById('contentGrid');
        const emptyState = document.getElementById('emptyState');
        
        // Filter content
        let filteredContent = currentContent;
        if (filterMode === 'folders') {
            filteredContent = currentContent.filter(c => c.is_folder);
        } else if (filterMode === 'documents') {
            filteredContent = currentContent.filter(c => !c.is_file && !c.is_folder);
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

        // Sort: folders first, then pinned, then by date
        filteredContent.sort((a, b) => {
            if (a.is_folder && !b.is_folder) return -1;
            if (!a.is_folder && b.is_folder) return 1;
            if (a.is_pinned && !b.is_pinned) return -1;
            if (!a.is_pinned && b.is_pinned) return 1;
            return new Date(b.updated_at) - new Date(a.updated_at);
        });

        // Display cards
        grid.innerHTML = filteredContent.map(item => {
            const isFolder = item.is_folder || false;
            const isFile = item.is_file || false;
            const isPinned = item.is_pinned || false;
            const icon = getContentIcon(item);
            const date = formatDate(new Date(item.updated_at));
            const type = isFolder ? 'folder' : (isFile ? getFileType(item) : 'document');
            const clickHandler = isFolder ? 'openFolder' : (isFile ? 'previewFile' : 'openDocument');

            if (viewMode === 'list') {
                return `
                    <div class="content-card ${type} ${isPinned ? 'pinned' : ''}"
                         onclick="WikiApp.${clickHandler}('${item.id}')">
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
                        <button class="card-delete-btn" onclick="event.stopPropagation(); WikiApp.deleteCardItem('${item.id}', '${type}')" title="Delete">
                            <i class="ph ph-trash"></i>
                        </button>
                    </div>
                `;
            } else {
                return `
                    <div class="content-card ${type} ${isPinned ? 'pinned' : ''}"
                         onclick="WikiApp.${clickHandler}('${item.id}')">
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
                        <button class="card-delete-btn" onclick="event.stopPropagation(); WikiApp.deleteCardItem('${item.id}', '${type}')" title="Delete">
                            <i class="ph ph-trash"></i>
                        </button>
                    </div>
                `;
            }
        }).join('');
    }

    // Get file type for styling
    function getFileType(item) {
        if (!item.is_file) return 'document';
        
        const filename = item.filename || '';
        const ext = filename.split('.').pop().toLowerCase();
        
        if (['jpg', 'jpeg', 'png', 'gif', 'svg'].includes(ext)) {
            return 'image';
        } else if (['pdf'].includes(ext)) {
            return 'pdf';
        } else if (['mp4', 'avi', 'mov', 'wmv'].includes(ext)) {
            return 'video';
        } else {
            return 'file';
        }
    }

    // Get content icon
    function getContentIcon(item) {
        if (item.is_folder) return 'ph ph-folder';
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

    // Create folder
    function createFolder() {
        if (!currentCategory) {
            showToast('Please select a category first', 'error');
            return;
        }

        const modal = document.getElementById('newFolderModal');
        modal.classList.add('active');
        document.getElementById('folderNameInput').value = '';
        document.getElementById('folderNameInput').focus();
    }

    // Confirm create folder
    async function confirmCreateFolder() {
        const folderName = document.getElementById('folderNameInput').value.trim();
        
        if (!folderName) {
            showToast('Please enter a folder name', 'error');
            return;
        }

        try {
            const response = await fetch('/api/content-wiki/pages', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: folderName,
                    category: currentCategory,
                    parent_folder: currentFolder,
                    is_folder: true
                })
            });

            const data = await response.json();

            if (data.success) {
                closeFolderModal();
                showToast('Folder created', 'success');
                loadCategoryContent(currentCategory, currentFolder);
                loadCategories(); // Update overview stats
            }
        } catch (error) {
            console.error('Error creating folder:', error);
            showToast('Failed to create folder', 'error');
        }
    }

    // Close folder modal
    function closeFolderModal() {
        document.getElementById('newFolderModal').classList.remove('active');
    }

    // Open folder
    async function openFolder(folderId) {
        currentFolder = folderId;
        await loadCategoryContent(currentCategory, folderId);
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
                    parent_folder: currentFolder,
                    tags: [],
                    is_file: false,
                    is_folder: false
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
                // Check if it's a file or folder - don't open as document
                // Also check for file extensions as fallback for old entries without is_file flag
                const filename = data.page.filename || data.page.title || '';
                const ext = filename.split('.').pop().toLowerCase();
                const isActualFile = data.page.is_file ||
                                   data.page.url ||
                                   ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'mp4', 'webm', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'rar'].includes(ext);

                if (isActualFile || data.page.is_folder) {
                    if (data.page.is_folder) {
                        openFolder(documentId);
                    } else {
                        previewFile(documentId);
                    }
                    return;
                }

                currentDocumentId = documentId;
                
                // Hide other views
                document.getElementById('categoryOverview').style.display = 'none';
                document.getElementById('categorySpace').style.display = 'none';
                
                // Show editor
                document.getElementById('documentEditor').style.display = 'flex';
                
                // Load document data
                document.getElementById('documentTitle').value = data.page.title || '';
                document.getElementById('wikiEditor').innerHTML = data.page.content || '';

                // Setup image resize for existing images
                setupImageResize();

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

    // Download document
    function downloadDocument() {
        if (!currentDocumentId) return;

        const title = document.getElementById('documentTitle').value || 'document';
        const content = document.getElementById('wikiEditor').innerHTML;

        // Create Word-compatible HTML document (.doc format)
        // This format can be opened by Google Docs, Microsoft Word, and other word processors
        const docContent = `
<html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'>
<head>
    <meta charset='utf-8'>
    <title>${escapeHtml(title)}</title>
    <style>
        body {
            font-family: 'Calibri', 'Arial', sans-serif;
            font-size: 11pt;
            line-height: 1.5;
            margin: 1in;
        }
        h1 {
            font-size: 20pt;
            font-weight: bold;
            margin-top: 12pt;
            margin-bottom: 6pt;
        }
        h2 {
            font-size: 16pt;
            font-weight: bold;
            margin-top: 10pt;
            margin-bottom: 6pt;
        }
        h3 {
            font-size: 14pt;
            font-weight: bold;
            margin-top: 10pt;
            margin-bottom: 6pt;
        }
        p {
            margin-top: 0;
            margin-bottom: 10pt;
        }
        pre, code {
            font-family: 'Courier New', monospace;
            background-color: #f3f4f6;
            padding: 10pt;
        }
        blockquote {
            border-left: 3pt solid #3B82F6;
            padding-left: 10pt;
            margin-left: 0;
            font-style: italic;
        }
        table {
            border-collapse: collapse;
            width: 100%;
        }
        table, th, td {
            border: 1pt solid #000;
            padding: 5pt;
        }
    </style>
</head>
<body>
    <h1>${escapeHtml(title)}</h1>
    ${content}
</body>
</html>`;

        const blob = new Blob(['\ufeff', docContent], { type: 'application/msword' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${title.replace(/[^a-z0-9]/gi, '_')}.doc`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showToast('Document downloaded as .doc (compatible with Google Docs & Word)', 'success');
    }

    // Close editor
    function closeEditor() {
        currentDocumentId = null;
        document.getElementById('documentEditor').style.display = 'none';
        
        if (currentCategory) {
            document.getElementById('categorySpace').style.display = 'flex';
            loadCategoryContent(currentCategory, currentFolder);
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
                loadCategories(); // Update overview stats
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
                    parent_folder: currentFolder,
                    is_file: true,
                    is_folder: false,
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
                    loadCategoryContent(currentCategory, currentFolder);
                    loadCategories(); // Update overview stats
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

                // Store current file for download and delete
                window.currentFileId = fileId;
                window.currentFileUrl = data.page.url;
                window.currentFileName = data.page.filename || data.page.title;
                
                // Display based on file type
                const ext = (data.page.filename || '').split('.').pop().toLowerCase();
                
                if (['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp'].includes(ext)) {
                    // Image preview
                    content.innerHTML = `
                        <div class="file-preview-container">
                            <img src="${data.page.url}" alt="${escapeHtml(data.page.filename)}">
                        </div>
                    `;
                } else if (ext === 'pdf') {
                    // PDF preview
                    content.innerHTML = `
                        <div class="file-preview-container">
                            <iframe src="${data.page.url}" type="application/pdf"></iframe>
                        </div>
                    `;
                } else if (['mp4', 'webm', 'ogg'].includes(ext)) {
                    // Video preview
                    content.innerHTML = `
                        <div class="file-preview-container">
                            <video controls style="max-width: 100%; height: auto;">
                                <source src="${data.page.url}" type="video/${ext}">
                                Your browser does not support the video tag.
                            </video>
                        </div>
                    `;
                } else if (['mp3', 'wav', 'ogg'].includes(ext)) {
                    // Audio preview
                    content.innerHTML = `
                        <div class="file-preview-container">
                            <audio controls style="width: 100%;">
                                <source src="${data.page.url}" type="audio/${ext}">
                                Your browser does not support the audio tag.
                            </audio>
                        </div>
                    `;
                } else {
                    // Other files - show info
                    content.innerHTML = `
                        <div style="text-align: center; padding: 3rem;">
                            <i class="${getContentIcon(data.page)}" style="font-size: 5rem; color: var(--text-tertiary); margin-bottom: 1.5rem; display: block;"></i>
                            <h3 style="margin-bottom: 1rem;">${escapeHtml(data.page.filename)}</h3>
                            <p style="color: var(--text-tertiary); margin-bottom: 0.5rem;">Size: ${formatFileSize(data.page.size || 0)}</p>
                            <p style="color: var(--text-tertiary);">Type: ${data.page.type || 'Unknown'}</p>
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
        window.currentFileId = null;
        window.currentFileUrl = null;
        window.currentFileName = null;
    }

    // Download file
    function downloadFile() {
        if (window.currentFileUrl) {
            const a = document.createElement('a');
            a.href = window.currentFileUrl;
            a.download = window.currentFileName || 'download';
            a.target = '_blank';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            showToast('Download started', 'success');
        }
    }

    // Delete file
    async function deleteFile() {
        if (!window.currentFileId) return;

        if (!confirm('Are you sure you want to delete this file? This action cannot be undone.')) {
            return;
        }

        try {
            const response = await fetch(`/api/content-wiki/pages/${window.currentFileId}`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                showToast('File deleted', 'success');
                closeFilePreview();
                loadCategoryContent(currentCategory, currentFolder);
                loadCategories(); // Update overview stats
            } else {
                showToast('Failed to delete file', 'error');
            }
        } catch (error) {
            console.error('Error deleting file:', error);
            showToast('Failed to delete file', 'error');
        }
    }

    // Delete item from card (works for files, folders, and pages)
    async function deleteCardItem(itemId, type) {
        const itemName = type === 'folder' ? 'folder' : (type === 'document' ? 'page' : 'file');

        if (!confirm(`Are you sure you want to delete this ${itemName}? This action cannot be undone.`)) {
            return;
        }

        try {
            const response = await fetch(`/api/content-wiki/pages/${itemId}`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                showToast(`${itemName.charAt(0).toUpperCase() + itemName.slice(1)} deleted`, 'success');
                loadCategoryContent(currentCategory, currentFolder);
                loadCategories(); // Update overview stats
            } else {
                showToast(`Failed to delete ${itemName}`, 'error');
            }
        } catch (error) {
            console.error(`Error deleting ${itemName}:`, error);
            showToast(`Failed to delete ${itemName}`, 'error');
        }
    }

    // Rename file
    function renameFile() {
        if (!window.currentFileId) return;

        const modal = document.getElementById('renameModal');
        const input = document.getElementById('renameInput');

        // Pre-fill with current name
        input.value = window.currentFileName || '';

        // Store the item ID and type for rename
        window.renameItemId = window.currentFileId;
        window.renameItemType = 'file';

        modal.classList.add('active');
        setTimeout(() => input.focus(), 100);
    }

    // Close rename modal
    function closeRenameModal() {
        document.getElementById('renameModal').classList.remove('active');
        window.renameItemId = null;
        window.renameItemType = null;
    }

    // Confirm rename
    async function confirmRename() {
        const newName = document.getElementById('renameInput').value.trim();

        if (!newName) {
            showToast('Please enter a name', 'error');
            return;
        }

        if (!window.renameItemId) return;

        try {
            const updateData = window.renameItemType === 'file'
                ? { filename: newName, title: newName }
                : { title: newName };

            const response = await fetch(`/api/content-wiki/pages/${window.renameItemId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updateData)
            });

            const data = await response.json();

            if (data.success) {
                showToast('Renamed successfully', 'success');
                closeRenameModal();

                // Update current file name if file is still open
                if (window.renameItemType === 'file' && window.currentFileId === window.renameItemId) {
                    window.currentFileName = newName;
                    document.getElementById('filePreviewTitle').textContent = newName;
                }

                // Reload content
                loadCategoryContent(currentCategory, currentFolder);
                loadCategories(); // Update overview stats
            } else {
                showToast('Failed to rename', 'error');
            }
        } catch (error) {
            console.error('Error renaming:', error);
            showToast('Failed to rename', 'error');
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

    // Search in space
    function searchInSpace(query) {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
            filterContentBySearch(query);
        }, 300);
    }

    // Filter content by search
    function filterContentBySearch(query) {
        if (!query) {
            displayContent();
            return;
        }

        const searchTerm = query.toLowerCase();
        const filtered = currentContent.filter(item => {
            const title = (item.title || item.filename || '').toLowerCase();
            return title.includes(searchTerm);
        });

        // Display filtered results
        const grid = document.getElementById('contentGrid');
        const emptyState = document.getElementById('emptyState');

        if (filtered.length === 0) {
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

        // Display filtered cards
        grid.innerHTML = filtered.map(item => {
            const isFolder = item.is_folder || false;
            const isFile = item.is_file || false;
            const isPinned = item.is_pinned || false;
            const icon = getContentIcon(item);
            const date = formatDate(new Date(item.updated_at));
            const type = isFolder ? 'folder' : (isFile ? getFileType(item) : 'document');
            const clickHandler = isFolder ? 'openFolder' : (isFile ? 'previewFile' : 'openDocument');
            
            if (viewMode === 'list') {
                return `
                    <div class="content-card ${type} ${isPinned ? 'pinned' : ''}"
                         onclick="WikiApp.${clickHandler}('${item.id}')">
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
                    <div class="content-card ${type} ${isPinned ? 'pinned' : ''}"
                         onclick="WikiApp.${clickHandler}('${item.id}')">
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
                // Insert resizable image into editor
                const img = `<img src="${data.attachment.url}" alt="${data.attachment.filename}" style="max-width: 100%; width: 600px; cursor: pointer;" class="resizable-image">`;
                document.execCommand('insertHTML', false, img);

                // Add resize functionality to all images
                setupImageResize();

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

    // Setup image resize functionality
    function setupImageResize() {
        const editor = document.getElementById('wikiEditor');
        if (!editor) return;

        const images = editor.querySelectorAll('img');
        images.forEach(img => {
            img.style.cursor = 'pointer';
            img.onclick = function(e) {
                e.preventDefault();
                e.stopPropagation();
                showImageResizeSlider(this);
            };
        });
    }

    // Show image resize slider
    function showImageResizeSlider(img) {
        // Remove any existing slider
        const existingSlider = document.querySelector('.image-resize-slider');
        if (existingSlider) {
            existingSlider.remove();
        }

        // Get current width
        const currentWidth = parseInt(img.style.width) || img.width;
        const maxWidth = img.parentElement.offsetWidth;

        // Create slider overlay
        const slider = document.createElement('div');
        slider.className = 'image-resize-slider';
        slider.innerHTML = `
            <div class="image-resize-slider-content">
                <div class="image-resize-header">
                    <span class="image-resize-title">Resize Image</span>
                    <span class="image-resize-value">${currentWidth}px</span>
                </div>
                <input type="range"
                       class="image-resize-range"
                       min="200"
                       max="${Math.max(maxWidth, 1200)}"
                       value="${currentWidth}"
                       step="10">
                <div class="image-resize-actions">
                    <button class="image-resize-btn image-resize-cancel">Cancel</button>
                    <button class="image-resize-btn image-resize-apply">Apply</button>
                </div>
            </div>
        `;

        document.body.appendChild(slider);

        const rangeInput = slider.querySelector('.image-resize-range');
        const valueDisplay = slider.querySelector('.image-resize-value');
        const cancelBtn = slider.querySelector('.image-resize-cancel');
        const applyBtn = slider.querySelector('.image-resize-apply');

        let newWidth = currentWidth;

        // Update value as slider moves
        rangeInput.addEventListener('input', (e) => {
            newWidth = parseInt(e.target.value);
            valueDisplay.textContent = `${newWidth}px`;
        });

        // Apply button
        applyBtn.addEventListener('click', () => {
            img.style.width = `${newWidth}px`;
            slider.remove();
        });

        // Cancel button
        cancelBtn.addEventListener('click', () => {
            slider.remove();
        });

        // Click outside to cancel
        slider.addEventListener('click', (e) => {
            if (e.target === slider) {
                slider.remove();
            }
        });

        // Show slider with animation
        setTimeout(() => slider.classList.add('show'), 10);
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
        return cat ? cat.name : categoryId;
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
        createFolder,
        confirmCreateFolder,
        closeFolderModal,
        openFolder,
        createDocument,
        openDocument,
        downloadDocument,
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
        deleteFile,
        deleteCardItem,
        renameFile,
        closeRenameModal,
        confirmRename,
        setupImageResize,
        showDocInfo,
        closeDocInfo,
        filterContent,
        setView,
        searchInSpace,
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