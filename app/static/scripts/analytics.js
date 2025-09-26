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

    // Determine initial platform based on URL parameter or connected accounts
    let defaultPlatform = xConnected ? 'x' : (youtubeConnected ? 'youtube' : 'none');
    let currentPlatform = platformParam || defaultPlatform;

    // Validate platform parameter
    if (platformParam === 'x' && !xConnected) {
        currentPlatform = defaultPlatform;
    } else if (platformParam === 'youtube' && !youtubeConnected) {
        currentPlatform = defaultPlatform;
    }

    // Function to get chart colors based on theme
    function getChartColors() {
        const isDarkMode = document.documentElement.classList.contains('dark');
        return {
            text: isDarkMode ? '#d1d5db' : '#6b7280',
            title: isDarkMode ? '#9ca3af' : '#6b7280',
            grid: isDarkMode ? '#374151' : '#e5e7eb',
            tooltip: isDarkMode ? 'dark' : 'light'
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
    let charts = {
        impressions: null,
        engagement: null,
        postsCount: null,
        followers: null
    };
    
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
        
        if (currentPlatform === 'x') {
            loadXAnalytics();
        } else if (currentPlatform === 'youtube') {
            // Use setTimeout to ensure DOM is ready
            setTimeout(() => {
                updateYouTubeTitles();
                loadYouTubeAnalytics();
            }, 100);
        }
    };
    
    // Platform switching
    window.switchPlatform = function(platform) {
        document.querySelectorAll('.platform-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-platform="${platform}"]`).classList.add('active');
        
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        
        const contentElement = document.getElementById(`${platform}-content`);
        if (contentElement) {
            contentElement.classList.add('active');
        }
        
        currentPlatform = platform;
        
        // Show/hide timeframe selector based on platform
        const timeframeSelector = document.querySelector('.timeframe-selector');
        if (timeframeSelector) {
            // YouTube now supports timeframes too!
            timeframeSelector.style.opacity = '1';
            timeframeSelector.style.pointerEvents = 'auto';
            timeframeSelector.title = '';
        }
        
        if (platform === 'x' && contentElement) {
            loadXAnalytics();
        } else if (platform === 'youtube' && contentElement) {
            // Use setTimeout to ensure the YouTube content is visible
            setTimeout(() => {
                updateYouTubeTitles();
                loadYouTubeAnalytics();
            }, 100);
        }
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
    
    // Load initial data based on platform
    if (currentPlatform === 'x' && xConnected) {
        // Switch to X platform
        switchPlatform('x');
    } else if (currentPlatform === 'youtube' && youtubeConnected) {
        // Switch to YouTube platform
        switchPlatform('youtube');
    } else if (xConnected) {
        // Default to X if connected
        switchPlatform('x');
    } else if (youtubeConnected) {
        // Default to YouTube if connected
        switchPlatform('youtube');
    }
    
    // X Analytics functions
    function loadXAnalytics() {
        fetch(`/analytics/x/overview?timeframe=${currentTimeframe}`)
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
        
        const formatNumber = (num) => {
            if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
            return num.toLocaleString();
        };
        
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
        document.getElementById('x-impressions-chart').innerHTML = '';

        fetch(`/analytics/x/impressions?timeframe=${currentTimeframe}`)
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    renderImpressionsChart(data.impressions_data, data.has_sufficient_data);
                } else {
                    document.getElementById('x-impressions-chart').innerHTML = '<div class="empty-state">Failed to load impressions data</div>';
                }
            })
            .catch(error => {
                console.error('Error loading impressions:', error);
                document.getElementById('x-impressions-chart').innerHTML = '<div class="empty-state">Failed to load impressions data</div>';
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
            series: series,
            chart: {
                type: chartViews.impressions === 'rolling' ? 'line' : 'bar',
                height: 300,
                toolbar: { show: false },
                background: 'transparent',
                fontFamily: 'Inter, sans-serif',
                zoom: { enabled: false },
                animations: {
                    enabled: true,
                    speed: 400
                }
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
                title: { text: 'Impressions', style: { color: getChartColors().title } },
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
                theme: getChartColors().tooltip,
                y: { 
                    formatter: function(val) { 
                        return val.toLocaleString() + ' impressions'; 
                    } 
                }
            },
            grid: { 
                borderColor: getChartColors().grid,
                strokeDashArray: 3
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
        
        if (charts.impressions) charts.impressions.destroy();
        charts.impressions = new ApexCharts(container, chartOptions);
        charts.impressions.render();
    }

    function loadEngagementChart() {
        document.getElementById('x-engagement-chart').innerHTML = '';
        
        fetch(`/analytics/x/engagement?timeframe=${currentTimeframe}`)
            .then(response => response.json())
            .then(data => {
                if (!data.error) {
                    renderEngagementChart(data.engagement_data, data.has_sufficient_data);
                } else {
                    document.getElementById('x-engagement-chart').innerHTML = '<div class="empty-state">Failed to load engagement data</div>';
                }
            })
            .catch(error => {
                console.error('Error loading engagement:', error);
                document.getElementById('x-engagement-chart').innerHTML = '<div class="empty-state">Failed to load engagement data</div>';
            });
    }
    
    function renderEngagementChart(engagementData, hasSufficientData) {
        const container = document.getElementById('x-engagement-chart');
        if (!engagementData || engagementData.length === 0) {
            container.innerHTML = '<div class="empty-state">No engagement data available</div>';
            return;
        }
        container.innerHTML = '';
        
        // Similar implementation to impressions chart but for engagement data
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
            series: series,
            chart: { 
                height: 300, 
                type: 'line', 
                toolbar: { show: false }, 
                background: 'transparent',
                zoom: { enabled: false },
                animations: {
                    enabled: true,
                    speed: 400
                }
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
                theme: getChartColors().tooltip,
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
            grid: { 
                borderColor: getChartColors().grid,
                strokeDashArray: 3
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
        
        if (charts.engagement) charts.engagement.destroy();
        charts.engagement = new ApexCharts(container, chartOptions);
        charts.engagement.render();
    }

    function loadPostsCountChart() {
        fetch(`/analytics/x/posts-count?timeframe=${currentTimeframe}`)
            .then(response => response.json())
            .then(data => {
                if (!data.error) renderPostsCountChart(data.posts_count_data);
            });
    }
    
    function renderPostsCountChart(data) {
        if (!data || data.length === 0) return;
        const container = document.getElementById('x-posts-count-chart');
        container.innerHTML = '';
        
        const isWeekly = data[0]?.is_week || false;
        
        const chartOptions = {
            series: [{ 
                name: isWeekly ? 'Weekly Posts' : 'Daily Posts', 
                data: data.map(d => ({ x: d.date, y: d.posts_count || 0 })) 
            }],
            chart: { 
                type: 'bar', 
                height: 300, 
                toolbar: { show: false },
                background: 'transparent',
                zoom: { enabled: false },
                animations: {
                    enabled: true,
                    speed: 400
                }
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
                title: { text: 'Number of Posts', style: { color: getChartColors().title } },
                labels: {
                    style: { colors: getChartColors().text },
                    formatter: function(val) {
                        return Math.round(val).toString();
                    }
                },
                min: 0
            },
            tooltip: {
                theme: getChartColors().tooltip,
                y: {
                    formatter: function(val) {
                        return val + ' posts';
                    }
                }
            },
            grid: {
                borderColor: getChartColors().grid,
                strokeDashArray: 3
            }
        };
        
        if (charts.postsCount) charts.postsCount.destroy();
        charts.postsCount = new ApexCharts(container, chartOptions);
        charts.postsCount.render();
    }

    function loadFollowersChart() {
        fetch(`/analytics/x/followers-history?timeframe=${currentTimeframe}`)
            .then(response => response.json())
            .then(data => {
                if (!data.error) renderFollowersChart(data.followers_data);
            });
    }
    
    function renderFollowersChart(data) {
        if (!data || data.length === 0) return;
        const container = document.getElementById('x-followers-chart');
        container.innerHTML = '';
        
        const isWeekly = data[0]?.is_week || false;
        const followers = data.map(d => d.followers_count || 0);
        const maxFollowers = Math.max(...followers);
        
        const chartOptions = {
            series: [{
                name: 'Total Followers',
                type: 'line',
                data: data.map(d => ({ x: d.date, y: d.followers_count || 0 }))
            }],
            chart: {
                height: 300,
                type: 'line',
                toolbar: { show: false },
                background: 'transparent',
                zoom: { enabled: false },
                animations: {
                    enabled: true,
                    speed: 400,
                    animateGradually: {
                        enabled: true,
                        delay: 50
                    }
                }
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
                theme: getChartColors().tooltip,
                y: {
                    formatter: function(val) {
                        return val.toLocaleString() + ' followers';
                    }
                }
            },
            grid: {
                borderColor: getChartColors().grid,
                strokeDashArray: 3
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
        
        if (charts.followers) charts.followers.destroy();
        charts.followers = new ApexCharts(container, chartOptions);
        charts.followers.render();
    }

    function loadXPosts(filter) {
        xPostsData.currentFilter = filter;
        xPostsData.currentPage = 1;

        fetch(`/analytics/x/posts-paginated?page=1&per_page=${xPostsData.itemsPerPage}&filter=${filter}`)
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
        
        const formatNumber = (num) => {
            if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
            return num.toLocaleString();
        };
        
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
        // Simplified pagination rendering
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
        
        fetch(`/analytics/x/posts-paginated?page=${page}&per_page=${xPostsData.itemsPerPage}&filter=${xPostsData.currentFilter}`)
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
    function updateYouTubeTitles() {
        const overviewTitle = document.getElementById('youtube-overview-title');
        if (overviewTitle) overviewTitle.textContent = 'Channel Overview';
        
        const performanceTitle = document.getElementById('youtube-performance-title');
        if (performanceTitle) performanceTitle.innerHTML = '<i class="ph ph-chart-bar"></i> Performance Overview';
        
        const trafficTitle = document.getElementById('youtube-traffic-title');
        if (trafficTitle) trafficTitle.innerHTML = '<i class="ph ph-funnel"></i> Traffic Sources';
    }
    
    function loadYouTubeAnalytics() {
        loadYouTubeDailyData();
    }
    
    function loadYouTubeDailyData() {
        fetch(`/analytics/youtube/daily-views?timeframe=${currentTimeframe}`)
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
        fetch(`/analytics/youtube/top-videos?timeframe=${currentTimeframe}`)
            .then(response => response.json())
            .then(data => {
                if (!data.error) renderYouTubeVideos(data.top_videos || []);
            });
    }
    
    function renderYouTubeMetrics(metrics) {
        const metricsGrid = document.getElementById('youtube-metrics-grid');
        const formatNumber = (num) => {
            if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
            return num.toLocaleString();
        };
        
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
                series: [
                    { name: 'Views', type: 'column', data: dailyData.map(d => ({ x: d.date, y: d.views || 0 })) },
                    { name: 'Watch Time (hrs)', type: 'line', data: dailyData.map(d => ({ x: d.date, y: d.watch_time_hours || 0 })) }
                ],
                chart: { 
                    height: 300, 
                    type: 'line', 
                    toolbar: { show: false },
                    background: 'transparent',
                    zoom: { enabled: false },
                    animations: {
                        enabled: true,
                        speed: 400
                    }
                },
                stroke: {
                    width: [0, 3],
                    curve: 'smooth'
                },
                plotOptions: {
                    bar: {
                        columnWidth: '60%'
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
                tooltip: { theme: getChartColors().tooltip },
                legend: {
                    show: true,
                    position: 'top',
                    labels: { colors: getChartColors().text }
                },
                grid: {
                    borderColor: getChartColors().grid,
                    strokeDashArray: 3
                },
                dataLabels: { enabled: false }
            };
            
            const viewsChart = new ApexCharts(viewsContainer, viewsOptions);
            viewsChart.render();
        }
        
        renderTrafficSourcesChart(overviewData);
    }
    
    function renderTrafficSourcesChart(metrics) {
        const trafficContainer = document.querySelector("#youtube-traffic-chart");
        if (trafficContainer) {
            trafficContainer.innerHTML = '';
            
            if (metrics.traffic_sources && metrics.traffic_sources.length > 0) {
                const trafficOptions = {
                    series: metrics.traffic_sources.map(s => s.views),
                    chart: { 
                        type: 'donut', 
                        height: 300,
                        background: 'transparent',
                        zoom: { enabled: false }
                    },
                    labels: metrics.traffic_sources.map(s => s.source),
                    colors: ['#3B82F6', '#60A5FA', '#EF4444', '#F59E0B', '#8B5CF6'],
                    legend: {
                        position: 'bottom',
                        labels: { colors: getChartColors().text }
                    },
                    dataLabels: { enabled: false },
                    tooltip: { theme: getChartColors().tooltip },
                    plotOptions: {
                        pie: {
                            donut: {
                                size: '65%'
                            }
                        }
                    }
                };
                
                const trafficChart = new ApexCharts(trafficContainer, trafficOptions);
                trafficChart.render();
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
        
        const formatNumber = (num) => {
            if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
            return num.toLocaleString();
        };
        
        tbody.innerHTML = videos.map(video => `
            <tr>
                <td><a href="https://youtube.com/watch?v=${video.id}" target="_blank" class="post-link">Video ${video.id}</a></td>
                <td class="font-medium">${formatNumber(video.views || 0)}</td>
                <td>${(video.watch_time_minutes / 60).toFixed(1)}</td>
                <td>${Math.floor((video.avg_view_duration || 0) / 60)}:${((video.avg_view_duration || 0) % 60).toString().padStart(2, '0')}</td>
                <td>${formatNumber(video.likes || 0)}</td>
                <td>${formatNumber(video.comments || 0)}</td>
                <td><span class="engagement-badge">${(video.engagement_rate || 0).toFixed(1)}%</span></td>
            </tr>
        `).join('');
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

    // Refresh functions
    window.refreshXData = function() {
        const refreshBtn = document.getElementById('x-refresh-btn');
        const originalContent = refreshBtn.innerHTML;
        
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '<div class="loading-spinner"></div><span>Refreshing...</span>';
        
        fetch('/analytics/x/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
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
        const originalContent = refreshBtn.innerHTML;
        
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '<div class="loading-spinner"></div><span>Refreshing...</span>';
        
        fetch('/analytics/youtube/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
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
}
