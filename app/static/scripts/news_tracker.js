/**
 * News Tracker - With Personalized Feeds, Categories, and Live RSS
 */

console.log('✓ news_tracker.js loaded successfully');

const NewsTracker = {
    state: {
        currentTab: 'for-you',
        forYouArticles: [],
        categoryArticles: [],
        liveFeedArticles: [],
        selectedCategory: null,
        selectedFeed: 'https://feeds.bbci.co.uk/news/rss.xml',
        selectedFeedName: 'BBC News',
        categories: [],
        userSubscriptions: [],
        rssFeeds: []
    },

    init() {
        console.log('NewsTracker initializing...');

        this.setupTabs();
        this.setupEventListeners();

        // Load categories, feeds, and subscriptions, then feed
        this.loadCategories().then(() => {
            this.loadUserSubscriptions().then(() => {
                this.loadForYouFeed();
            });
        });

        // Load RSS feeds
        this.loadRSSFeeds();
    },

    setupTabs() {
        console.log('Setting up tabs...');
        const tabButtons = document.querySelectorAll('.tab-btn');
        const tabContents = document.querySelectorAll('.tab-content');

        console.log('Found tab buttons:', tabButtons.length);
        console.log('Found tab contents:', tabContents.length);

        tabButtons.forEach((btn, index) => {
            console.log(`Setting up tab ${index}:`, btn.dataset.tab);

            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();

                const tabName = btn.dataset.tab;
                console.log('=== Tab clicked:', tabName);

                // Update active states
                tabButtons.forEach(b => b.classList.remove('active'));
                tabContents.forEach(c => c.classList.remove('active'));

                btn.classList.add('active');
                const tabContent = document.getElementById(`${tabName}-tab`);
                if (tabContent) {
                    tabContent.classList.add('active');
                    console.log('✓ Activated tab:', tabName);
                } else {
                    console.error('✗ Tab content not found:', `${tabName}-tab`);
                }

                this.state.currentTab = tabName;

                // Load content for tab if needed
                if (tabName === 'for-you' && this.state.forYouArticles.length === 0) {
                    this.loadForYouFeed();
                } else if (tabName === 'categories' && !this.state.selectedCategory && this.state.categories.length > 0) {
                    // Auto-select first category when switching to Categories tab
                    this.selectCategory(this.state.categories[0]);
                }
            });
        });

        console.log('✓ Tabs setup complete');
    },

    setupEventListeners() {
        // For You refresh
        document.getElementById('refreshForYou')?.addEventListener('click', () => {
            this.loadForYouFeed();
        });

        // Save subscriptions
        document.getElementById('saveSubscriptions')?.addEventListener('click', () => {
            this.saveUserSubscriptions();
        });

        // Live RSS feed dropdown
        document.getElementById('feedDropdown')?.addEventListener('click', (e) => {
            e.stopPropagation();
            const menu = document.getElementById('feedMenu');
            const trigger = document.getElementById('feedDropdown');
            menu.classList.toggle('active');
            trigger.classList.toggle('active');
        });

        // Fetch live feed button
        document.getElementById('fetchLiveFeed')?.addEventListener('click', () => {
            this.fetchLiveFeed();
        });

        // Close dropdowns when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.dropdown')) {
                document.querySelectorAll('.dropdown-menu').forEach(menu => {
                    menu.classList.remove('active');
                });
                document.querySelectorAll('.dropdown-trigger').forEach(trigger => {
                    trigger.classList.remove('active');
                });
            }
        });
    },

    async loadRSSFeeds() {
        try {
            const response = await fetch('/news-tracker/api/feeds');
            const data = await response.json();

            if (data.success) {
                this.state.rssFeeds = data.feeds;
                this.renderFeedDropdown();
            }
        } catch (error) {
            console.error('Error loading RSS feeds:', error);
        }
    },

    renderFeedDropdown() {
        const feedMenu = document.getElementById('feedMenu');
        if (!feedMenu || this.state.rssFeeds.length === 0) return;

        feedMenu.innerHTML = this.state.rssFeeds.map((feed, index) => `
            <div class="dropdown-option" data-feed="${escapeHtml(feed.url)}" data-name="${escapeHtml(feed.name)}">
                <i class="ph ph-check" style="opacity: ${index === 0 ? '1' : '0'}"></i>
                <span>${escapeHtml(feed.name)}</span>
            </div>
        `).join('');

        // Add click handlers for feed selection
        feedMenu.querySelectorAll('.dropdown-option').forEach(option => {
            option.addEventListener('click', () => {
                const feedUrl = option.dataset.feed;
                const feedName = option.dataset.name;

                this.state.selectedFeed = feedUrl;
                this.state.selectedFeedName = feedName;

                // Update UI
                document.getElementById('selectedFeed').textContent = feedName;

                // Update check marks
                feedMenu.querySelectorAll('.dropdown-option i').forEach(icon => {
                    icon.style.opacity = '0';
                });
                option.querySelector('i').style.opacity = '1';

                // Close dropdown
                feedMenu.classList.remove('active');
                document.getElementById('feedDropdown').classList.remove('active');
            });
        });
    },

    async loadCategories() {
        try {
            const response = await fetch('/news-tracker/api/categories');
            const data = await response.json();

            if (data.success) {
                this.state.categories = data.categories;
                this.renderCategoryBubbles();
                this.renderCategorySettings();
            }
        } catch (error) {
            console.error('Error loading categories:', error);
        }
    },

    async loadUserSubscriptions() {
        try {
            const response = await fetch('/news-tracker/api/subscriptions');
            const data = await response.json();

            if (data.success) {
                this.state.userSubscriptions = data.subscriptions;
                this.renderCategorySettings();
            }
        } catch (error) {
            console.error('Error loading subscriptions:', error);
        }
    },

    renderCategoryBubbles() {
        const container = document.getElementById('categoryBubbles');
        if (!container) return;

        // Category icons mapping
        const categoryIcons = {
            'Tech & AI': 'ph-cpu',
            'Crypto & Finance': 'ph-currency-bitcoin',
            'Sports & Fitness': 'ph-basketball',
            'Gaming & Esports': 'ph-game-controller',
            'Entertainment & Culture': 'ph-film-slate',
            'Politics & World': 'ph-globe-hemisphere-west',
            'Science & Innovation': 'ph-atom',
            'Business & Startups': 'ph-briefcase',
            'Health & Wellness': 'ph-heart-pulse',
            'Climate & Environment': 'ph-leaf'
        };

        container.innerHTML = this.state.categories.map(category => {
            const icon = categoryIcons[category] || 'ph-folder';
            return `
                <button class="category-bubble" data-category="${escapeHtml(category)}">
                    <i class="ph ${icon}"></i>
                    <span>${escapeHtml(category)}</span>
                </button>
            `;
        }).join('');

        // Add click handlers
        container.querySelectorAll('.category-bubble').forEach(bubble => {
            bubble.addEventListener('click', () => {
                const category = bubble.dataset.category;
                this.selectCategory(category);
            });
        });
    },

    renderCategorySettings() {
        const grid = document.getElementById('categoriesGrid');
        if (!grid) return;

        grid.innerHTML = this.state.categories.map((category, index) => {
            const id = `category_${index}`;
            return `
            <div class="permission-item">
                <input type="checkbox"
                       id="${id}"
                       value="${escapeHtml(category)}"
                       ${this.state.userSubscriptions.includes(category) ? 'checked' : ''}>
                <label for="${id}">${escapeHtml(category)}</label>
            </div>
        `;
        }).join('');
    },

    async saveUserSubscriptions() {
        const checkboxes = document.querySelectorAll('#categoriesGrid input[type="checkbox"]');
        const selected = Array.from(checkboxes)
            .filter(cb => cb.checked)
            .map(cb => cb.value);

        try {
            const response = await fetch('/news-tracker/api/subscriptions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ categories: selected })
            });

            const data = await response.json();

            if (data.success) {
                this.state.userSubscriptions = selected;
                showToast('Preferences saved successfully', 'success');
                // Reload For You feed
                this.loadForYouFeed();
            } else {
                showToast(data.error || 'Failed to save preferences', 'error');
            }
        } catch (error) {
            console.error('Error saving subscriptions:', error);
            showToast('Failed to save preferences', 'error');
        }
    },

    async loadForYouFeed() {
        const loading = document.getElementById('forYouLoading');
        const list = document.getElementById('forYouList');
        const empty = document.getElementById('forYouEmpty');

        // Check if user has subscriptions first
        if (this.state.userSubscriptions.length === 0) {
            loading.style.display = 'none';
            list.style.display = 'none';
            empty.style.display = 'block';
            empty.querySelector('.empty-title').textContent = 'No categories selected';
            empty.querySelector('.empty-text').textContent = 'Go to Settings tab to subscribe to categories you\'re interested in';
            return;
        }

        loading.style.display = 'flex';
        list.style.display = 'none';
        empty.style.display = 'none';

        try {
            const response = await fetch('/news-tracker/api/personalized-feed?limit=50');
            const data = await response.json();

            if (data.success) {
                this.state.forYouArticles = data.articles;
                loading.style.display = 'none';

                if (data.articles.length === 0) {
                    empty.style.display = 'block';
                    empty.querySelector('.empty-title').textContent = 'No articles found';
                    empty.querySelector('.empty-text').textContent = 'No articles available in your subscribed categories yet. Check back later!';
                } else {
                    list.style.display = 'block';
                    this.renderArticles(data.articles, 'forYouList');
                }
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            console.error('Error loading For You feed:', error);
            loading.style.display = 'none';
            empty.style.display = 'block';
            empty.querySelector('.empty-title').textContent = 'Error loading feed';
            empty.querySelector('.empty-text').textContent = error.message || 'Failed to load personalized feed';
        }
    },

    async selectCategory(category) {
        this.state.selectedCategory = category;

        // Update active state on bubbles
        document.querySelectorAll('.category-bubble').forEach(bubble => {
            if (bubble.dataset.category === category) {
                bubble.classList.add('active');
            } else {
                bubble.classList.remove('active');
            }
        });

        const loading = document.getElementById('categoryLoading');
        const list = document.getElementById('categoryList');
        const empty = document.getElementById('categoryEmpty');

        loading.style.display = 'flex';
        list.style.display = 'none';
        empty.style.display = 'none';

        try {
            const response = await fetch(`/news-tracker/api/category-feed/${encodeURIComponent(category)}?limit=50`);
            const data = await response.json();

            if (data.success) {
                this.state.categoryArticles = data.articles;
                loading.style.display = 'none';

                if (data.articles.length === 0) {
                    empty.querySelector('.empty-title').textContent = 'No articles in this category';
                    empty.querySelector('.empty-text').textContent = 'Check back later for new content';
                    empty.style.display = 'block';
                } else {
                    list.style.display = 'block';
                    this.renderArticles(data.articles, 'categoryList');
                }
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            console.error('Error loading category feed:', error);
            loading.style.display = 'none';
            empty.style.display = 'block';
            showToast('Failed to load category feed', 'error');
        }
    },

    renderArticles(articles, containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = articles.map((article, index) => `
            <div class="news-card" data-index="${index}">
                <div style="display: flex; align-items: flex-start; margin-bottom: 1rem;">
                    <div class="news-image-container">
                        <div class="news-image-placeholder">
                            <i class="ph ph-newspaper"></i>
                        </div>
                    </div>
                    <div class="news-content-wrapper">
                        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                            <span class="category-badge">${escapeHtml(article.category)}</span>
                            <span class="importance-badge">${this.renderImportanceStars(article.importance_score)}</span>
                        </div>
                        <h3 class="news-title">${escapeHtml(article.title)}</h3>
                        <div class="news-meta">
                            <span class="news-source">${escapeHtml(article.source)}</span>
                            ${article.published ? `<span class="news-date">${formatDate(article.published)}</span>` : ''}
                        </div>
                        ${article.summary ? `<p class="news-description">${escapeHtml(article.summary)}</p>` : ''}
                    </div>
                </div>

                <!-- Loading State -->
                <div class="generating-state" id="generating-${containerId}-${index}" style="display: none;">
                    <div class="generating-spinner">
                        <i class="ph ph-spinner"></i>
                    </div>
                    <p class="generating-text">Generating your X post...</p>
                </div>

                <!-- Generated Post Container -->
                <div class="generated-post-section" id="generatedPost-${containerId}-${index}" style="display: none;">
                    <div class="post-display" id="postContent-${containerId}-${index}"></div>
                    <div style="margin-top: 0.75rem;">
                        <button class="suggestion-btn btn-post-x" onclick="NewsTracker.postToX('${containerId}', ${index})">
                            <i class="ph ph-x-logo"></i>
                            <span>Post on X</span>
                        </button>
                    </div>
                </div>

                <!-- Action Buttons -->
                <div class="news-actions" id="actions-${containerId}-${index}">
                    <button class="news-btn" onclick="NewsTracker.generatePost('${containerId}', ${index})">
                        <i class="ph ph-magic-wand"></i>
                        Generate X Post
                    </button>
                    <a href="${escapeHtml(article.link)}" target="_blank" class="news-btn">
                        <i class="ph ph-arrow-square-out"></i>
                        View Article
                    </a>
                </div>
            </div>
        `).join('');
    },

    renderImportanceStars(score) {
        const fullStars = Math.floor(score / 2); // 1-10 → 0-5 stars
        const halfStar = score % 2 >= 1;
        let stars = '';

        for (let i = 0; i < fullStars; i++) {
            stars += '<i class="ph-fill ph-star" style="color: #F59E0B;"></i>';
        }
        if (halfStar) {
            stars += '<i class="ph-fill ph-star-half" style="color: #F59E0B;"></i>';
        }

        return `<span style="display: flex; gap: 2px;" title="Importance: ${score}/10">${stars}</span>`;
    },

    async generatePost(containerId, index) {
        const articles = containerId === 'forYouList' ? this.state.forYouArticles : this.state.categoryArticles;
        const article = articles[index];

        const generating = document.getElementById(`generating-${containerId}-${index}`);
        const generated = document.getElementById(`generatedPost-${containerId}-${index}`);
        const actions = document.getElementById(`actions-${containerId}-${index}`);

        actions.style.display = 'none';
        generating.style.display = 'block';

        try {
            const response = await fetch('/news-tracker/api/generate-post', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: article.link,
                    title: article.title
                })
            });

            const data = await response.json();

            console.log('Generate post response:', { ok: response.ok, data });

            generating.style.display = 'none';

            // Check for success response
            if (response.ok && data.success) {
                const postContentEl = document.getElementById(`postContent-${containerId}-${index}`);
                if (postContentEl && data.post) {
                    postContentEl.textContent = data.post;
                    generated.style.display = 'block';

                    // Update credits if available
                    if (typeof BaseApp !== 'undefined' && typeof BaseApp.updateCredits === 'function' && data.credits_used) {
                        BaseApp.updateCredits(-data.credits_used);
                    }
                } else {
                    console.error('Missing elements or post data:', { postContentEl, post: data.post });
                    actions.style.display = 'flex';
                    showToast('Error displaying post', 'error');
                }
            } else {
                // Show error
                actions.style.display = 'flex';
                if (data.error_type === 'insufficient_credits') {
                    showToast(data.error, 'error');
                } else {
                    showToast(data.error || 'Failed to generate post', 'error');
                }
            }
        } catch (error) {
            console.error('Error generating post:', error);
            generating.style.display = 'none';
            actions.style.display = 'flex';
            showToast('Network error. Please try again.', 'error');
        }
    },

    regeneratePost(containerId, index) {
        const generated = document.getElementById(`generatedPost-${containerId}-${index}`);
        const actions = document.getElementById(`actions-${containerId}-${index}`);

        generated.style.display = 'none';
        actions.style.display = 'flex';

        this.generatePost(containerId, index);
    },

    postToX(containerId, index) {
        const postContent = document.getElementById(`postContent-${containerId}-${index}`).textContent;

        // Create X (Twitter) intent URL
        const tweetText = encodeURIComponent(postContent);
        const twitterUrl = `https://twitter.com/intent/tweet?text=${tweetText}`;

        // Open in new window
        window.open(twitterUrl, '_blank', 'width=550,height=420');
    },

    async fetchLiveFeed() {
        const feedUrl = this.state.selectedFeed;
        const feedName = this.state.selectedFeedName;

        if (!feedUrl) {
            showToast('Please select a feed', 'error');
            return;
        }

        const loading = document.getElementById('liveFeedLoading');
        const list = document.getElementById('liveFeedList');

        loading.style.display = 'flex';
        list.style.display = 'none';

        try {
            const response = await fetch('/news-tracker/api/fetch-news', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ feed_url: feedUrl })
            });

            const data = await response.json();

            if (data.success) {
                this.state.liveFeedArticles = data.news || [];
                this.renderArticles(this.state.liveFeedArticles, 'liveFeedList');
                loading.style.display = 'none';
                list.style.display = 'block';
            } else {
                throw new Error(data.error || 'Failed to fetch news');
            }
        } catch (error) {
            console.error('Error fetching live feed:', error);
            loading.style.display = 'none';
            showToast('Failed to fetch RSS feed', 'error');
        }
    }
};

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateStr) {
    try {
        const date = new Date(dateStr);
        const now = new Date();
        const diff = now - date;
        const hours = Math.floor(diff / (1000 * 60 * 60));

        if (hours < 1) return 'Just now';
        if (hours < 24) return `${hours}h ago`;
        const days = Math.floor(hours / 24);
        if (days === 1) return 'Yesterday';
        if (days < 7) return `${days}d ago`;

        // Format as "Oct 17, 2025" instead of locale-dependent format
        const options = { month: 'short', day: 'numeric', year: 'numeric' };
        return date.toLocaleDateString('en-US', options);
    } catch {
        return dateStr;
    }
}

function showToast(message, type = 'info') {
    if (typeof BaseApp !== 'undefined' && BaseApp.showToast) {
        BaseApp.showToast(message, type);
    } else {
        alert(message);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    NewsTracker.init();
});
