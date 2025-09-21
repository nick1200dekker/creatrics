from flask import render_template, request, jsonify, g
from . import bp
from app.system.auth.middleware import auth_required
import logging

logger = logging.getLogger(__name__)

@bp.route('/video-script')
@auth_required
def video_script():
    """Video script generator page"""
    return render_template('video_script/index.html')

@bp.route('/api/video-script/generate', methods=['POST'])
@auth_required
def generate_video_script():
    """Generate a video script based on user input"""
    try:
        data = request.json
        topic = data.get('topic')
        video_length = data.get('video_length', '5-10')  # in minutes
        tone = data.get('tone', 'professional')  # professional, casual, educational, entertaining
        style = data.get('style', 'standard')  # standard, tutorial, story, review
        target_audience = data.get('target_audience', 'general')
        include_hook = data.get('include_hook', True)
        include_cta = data.get('include_cta', True)

        if not topic:
            return jsonify({
                'success': False,
                'error': 'Topic is required'
            }), 400

        # TODO: Integrate with AI service to generate script
        # For now, return a sample script structure

        script = {
            'hook': f"Have you ever wondered about {topic}? In today's video, I'm going to reveal something that will completely change your perspective!",
            'introduction': f"Welcome back to the channel! Today we're diving deep into {topic}. If you're new here, make sure to subscribe and hit the notification bell so you never miss an update.",
            'sections': [
                {
                    'title': 'Background & Context',
                    'content': f"Let's start with understanding the basics of {topic}. This is crucial because it sets the foundation for everything we'll discuss today.",
                    'talking_points': [
                        'Define key concepts and terminology',
                        'Explain why this topic matters',
                        'Share relevant statistics or facts'
                    ],
                    'duration_estimate': '2-3 minutes'
                },
                {
                    'title': 'Main Content',
                    'content': f"Now, let's get into the meat of {topic}. I'll break this down into easy-to-understand segments.",
                    'talking_points': [
                        'Point 1: Core concept explanation',
                        'Point 2: Real-world examples',
                        'Point 3: Common misconceptions',
                        'Point 4: Best practices or tips'
                    ],
                    'duration_estimate': '4-5 minutes'
                },
                {
                    'title': 'Practical Application',
                    'content': "Here's how you can apply this knowledge in your own life or work.",
                    'talking_points': [
                        'Step-by-step implementation guide',
                        'Tools or resources needed',
                        'Common pitfalls to avoid'
                    ],
                    'duration_estimate': '2-3 minutes'
                }
            ],
            'conclusion': f"That wraps up our deep dive into {topic}. Remember, the key takeaway here is to start implementing what you've learned today.",
            'call_to_action': "If you found this video helpful, please give it a thumbs up and share it with someone who could benefit from this information. Don't forget to subscribe for more content like this, and leave a comment below with your thoughts or questions!",
            'metadata': {
                'estimated_length': f"{video_length} minutes",
                'tone': tone,
                'style': style,
                'target_audience': target_audience,
                'word_count': 850
            }
        }

        # Format script for better readability
        formatted_script = format_script_output(script)

        return jsonify({
            'success': True,
            'script': script,
            'formatted': formatted_script
        })

    except Exception as e:
        logger.error(f"Error generating video script: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to generate video script'
        }), 500

@bp.route('/api/video-script/templates', methods=['GET'])
@auth_required
def get_script_templates():
    """Get pre-defined script templates"""
    try:
        templates = [
            {
                'id': 'tutorial',
                'name': 'Tutorial/How-To',
                'description': 'Step-by-step instructional format',
                'structure': ['Hook', 'Introduction', 'Prerequisites', 'Steps', 'Tips & Tricks', 'Conclusion', 'CTA']
            },
            {
                'id': 'review',
                'name': 'Product Review',
                'description': 'Comprehensive product analysis',
                'structure': ['Hook', 'Introduction', 'Unboxing/First Impressions', 'Features', 'Pros & Cons', 'Comparison', 'Verdict', 'CTA']
            },
            {
                'id': 'listicle',
                'name': 'Top 10/List',
                'description': 'Countdown or list format',
                'structure': ['Hook', 'Introduction', 'List Items (10-1)', 'Honorable Mentions', 'Conclusion', 'CTA']
            },
            {
                'id': 'story',
                'name': 'Story/Vlog',
                'description': 'Narrative-driven content',
                'structure': ['Hook', 'Setup', 'Rising Action', 'Climax', 'Resolution', 'Reflection', 'CTA']
            },
            {
                'id': 'educational',
                'name': 'Educational',
                'description': 'Teaching complex topics',
                'structure': ['Hook', 'Learning Objectives', 'Theory', 'Examples', 'Practice', 'Summary', 'CTA']
            }
        ]

        return jsonify({
            'success': True,
            'templates': templates
        })

    except Exception as e:
        logger.error(f"Error fetching script templates: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch templates'
        }), 500

@bp.route('/api/video-script/improve', methods=['POST'])
@auth_required
def improve_script():
    """Improve an existing script"""
    try:
        data = request.json
        script = data.get('script')
        improvement_type = data.get('improvement_type', 'general')  # general, engagement, clarity, seo

        if not script:
            return jsonify({
                'success': False,
                'error': 'Script content is required'
            }), 400

        # TODO: Integrate with AI service to improve script
        # For now, return suggestions

        suggestions = {
            'engagement': [
                'Add a stronger hook in the first 5 seconds',
                'Include more emotional triggers',
                'Add pattern interrupts every 30-60 seconds',
                'Use more direct questions to the audience'
            ],
            'clarity': [
                'Simplify technical jargon',
                'Add transition phrases between sections',
                'Break down complex points into smaller chunks',
                'Include more concrete examples'
            ],
            'seo': [
                'Naturally include target keywords 3-5 times',
                'Mention the main topic in the first 30 seconds',
                'Add timestamps for better YouTube indexing',
                'Include related keywords and phrases'
            ],
            'pacing': [
                'Vary sentence length for better rhythm',
                'Add pauses for emphasis',
                'Speed up during lists, slow down for important points',
                'Include breathing room between major sections'
            ]
        }

        improved_script = script  # In production, this would be AI-enhanced

        return jsonify({
            'success': True,
            'improved_script': improved_script,
            'suggestions': suggestions.get(improvement_type, suggestions['engagement'])
        })

    except Exception as e:
        logger.error(f"Error improving script: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to improve script'
        }), 500

def format_script_output(script):
    """Format script for display"""
    formatted = []

    if script.get('hook'):
        formatted.append(f"🎬 HOOK:\n{script['hook']}\n")

    if script.get('introduction'):
        formatted.append(f"👋 INTRODUCTION:\n{script['introduction']}\n")

    for i, section in enumerate(script.get('sections', []), 1):
        formatted.append(f"📌 SECTION {i}: {section['title']}")
        formatted.append(f"{section['content']}")
        if section.get('talking_points'):
            formatted.append("Key Points:")
            for point in section['talking_points']:
                formatted.append(f"  • {point}")
        if section.get('duration_estimate'):
            formatted.append(f"⏱️ Duration: {section['duration_estimate']}")
        formatted.append("")

    if script.get('conclusion'):
        formatted.append(f"🎯 CONCLUSION:\n{script['conclusion']}\n")

    if script.get('call_to_action'):
        formatted.append(f"📢 CALL TO ACTION:\n{script['call_to_action']}\n")

    return "\n".join(formatted)