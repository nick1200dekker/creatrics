from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required
import logging

logger = logging.getLogger(__name__)

@bp.route('/video-title')
@auth_required
def video_title():
    """Video title generator page"""
    return render_template('video_title/index.html')

@bp.route('/api/video-title/generate', methods=['POST'])
@auth_required
def generate_video_title():
    """Generate video title using AI"""
    try:
        data = request.json
        topic = data.get('topic', '')
        content_type = data.get('content_type', '')
        tone = data.get('tone', 'engaging')
        keywords = data.get('keywords', '')

        # TODO: Integrate with AI provider to generate titles
        # For now, return placeholder titles
        titles = [
            f"How to {topic} - Complete Guide for Beginners",
            f"{topic}: 10 Things You Need to Know",
            f"The Ultimate {topic} Tutorial (Step by Step)",
            f"Why {topic} Will Change Everything in 2024",
            f"{topic} Explained in 5 Minutes",
            f"I Tried {topic} for 30 Days - Here's What Happened",
            f"The Truth About {topic} Nobody Talks About",
            f"{topic} vs Others: Which is Better?",
            f"Master {topic} with These Simple Tips",
            f"Everything You Need to Know About {topic}"
        ]

        return jsonify({
            'success': True,
            'titles': titles[:5],  # Return top 5 suggestions
            'message': 'Video titles generated successfully'
        })
    except Exception as e:
        logger.error(f"Error generating video titles: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/video-title/analyze', methods=['POST'])
@auth_required
def analyze_title():
    """Analyze a video title for SEO and engagement potential"""
    try:
        data = request.json
        title = data.get('title', '')

        if not title:
            return jsonify({'success': False, 'error': 'Title is required'}), 400

        # TODO: Implement actual title analysis
        # For now, return placeholder analysis
        analysis = {
            'score': 85,
            'length': len(title),
            'word_count': len(title.split()),
            'strengths': [
                'Good length for YouTube (under 60 characters)' if len(title) < 60 else 'Consider shortening for better display',
                'Contains action words' if any(word in title.lower() for word in ['how', 'why', 'best', 'top', 'ultimate']) else 'Add action words for better engagement',
                'Clear and specific' if len(title.split()) > 3 else 'Add more context'
            ],
            'suggestions': [
                'Add numbers for better CTR (e.g., "5 Ways", "Top 10")',
                'Consider adding emotional triggers',
                'Include your main keyword at the beginning'
            ],
            'seo_keywords': title.split()[:3]  # Mock keywords
        }

        return jsonify({
            'success': True,
            'analysis': analysis
        })
    except Exception as e:
        logger.error(f"Error analyzing title: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500