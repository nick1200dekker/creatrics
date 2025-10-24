/**
 * News Tracker Application
 */

window.NewsTracker = (function() {
    // State
    let state = {
        selectedFeed: {
            url: 'https://feeds.bbci.co.uk/news/rss.xml',
            name: 'BBC News'
        },
        news: [],
        currentArticle: null,
        generatedPost: ''
    };

    /**
     * Initialize News Tracker
     */
    function init() {
        setupEventListeners();
        console.log('News Tracker initialized');
    }

    /**
     * Setup event listeners
     */
    function setupEventListeners() {
        // Feed dropdown
        const feedDropdown = document.getElementById('feedDropdown');
        const feedMenu = document.getElementById('feedMenu');

        if (feedDropdown) {
            feedDropdown.addEventListener('click', (e) => {
                e.stopPropagation();
                feedDropdown.classList.toggle('active');
                feedMenu.classList.toggle('active');
            });
        }

        // Feed options
        document.querySelectorAll('.dropdown-option').forEach(option => {
            option.addEventListener('click', (e) => {
                e.stopPropagation();
                selectFeed(
                    option.dataset.feed,
                    option.dataset.name
                );
                feedDropdown.classList.remove('active');
                feedMenu.classList.remove('active');
            });
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (feedDropdown && feedMenu) {
                if (!feedDropdown.contains(e.target) && !feedMenu.contains(e.target)) {
                    feedDropdown.classList.remove('active');
                    feedMenu.classList.remove('active');
                }
            }
        });

        // Fetch news button
        const fetchNewsBtn = document.getElementById('fetchNewsBtn');
        if (fetchNewsBtn) {
            fetchNewsBtn.addEventListener('click', fetchNews);
        }

        // Modal close on background click
        const modal = document.getElementById('generateModal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    closeModal();
                }
            });
        }
    }

    /**
     * Select news feed
     */
    function selectFeed(url, name) {
        state.selectedFeed = { url, name };

        // Update UI
        document.getElementById('selectedFeed').textContent = name;

        // Update selected option
        document.querySelectorAll('.dropdown-option').forEach(opt => {
            if (opt.dataset.feed === url) {
                opt.classList.add('selected');
            } else {
                opt.classList.remove('selected');
            }
        });

        console.log('Selected feed:', name);
    }

    /**
     * Fetch news from selected feed
     */
    async function fetchNews() {
        try {
            // Show loading state
            showLoading();

            const response = await fetch('/news-tracker/api/fetch-news', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    feed_url: state.selectedFeed.url
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch news');
            }

            state.news = data.news;
            renderNews();

        } catch (error) {
            console.error('Error fetching news:', error);
            showToast(error.message || 'Failed to fetch news', 'error');
            hideLoading();
        }
    }

    /**
     * Show loading state
     */
    function showLoading() {
        document.getElementById('emptyState').style.display = 'none';
        document.getElementById('newsList').style.display = 'none';
        document.getElementById('loadingState').style.display = 'flex';
    }

    /**
     * Hide loading state
     */
    function hideLoading() {
        document.getElementById('loadingState').style.display = 'none';
    }

    /**
     * Render news items
     */
    function renderNews() {
        hideLoading();

        const newsListEl = document.getElementById('newsList');

        if (state.news.length === 0) {
            document.getElementById('emptyState').style.display = 'block';
            newsListEl.style.display = 'none';
            return;
        }

        document.getElementById('emptyState').style.display = 'none';
        newsListEl.style.display = 'flex';

        newsListEl.innerHTML = state.news.map((item, index) => `
            <div class="news-card" data-index="${index}">
                <div style="display: flex; align-items: flex-start; margin-bottom: 1rem;">
                    ${item.image ? `
                        <div class="news-image-container">
                            <img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.title)}" class="news-image" loading="lazy" onerror="this.parentElement.style.display='none'">
                        </div>
                    ` : ''}
                    <div class="news-content-wrapper">
                        <h3 class="news-title" style="margin-bottom: 0.5rem;">${escapeHtml(item.title)}</h3>
                        <div class="news-meta" style="margin-bottom: 0.5rem;">
                            <span class="news-source">
                                <i class="ph ph-newspaper"></i>
                                ${escapeHtml(item.source)}
                            </span>
                            ${item.published ? `
                                <span class="news-date">
                                    <i class="ph ph-clock"></i>
                                    ${formatDate(item.published)}
                                </span>
                            ` : ''}
                        </div>
                        ${item.description ? `
                            <p class="news-description" style="margin: 0;">${escapeHtml(item.description)}</p>
                        ` : ''}
                    </div>
                </div>

                    <!-- Generated Post Container (hidden by default) -->
                    <div class="generated-post-section" id="generatedPost-${index}" style="display: none;">
                        <div class="generated-post-header">
                            <label style="display: block; margin-bottom: 0.5rem; color: var(--text-primary); font-weight: 600; font-size: 0.875rem;">
                                <i class="ph ph-check-circle" style="color: #10B981;"></i>
                                Generated X Post
                            </label>
                        </div>
                        <div class="post-display" id="postContent-${index}"></div>
                        <div style="margin-top: 0.75rem; display: flex; gap: 0.75rem;">
                            <button class="suggestion-btn btn-copy" onclick="NewsTracker.copyPost(${index})">
                                <i class="ph ph-copy"></i>
                                <span>Copy Post</span>
                            </button>
                            <button class="suggestion-btn" onclick="NewsTracker.regeneratePost(${index})">
                                <i class="ph ph-arrows-clockwise"></i>
                                <span>Regenerate</span>
                            </button>
                        </div>
                    </div>

                    <!-- Loading State -->
                    <div class="generating-state" id="generating-${index}" style="display: none;">
                        <div class="generating-spinner">
                            <i class="ph ph-spinner"></i>
                        </div>
                        <p class="generating-text">Generating your X post...</p>
                    </div>

                    <!-- Action Buttons -->
                    <div class="news-actions" id="actions-${index}">
                        <button class="news-btn" onclick="NewsTracker.generatePost(${index})">
                            <i class="ph ph-magic-wand"></i>
                            Generate X Post
                        </button>
                        <a href="${escapeHtml(item.link)}" target="_blank" class="news-btn" style="background: transparent; border: 1px solid var(--border-primary); color: var(--text-primary);" onclick="event.stopPropagation();">
                            <i class="ph ph-arrow-square-out"></i>
                            View Article
                        </a>
                    </div>
                </div>
            </div>
        `).join('');
    }

    /**
     * Generate X post inline
     */
    async function generatePost(index) {
        try {
            const article = state.news[index];
            if (!article) {
                throw new Error('Article not found');
            }

            // Hide action buttons, show loading
            document.getElementById(`actions-${index}`).style.display = 'none';
            document.getElementById(`generating-${index}`).style.display = 'block';
            document.getElementById(`generatedPost-${index}`).style.display = 'none';

            const response = await fetch('/news-tracker/api/generate-post', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    url: article.link,
                    title: article.title
                })
            });

            const data = await response.json();

            // Handle insufficient credits
            if (response.status === 402) {
                document.getElementById(`generating-${index}`).style.display = 'none';
                document.getElementById(`actions-${index}`).style.display = 'flex';

                const message = data.required_credits && data.current_credits
                    ? `Insufficient credits. Need ${data.required_credits.toFixed(2)}, have ${data.current_credits.toFixed(2)}.`
                    : 'Insufficient credits to generate post.';
                showToast(message, 'error');
                return;
            }

            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate post');
            }

            // Store generated post
            article.generatedPost = data.post;

            // Show generated post inline
            document.getElementById(`generating-${index}`).style.display = 'none';
            document.getElementById(`postContent-${index}`).textContent = data.post;
            document.getElementById(`generatedPost-${index}`).style.display = 'block';

        } catch (error) {
            console.error('Error generating post:', error);
            showToast(error.message || 'Failed to generate post', 'error');

            // Show action buttons again
            document.getElementById(`generating-${index}`).style.display = 'none';
            document.getElementById(`actions-${index}`).style.display = 'flex';
        }
    }

    /**
     * Regenerate post
     */
    function regeneratePost(index) {
        generatePost(index);
    }

    /**
     * Copy post to clipboard
     */
    async function copyPost(index) {
        try {
            const postContent = document.getElementById(`postContent-${index}`).textContent;
            if (!postContent) {
                return;
            }
            await navigator.clipboard.writeText(postContent);
            showToast('Post copied to clipboard!', 'success');
        } catch (error) {
            console.error('Error copying to clipboard:', error);
        }
    }

    /**
     * Format date
     */
    function formatDate(dateString) {
        try {
            const date = new Date(dateString);
            const now = new Date();
            const diff = now - date;
            const hours = Math.floor(diff / (1000 * 60 * 60));

            if (hours < 1) {
                const minutes = Math.floor(diff / (1000 * 60));
                return `${minutes}m ago`;
            } else if (hours < 24) {
                return `${hours}h ago`;
            } else {
                const days = Math.floor(hours / 24);
                return `${days}d ago`;
            }
        } catch {
            return dateString;
        }
    }

    /**
     * Escape HTML
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Show toast notification
     */
    function showToast(message, type = 'info') {
        if (window.BaseApp && window.BaseApp.showToast) {
            window.BaseApp.showToast(message, type);
        } else {
            console.log(`[${type}] ${message}`);
        }
    }

    // Public API
    return {
        init,
        generatePost,
        regeneratePost,
        copyPost
    };
})();
