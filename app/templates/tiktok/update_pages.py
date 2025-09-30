# Quick script to update remaining TikTok pages
pages = [
    {
        'file': 'trending_sounds.html',
        'title': 'Trending Sounds',
        'icon': 'ph-music-notes',
        'hero_title': 'Discover <span class="gradient-text">Viral Sounds</span>',
        'description': 'Find the hottest sounds trending in your niche. Use audio that\'s already going viral to boost your content\'s reach and engagement.',
        'secondary_link': 'tiktok.trend_finder',
        'secondary_icon': 'ph-trend-up',
        'secondary_text': 'Find Trends',
        'features': [
            ('ph-fire', 'Hot Sounds', 'Discover the most viral sounds right now in real-time.'),
            ('ph-target', 'Niche Specific', 'Sounds popular in your specific content category.'),
            ('ph-chart-line-up', 'Usage Stats', 'See how many creators are using each sound.')
        ]
    },
    {
        'file': 'trend_finder.html',
        'title': 'Trend Finder',
        'icon': 'ph-trend-up',
        'hero_title': 'Spot <span class="gradient-text">Rising Trends</span>',
        'description': 'Stay ahead of the curve by identifying challenges and content styles before they peak. Be an early adopter of the next viral trend.',
        'secondary_link': 'tiktok.analytics',
        'secondary_icon': 'ph-chart-line',
        'secondary_text': 'View Analytics',
        'features': [
            ('ph-rocket', 'Early Detection', 'Catch trends before they peak for maximum impact.'),
            ('ph-users', 'Viral Challenges', 'Find and join challenges that are gaining momentum.'),
            ('ph-sparkle', 'Content Styles', 'Discover formats and styles that are working now.')
        ]
    },
    {
        'file': 'analytics.html',
        'title': 'TikTok Analytics',
        'icon': 'ph-chart-line',
        'hero_title': 'Track Your <span class="gradient-text">Performance</span>',
        'description': 'Monitor your growth with detailed analytics. Understand what\'s working, track your follower growth, and optimize your content strategy.',
        'secondary_link': 'tiktok.hook_generator',
        'secondary_icon': 'ph-megaphone-simple',
        'secondary_text': 'Create Hooks',
        'features': [
            ('ph-users-three', 'Follower Growth', 'Track your audience growth over time with insights.'),
            ('ph-eye', 'View Analytics', 'Understand which content performs best and why.'),
            ('ph-heart', 'Engagement Metrics', 'Monitor likes, comments, shares, and saves.')
        ]
    }
]

template = '''{% extends "base.html" %}
{% set check_auth = true %}
{% block title %}TITLE - TikTok Tools - Creatrics{% endblock %}

{% block seo_meta %}
<meta name="description" content="DESCRIPTION">
<meta name="keywords" content="tiktok, viral content, content creation">
{% endblock %}

{% block additional_styles %}
{% include 'tiktok/base_styles.html' %}
{% endblock %}

{% block content %}
<div class="coming-soon-wrapper">
    <!-- Header -->
    <div class="coming-soon-header">
        <h1 class="coming-soon-title">
            <i class="ph ICON"></i>
            TITLE
        </h1>
    </div>

    <!-- Content -->
    <div class="coming-soon-content">
        <div class="coming-soon-hero">
            <div class="coming-soon-icon">
                <i class="ph ICON"></i>
            </div>

            <div class="coming-soon-badge">Coming Soon</div>

            <h1>HERO_TITLE</h1>

            <p>HERO_DESCRIPTION</p>

            <div class="coming-soon-cta">
                <a href="{{ url_for('home.dashboard') }}" class="btn-primary">
                    <i class="ph ph-house"></i>
                    Back to Dashboard
                </a>
                <a href="{{ url_for('SECONDARY_LINK') }}" class="btn-secondary">
                    <i class="ph SECONDARY_ICON"></i>
                    SECONDARY_TEXT
                </a>
            </div>
        </div>

        <!-- Features Preview -->
        <div class="features-preview">
FEATURES
        </div>
    </div>
</div>
{% endblock %}'''

for page in pages:
    features_html = ''
    for icon, title, desc in page['features']:
        features_html += f'''            <div class="feature-preview-card">
                <h3><i class="ph {icon}"></i>{title}</h3>
                <p>{desc}</p>
            </div>
'''
    
    content = template.replace('TITLE', page['title'])
    content = content.replace('ICON', page['icon'])
    content = content.replace('HERO_TITLE', page['hero_title'])
    content = content.replace('HERO_DESCRIPTION', page['description'])
    content = content.replace('DESCRIPTION', page['description'][:150])
    content = content.replace('SECONDARY_LINK', page['secondary_link'])
    content = content.replace('SECONDARY_ICON', page['secondary_icon'])
    content = content.replace('SECONDARY_TEXT', page['secondary_text'])
    content = content.replace('FEATURES', features_html)
    
    with open(f'/Users/nickdekker/Downloads/creator-tools/app/templates/tiktok/{page["file"]}', 'w') as f:
        f.write(content)
    print(f"Updated {page['file']}")
