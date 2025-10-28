document.addEventListener('DOMContentLoaded', function() {
    // Check if ApexCharts is loaded
    if (typeof ApexCharts === 'undefined') {
        console.error('ApexCharts library failed to load. Trying to reload...');
        // Try loading ApexCharts again
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/apexcharts@latest/dist/apexcharts.min.js';
        script.onload = function() {
            console.log('ApexCharts loaded successfully');
            initializeAnalytics();
        };
        script.onerror = function() {
            console.error('Failed to load ApexCharts');
        };
        document.head.appendChild(script);
        return;
    }

    initializeAnalytics();
});

function initializeAnalytics() {
    // Check URL parameters for platform
    const urlParams = new URLSearchParams(window.location.search);
    const platformParam = urlParams.get('platform');

    // Get connection status from data attributes or global variables
    const xConnected = window.analyticsConfig?.xConnected || false;
    const youtubeConnected = window.analyticsConfig?.youtubeConnected || false;
    const tiktokConnected = window.analyticsConfig?.tiktokConnected || false;

    // Determine initial platform based on URL parameter or connected accounts
    let defaultPlatform = 'none';
    if (xConnected) defaultPlatform = 'x';
    else if (youtubeConnected) defaultPlatform = 'youtube';
    else if (tiktokConnected) defaultPlatform = 'tiktok';

    let currentPlatform = platformParam || defaultPlatform;

    // Validate platform parameter against connected accounts
    if (platformParam === 'x' && !xConnected) {
        currentPlatform = defaultPlatform;
    } else if (platformParam === 'youtube' && !youtubeConnected) {
        currentPlatform = defaultPlatform;
    } else if (platformParam === 'tiktok' && !tiktokConnected) {
        currentPlatform = defaultPlatform;
    }

    // Utility function to format numbers
    function formatNumber(num) {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num.toLocaleString();
    }

    // Function to get chart colors based on theme
    function getChartColors() {
        const isDarkMode = document.documentElement.classList.contains('dark');
        return {
            text: isDarkMode ? '#d1d5db' : '#6b7280',
            title: isDarkMode ? '#9ca3af' : '#6b7280',
            grid: isDarkMode ? '#374151' : '#e5e7eb',
            tooltip: isDarkMode ? 'dark' : 'light',
            background: 'transparent'
        };
    }

    // Common chart defaults
    function getChartDefaults() {
        return {
            chart: {
                background: 'transparent',
                toolbar: { show: false },
                zoom: { enabled: false },
                fontFamily: 'Inter, sans-serif',
                animations: {
                    enabled: true,
                    speed: 400,
                    animateGradually: {
                        enabled: true,
                        delay: 50
                    }
                }
            },
            grid: {
                borderColor: getChartColors().grid,
                strokeDashArray: 3
            },
            tooltip: {
                theme: getChartColors().tooltip
            }
        };
    }

    let currentTimeframe = '30days';
    let chartViews = {
        impressions: 'daily',
        engagement: 'daily'
    };
    let xPostsData = {
        all: [],
        currentPage: 1,
        itemsPerPage: 12,
        currentFilter: 'all'
    };
    let charts = {};
    
    // Destroy all charts safely
    function destroyAllCharts() {
        Object.keys(charts).forEach(key => {
            if (charts[key] && typeof charts[key].destroy === 'function') {
                try {
                    charts[key].destroy();
                } catch (e) {
                    console.warn('Error destroying chart:', key, e);
                }
                charts[key] = null;
            }
        });
    }
    
    // Timeframe change handler
    window.changeTimeframe = function(timeframe) {
        currentTimeframe = timeframe;
        
        document.querySelectorAll('.timeframe-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.timeframe === timeframe) {
                btn.classList.add('active');
            }
        });
        
        const impressionsTitle = document.getElementById('impressions-title');
        const engagementTitle = document.getElementById('engagement-title');
        const postsCountTitle = document.getElementById('posts-count-title');
        const followersTitle = document.getElementById('followers-title');
        const impressionsDailyBtn = document.getElementById('impressions-daily-btn');
        const engagementDailyBtn = document.getElementById('engagement-daily-btn');
        
        if (timeframe === '6months') {
            if (impressionsTitle) impressionsTitle.textContent = 'Weekly Impressions';
            if (engagementTitle) engagementTitle.textContent = 'Weekly Engagement';
            if (postsCountTitle) postsCountTitle.textContent = 'Weekly Posts Count';
            if (followersTitle) followersTitle.textContent = 'Followers Growth';
            if (impressionsDailyBtn) impressionsDailyBtn.textContent = 'Weekly';
            if (engagementDailyBtn) engagementDailyBtn.textContent = 'Weekly';
        } else {
            if (impressionsTitle) impressionsTitle.textContent = 'Daily Impressions';
            if (engagementTitle) engagementTitle.textContent = 'Daily Engagement';
            if (postsCountTitle) postsCountTitle.textContent = 'Daily Posts Count';
            if (followersTitle) followersTitle.textContent = 'Followers Growth';
            if (impressionsDailyBtn) impressionsDailyBtn.textContent = 'Daily';
            if (engagementDailyBtn) engagementDailyBtn.textContent = 'Daily';
        }
        
        // Load appropriate analytics based on current platform
        if (currentPlatform === 'x') {
            loadXAnalytics();
        } else if (currentPlatform === 'youtube') {
            loadYouTubeAnalytics();
        } else if (currentPlatform === 'tiktok') {
            loadTikTokAnalytics();
        }
    };
    
    // Platform switching
    window.switchPlatform = function(platform) {
        // Destroy all existing charts before switching
        destroyAllCharts();
        
        // Update active states
        document.querySelectorAll('.platform-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.platform === platform) {
                btn.classList.add('active');
            }
        });
        
        // Hide all content tabs
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        
        // Show selected platform content
        const contentElement = document.getElementById(`${platform}-content`);
        if (contentElement) {
            contentElement.classList.add('active');
        }
        
        currentPlatform = platform;

        // Show timeframe selector for all platforms
        const timeframeSelector = document.querySelector('.timeframe-selector');
        if (timeframeSelector) {
            timeframeSelector.style.visibility = 'visible';
            timeframeSelector.style.opacity = '1';
            timeframeSelector.style.pointerEvents = 'auto';
            timeframeSelector.title = '';
        }

        // Add delay to ensure DOM is ready and animations complete
        setTimeout(() => {
            if (platform === 'x' && contentElement) {
                loadXAnalytics();
            } else if (platform === 'youtube' && contentElement) {
                loadYouTubeAnalytics();
            } else if (platform === 'tiktok' && contentElement) {
                loadTikTokAnalytics();
            }
        }, 100);
    };
    
    // Toggle chart view
    window.toggleChartView = function(chartType, viewType) {
        chartViews[chartType] = viewType;
        
        const chartCard = document.querySelector(`#x-${chartType}-chart`).closest('.chart-card');
        const toggleBtns = chartCard.querySelectorAll('.toggle-btn');
        toggleBtns.forEach(btn => {
            btn.classList.remove('active');
            
            if ((viewType === 'daily' && (btn.textContent.includes('Daily') || btn.textContent.includes('Weekly'))) ||
                (viewType === 'rolling' && btn.textContent.includes('Rolling'))) {
                btn.classList.add('active');
            }
        });
        
        if (chartType === 'impressions') {
            loadImpressionsChart();
        } else if (chartType === 'engagement') {
            loadEngagementChart();
        }
    };

    function getTickInterval(timeframe) {
        const intervals = {
            '7days': 1,
            '30days': 5,
            '90days': 15,
            '6months': 30
        };
        return intervals[timeframe] || 30;
    }
    
    // X Analytics functions
    function loadXAnalytics() {
        fetch(`/analytics/x/overview?timeframe=${currentTimeframe}`, {
            credentials: 'include'
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    showXError(data.error);
                    return;
                }
                renderXMetrics(data.current, data.trends);
            })
            .catch(error => {
                console.error('Error loading X overview:', error);
                showXError('Failed to load analytics data');
            });

        loadImpressionsChart();
        loadEngagementChart();
        loadPostsCountChart();
        loadFollowersChart();
        loadXPosts('all');
    }
    
    function renderXMetrics(metrics, trends) {
        const metricsGrid = document.getElementById('x-metrics-grid');
        
        const getTrendIcon = (trend) => {
            if (trend > 0) return '<i class="ph ph-trending-up"></i>';
            if (trend < 0) return '<i class="ph ph-trending-down"></i>';
            return '<i class="ph ph-minus"></i>';
        };
        
        const getTrendClass = (trend) => {
            if (trend > 0) return 'trend-up';
            if (trend < 0) return 'trend-down';
            return 'trend-neutral';
        };
        
        metricsGrid.innerHTML = `
            <div class="metric-card">
                <div class="metric-label">
                    <i class="ph ph-users"></i>
                    Followers
                </div>
                <div class="metric-value">${formatNumber(metrics.followers_count || 0)}</div>
                <div class="metric-trend ${getTrendClass(trends?.followers_trend || 0)}">
                    ${getTrendIcon(trends?.followers_trend || 0)}
                    <span>${Math.abs(trends?.followers_trend || 0).toFixed(1)}%</span>
                </div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">
                    <i class="ph ph-eye"></i>
                    Avg Views Per Post
                </div>
                <div class="metric-value">${formatNumber(Math.round(metrics.avg_views_per_post || 0))}</div>
                <div class="text-xs mt-2 text-gray-400">
                    ${metrics.posts_in_timeframe || 0} posts in timeframe
                </div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">
                    <i class="ph ph-heart"></i>
                    Engagement Rate
                </div>
                <div class="metric-value">${(metrics.timeframe_engagement_rate || 0).toFixed(1)}%</div>
                <div class="text-xs mt-2 text-gray-400">
                    ${metrics.posts_in_timeframe || 0} posts in timeframe
                </div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">
                    <i class="ph ph-scales"></i>
                    Following Ratio
                </div>
                <div class="metric-value">${(metrics.followers_to_following_ratio || 0).toFixed(1)}%</div>
                <div class="text-xs mt-2 ${
                    metrics.ratio_status === 'Good' ? 'text-green-400' : 
                    metrics.ratio_status === 'Average' ? 'text-yellow-400' : 'text-red-400'
                }">
                    ${metrics.ratio_status || 'N/A'}
                </div>
            </div>
        `;
    }
    
    function loadImpressionsChart() {
        const container = document.getElementById('x-impressions-chart');
        if (!container) return;
        
        container.innerHTML = '<div class="loading-container"><div class="loading-spinner"><i class="ph ph-spinner spin"></i></div></div>';

        fetch(`/analytics/x/impressions?timeframe=${currentTimeframe}`, {
            credentials: 'include'
        })
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    renderImpressionsChart(data.impressions_data, data.has_sufficient_data);
                } else {
                    container.innerHTML = '<div class="empty-state">Failed to load impressions data</div>';
                }
            })
            .catch(error => {
                console.error('Error loading impressions:', error);
                container.innerHTML = '<div class="empty-state">Failed to load impressions data</div>';
            });
    }
    
    function renderImpressionsChart(impressionsData, hasSufficientData) {
        const container = document.getElementById('x-impressions-chart');
        if (!container || !impressionsData || impressionsData.length === 0) {
            container.innerHTML = '<div class="empty-state">No impressions data available</div>';
            return;
        }
        container.innerHTML = '';
        
        const noteElement = document.getElementById('x-impressions-note');
        if (noteElement) {
            if (chartViews.impressions === 'rolling' && !hasSufficientData) {
                noteElement.classList.remove('hidden');
            } else {
                noteElement.classList.add('hidden');
            }
        }
        
        const isWeekly = impressionsData[0]?.is_week || false;
        const series = [];
        
        if (chartViews.impressions === 'rolling') {
            const rollingData = impressionsData
                .filter(d => d.rolling_avg !== null && d.rolling_avg !== undefined)
                .map(d => ({ x: d.date, y: Math.round(d.rolling_avg) }));
            series.push({ name: 'Rolling Avg (10 Posts)', data: rollingData });
        } else {
            series.push({
                name: isWeekly ? 'Weekly Impressions' : 'Daily Impressions',
                data: impressionsData.map(d => ({ x: d.date, y: d.daily_impressions || 0 }))
            });
        }
        
        const chartOptions = {
            ...getChartDefaults(),
            series: series,
            chart: {
                ...getChartDefaults().chart,
                type: chartViews.impressions === 'rolling' ? 'line' : 'bar',
                height: 300
            },
            dataLabels: { enabled: false },
            stroke: { 
                curve: 'smooth', 
                width: chartViews.impressions === 'rolling' ? 3 : 0,
                lineCap: 'round'
            },
            plotOptions: { 
                bar: { 
                    columnWidth: '70%', 
                    borderRadius: 4 
                } 
            },
            colors: ['#3B82F6'],
            xaxis: {
                type: 'datetime',
                labels: { 
                    style: { colors: getChartColors().text, fontSize: '11px' }, 
                    rotate: -45,
                    rotateAlways: false
                },
                tickAmount: getTickInterval(currentTimeframe)
            },
            yaxis: {
                title: {
                    text: 'Impressions',
                    style: { color: getChartColors().title },
                    offsetX: 10  // Move title to the right to prevent cutoff
                },
                labels: {
                    style: { colors: getChartColors().text },
                    formatter: function(val) {
                        if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
                        if (val >= 1000) return (val / 1000).toFixed(0) + 'K';
                        return Math.round(val).toString();
                    }
                }
            },
            tooltip: {
                ...getChartDefaults().tooltip,
                y: { 
                    formatter: function(val) { 
                        return val.toLocaleString() + ' impressions'; 
                    } 
                }
            },
            legend: { show: false },
            markers: {
                size: 0,
                strokeWidth: 0,
                hover: {
                    size: chartViews.impressions === 'rolling' ? 6 : 0
                }
            }
        };
        
        if (charts.impressions) {
            try {
                charts.impressions.destroy();
            } catch (e) {}
        }
        charts.impressions = new ApexCharts(container, chartOptions);
        charts.impressions.render();
    }

    function loadEngagementChart() {
        const container = document.getElementById('x-engagement-chart');
        if (!container) return;
        
        container.innerHTML = '<div class="loading-container"><div class="loading-spinner"><i class="ph ph-spinner spin"></i></div></div>';
        
        fetch(`/analytics/x/engagement?timeframe=${currentTimeframe}`, {
            credentials: 'include'
        })
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    renderEngagementChart(data.engagement_data, data.has_sufficient_data);
                } else {
                    container.innerHTML = '<div class="empty-state">Failed to load engagement data</div>';
                }
            })
            .catch(error => {
                console.error('Error loading engagement:', error);
                container.innerHTML = '<div class="empty-state">Failed to load engagement data</div>';
            });
    }
    
    function renderEngagementChart(engagementData, hasSufficientData) {
        const container = document.getElementById('x-engagement-chart');
        if (!engagementData || engagementData.length === 0) {
            container.innerHTML = '<div class="empty-state">No engagement data available</div>';
            return;
        }
        container.innerHTML = '';
        
        const series = [];
        if (chartViews.engagement === 'rolling') {
            const rollingData = engagementData
                .filter(d => d.rolling_engagement_rate !== null)
                .map(d => ({ x: d.date, y: d.rolling_engagement_rate }));
            series.push({ name: 'Rolling Avg (10 Posts)', type: 'line', data: rollingData });
        } else {
            series.push({
                name: 'Engagement Rate', type: 'line',
                data: engagementData.map(d => ({ x: d.date, y: d.engagement_rate || 0 }))
            });
            series.push({
                name: 'Total Engagements', type: 'column',
                data: engagementData.map(d => ({ x: d.date, y: Math.round(d.total_engagement || 0) }))
            });
        }
        
        const chartOptions = {
            ...getChartDefaults(),
            series: series,
            chart: { 
                ...getChartDefaults().chart,
                height: 300, 
                type: 'line'
            },
            stroke: { 
                width: chartViews.engagement === 'rolling' ? [3] : [3, 0], 
                curve: ['smooth', 'straight'],
                lineCap: 'round'
            },
            plotOptions: {
                bar: {
                    columnWidth: '70%',
                    borderRadius: 4
                }
            },
            fill: {
                type: 'solid',
                opacity: chartViews.engagement === 'rolling' ? [1] : [1, 0.8]
            },
            colors: chartViews.engagement === 'rolling' ? ['#3B82F6'] : ['#3B82F6', '#60A5FA'],
            xaxis: { 
                type: 'datetime', 
                labels: { 
                    style: { colors: getChartColors().text, fontSize: '11px' },
                    rotate: -45,
                    rotateAlways: false
                },
                tickAmount: getTickInterval(currentTimeframe)
            },
            yaxis: chartViews.engagement === 'rolling' ?
                {
                    title: { text: 'Engagement Rate (%)', style: { color: getChartColors().title } },
                    labels: {
                        style: { colors: getChartColors().text },
                        formatter: function(val) {
                            return val !== null ? val.toFixed(1) + '%' : '';
                        }
                    },
                    min: 0
                } :
                [
                    {
                        title: { text: 'Engagement Rate (%)', style: { color: getChartColors().title } },
                        labels: {
                            style: { colors: getChartColors().text },
                            formatter: function(val) {
                                return val.toFixed(1) + '%';
                            }
                        },
                        min: 0
                    },
                    {
                        opposite: true,
                        title: { text: 'Total Engagements', style: { color: getChartColors().title } },
                        labels: {
                            style: { colors: getChartColors().text },
                            formatter: function(val) {
                                if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
                                if (val >= 1000) return (val / 1000).toFixed(0) + 'K';
                                return Math.round(val).toString();
                            }
                        },
                        min: 0
                    }
                ],
            tooltip: { 
                ...getChartDefaults().tooltip,
                shared: chartViews.engagement === 'rolling' ? false : true,
                intersect: false,
                y: {
                    formatter: function(val, opts) {
                        if (chartViews.engagement === 'rolling') {
                            return val !== null ? val.toFixed(1) + '%' : 'No data';
                        } else {
                            if (opts && opts.seriesIndex === 0) {
                                return val.toFixed(1) + '%';
                            } else {
                                return Math.round(val).toLocaleString() + ' engagements';
                            }
                        }
                    }
                }
            },
            legend: { show: false },
            markers: {
                size: 0,
                strokeWidth: 0,
                hover: {
                    size: chartViews.engagement === 'rolling' ? 6 : 4
                }
            },
            dataLabels: { enabled: false }
        };
        
        if (charts.engagement) {
            try {
                charts.engagement.destroy();
            } catch (e) {}
        }
        charts.engagement = new ApexCharts(container, chartOptions);
        charts.engagement.render();
    }

    function loadPostsCountChart() {
        const container = document.getElementById('x-posts-count-chart');
        if (!container) return;

        container.innerHTML = '<div class="loading-container"><div class="loading-spinner"><i class="ph ph-spinner spin"></i></div></div>';

        fetch(`/analytics/x/posts-count?timeframe=${currentTimeframe}`, {
            credentials: 'include'
        })
            .then(response => response.json())
            .then(data => {
                if (!data.error) renderPostsCountChart(data.posts_count_data);
            });
    }
    
    function renderPostsCountChart(data) {
        if (!data || data.length === 0) return;
        const container = document.getElementById('x-posts-count-chart');
        if (!container) return;
        
        container.innerHTML = '';
        
        const isWeekly = data[0]?.is_week || false;
        
        const chartOptions = {
            ...getChartDefaults(),
            series: [{ 
                name: isWeekly ? 'Weekly Posts' : 'Daily Posts', 
                data: data.map(d => ({ x: d.date, y: d.posts_count || 0 })) 
            }],
            chart: { 
                ...getChartDefaults().chart,
                type: 'bar', 
                height: 300
            },
            plotOptions: {
                bar: {
                    borderRadius: 4,
                    columnWidth: '60%'
                }
            },
            dataLabels: { enabled: false },
            colors: ['#8B5CF6'],
            xaxis: { 
                type: 'datetime',
                labels: {
                    style: { colors: getChartColors().text, fontSize: '11px' },
                    rotate: -45,
                    rotateAlways: false
                },
                tickAmount: getTickInterval(currentTimeframe)
            },
            yaxis: {
                title: {
                    text: 'Number of Posts',
                    style: { color: getChartColors().title },
                    offsetX: 10  // Move title to the right to prevent cutoff
                },
                labels: {
                    style: { colors: getChartColors().text },
                    formatter: function(val) {
                        return Math.round(val).toString();
                    }
                },
                min: 0
            },
            tooltip: {
                ...getChartDefaults().tooltip,
                y: {
                    formatter: function(val) {
                        return val + ' posts';
                    }
                }
            },
            legend: { show: false }
        };
        
        if (charts.postsCount) {
            try {
                charts.postsCount.destroy();
            } catch (e) {}
        }
        charts.postsCount = new ApexCharts(container, chartOptions);
        charts.postsCount.render();
    }

    function loadFollowersChart() {
        const container = document.getElementById('x-followers-chart');
        if (!container) return;

        container.innerHTML = '<div class="loading-container"><div class="loading-spinner"><i class="ph ph-spinner spin"></i></div></div>';

        fetch(`/analytics/x/followers-history?timeframe=${currentTimeframe}`, {
            credentials: 'include'
        })
            .then(response => response.json())
            .then(data => {
                if (!data.error) renderFollowersChart(data.followers_data);
            });
    }
    
    function renderFollowersChart(data) {
        if (!data || data.length === 0) return;
        const container = document.getElementById('x-followers-chart');
        if (!container) return;
        
        container.innerHTML = '';
        
        const isWeekly = data[0]?.is_week || false;
        const followers = data.map(d => d.followers_count || 0);
        const maxFollowers = Math.max(...followers);
        
        const chartOptions = {
            ...getChartDefaults(),
            series: [{
                name: 'Total Followers',
                type: 'line',
                data: data.map(d => ({ x: d.date, y: d.followers_count || 0 }))
            }],
            chart: {
                ...getChartDefaults().chart,
                height: 300,
                type: 'line'
            },
            stroke: {
                width: [3],
                curve: 'smooth',
                lineCap: 'round'
            },
            colors: ['#3B82F6'],
            dataLabels: { enabled: false },
            xaxis: {
                type: 'datetime',
                labels: {
                    style: { colors: getChartColors().text, fontSize: '11px' },
                    rotate: -45,
                    rotateAlways: false
                },
                tickAmount: getTickInterval(currentTimeframe)
            },
            yaxis: {
                title: { text: 'Total Followers', style: { color: getChartColors().title } },
                labels: {
                    style: { colors: getChartColors().text },
                    formatter: function(val) {
                        if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
                        if (val >= 1000) return (val / 1000).toFixed(1) + 'K';
                        return Math.round(val).toString();
                    }
                },
                min: Math.floor(Math.min(...followers) * 0.95),
                max: Math.ceil(maxFollowers * 1.05)
            },
            tooltip: {
                ...getChartDefaults().tooltip,
                y: {
                    formatter: function(val) {
                        return val.toLocaleString() + ' followers';
                    }
                }
            },
            legend: {
                show: false
            },
            markers: {
                size: 0,
                strokeWidth: 0,
                hover: {
                    size: 6
                }
            }
        };
        
        if (charts.followers) {
            try {
                charts.followers.destroy();
            } catch (e) {}
        }
        charts.followers = new ApexCharts(container, chartOptions);
        charts.followers.render();
    }

    function loadXPosts(filter) {
        xPostsData.currentFilter = filter;
        xPostsData.currentPage = 1;

        fetch(`/analytics/x/posts-paginated?page=1&per_page=${xPostsData.itemsPerPage}&filter=${filter}`, {
            credentials: 'include'
        })
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    xPostsData.all = data.posts || [];
                    renderXPosts();
                    renderXPostsPagination(data.total_posts, data.total_pages);
                }
            });
    }

    window.loadXPosts = loadXPosts;
    
    function renderXPosts() {
        const tbody = document.getElementById('x-posts-tbody');
        const posts = xPostsData.all;
        
        if (!posts || posts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center"><div class="empty-state">No Posts Found</div></td></tr>';
            return;
        }
        
        tbody.innerHTML = posts.map(post => `
            <tr>
                <td><div class="post-preview">${post.text || 'No text'}</div></td>
                <td>${new Date(post.created_at).toLocaleDateString()}</td>
                <td class="font-medium">${formatNumber(post.views || 0)}</td>
                <td>${formatNumber(post.likes || 0)}</td>
                <td>${formatNumber(post.retweets || 0)}</td>
                <td>${formatNumber(post.replies || 0)}</td>
                <td><span class="engagement-badge">${(post.engagement_rate || 0).toFixed(1)}%</span></td>
                <td>${post.id ? `<a href="https://twitter.com/i/web/status/${post.id}" target="_blank" class="post-link">View</a>` : '-'}</td>
            </tr>
        `).join('');
    }
    
    function renderXPostsPagination(totalPosts, totalPages) {
        const pagination = document.getElementById('x-posts-pagination');
        if (!pagination) return;
        
        const currentPage = xPostsData.currentPage;
        pagination.innerHTML = `
            <button class="pagination-btn" onclick="changePage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>Previous</button>
            <span class="pagination-info">Page ${currentPage} of ${totalPages}</span>
            <button class="pagination-btn" onclick="changePage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>Next</button>
        `;
    }
    
    window.changePage = function(page) {
        if (page < 1) return;
        xPostsData.currentPage = page;
        
        fetch(`/analytics/x/posts-paginated?page=${page}&per_page=${xPostsData.itemsPerPage}&filter=${xPostsData.currentFilter}`, {
            credentials: 'include'
        })
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    xPostsData.all = data.posts || [];
                    renderXPosts();
                    renderXPostsPagination(data.total_posts, data.total_pages);
                }
            });
    };

    // YouTube Analytics functions
    function loadYouTubeAnalytics() {
        // Clear any existing charts first
        destroyYouTubeCharts();
        
        // Add delay to ensure DOM is ready
        setTimeout(() => {
            loadYouTubeDailyData();
        }, 100);
    }
    
    function destroyYouTubeCharts() {
        ['youtubeViews', 'youtubeTraffic'].forEach(key => {
            if (charts[key]) {
                try {
                    charts[key].destroy();
                } catch (e) {}
                charts[key] = null;
            }
        });
    }
    
    function loadYouTubeDailyData() {
        // Show loading spinners for YouTube charts
        const viewsChart = document.getElementById('youtube-views-chart');
        const trafficChart = document.getElementById('youtube-traffic-chart');
        if (viewsChart) viewsChart.innerHTML = '<div class="loading-container"><div class="loading-spinner"><i class="ph ph-spinner spin"></i></div></div>';
        if (trafficChart) trafficChart.innerHTML = '<div class="loading-container"><div class="loading-spinner"><i class="ph ph-spinner spin"></i></div></div>';

        fetch(`/analytics/youtube/daily-views?timeframe=${currentTimeframe}`, {
            credentials: 'include'
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    showYouTubeError('No daily data available');
                    return;
                }

                if (data.calculated_metrics) {
                    renderYouTubeMetrics(data.calculated_metrics);
                }

                renderYouTubeChartsWithDailyData(data.daily_data, data.calculated_metrics);
                loadYouTubeTopVideos();
            })
            .catch(error => {
                console.error('Error loading YouTube daily data:', error);
                showYouTubeError('Failed to load analytics data');
            });
    }
    
    function loadYouTubeTopVideos() {
        fetch(`/analytics/youtube/top-videos?timeframe=${currentTimeframe}`, {
            credentials: 'include'
        })
            .then(response => response.json())
            .then(data => {
                if (!data.error) renderYouTubeVideos(data.top_videos || []);
            });
    }
    
    function renderYouTubeMetrics(metrics) {
        const metricsGrid = document.getElementById('youtube-metrics-grid');
        
        metricsGrid.innerHTML = `
            <div class="metric-card">
                <div class="metric-label"><i class="ph ph-eye"></i> Total Views</div>
                <div class="metric-value">${formatNumber(metrics.views || 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label"><i class="ph ph-clock"></i> Watch Time</div>
                <div class="metric-value">${formatNumber(metrics.watch_time_hours || 0)}h</div>
            </div>
            <div class="metric-card">
                <div class="metric-label"><i class="ph ph-timer"></i> Avg View Duration</div>
                <div class="metric-value">${Math.floor((metrics.avg_view_duration_seconds || 0) / 60)}:${((metrics.avg_view_duration_seconds || 0) % 60).toString().padStart(2, '0')}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label"><i class="ph ph-users-three"></i> Subscribers Gained</div>
                <div class="metric-value">+${formatNumber(metrics.subscribers_gained || 0)}</div>
            </div>
        `;
    }
    
    function renderYouTubeChartsWithDailyData(dailyData, overviewData) {
        const viewsContainer = document.querySelector("#youtube-views-chart");
        if (viewsContainer && dailyData && dailyData.length > 0) {
            viewsContainer.innerHTML = '';
            
            const viewsOptions = {
                ...getChartDefaults(),
                series: [
                    { name: 'Views', type: 'column', data: dailyData.map(d => ({ x: d.date, y: d.views || 0 })) },
                    { name: 'Watch Time (hrs)', type: 'line', data: dailyData.map(d => ({ x: d.date, y: d.watch_time_hours || 0 })) }
                ],
                chart: { 
                    ...getChartDefaults().chart,
                    height: 300, 
                    type: 'line'
                },
                stroke: {
                    width: [0, 3],
                    curve: 'smooth'
                },
                plotOptions: {
                    bar: {
                        columnWidth: '60%',
                        borderRadius: 4
                    }
                },
                colors: ['#3B82F6', '#10B981'],
                xaxis: { 
                    type: 'datetime',
                    labels: {
                        style: { colors: getChartColors().text },
                        rotate: -45
                    }
                },
                yaxis: [
                    {
                        title: { text: 'Views', style: { color: getChartColors().title } },
                        labels: {
                            style: { colors: getChartColors().text },
                            formatter: function(val) {
                                if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
                                if (val >= 1000) return (val / 1000).toFixed(0) + 'K';
                                return Math.round(val).toString();
                            }
                        }
                    },
                    {
                        opposite: true,
                        title: { text: 'Watch Time (hrs)', style: { color: getChartColors().title } },
                        labels: {
                            style: { colors: getChartColors().text },
                            formatter: function(val) {
                                return val.toFixed(2) + 'h';
                            }
                        }
                    }
                ],
                legend: {
                    show: true,
                    position: 'top',
                    labels: { colors: getChartColors().text }
                },
                dataLabels: { enabled: false }
            };
            
            if (charts.youtubeViews) {
                try {
                    charts.youtubeViews.destroy();
                } catch (e) {}
            }
            charts.youtubeViews = new ApexCharts(viewsContainer, viewsOptions);
            charts.youtubeViews.render();
        }
        
        renderTrafficSourcesChart(overviewData);
    }
    
    function renderTrafficSourcesChart(metrics) {
        const trafficContainer = document.querySelector("#youtube-traffic-chart");
        if (trafficContainer) {
            trafficContainer.innerHTML = '';
            
            if (metrics.traffic_sources && metrics.traffic_sources.length > 0) {
                const trafficOptions = {
                    ...getChartDefaults(),
                    series: metrics.traffic_sources.map(s => s.views),
                    chart: { 
                        ...getChartDefaults().chart,
                        type: 'donut', 
                        height: 300
                    },
                    labels: metrics.traffic_sources.map(s => s.source),
                    colors: ['#3B82F6', '#60A5FA', '#EF4444', '#F59E0B', '#8B5CF6'],
                    legend: {
                        position: 'bottom',
                        labels: { colors: getChartColors().text }
                    },
                    dataLabels: { enabled: false },
                    plotOptions: {
                        pie: {
                            donut: {
                                size: '65%'
                            }
                        }
                    }
                };
                
                if (charts.youtubeTraffic) {
                    try {
                        charts.youtubeTraffic.destroy();
                    } catch (e) {}
                }
                charts.youtubeTraffic = new ApexCharts(trafficContainer, trafficOptions);
                charts.youtubeTraffic.render();
            } else {
                trafficContainer.innerHTML = '<div class="empty-state">No traffic data available</div>';
            }
        }
    }
    
    function renderYouTubeVideos(videos) {
        const tbody = document.getElementById('youtube-videos-tbody');

        if (!videos || videos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center"><div class="empty-state">No Videos Found</div></td></tr>';
            return;
        }

        tbody.innerHTML = videos.map(video => {
            const thumbnailHtml = video.thumbnail
                ? `<img src="${video.thumbnail}" alt="${video.title || 'Video'}" style="width: 80px; height: 45px; object-fit: cover; border-radius: 4px; margin-right: 12px;">`
                : '';
            const videoTitle = video.title || `Video ${video.id}`;

            return `
                <tr>
                    <td>
                        <a href="https://youtube.com/watch?v=${video.id}" target="_blank" class="post-link" style="display: flex; align-items: center; text-decoration: none;">
                            ${thumbnailHtml}
                            <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${videoTitle}</span>
                        </a>
                    </td>
                    <td class="font-medium">${formatNumber(video.views || 0)}</td>
                    <td>${(video.watch_time_minutes / 60).toFixed(1)}</td>
                    <td>${Math.floor((video.avg_view_duration || 0) / 60)}:${((video.avg_view_duration || 0) % 60).toString().padStart(2, '0')}</td>
                    <td>${formatNumber(video.likes || 0)}</td>
                    <td>${formatNumber(video.comments || 0)}</td>
                    <td><span class="engagement-badge">${(video.engagement_rate || 0).toFixed(1)}%</span></td>
                </tr>
            `;
        }).join('');
    }

    // TikTok Analytics functions
    function loadTikTokAnalytics() {
        // Clear any existing charts first
        destroyTikTokCharts();
        
        // Get current timeframe
        const timeframe = currentTimeframe || '30days';
        console.log(`Loading TikTok analytics with timeframe: ${timeframe}`);

        // Load overview metrics
        fetch('/analytics/tiktok/overview', {
            credentials: 'include'
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    showTikTokError(data.error);
                    return;
                }
                renderTikTokMetrics(data.current, timeframe);
            })
            .catch(error => {
                console.error('Error loading TikTok overview:', error);
                showTikTokError('Failed to load TikTok analytics');
            });

        // Load posts and render charts with timeframe
        loadTikTokPosts('recent');
        loadTikTokCharts(timeframe);
    }
    
    function destroyTikTokCharts() {
        ['tiktokViews', 'tiktokEngagement', 'tiktokFrequency'].forEach(key => {
            if (charts[key]) {
                try {
                    charts[key].destroy();
                } catch (e) {}
                charts[key] = null;
            }
        });
    }

    function loadTikTokCharts(timeframe = '30days') {
        // Show loading spinners for TikTok charts
        const viewsChart = document.getElementById('tiktok-views-chart');
        const engagementChart = document.getElementById('tiktok-engagement-chart');
        const frequencyChart = document.getElementById('tiktok-frequency-chart');
        if (viewsChart) viewsChart.innerHTML = '<div class="loading-container"><div class="loading-spinner"><i class="ph ph-spinner spin"></i></div></div>';
        if (engagementChart) engagementChart.innerHTML = '<div class="loading-container"><div class="loading-spinner"><i class="ph ph-spinner spin"></i></div></div>';
        if (frequencyChart) frequencyChart.innerHTML = '<div class="loading-container"><div class="loading-spinner"><i class="ph ph-spinner spin"></i></div></div>';

        fetch('/analytics/tiktok/posts', {
            credentials: 'include'
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    return;
                }
                const posts = data.posts || [];

                // Filter posts by timeframe
                const filteredPosts = filterPostsByTimeframe(posts, timeframe);

                renderTikTokViewsChart(filteredPosts);
                renderTikTokEngagementChart(filteredPosts);
                renderTikTokFrequencyChart(filteredPosts);
            })
            .catch(error => {
                console.error('Error loading TikTok charts:', error);
            });
    }

    // Helper function to filter TikTok posts by timeframe
    function filterPostsByTimeframe(posts, timeframe) {
        const now = new Date();
        let cutoffDate;

        switch(timeframe) {
            case '7days':
                cutoffDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                break;
            case '30days':
                cutoffDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
                break;
            case '90days':
                cutoffDate = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
                break;
            case '6months':
                cutoffDate = new Date(now.getTime() - 180 * 24 * 60 * 60 * 1000);
                break;
            default:
                cutoffDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        }

        const filtered = posts.filter(post => {
            const postDate = new Date(post.create_time * 1000);
            return postDate >= cutoffDate;
        });

        return filtered;
    }

    function renderTikTokViewsChart(posts) {
        const chartElement = document.getElementById('tiktok-views-chart');
        if (!chartElement) return;

        chartElement.innerHTML = '';

        // Group posts by date and sum views
        const viewsByDate = {};
        posts.forEach(post => {
            const createTime = post.create_time;
            if (createTime) {
                const date = new Date(createTime * 1000);
                const dateStr = date.toISOString().split('T')[0];
                viewsByDate[dateStr] = (viewsByDate[dateStr] || 0) + (post.views || 0);
            }
        });

        // Calculate date range based on current timeframe (not post dates)
        const now = new Date();
        now.setHours(0, 0, 0, 0);
        const timeframe = currentTimeframe || '30days';
        let daysBack;

        switch(timeframe) {
            case '7days': daysBack = 7; break;
            case '30days': daysBack = 30; break;
            case '90days': daysBack = 90; break;
            case '6months': daysBack = 180; break;
            default: daysBack = 30;
        }

        // Fill in all dates in timeframe with 0 for missing dates
        const chartData = [];
        for (let i = daysBack; i >= 0; i--) {
            const date = new Date(now);
            date.setDate(date.getDate() - i);
            // Use local date string instead of UTC to avoid timezone issues
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const dateStr = `${year}-${month}-${day}`;
            chartData.push({
                x: new Date(dateStr).getTime(),
                y: viewsByDate[dateStr] || 0
            });
        }

        const options = {
            ...getChartDefaults(),
            series: [{
                name: 'Views',
                data: chartData
            }],
            chart: {
                ...getChartDefaults().chart,
                type: 'bar',
                height: 300
            },
            plotOptions: {
                bar: {
                    borderRadius: 4,
                    columnWidth: '70%'
                }
            },
            dataLabels: { enabled: false },
            colors: ['#3B82F6'],
            xaxis: {
                type: 'datetime',
                labels: {
                    format: 'MMM dd',
                    style: { colors: getChartColors().text, fontSize: '11px' },
                    rotate: -45
                }
            },
            yaxis: {
                labels: {
                    style: { colors: getChartColors().text },
                    formatter: function(val) {
                        return formatNumber(val);
                    }
                }
            },
            tooltip: {
                ...getChartDefaults().tooltip,
                x: {
                    format: 'MMM dd, yyyy'
                },
                y: {
                    formatter: function(val) {
                        return formatNumber(val) + ' views';
                    }
                }
            }
        };

        if (charts.tiktokViews) {
            try {
                charts.tiktokViews.destroy();
            } catch (e) {}
        }
        charts.tiktokViews = new ApexCharts(chartElement, options);
        charts.tiktokViews.render();
    }

    function renderTikTokEngagementChart(posts) {
        const chartElement = document.getElementById('tiktok-engagement-chart');
        if (!chartElement) return;

        chartElement.innerHTML = '';

        // Group posts by date and calculate average engagement rate
        const engagementByDate = {};
        const countByDate = {};

        posts.forEach(post => {
            const createTime = post.create_time;
            if (createTime) {
                const date = new Date(createTime * 1000);
                const dateStr = date.toISOString().split('T')[0];

                if (!engagementByDate[dateStr]) {
                    engagementByDate[dateStr] = 0;
                    countByDate[dateStr] = 0;
                }

                engagementByDate[dateStr] += (post.engagement_rate || 0);
                countByDate[dateStr]++;
            }
        });

        // Calculate averages
        const avgEngagementByDate = {};
        Object.keys(engagementByDate).forEach(dateStr => {
            avgEngagementByDate[dateStr] = engagementByDate[dateStr] / countByDate[dateStr];
        });

        // Calculate date range based on current timeframe
        const now = new Date();
        now.setHours(0, 0, 0, 0);
        const timeframe = currentTimeframe || '30days';
        let daysBack;

        switch(timeframe) {
            case '7days': daysBack = 7; break;
            case '30days': daysBack = 30; break;
            case '90days': daysBack = 90; break;
            case '6months': daysBack = 180; break;
            default: daysBack = 30;
        }

        // Only include dates that have posts - this keeps line connected between actual data points
        const chartData = [];
        const sortedDates = Object.keys(avgEngagementByDate).sort();

        sortedDates.forEach(dateStr => {
            chartData.push({
                x: new Date(dateStr).getTime(),
                y: avgEngagementByDate[dateStr]
            });
        });

        // Calculate min/max dates for x-axis range based on timeframe
        const minDate = new Date(now);
        minDate.setDate(minDate.getDate() - daysBack);

        const options = {
            ...getChartDefaults(),
            series: [{
                name: 'Engagement Rate',
                data: chartData
            }],
            chart: {
                ...getChartDefaults().chart,
                type: 'line',
                height: 300
            },
            stroke: {
                curve: 'smooth',
                width: 3,
                colors: ['#8B5CF6']
            },
            markers: {
                size: 4,
                colors: ['#8B5CF6'],
                strokeColors: '#fff',
                strokeWidth: 2
            },
            dataLabels: { enabled: false },
            colors: ['#8B5CF6'],
            xaxis: {
                type: 'datetime',
                min: minDate.getTime(),
                max: now.getTime(),
                labels: {
                    format: 'MMM dd',
                    style: { colors: getChartColors().text, fontSize: '11px' },
                    rotate: -45
                }
            },
            yaxis: {
                labels: {
                    style: { colors: getChartColors().text },
                    formatter: function(val) {
                        return val ? val.toFixed(1) + '%' : '0%';
                    }
                }
            },
            tooltip: {
                ...getChartDefaults().tooltip,
                x: {
                    format: 'MMM dd, yyyy'
                },
                y: {
                    formatter: function(val) {
                        return val ? val.toFixed(1) + '%' : 'No posts';
                    }
                }
            }
        };

        if (charts.tiktokEngagement) {
            try {
                charts.tiktokEngagement.destroy();
            } catch (e) {}
        }
        charts.tiktokEngagement = new ApexCharts(chartElement, options);
        charts.tiktokEngagement.render();
    }

    function renderTikTokFrequencyChart(posts) {
        const chartElement = document.getElementById('tiktok-frequency-chart');
        if (!chartElement) return;

        chartElement.innerHTML = '';

        // Group posts by date
        const postsByDate = {};
        posts.forEach(post => {
            const createTime = post.create_time;
            if (createTime) {
                const date = new Date(createTime * 1000);
                const dateStr = date.toISOString().split('T')[0];
                postsByDate[dateStr] = (postsByDate[dateStr] || 0) + 1;
            }
        });

        // Calculate date range based on current timeframe (not post dates)
        const now = new Date();
        now.setHours(0, 0, 0, 0);
        const timeframe = currentTimeframe || '30days';
        let daysBack;

        switch(timeframe) {
            case '7days': daysBack = 7; break;
            case '30days': daysBack = 30; break;
            case '90days': daysBack = 90; break;
            case '6months': daysBack = 180; break;
            default: daysBack = 30;
        }

        // Fill in all dates in timeframe with 0 for missing dates
        const chartData = [];
        for (let i = daysBack; i >= 0; i--) {
            const date = new Date(now);
            date.setDate(date.getDate() - i);
            // Use local date string instead of UTC to avoid timezone issues
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const dateStr = `${year}-${month}-${day}`;
            chartData.push({
                x: new Date(dateStr).getTime(),
                y: postsByDate[dateStr] || 0
            });
        }

        const options = {
            ...getChartDefaults(),
            series: [{
                name: 'Posts',
                data: chartData
            }],
            chart: {
                ...getChartDefaults().chart,
                type: 'bar',
                height: 300
            },
            plotOptions: {
                bar: {
                    borderRadius: 4,
                    columnWidth: '60%'
                }
            },
            dataLabels: { enabled: false },
            colors: ['#10B981'],
            xaxis: {
                type: 'datetime',
                labels: {
                    format: 'MMM dd',
                    style: {
                        colors: getChartColors().text
                    }
                }
            },
            yaxis: {
                title: {
                    text: 'Number of Posts',
                    style: { color: getChartColors().title }
                },
                labels: {
                    style: { colors: getChartColors().text },
                    formatter: function(val) {
                        return Math.floor(val);
                    }
                }
            },
            tooltip: {
                ...getChartDefaults().tooltip,
                x: {
                    format: 'MMM dd, yyyy'
                },
                y: {
                    formatter: function(val) {
                        return val + ' post' + (val !== 1 ? 's' : '');
                    }
                }
            }
        };

        if (charts.tiktokFrequency) {
            try {
                charts.tiktokFrequency.destroy();
            } catch (e) {}
        }
        charts.tiktokFrequency = new ApexCharts(chartElement, options);
        charts.tiktokFrequency.render();
    }

    function renderTikTokMetrics(data, timeframe = '30days') {
        const metricsGrid = document.getElementById('tiktok-metrics');
        if (!metricsGrid) return;

        const followers = data.followers || 0;
        const totalLikes = data.likes || 0;

        // Fetch posts and calculate metrics based on timeframe
        fetch('/analytics/tiktok/posts', {
            credentials: 'include'
        })
            .then(response => response.json())
            .then(postsData => {
                const allPosts = postsData.posts || [];
                const filteredPosts = filterPostsByTimeframe(allPosts, timeframe);

                // Calculate metrics from filtered posts
                let engagementRate = 0;
                let totalViews = 0;
                let totalLikesFiltered = 0;
                let totalEngagementRate = 0;
                let postsWithViews = 0;

                filteredPosts.forEach(post => {
                    const views = post.views || 0;
                    const likes = post.likes || 0;
                    const comments = post.comments || 0;
                    const shares = post.shares || 0;

                    totalViews += views;
                    totalLikesFiltered += likes;

                    if (views > 0) {
                        const engagement = likes + comments + shares;
                        const postEngagementRate = (engagement / views) * 100;
                        totalEngagementRate += postEngagementRate;
                        postsWithViews++;
                    }
                });

                if (postsWithViews > 0) {
                    engagementRate = totalEngagementRate / postsWithViews;
                }

                // Get timeframe label
                const timeframeLabels = {
                    '7days': '7 days',
                    '30days': '30 days',
                    '90days': '90 days',
                    '6months': '6 months'
                };
                const timeframeLabel = timeframeLabels[timeframe] || '30 days';

                // Use grid layout with 5 columns
                metricsGrid.innerHTML = `
                    <div class="metric-card">
                        <div class="metric-icon">
                            <i class="ph ph-users"></i>
                        </div>
                        <div class="metric-content">
                            <div class="metric-value">${formatNumber(followers)}</div>
                            <div class="metric-label">Followers</div>
                        </div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-icon">
                            <i class="ph ph-heart"></i>
                        </div>
                        <div class="metric-content">
                            <div class="metric-value">${formatNumber(totalLikes)}</div>
                            <div class="metric-label">Total Likes</div>
                        </div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-icon">
                            <i class="ph ph-eye"></i>
                        </div>
                        <div class="metric-content">
                            <div class="metric-value">${formatNumber(totalViews)}</div>
                            <div class="metric-label">Total Views</div>
                            <div class="metric-sublabel">(${timeframeLabel})</div>
                        </div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-icon">
                            <i class="ph ph-heart"></i>
                        </div>
                        <div class="metric-content">
                            <div class="metric-value">${formatNumber(totalLikesFiltered)}</div>
                            <div class="metric-label">Likes</div>
                            <div class="metric-sublabel">(${timeframeLabel})</div>
                        </div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-icon">
                            <i class="ph ph-chart-line"></i>
                        </div>
                        <div class="metric-content">
                            <div class="metric-value">${engagementRate.toFixed(1)}%</div>
                            <div class="metric-label">Engagement Rate</div>
                            <div class="metric-sublabel">(${timeframeLabel})</div>
                        </div>
                    </div>
                `;
            })
            .catch(error => {
                console.error('Error calculating TikTok metrics:', error);
            });
    }

    window.loadTikTokPosts = function(filter = 'recent') {
        const timeframe = currentTimeframe || '30days';

        fetch(`/analytics/tiktok/posts`, {
            credentials: 'include'
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    showTikTokError(data.error);
                    return;
                }
                // Filter posts by timeframe before rendering
                const filteredPosts = filterPostsByTimeframe(data.posts || [], timeframe);
                renderTikTokPosts(filteredPosts, filter);
            })
            .catch(error => {
                console.error('Error loading TikTok posts:', error);
                showTikTokError('Failed to load TikTok posts');
            });
    };

    function renderTikTokPosts(posts, filter) {
        const tbody = document.getElementById('tiktok-posts-tbody');
        if (!tbody) return;

        // Apply sorting based on filter
        let sortedPosts = [...posts];
        if (filter === 'views') {
            sortedPosts.sort((a, b) => b.views - a.views);
        } else if (filter === 'engagement') {
            sortedPosts.sort((a, b) => b.engagement_rate - a.engagement_rate);
        }

        if (sortedPosts.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center py-8">No posts available</td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = sortedPosts.map((post, index) => {
            const date = new Date(post.create_time * 1000);
            const formattedDate = date.toLocaleDateString();
            const truncatedDesc = post.desc.length > 80 ? post.desc.substring(0, 80) + '...' : post.desc;

            return `
                <tr>
                    <td>${index + 1}</td>
                    <td>
                        <div class="post-preview">${escapeHtml(truncatedDesc)}</div>
                    </td>
                    <td>${formattedDate}</td>
                    <td class="font-medium">${formatNumber(post.views)}</td>
                    <td>${formatNumber(post.likes)}</td>
                    <td>${formatNumber(post.comments)}</td>
                    <td>${formatNumber(post.shares)}</td>
                    <td>
                        <span class="engagement-badge">${post.engagement_rate.toFixed(1)}%</span>
                    </td>
                    <td>
                        <a href="https://www.tiktok.com/@${window.analyticsConfig.tiktokUsername}/video/${post.id}"
                           target="_blank" class="post-link">View</a>
                    </td>
                </tr>
            `;
        }).join('');
    }

    // Error handling functions
    function showXError(message) {
        document.getElementById('x-metrics-grid').innerHTML = `
            <div class="col-span-full">
                <div class="empty-state">
                    <div class="empty-state-icon"><i class="ph ph-warning"></i></div>
                    <div class="empty-state-title">Error Loading Data</div>
                    <div class="empty-state-description">${message}</div>
                </div>
            </div>
        `;
    }
    
    function showYouTubeError(message) {
        document.getElementById('youtube-metrics-grid').innerHTML = `
            <div class="col-span-full">
                <div class="empty-state">
                    <div class="empty-state-icon"><i class="ph ph-warning"></i></div>
                    <div class="empty-state-title">Error Loading Data</div>
                    <div class="empty-state-description">${message}</div>
                </div>
            </div>
        `;
    }

    function showTikTokError(message) {
        const metricsGrid = document.getElementById('tiktok-metrics');
        if (metricsGrid) {
            metricsGrid.innerHTML = `
                <div class="col-span-full text-center py-8 text-red-500">
                    <i class="ph ph-warning-circle text-4xl mb-2"></i>
                    <p>${message}</p>
                </div>
            `;
        }
    }

    // Refresh all connected platforms
    window.refreshAllData = function() {
        const refreshBtn = document.getElementById('refresh-all-btn');
        if (!refreshBtn) return;

        const originalContent = refreshBtn.innerHTML;
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '<div class="loading-spinner"><i class="ph ph-spinner spin"></i></div><span>Refreshing...</span>';

        // Get connected platforms from the page
        const xConnected = document.getElementById('x-content') !== null;
        const youtubeConnected = document.getElementById('youtube-content') !== null;
        const tiktokConnected = document.getElementById('tiktok-content') !== null;

        // Create array of promises for all connected platforms
        const refreshPromises = [];
        const platformsToRefresh = [];

        if (xConnected) {
            platformsToRefresh.push('X');
            refreshPromises.push(
                fetch('/analytics/x/refresh', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include'
                }).then(r => r.json())
            );
        }

        if (youtubeConnected) {
            platformsToRefresh.push('YouTube');
            refreshPromises.push(
                fetch('/analytics/youtube/refresh', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include'
                }).then(r => r.json())
            );
        }

        if (tiktokConnected) {
            platformsToRefresh.push('TikTok');
            refreshPromises.push(
                fetch('/analytics/tiktok/refresh', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include'
                }).then(r => r.json())
            );
        }

        // Wait for all refreshes to complete
        Promise.all(refreshPromises)
            .then(results => {
                const allSuccessful = results.every(r => r.success);
                const someSuccessful = results.some(r => r.success);

                if (allSuccessful) {
                    if (window.BaseApp && window.BaseApp.showToast) {
                        window.BaseApp.showToast('All platforms refreshed successfully!', 'success');
                    }

                    // Reload all analytics after a short delay
                    setTimeout(() => {
                        if (xConnected) loadXAnalytics();
                        if (youtubeConnected) loadYouTubeAnalytics();
                        if (tiktokConnected) loadTikTokAnalytics();
                    }, 1000);
                } else if (someSuccessful) {
                    const failedPlatforms = results
                        .map((r, i) => r.success ? null : platformsToRefresh[i])
                        .filter(p => p !== null);

                    if (window.BaseApp && window.BaseApp.showToast) {
                        window.BaseApp.showToast(
                            `Some platforms failed to refresh: ${failedPlatforms.join(', ')}`,
                            'warning'
                        );
                    }

                    // Reload successful ones
                    setTimeout(() => {
                        results.forEach((r, i) => {
                            if (r.success) {
                                if (platformsToRefresh[i] === 'X') loadXAnalytics();
                                if (platformsToRefresh[i] === 'YouTube') loadYouTubeAnalytics();
                                if (platformsToRefresh[i] === 'TikTok') loadTikTokAnalytics();
                            }
                        });
                    }, 1000);
                } else {
                    if (window.BaseApp && window.BaseApp.showToast) {
                        window.BaseApp.showToast('Failed to refresh platforms', 'error');
                    }
                }
            })
            .catch(error => {
                console.error('Error refreshing platforms:', error);
                if (window.BaseApp && window.BaseApp.showToast) {
                    window.BaseApp.showToast('Error refreshing platforms', 'error');
                }
            })
            .finally(() => {
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = originalContent;
            });
    };

    // Individual refresh functions (kept for backwards compatibility)
    window.refreshXData = function() {
        const refreshBtn = document.getElementById('x-refresh-btn');
        if (!refreshBtn) return;
        const originalContent = refreshBtn.innerHTML;
        
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '<div class="loading-spinner"><i class="ph ph-spinner spin"></i></div><span>Refreshing...</span>';
        
        fetch('/analytics/x/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (window.BaseApp && window.BaseApp.showToast) {
                        window.BaseApp.showToast('X data refreshed successfully!', 'success');
                    }
                    setTimeout(() => loadXAnalytics(), 1000);
                } else {
                    if (window.BaseApp && window.BaseApp.showToast) {
                        window.BaseApp.showToast(data.error || 'Failed to refresh data', 'error');
                    }
                }
            })
            .finally(() => {
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = originalContent;
            });
    };
    
    window.refreshYouTubeData = function() {
        const refreshBtn = document.getElementById('youtube-refresh-btn');
        if (!refreshBtn) return;
        const originalContent = refreshBtn.innerHTML;
        
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '<div class="loading-spinner"><i class="ph ph-spinner spin"></i></div><span>Refreshing...</span>';
        
        fetch('/analytics/youtube/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (window.BaseApp && window.BaseApp.showToast) {
                        window.BaseApp.showToast('YouTube data refreshed successfully!', 'success');
                    }
                    setTimeout(() => loadYouTubeAnalytics(), 1000);
                } else {
                    if (window.BaseApp && window.BaseApp.showToast) {
                        window.BaseApp.showToast(data.error || 'Failed to refresh data', 'error');
                    }
                }
            })
            .finally(() => {
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = originalContent;
            });
    };

    window.refreshTikTokData = function() {
        const refreshBtn = document.getElementById('tiktok-refresh-btn');
        if (!refreshBtn) return;

        const originalContent = refreshBtn.innerHTML;

        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '<div class="loading-spinner"><i class="ph ph-spinner spin"></i></div><span>Refreshing...</span>';

        fetch('/analytics/tiktok/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (window.BaseApp && window.BaseApp.showToast) {
                        window.BaseApp.showToast('TikTok data refreshed successfully!', 'success');
                    }
                    setTimeout(() => loadTikTokAnalytics(), 1000);
                } else {
                    if (window.BaseApp && window.BaseApp.showToast) {
                        window.BaseApp.showToast(data.error || 'Failed to refresh data', 'error');
                    }
                }
            })
            .finally(() => {
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = originalContent;
            });
    };

    // Helper function to escape HTML
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

    // Helper function to get engagement class
    function getEngagementClass(rate) {
        if (rate >= 10) return 'high';
        if (rate >= 5) return 'medium';
        return 'low';
    }

    // Initialize the appropriate platform on load
    if (currentPlatform !== 'none') {
        // Set active button correctly
        document.querySelectorAll('.platform-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.platform === currentPlatform) {
                btn.classList.add('active');
            }
        });
        
        // Show correct content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        
        const contentElement = document.getElementById(`${currentPlatform}-content`);
        if (contentElement) {
            contentElement.classList.add('active');
        }
        
        // Load analytics after a delay to ensure DOM is ready
        setTimeout(() => {
            if (currentPlatform === 'x') {
                loadXAnalytics();
            } else if (currentPlatform === 'youtube') {
                loadYouTubeAnalytics();
            } else if (currentPlatform === 'tiktok') {
                loadTikTokAnalytics();
            }
        }, 100);
    }
}