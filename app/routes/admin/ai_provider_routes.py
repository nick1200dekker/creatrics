from flask import Blueprint, render_template, request, jsonify, g, redirect, url_for
from pathlib import Path
import logging
import os
import json

logger = logging.getLogger(__name__)

ai_provider_bp = Blueprint('ai_provider', __name__, url_prefix='/admin/ai-provider')

SCRIPTS_DIR = Path(__file__).parent.parent.parent / 'scripts'

def check_admin_access():
    """Check if user has admin access"""
    if not hasattr(g, 'user') or not g.user:
        return False

    subscription_plan = g.user.get('subscription_plan', '').lower().strip()
    return subscription_plan in ['admin', 'admin plan', 'administrator']

@ai_provider_bp.before_request
def require_admin():
    """Require admin access for all routes in this blueprint"""
    if not check_admin_access():
        return redirect(url_for('home.dashboard'))

# AI Provider configurations with metadata
AI_PROVIDERS = {
    'deepseek': {
        'name': 'DeepSeek',
        'model': 'deepseek-v3.2-exp',
        'logo_url': 'https://avatars.githubusercontent.com/u/165199292?s=200&v=4'
    },
    'claude': {
        'name': 'Claude',
        'model': 'claude-sonnet-4.5',
        'logo_url': None  # No logo, will use icon
    },
    'openai': {
        'name': 'OpenAI',
        'model': 'gpt-5-chat',
        'logo_url': 'https://cdn.oaistatic.com/_next/static/media/apple-touch-icon.82af6fe1.png'
    },
    'google': {
        'name': 'Google',
        'model': 'gemini-2.5-pro',
        'logo_url': 'https://www.gstatic.com/lamda/images/gemini_sparkle_v002_d4735304ff6292a690345.svg'
    }
}

def get_ai_scripts():
    """
    Scan scripts directory and find all Python files that use AI
    Returns dict with script identifier as key and metadata as value
    """
    ai_scripts = {}

    try:
        for folder in sorted(SCRIPTS_DIR.iterdir()):
            if folder.is_dir() and not folder.name.startswith('_'):
                # Look for Python files that import get_ai_provider
                py_files = list(folder.glob('*.py'))

                for py_file in py_files:
                    # Skip __init__.py and __pycache__
                    if py_file.name.startswith('__'):
                        continue

                    try:
                        with open(py_file, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # Check if this file uses AI provider
                        if 'get_ai_provider' in content or 'script_name=' in content:
                            # Create unique script identifier: folder_name/file_name (without .py)
                            file_stem = py_file.stem  # filename without extension
                            script_key = f"{folder.name}/{file_stem}"

                            # Format display name - shorten it
                            folder_display = folder.name.replace('_', ' ').title()
                            file_display = file_stem.replace('_', ' ').title()

                            # If folder and file names are similar, just use the folder name
                            # e.g., "video_title/video_title" -> "Video Title"
                            if folder.name == file_stem:
                                display_name = folder_display
                            # If file name contains common suffixes, remove them
                            elif file_stem.endswith('_generator') or file_stem.endswith('_analyzer') or file_stem.endswith('_processor') or file_stem.endswith('_correction'):
                                # e.g., "hook_generator" -> "Hook Generator", "caption_correction" -> "Caption Correction"
                                display_name = file_display
                            else:
                                # Use abbreviated format
                                display_name = f"{folder_display} › {file_display}"

                            ai_scripts[script_key] = {
                                'display_name': display_name,
                                'folder_name': folder.name,
                                'file_name': file_stem,
                                'path': f"{folder.name}/{py_file.name}"
                            }

                    except Exception as e:
                        logger.debug(f"Error reading {py_file}: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error scanning AI scripts: {e}")

    return ai_scripts

def get_preferences_file_path():
    """Get path to AI provider preferences JSON file"""
    config_dir = Path(__file__).parent.parent.parent.parent / 'config'
    config_dir.mkdir(exist_ok=True)
    return config_dir / 'ai_provider_preferences.json'

def load_preferences():
    """Load AI provider preferences from JSON file"""
    try:
        prefs_file = get_preferences_file_path()
        if prefs_file.exists():
            with open(prefs_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'free_users_deepseek': False,
            'script_preferences': {}
        }
    except Exception as e:
        logger.error(f"Error loading preferences: {e}")
        return {
            'free_users_deepseek': False,
            'script_preferences': {}
        }

def save_preferences(preferences):
    """Save AI provider preferences to JSON file"""
    try:
        prefs_file = get_preferences_file_path()
        with open(prefs_file, 'w', encoding='utf-8') as f:
            json.dump(preferences, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving preferences: {e}")
        return False

@ai_provider_bp.route('/')
def index():
    """Display AI Provider configuration page"""
    try:
        ai_scripts = get_ai_scripts()
        preferences = load_preferences()

        return render_template('admin/ai_provider_index.html',
                             scripts=ai_scripts,
                             providers=AI_PROVIDERS,
                             preferences=preferences)

    except Exception as e:
        logger.error(f"Error loading AI provider page: {e}")
        return jsonify({'error': str(e)}), 500

@ai_provider_bp.route('/preferences', methods=['GET'])
def get_preferences():
    """Get current AI provider preferences"""
    try:
        preferences = load_preferences()
        return jsonify({
            'success': True,
            'preferences': preferences
        })
    except Exception as e:
        logger.error(f"Error getting preferences: {e}")
        return jsonify({'error': str(e)}), 500

@ai_provider_bp.route('/preferences', methods=['POST'])
def update_preferences():
    """Update AI provider preferences"""
    try:
        data = request.json

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        preferences = load_preferences()

        # Update free users setting
        if 'free_users_deepseek' in data:
            preferences['free_users_deepseek'] = bool(data['free_users_deepseek'])

        # Update script preferences
        if 'script_preferences' in data:
            preferences['script_preferences'] = data['script_preferences']

        # Save to file
        if save_preferences(preferences):
            logger.info(f"AI provider preferences updated successfully")
            return jsonify({
                'success': True,
                'message': 'Preferences updated successfully'
            })
        else:
            return jsonify({'error': 'Failed to save preferences'}), 500

    except Exception as e:
        logger.error(f"Error updating preferences: {e}")
        return jsonify({'error': str(e)}), 500

@ai_provider_bp.route('/preferences/script', methods=['POST'])
def update_script_preference():
    """Update preferred provider for a specific script"""
    try:
        data = request.json
        script_name = data.get('script_name')
        provider = data.get('provider')

        if not script_name:
            return jsonify({'error': 'Script name is required'}), 400

        if not provider or provider not in AI_PROVIDERS:
            return jsonify({'error': 'Invalid provider'}), 400

        preferences = load_preferences()

        if 'script_preferences' not in preferences:
            preferences['script_preferences'] = {}

        preferences['script_preferences'][script_name] = provider

        if save_preferences(preferences):
            logger.info(f"Updated {script_name} to use {provider}")
            return jsonify({
                'success': True,
                'message': f'Updated {script_name} to use {provider}'
            })
        else:
            return jsonify({'error': 'Failed to save preference'}), 500

    except Exception as e:
        logger.error(f"Error updating script preference: {e}")
        return jsonify({'error': str(e)}), 500

@ai_provider_bp.route('/preferences/free-users', methods=['POST'])
def update_free_users_setting():
    """Toggle free users to use DeepSeek only"""
    try:
        data = request.json
        enabled = data.get('enabled', False)

        preferences = load_preferences()
        preferences['free_users_deepseek'] = bool(enabled)

        if save_preferences(preferences):
            status = 'enabled' if enabled else 'disabled'
            logger.info(f"Free users DeepSeek mode {status}")
            return jsonify({
                'success': True,
                'message': f'Free users DeepSeek mode {status}'
            })
        else:
            return jsonify({'error': 'Failed to save setting'}), 500

    except Exception as e:
        logger.error(f"Error updating free users setting: {e}")
        return jsonify({'error': str(e)}), 500
