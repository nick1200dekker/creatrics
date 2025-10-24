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
        userSubscriptions: []
    },

    init() {
        console.log('NewsTracker initializing...');

        this.setupTabs();
        this.setupEventListeners();

        // Load categories and subscriptions, then feed
        this.loadCategories().then(() => {
            this.loadUserSubscriptions().then(() => {
                this.loadForYouFeed();
            });
        });
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
                    ${article.image ? `
                        <div class="news-image-container">
                            <img src="${escapeHtml(article.image)}" alt="${escapeHtml(article.title)}"
                                 class="news-image" loading="lazy"
                                 onerror="this.parentElement.style.display='none'">
                        </div>
                    ` : ''}
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
                        ${article.description ? `<p class="news-description">${escapeHtml(article.description)}</p>` : ''}
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
                    <div style="margin-top: 0.75rem; display: flex; gap: 0.75rem;">
                        <button class="suggestion-btn btn-copy" onclick="NewsTracker.copyPost('${containerId}', ${index})">
                            <i class="ph ph-copy"></i>
                            <span>Copy Post</span>
                        </button>
                        <button class="suggestion-btn" onclick="NewsTracker.regeneratePost('${containerId}', ${index})">
                            <i class="ph ph-arrows-clockwise"></i>
                            <span>Regenerate</span>
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

            generating.style.display = 'none';

            if (data.success) {
                document.getElementById(`postContent-${containerId}-${index}`).textContent = data.post;
                generated.style.display = 'block';

                // Update credits
                if (typeof BaseApp !== 'undefined' && data.credits_used) {
                    BaseApp.updateCredits(-data.credits_used);
                }
            } else {
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
            showToast('Failed to generate post', 'error');
        }
    },

    regeneratePost(containerId, index) {
        const generated = document.getElementById(`generatedPost-${containerId}-${index}`);
        const actions = document.getElementById(`actions-${containerId}-${index}`);

        generated.style.display = 'none';
        actions.style.display = 'flex';

        this.generatePost(containerId, index);
    },

    copyPost(containerId, index) {
        const postContent = document.getElementById(`postContent-${containerId}-${index}`).textContent;

        navigator.clipboard.writeText(postContent).then(() => {
            showToast('Post copied to clipboard', 'success');
        }).catch(err => {
            console.error('Failed to copy:', err);
            showToast('Failed to copy post', 'error');
        });
    },

    async fetchLiveFeed() {
        const selectedOption = document.querySelector('#feedMenu .dropdown-option');
        if (!selectedOption) return;

        const feedUrl = selectedOption.dataset.feed;
        const feedName = selectedOption.dataset.name;

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
        if (days < 7) return `${days}d ago`;
        return date.toLocaleDateString();
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
