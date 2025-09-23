"""
Sitemap generation for SEO
"""
from flask import Blueprint, Response, url_for, request
from datetime import datetime

bp = Blueprint('sitemap', __name__)

@bp.route('/sitemap.xml')
def sitemap():
    """Generate XML sitemap for search engines"""
    
    # Define all public pages with their priorities and change frequencies
    pages = [
        {
            'url': url_for('core.landing', _external=True),
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'changefreq': 'weekly',
            'priority': '1.0'
        },
        {
            'url': url_for('auth.login', _external=True),
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'changefreq': 'monthly',
            'priority': '0.8'
        },
        {
            'url': url_for('auth.register', _external=True),
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'changefreq': 'monthly',
            'priority': '0.8'
        },
        {
            'url': url_for('auth.terms_conditions', _external=True),
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'changefreq': 'yearly',
            'priority': '0.3'
        },
        {
            'url': url_for('auth.privacy_policy', _external=True),
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'changefreq': 'yearly',
            'priority': '0.3'
        }
    ]
    
    # Generate XML
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'''
    
    for page in pages:
        xml_content += f'''
    <url>
        <loc>{page['url']}</loc>
        <lastmod>{page['lastmod']}</lastmod>
        <changefreq>{page['changefreq']}</changefreq>
        <priority>{page['priority']}</priority>
    </url>'''
    
    xml_content += '''
</urlset>'''
    
    return Response(xml_content, mimetype='application/xml')

@bp.route('/robots.txt')
def robots():
    """Generate robots.txt for search engines"""
    
    robots_content = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/
Disallow: /auth/callback
Disallow: /auth/reset-password

Sitemap: {url_for('sitemap.sitemap', _external=True)}
"""
    
    return Response(robots_content, mimetype='text/plain')
