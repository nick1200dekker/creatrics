from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required
import logging
import re

logger = logging.getLogger(__name__)

@bp.route('/x-post-editor')
@auth_required
def x_post_editor():
    """X (Twitter) post editor page"""
    return render_template('x_post_editor/index.html')

@bp.route('/api/x-post/generate', methods=['POST'])
@auth_required
def generate_post():
    """Generate an X post based on user input"""
    try:
        data = request.json
        topic = data.get('topic')
        tone = data.get('tone', 'professional')  # professional, casual, humorous, inspiring
        style = data.get('style', 'single')  # single, thread, poll
        include_hashtags = data.get('include_hashtags', True)
        include_emojis = data.get('include_emojis', False)
        target_audience = data.get('target_audience', 'general')

        if not topic:
            return jsonify({
                'success': False,
                'error': 'Topic is required'
            }), 400

        # TODO: Integrate with AI service to generate post
        # For now, return sample posts

        if style == 'single':
            posts = [{
                'content': f"🚀 Breaking down {topic} in a way that actually makes sense.\n\nHere's what most people miss:\n\n→ Key insight about {topic}\n→ Practical application\n→ Common misconception debunked\n\nWhat's your experience with this?",
                'character_count': 215,
                'hashtags': ['#TechTwitter', '#Innovation', '#Learning'],
                'media_suggestions': ['infographic', 'chart']
            }]
        elif style == 'thread':
            posts = [
                {
                    'content': f"🧵 Let's talk about {topic}.\n\nI've spent the last few months diving deep into this, and here's what I've learned:",
                    'character_count': 120,
                    'thread_position': '1/'
                },
                {
                    'content': f"First, the fundamentals:\n\n{topic} isn't just another buzzword. It's fundamentally changing how we approach problems.\n\nHere's why:",
                    'character_count': 140,
                    'thread_position': '2/'
                },
                {
                    'content': "The 3 key benefits:\n\n1. Efficiency gains of 40-60%\n2. Reduced complexity\n3. Better scalability\n\nBut there's a catch...",
                    'character_count': 125,
                    'thread_position': '3/'
                },
                {
                    'content': "The main challenges:\n\n• Initial learning curve\n• Integration with existing systems\n• Change management\n\nHere's how to overcome them:",
                    'character_count': 145,
                    'thread_position': '4/'
                },
                {
                    'content': f"Key takeaway:\n\n{topic} is worth the investment if you're looking for long-term gains.\n\nStart small, iterate, and scale.\n\nWhat questions do you have?",
                    'character_count': 155,
                    'thread_position': '5/5'
                }
            ]
        else:  # poll
            posts = [{
                'content': f"Quick poll on {topic}:\n\nWhat's your biggest challenge?",
                'character_count': 60,
                'poll_options': [
                    'Getting started',
                    'Scaling up',
                    'Team adoption',
                    'ROI measurement'
                ],
                'poll_duration': '1 day'
            }]

        return jsonify({
            'success': True,
            'posts': posts,
            'total_characters': sum(p.get('character_count', 0) for p in posts),
            'style': style
        })

    except Exception as e:
        logger.error(f"Error generating X post: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate post'
        }), 500

@bp.route('/api/x-post/optimize', methods=['POST'])
@auth_required
def optimize_post():
    """Optimize an existing X post"""
    try:
        data = request.json
        content = data.get('content')
        optimization_goal = data.get('goal', 'engagement')  # engagement, clarity, viral

        if not content:
            return jsonify({
                'success': False,
                'error': 'Content is required'
            }), 400

        # Character count
        char_count = len(content)

        # Extract hashtags
        hashtags = re.findall(r'#\w+', content)

        # Extract mentions
        mentions = re.findall(r'@\w+', content)

        # TODO: Integrate with AI for actual optimization
        suggestions = []

        if char_count > 280:
            suggestions.append(f"Post is {char_count - 280} characters over the limit. Consider shortening.")

        if len(hashtags) > 3:
            suggestions.append("Consider using 1-3 hashtags for optimal reach")

        if len(hashtags) == 0 and optimization_goal == 'engagement':
            suggestions.append("Add 1-2 relevant hashtags to increase discoverability")

        if '?' not in content and optimization_goal == 'engagement':
            suggestions.append("Consider ending with a question to boost engagement")

        if len(content.split('\n\n')) < 2:
            suggestions.append("Break up text with line breaks for better readability")

        optimized_content = content  # In production, this would be AI-enhanced

        return jsonify({
            'success': True,
            'original': content,
            'optimized': optimized_content,
            'character_count': char_count,
            'suggestions': suggestions,
            'hashtags': hashtags,
            'mentions': mentions
        })

    except Exception as e:
        logger.error(f"Error optimizing post: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to optimize post'
        }), 500

@bp.route('/api/x-post/templates', methods=['GET'])
@auth_required
def get_post_templates():
    """Get X post templates"""
    try:
        templates = [
            {
                'id': 'announcement',
                'name': 'Product Announcement',
                'template': "🎉 Excited to announce [PRODUCT/FEATURE]!\n\n✨ [KEY BENEFIT 1]\n✨ [KEY BENEFIT 2]\n✨ [KEY BENEFIT 3]\n\n[CALL TO ACTION]\n\n[LINK]",
                'category': 'business'
            },
            {
                'id': 'tips',
                'name': 'Tips Thread',
                'template': "5 [TOPIC] tips I wish I knew earlier:\n\n1. [TIP 1]\n2. [TIP 2]\n3. [TIP 3]\n4. [TIP 4]\n5. [TIP 5]\n\nWhat would you add?",
                'category': 'educational'
            },
            {
                'id': 'story',
                'name': 'Story/Experience',
                'template': "[TIME PERIOD] ago, I [SITUATION].\n\nToday, [CURRENT SITUATION].\n\nHere's what I learned:\n\n[KEY LESSON]\n\n[QUESTION TO AUDIENCE]",
                'category': 'personal'
            },
            {
                'id': 'hot_take',
                'name': 'Hot Take',
                'template': "Unpopular opinion:\n\n[CONTROVERSIAL STATEMENT]\n\nHere's why:\n\n[REASONING]\n\nAgree or disagree?",
                'category': 'engagement'
            },
            {
                'id': 'resource',
                'name': 'Resource Share',
                'template': "📚 [NUMBER] [RESOURCE TYPE] for [TOPIC]:\n\n1. [RESOURCE 1] - [DESCRIPTION]\n2. [RESOURCE 2] - [DESCRIPTION]\n3. [RESOURCE 3] - [DESCRIPTION]\n\nSave this for later! 🔖",
                'category': 'value'
            }
        ]

        return jsonify({
            'success': True,
            'templates': templates
        })

    except Exception as e:
        logger.error(f"Error fetching templates: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch templates'
        }), 500

@bp.route('/api/x-post/analyze-timing', methods=['POST'])
@auth_required
def analyze_timing():
    """Analyze best posting time"""
    try:
        data = request.json
        timezone = data.get('timezone', 'UTC')
        audience_location = data.get('audience_location', 'global')

        # TODO: Integrate with actual analytics
        # For now, return general best times

        best_times = {
            'weekdays': [
                {'time': '9:00 AM', 'engagement_score': 85},
                {'time': '12:00 PM', 'engagement_score': 92},
                {'time': '5:00 PM', 'engagement_score': 88},
                {'time': '7:00 PM', 'engagement_score': 79}
            ],
            'weekends': [
                {'time': '11:00 AM', 'engagement_score': 82},
                {'time': '2:00 PM', 'engagement_score': 75},
                {'time': '8:00 PM', 'engagement_score': 71}
            ],
            'best_days': ['Tuesday', 'Wednesday', 'Thursday'],
            'avoid_times': ['Late nights (12 AM - 6 AM)', 'Sunday evenings']
        }

        return jsonify({
            'success': True,
            'best_times': best_times,
            'timezone': timezone
        })

    except Exception as e:
        logger.error(f"Error analyzing timing: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to analyze timing'
        }), 500