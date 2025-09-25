from flask import render_template, request, jsonify, g, redirect, url_for
from . import bp
from app.system.auth.middleware import auth_required
from app.system.services.firebase_service import db
from datetime import datetime, timedelta
import logging
import json
import uuid
import secrets

logger = logging.getLogger(__name__)

# Preset tags configuration
PRESET_TAGS = [
    {'name': 'video-idea', 'label': '🎥 Video Idea', 'color': '#FF6B6B'},
    {'name': 'content-idea', 'label': '💡 Content Idea', 'color': '#4ECDC4'},
    {'name': 'draft', 'label': '📝 Draft', 'color': '#45B7D1'},
    {'name': 'important', 'label': '⭐ Important', 'color': '#FFA500'},
    {'name': 'research', 'label': '🔍 Research', 'color': '#9B59B6'},
    {'name': 'script', 'label': '📜 Script', 'color': '#3498DB'},
    {'name': 'social-media', 'label': '📱 Social Media', 'color': '#E91E63'},
    {'name': 'tutorial', 'label': '📚 Tutorial', 'color': '#2ECC71'},
]

@bp.route('/brain-dump')
@auth_required
def brain_dump():
    """Brain Dump main page"""
    return render_template('brain_dump/index.html')

@bp.route('/api/brain-dump/notes', methods=['GET'])
@auth_required
def get_notes():
    """Get all notes for the current user"""
    try:
        user_id = str(g.user.get('id'))

        # Get user's notes from Firebase
        notes_ref = db.collection('users').document(user_id).collection('brain_dump')
        notes_docs = notes_ref.stream()

        # Convert to list
        notes = []
        for doc in notes_docs:
            note_data = doc.to_dict()
            note_data['id'] = doc.id
            notes.append(note_data)

        # Sort by updated_at descending (newest first)
        notes.sort(key=lambda x: x.get('updated_at', ''), reverse=True)

        return jsonify({
            'success': True,
            'notes': notes,
            'total': len(notes)
        })

    except Exception as e:
        logger.error(f"Error fetching notes: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch notes'
        }), 500

@bp.route('/api/brain-dump/notes', methods=['POST'])
@auth_required
def create_note():
    """Create a new note"""
    try:
        data = request.json or {}
        user_id = str(g.user.get('id'))

        # Create new note
        now = datetime.utcnow().isoformat() + 'Z'

        new_note = {
            'title': data.get('title', 'Untitled'),
            'content': data.get('content', ''),
            'tags': data.get('tags', []),
            'is_favorite': data.get('is_favorite', False),
            'created_at': now,
            'updated_at': now
        }

        # Store note in Firebase
        notes_ref = db.collection('users').document(user_id).collection('brain_dump')
        doc_ref = notes_ref.add(new_note)
        note_id = doc_ref[1].id

        # Add the ID to the note object for response
        new_note['id'] = note_id

        logger.info(f"Created note {note_id} for user {user_id}")

        return jsonify({
            'success': True,
            'note': new_note,
            'message': 'Note created successfully'
        })

    except Exception as e:
        logger.error(f"Error creating note: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to create note'
        }), 500

@bp.route('/api/brain-dump/notes/<note_id>', methods=['GET'])
@auth_required
def get_note(note_id):
    """Get a specific note"""
    try:
        user_id = str(g.user.get('id'))

        # Get note from Firebase
        note_ref = db.collection('users').document(user_id).collection('brain_dump').document(note_id)
        note_doc = note_ref.get()

        if not note_doc.exists:
            return jsonify({
                'success': False,
                'error': 'Note not found'
            }), 404

        note = note_doc.to_dict()
        note['id'] = note_doc.id

        return jsonify({
            'success': True,
            'note': note
        })

    except Exception as e:
        logger.error(f"Error fetching note: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch note'
        }), 500

@bp.route('/api/brain-dump/notes/<note_id>', methods=['PUT'])
@auth_required
def update_note(note_id):
    """Update an existing note"""
    try:
        data = request.json or {}
        user_id = str(g.user.get('id'))

        # Check if note exists in Firebase
        note_ref = db.collection('users').document(user_id).collection('brain_dump').document(note_id)
        note_doc = note_ref.get()

        if not note_doc.exists:
            return jsonify({
                'success': False,
                'error': 'Note not found'
            }), 404

        # Prepare update data
        update_data = {}

        # Update fields if provided
        if 'title' in data:
            update_data['title'] = data['title'] if data['title'] else 'Untitled'
        if 'content' in data:
            update_data['content'] = data['content']
        if 'tags' in data:
            update_data['tags'] = data['tags']
        if 'is_favorite' in data:
            update_data['is_favorite'] = data['is_favorite']

        update_data['updated_at'] = datetime.utcnow().isoformat() + 'Z'

        # Update note in Firebase
        note_ref.update(update_data)

        # Get updated note
        updated_doc = note_ref.get()
        note = updated_doc.to_dict()
        note['id'] = updated_doc.id

        logger.info(f"Updated note {note_id} for user {user_id}")

        return jsonify({
            'success': True,
            'note': note,
            'message': 'Note updated successfully'
        })

    except Exception as e:
        logger.error(f"Error updating note: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to update note'
        }), 500

@bp.route('/api/brain-dump/notes/<note_id>', methods=['DELETE'])
@auth_required
def delete_note(note_id):
    """Delete a note"""
    try:
        user_id = str(g.user.get('id'))

        # Check if note exists in Firebase
        note_ref = db.collection('users').document(user_id).collection('brain_dump').document(note_id)
        note_doc = note_ref.get()

        if not note_doc.exists:
            return jsonify({
                'success': False,
                'error': 'Note not found'
            }), 404

        # Delete note from Firebase
        note_ref.delete()

        logger.info(f"Deleted note {note_id} for user {user_id}")

        return jsonify({
            'success': True,
            'message': 'Note deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting note: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to delete note'
        }), 500

@bp.route('/api/brain-dump/notes/<note_id>/favorite', methods=['POST'])
@auth_required
def toggle_favorite(note_id):
    """Toggle favorite status of a note"""
    try:
        data = request.json or {}
        user_id = str(g.user.get('id'))

        # Check if note exists in Firebase
        note_ref = db.collection('users').document(user_id).collection('brain_dump').document(note_id)
        note_doc = note_ref.get()

        if not note_doc.exists:
            return jsonify({
                'success': False,
                'error': 'Note not found'
            }), 404

        # Update favorite status in Firebase
        update_data = {
            'is_favorite': data.get('is_favorite', False),
            'updated_at': datetime.utcnow().isoformat() + 'Z'
        }
        note_ref.update(update_data)

        # Get updated note
        updated_doc = note_ref.get()
        note = updated_doc.to_dict()
        note['id'] = updated_doc.id

        return jsonify({
            'success': True,
            'note': note,
            'message': 'Favorite status updated'
        })

    except Exception as e:
        logger.error(f"Error toggling favorite: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to update favorite status'
        }), 500

@bp.route('/api/brain-dump/search', methods=['GET'])
@auth_required
def search_notes():
    """Search notes with query parameter"""
    try:
        query = request.args.get('q', '').lower().strip()
        user_id = str(g.user.get('id'))

        # Get all user's notes from Firebase
        notes_ref = db.collection('users').document(user_id).collection('brain_dump')
        notes_docs = notes_ref.stream()

        notes = []
        for doc in notes_docs:
            note_data = doc.to_dict()
            note_data['id'] = doc.id

            if not query:
                # Return all notes if no query
                notes.append(note_data)
            else:
                # Search in title and content
                title_match = query in (note_data.get('title', '') or '').lower()

                # Remove HTML tags for content search
                content = note_data.get('content', '') or ''
                import re
                clean_content = re.sub('<[^<]+?>', '', content)
                content_match = query in clean_content.lower()

                # Search in tags
                tags_match = any(query in tag.lower() for tag in (note_data.get('tags', []) or []))

                if title_match or content_match or tags_match:
                    notes.append(note_data)

        # Sort by updated_at descending
        notes.sort(key=lambda x: x.get('updated_at', ''), reverse=True)

        return jsonify({
            'success': True,
            'notes': notes,
            'query': query,
            'total': len(notes)
        })

    except Exception as e:
        logger.error(f"Error searching notes: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to search notes'
        }), 500

@bp.route('/api/brain-dump/tags', methods=['GET'])
@auth_required
def get_all_tags():
    """Get all unique tags used by the user"""
    try:
        user_id = str(g.user.get('id'))

        # Get all user's notes from Firebase
        notes_ref = db.collection('users').document(user_id).collection('brain_dump')
        notes_docs = notes_ref.stream()

        # Collect all unique tags
        all_tags = set()
        for doc in notes_docs:
            note_data = doc.to_dict()
            tags = note_data.get('tags', [])
            if tags:
                all_tags.update(tags)

        # Sort tags alphabetically
        tags_list = sorted(list(all_tags))

        return jsonify({
            'success': True,
            'tags': tags_list,
            'preset_tags': PRESET_TAGS,
            'total': len(tags_list)
        })

    except Exception as e:
        logger.error(f"Error fetching tags: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch tags'
        }), 500

@bp.route('/api/brain-dump/notes/<note_id>/share', methods=['POST'])
@auth_required
def share_note(note_id):
    """Create a public share link for a note"""
    try:
        user_id = str(g.user.get('id'))

        # Get the note from Firebase
        note_ref = db.collection('users').document(user_id).collection('brain_dump').document(note_id)
        note_doc = note_ref.get()

        if not note_doc.exists:
            return jsonify({
                'success': False,
                'error': 'Note not found'
            }), 404

        note_data = note_doc.to_dict()

        # Generate unique share ID
        share_id = secrets.token_urlsafe(8)

        # Create shared note document
        shared_note = {
            'note_id': note_id,
            'owner_id': user_id,
            'title': note_data.get('title', 'Untitled'),
            'content': note_data.get('content', ''),
            'tags': note_data.get('tags', []),
            'shared_at': datetime.utcnow().isoformat() + 'Z',
            'expires_at': (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z',  # 30 days expiry
            'views': 0
        }

        # Store in global shared_notes collection for easy public access
        shared_ref = db.collection('shared_notes').document(share_id)
        shared_ref.set(shared_note)

        # Update the original note with share info
        note_ref.update({
            'is_shared': True,
            'share_id': share_id,
            'share_url': f'https://creatrics.com/shared/note/{share_id}',
            'shared_at': datetime.utcnow().isoformat() + 'Z'
        })

        return jsonify({
            'success': True,
            'share_url': f'https://creatrics.com/shared/note/{share_id}',
            'share_id': share_id,
            'expires_in_days': 30,
            'message': 'Note shared successfully'
        })

    except Exception as e:
        logger.error(f"Error sharing note: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to share note'
        }), 500

@bp.route('/api/brain-dump/notes/<note_id>/unshare', methods=['POST'])
@auth_required
def unshare_note(note_id):
    """Remove public share link for a note"""
    try:
        user_id = str(g.user.get('id'))

        # Get the note
        note_ref = db.collection('users').document(user_id).collection('brain_dump').document(note_id)
        note_doc = note_ref.get()

        if not note_doc.exists:
            return jsonify({
                'success': False,
                'error': 'Note not found'
            }), 404

        note_data = note_doc.to_dict()
        share_id = note_data.get('share_id')

        if share_id:
            # Delete from global shared_notes collection
            shared_ref = db.collection('shared_notes').document(share_id)
            # Verify ownership before deleting
            shared_doc = shared_ref.get()
            if shared_doc.exists and shared_doc.to_dict().get('owner_id') == user_id:
                shared_ref.delete()

        # Update the original note
        note_ref.update({
            'is_shared': False,
            'share_id': None,
            'share_url': None,
            'shared_at': None
        })

        return jsonify({
            'success': True,
            'message': 'Note unshared successfully'
        })

    except Exception as e:
        logger.error(f"Error unsharing note: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to unshare note'
        }), 500

@bp.route('/shared/note/<share_id>')
def view_shared_note(share_id):
    """View a publicly shared note (no auth required)"""
    try:
        # Get shared note from global collection
        shared_ref = db.collection('shared_notes').document(share_id)
        shared_doc = shared_ref.get()

        if not shared_doc.exists:
            return render_template('errors/404.html'), 404

        shared_data = shared_doc.to_dict()

        # Check if expired
        expires_at = datetime.fromisoformat(shared_data['expires_at'].replace('Z', '+00:00'))
        if datetime.utcnow() > expires_at:
            return render_template('brain_dump/expired.html'), 410

        # Increment view count
        shared_ref.update({'views': shared_data.get('views', 0) + 1})

        # Render public view template
        return render_template('brain_dump/public_note.html',
                             note=shared_data,
                             share_id=share_id)

    except Exception as e:
        logger.error(f"Error viewing shared note: {e}")
        return render_template('errors/404.html'), 404

@bp.route('/api/brain-dump/export', methods=['POST'])
@auth_required
def export_notes():
    """Export notes in various formats (JSON, Markdown, HTML)"""
    try:
        data = request.json or {}
        format_type = data.get('format', 'json').lower()
        note_ids = data.get('note_ids', [])
        user_id = str(g.user.get('id'))

        # Get notes from Firebase
        notes_ref = db.collection('users').document(user_id).collection('brain_dump')

        notes_list = []
        if note_ids:
            # Get specific notes
            for note_id in note_ids:
                note_doc = notes_ref.document(note_id).get()
                if note_doc.exists:
                    note_data = note_doc.to_dict()
                    note_data['id'] = note_doc.id
                    notes_list.append(note_data)
        else:
            # Get all notes
            notes_docs = notes_ref.stream()
            for doc in notes_docs:
                note_data = doc.to_dict()
                note_data['id'] = doc.id
                notes_list.append(note_data)
        
        if format_type == 'json':
            return jsonify({
                'success': True,
                'data': notes_list,
                'format': 'json',
                'count': len(notes_list)
            })
        
        elif format_type == 'markdown':
            # Convert to markdown format
            markdown_content = "# Brain Dump Export\n\n"
            
            for note in notes_list:
                title = note.get('title', 'Untitled')
                content = note.get('content', '')
                tags = note.get('tags', [])
                created = note.get('created_at', '')
                updated = note.get('updated_at', '')
                
                # Remove HTML tags from content
                import re
                clean_content = re.sub('<[^<]+?>', '', content)
                
                markdown_content += f"## {title}\n\n"
                markdown_content += f"**Created:** {created}\n"
                markdown_content += f"**Updated:** {updated}\n"
                if tags:
                    markdown_content += f"**Tags:** {', '.join(tags)}\n"
                markdown_content += f"\n{clean_content}\n\n"
                markdown_content += "---\n\n"
            
            return jsonify({
                'success': True,
                'data': markdown_content,
                'format': 'markdown',
                'count': len(notes_list)
            })
        
        elif format_type == 'html':
            # Convert to HTML format
            html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Brain Dump Export</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 2rem; max-width: 800px; margin: 0 auto; }
        h1 { color: #667eea; }
        .note { margin-bottom: 2rem; padding: 1rem; border-left: 3px solid #667eea; background: #f9fafb; }
        .note-title { font-size: 1.5rem; font-weight: 600; margin-bottom: 0.5rem; }
        .note-meta { font-size: 0.875rem; color: #6b7280; margin-bottom: 1rem; }
        .note-content { line-height: 1.6; }
        .tags { display: flex; gap: 0.5rem; margin-top: 1rem; }
        .tag { background: #dbeafe; color: #1e40af; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; }
    </style>
</head>
<body>
    <h1>Brain Dump Export</h1>
"""
            
            for note in notes_list:
                title = note.get('title', 'Untitled')
                content = note.get('content', '')
                tags = note.get('tags', [])
                created = note.get('created_at', '')
                
                html_content += f"""
    <div class="note">
        <div class="note-title">{title}</div>
        <div class="note-meta">Created: {created}</div>
        <div class="note-content">{content}</div>
"""
                
                if tags:
                    html_content += '        <div class="tags">\n'
                    for tag in tags:
                        html_content += f'            <span class="tag">{tag}</span>\n'
                    html_content += '        </div>\n'
                
                html_content += '    </div>\n'
            
            html_content += """
</body>
</html>"""
            
            return jsonify({
                'success': True,
                'data': html_content,
                'format': 'html',
                'count': len(notes_list)
            })
        
        else:
            return jsonify({
                'success': False,
                'error': f'Export format {format_type} not supported. Use "json", "markdown", or "html".'
            }), 400

    except Exception as e:
        logger.error(f"Error exporting notes: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to export notes'
        }), 500

@bp.route('/api/brain-dump/stats', methods=['GET'])
@auth_required
def get_stats():
    """Get user's notes statistics"""
    try:
        user_id = str(g.user.get('id'))

        # Get all user's notes from Firebase
        notes_ref = db.collection('users').document(user_id).collection('brain_dump')
        notes_docs = notes_ref.stream()

        notes_list = []
        for doc in notes_docs:
            note_data = doc.to_dict()
            notes_list.append(note_data)
        
        # Calculate stats
        total_notes = len(notes_list)
        favorite_count = sum(1 for note in notes_list if note.get('is_favorite', False))
        
        # Get all tags
        all_tags = []
        for note in notes_list:
            tags = note.get('tags', [])
            if tags:
                all_tags.extend(tags)
        
        unique_tags = len(set(all_tags))
        
        # Calculate average note length
        total_length = 0
        for note in notes_list:
            content = note.get('content', '')
            # Remove HTML tags
            import re
            clean_content = re.sub('<[^<]+?>', '', content)
            total_length += len(clean_content)
        
        avg_length = total_length // total_notes if total_notes > 0 else 0
        
        # Get recent notes (last 7 days)
        from datetime import timedelta
        week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat() + 'Z'
        recent_notes = sum(1 for note in notes_list if note.get('updated_at', '') >= week_ago)
        
        return jsonify({
            'success': True,
            'stats': {
                'total_notes': total_notes,
                'favorites': favorite_count,
                'unique_tags': unique_tags,
                'average_note_length': avg_length,
                'recent_notes': recent_notes,
                'total_words': total_length // 5  # Rough word count estimate
            }
        })

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get statistics'
        }), 500

# Helper function to bulk import notes (useful for testing)
@bp.route('/api/brain-dump/import', methods=['POST'])
@auth_required
def import_notes():
    """Import notes from JSON"""
    try:
        data = request.json or {}
        imported_notes = data.get('notes', [])
        user_id = str(g.user.get('id'))

        # Get Firebase reference
        notes_ref = db.collection('users').document(user_id).collection('brain_dump')

        imported_count = 0

        for note_data in imported_notes:
            now = datetime.utcnow().isoformat() + 'Z'

            new_note = {
                'title': note_data.get('title', 'Imported Note'),
                'content': note_data.get('content', ''),
                'tags': note_data.get('tags', []),
                'is_favorite': note_data.get('is_favorite', False),
                'created_at': note_data.get('created_at', now),
                'updated_at': now
            }

            # Add to Firebase
            notes_ref.add(new_note)
            imported_count += 1

        logger.info(f"Imported {imported_count} notes for user {user_id}")

        return jsonify({
            'success': True,
            'message': f'Successfully imported {imported_count} notes',
            'count': imported_count
        })

    except Exception as e:
        logger.error(f"Error importing notes: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to import notes'
        }), 500