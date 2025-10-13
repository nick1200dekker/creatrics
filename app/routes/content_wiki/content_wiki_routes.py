from flask import render_template, request, jsonify, g, redirect, url_for
from . import bp
from app.system.auth.middleware import auth_required
from app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission
from app.system.services.firebase_service import db, storage
from datetime import datetime, timezone
import logging
import json
import uuid
import re
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

# Preset categories for wiki organization
PRESET_CATEGORIES = [
    {'id': 'brand', 'name': 'Brand Guidelines', 'icon': 'ph-palette', 'color': '#8B5CF6'},
    {'id': 'content', 'name': 'Content Standards', 'icon': 'ph-article', 'color': '#3B82F6'},
    {'id': 'visual', 'name': 'Visual Assets', 'icon': 'ph-image', 'color': '#EC4899'},
    {'id': 'templates', 'name': 'Templates', 'icon': 'ph-files', 'color': '#F59E0B'},
    {'id': 'processes', 'name': 'Processes', 'icon': 'ph-gear-six', 'color': '#10B981'},
    {'id': 'team', 'name': 'Team Resources', 'icon': 'ph-users-three', 'color': '#06B6D4'},
    {'id': 'legal', 'name': 'Legal & Compliance', 'icon': 'ph-scales', 'color': '#EF4444'},
    {'id': 'reference', 'name': 'Reference Materials', 'icon': 'ph-book-open', 'color': '#84CC16'},
]

@bp.route('/content-wiki')
@auth_required
@require_permission('content_wiki')
def content_wiki():
    """Content Wiki main page"""
    return render_template('content_wiki/index.html')

@bp.route('/api/content-wiki/pages', methods=['GET'])
@auth_required
@require_permission('content_wiki')
def get_pages():
    """Get all wiki pages for the current workspace"""
    try:
        user_id = get_workspace_user_id()
        category = request.args.get('category')
        folder = request.args.get('folder')
        search_query = request.args.get('q', '').lower()

        # Get user's wiki pages from Firebase
        pages_ref = db.collection('users').document(user_id).collection('content_wiki')

        # Filter by category if specified
        if category:
            pages_query = pages_ref.where('category', '==', category)
        else:
            pages_query = pages_ref

        pages_docs = pages_query.stream()

        # Convert to list and filter
        pages = []
        for doc in pages_docs:
            page_data = doc.to_dict()
            page_data['id'] = doc.id

            # Apply folder filter if specified
            if folder:
                # Only show items in this specific folder
                if page_data.get('parent_folder') != folder:
                    continue
            elif category:
                # If category is specified but no folder, only show items at root level (no parent_folder)
                if page_data.get('parent_folder'):
                    continue

            # Apply search filter if needed
            if search_query:
                title_match = search_query in (page_data.get('title', '') or '').lower()
                content_match = search_query in (page_data.get('content', '') or '').lower()
                if not (title_match or content_match):
                    continue

            pages.append(page_data)
        
        # Sort by updated_at descending (newest first)
        pages.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'pages': pages,
            'total': len(pages),
            'categories': PRESET_CATEGORIES
        })
    
    except Exception as e:
        logger.error(f"Error fetching wiki pages: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch wiki pages'
        }), 500

@bp.route('/api/content-wiki/pages', methods=['POST'])
@auth_required
@require_permission('content_wiki')
def create_page():
    """Create a new wiki page, file entry, or folder"""
    try:
        data = request.json or {}
        user_id = get_workspace_user_id()

        # Check if it's a file, folder, or document
        is_file = data.get('is_file', False)
        is_folder = data.get('is_folder', False)

        # Generate slug from title (for documents and folders)
        title = data.get('title', 'Untitled')
        if not is_file:
            slug = generate_slug(title)

            # Check if slug exists and make it unique
            pages_ref = db.collection('users').document(user_id).collection('content_wiki')
            existing = pages_ref.where('slug', '==', slug).get()
            if existing:
                slug = f"{slug}-{uuid.uuid4().hex[:6]}"
        else:
            slug = None
            title = data.get('filename', title)

        now = datetime.now(timezone.utc).isoformat()

        new_page = {
            'title': title,
            'slug': slug,
            'content': data.get('content', ''),
            'category': data.get('category', 'brand'),
            'tags': data.get('tags', []),
            'is_pinned': data.get('is_pinned', False),
            'is_template': data.get('is_template', False),
            'is_file': is_file,
            'is_folder': is_folder,
            'parent_folder': data.get('parent_folder'),
            'metadata': data.get('metadata', {}),
            'attachments': data.get('attachments', []),
            'created_at': now,
            'updated_at': now,
            'version': 1,
            'last_edited_by': g.user.get('data', {}).get('username', 'Unknown')
        }

        # Add file-specific fields
        if is_file:
            new_page['filename'] = data.get('filename', '')
            new_page['url'] = data.get('url', '')
            new_page['size'] = data.get('size', 0)
            new_page['type'] = data.get('type', '')

        # Store page in Firebase
        pages_ref = db.collection('users').document(user_id).collection('content_wiki')
        doc_ref = pages_ref.add(new_page)
        page_id = doc_ref[1].id

        # Add the ID to the page object for response
        new_page['id'] = page_id

        item_type = 'folder' if is_folder else 'file' if is_file else 'page'
        logger.info(f"Created wiki {item_type} {page_id} for user {user_id}")

        return jsonify({
            'success': True,
            'page': new_page,
            'message': f"{'Folder' if is_folder else 'File' if is_file else 'Page'} created successfully"
        })

    except Exception as e:
        logger.error(f"Error creating wiki page: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to create'
        }), 500

@bp.route('/api/content-wiki/pages/<page_id>', methods=['GET'])
@auth_required
@require_permission('content_wiki')
def get_page(page_id):
    """Get a specific wiki page"""
    try:
        user_id = get_workspace_user_id()
        
        # Get page from Firebase
        page_ref = db.collection('users').document(user_id).collection('content_wiki').document(page_id)
        page_doc = page_ref.get()
        
        if not page_doc.exists:
            return jsonify({
                'success': False,
                'error': 'Page not found'
            }), 404
        
        page = page_doc.to_dict()
        page['id'] = page_doc.id
        
        return jsonify({
            'success': True,
            'page': page
        })
    
    except Exception as e:
        logger.error(f"Error fetching wiki page: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch page'
        }), 500

@bp.route('/api/content-wiki/pages/<page_id>', methods=['PUT'])
@auth_required
@require_permission('content_wiki')
def update_page(page_id):
    """Update an existing wiki page"""
    try:
        data = request.json or {}
        user_id = get_workspace_user_id()
        
        # Check if page exists in Firebase
        page_ref = db.collection('users').document(user_id).collection('content_wiki').document(page_id)
        page_doc = page_ref.get()
        
        if not page_doc.exists:
            return jsonify({
                'success': False,
                'error': 'Page not found'
            }), 404
        
        existing_page = page_doc.to_dict()
        
        # Prepare update data
        update_data = {}
        
        # Update fields if provided
        if 'title' in data:
            update_data['title'] = data['title']
            # Update slug if title changed
            new_slug = generate_slug(data['title'])
            if new_slug != existing_page.get('slug'):
                # Check if new slug is unique
                pages_ref = db.collection('users').document(user_id).collection('content_wiki')
                existing_slugs = pages_ref.where('slug', '==', new_slug).get()
                if existing_slugs and len(existing_slugs) > 0:
                    # Check if it's not the same document
                    for doc in existing_slugs:
                        if doc.id != page_id:
                            new_slug = f"{new_slug}-{uuid.uuid4().hex[:6]}"
                            break
                update_data['slug'] = new_slug
        
        if 'content' in data:
            update_data['content'] = data['content']
        if 'category' in data:
            update_data['category'] = data['category']
        if 'tags' in data:
            update_data['tags'] = data['tags']
        if 'is_pinned' in data:
            update_data['is_pinned'] = data['is_pinned']
        if 'is_template' in data:
            update_data['is_template'] = data['is_template']
        if 'metadata' in data:
            update_data['metadata'] = data['metadata']
        if 'attachments' in data:
            update_data['attachments'] = data['attachments']
        if 'filename' in data:
            update_data['filename'] = data['filename']
        
        update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
        update_data['version'] = existing_page.get('version', 1) + 1
        update_data['last_edited_by'] = g.user.get('data', {}).get('username', 'Unknown')
        
        # Update page in Firebase
        page_ref.update(update_data)
        
        # Get updated page
        updated_doc = page_ref.get()
        page = updated_doc.to_dict()
        page['id'] = updated_doc.id
        
        logger.info(f"Updated wiki page {page_id} for user {user_id}")
        
        return jsonify({
            'success': True,
            'page': page,
            'message': 'Page updated successfully'
        })
    
    except Exception as e:
        logger.error(f"Error updating wiki page: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to update page'
        }), 500

@bp.route('/api/content-wiki/pages/<page_id>', methods=['DELETE'])
@auth_required
@require_permission('content_wiki')
def delete_page(page_id):
    """Delete a wiki page"""
    try:
        user_id = get_workspace_user_id()
        
        # Check if page exists in Firebase
        page_ref = db.collection('users').document(user_id).collection('content_wiki').document(page_id)
        page_doc = page_ref.get()
        
        if not page_doc.exists:
            return jsonify({
                'success': False,
                'error': 'Page not found'
            }), 404
        
        # Get page data for cleanup
        page_data = page_doc.to_dict()
        
        # Delete associated attachments from storage if any
        if page_data.get('attachments'):
            bucket = storage.bucket()
            for attachment in page_data['attachments']:
                # Extract blob path from URL if needed
                if 'url' in attachment:
                    try:
                        # Parse the storage URL to get the blob path
                        url_parts = attachment['url'].split('/')
                        if 'content_wiki' in attachment['url']:
                            # Find the content_wiki part and reconstruct path
                            idx = url_parts.index('content_wiki')
                            blob_path = '/'.join(url_parts[idx-2:])  # Get users/{user_id}/content_wiki/...
                            blob = bucket.blob(blob_path)
                            if blob.exists():
                                blob.delete()
                                logger.info(f"Deleted attachment {blob_path}")
                    except Exception as e:
                        logger.warning(f"Could not delete attachment: {e}")
        
        # Delete page from Firebase
        page_ref.delete()
        
        logger.info(f"Deleted wiki page {page_id} for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Page deleted successfully'
        })
    
    except Exception as e:
        logger.error(f"Error deleting wiki page: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to delete page'
        }), 500

@bp.route('/api/content-wiki/pages/<page_id>/duplicate', methods=['POST'])
@auth_required
@require_permission('content_wiki')
def duplicate_page(page_id):
    """Duplicate a wiki page"""
    try:
        user_id = get_workspace_user_id()
        
        # Get original page
        page_ref = db.collection('users').document(user_id).collection('content_wiki').document(page_id)
        page_doc = page_ref.get()
        
        if not page_doc.exists:
            return jsonify({
                'success': False,
                'error': 'Page not found'
            }), 404
        
        original = page_doc.to_dict()
        
        # Create duplicate with modified title and slug
        title = f"{original.get('title', 'Untitled')} (Copy)"
        slug = generate_slug(title)
        
        # Check if slug exists and make it unique
        pages_ref = db.collection('users').document(user_id).collection('content_wiki')
        existing = pages_ref.where('slug', '==', slug).get()
        if existing:
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"
        
        now = datetime.now(timezone.utc).isoformat()
        
        duplicate_page_data = {
            'title': title,
            'slug': slug,
            'content': original.get('content', ''),
            'category': original.get('category', 'brand'),
            'tags': original.get('tags', []),
            'is_pinned': False,  # Don't pin duplicates by default
            'is_template': original.get('is_template', False),
            'metadata': original.get('metadata', {}),
            'attachments': original.get('attachments', []),  # Keep attachment references
            'created_at': now,
            'updated_at': now,
            'version': 1,
            'last_edited_by': g.user.get('data', {}).get('username', 'Unknown'),
            'duplicated_from': page_id
        }
        
        # Store duplicate in Firebase
        doc_ref = pages_ref.add(duplicate_page_data)
        new_page_id = doc_ref[1].id
        
        # Add the ID to the page object for response
        duplicate_page_data['id'] = new_page_id
        
        logger.info(f"Duplicated wiki page {page_id} to {new_page_id} for user {user_id}")
        
        return jsonify({
            'success': True,
            'page': duplicate_page_data,
            'message': 'Page duplicated successfully'
        })
    
    except Exception as e:
        logger.error(f"Error duplicating wiki page: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to duplicate page'
        }), 500

@bp.route('/api/content-wiki/upload', methods=['POST'])
@auth_required
@require_permission('content_wiki')
def upload_attachment():
    """Upload attachment for wiki pages"""
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        user_id = get_workspace_user_id()
        
        # Validate file size (max 10MB)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > 10 * 1024 * 1024:  # 10MB
            return jsonify({
                'success': False,
                'error': 'File too large. Maximum size is 10MB'
            }), 400
        
        # Generate unique filename
        filename = secure_filename(file.filename)
        file_extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}" if file_extension else uuid.uuid4().hex
        
        # Upload to Firebase Storage
        blob_path = f"users/{user_id}/content_wiki/{unique_filename}"
        bucket = storage.bucket()
        blob = bucket.blob(blob_path)
        
        # Set content type
        content_type = file.content_type or 'application/octet-stream'
        
        # Upload the file
        blob.upload_from_file(file, content_type=content_type)
        
        # Make the blob publicly accessible
        blob.make_public()
        
        # Get the public URL
        public_url = blob.public_url
        
        # Create attachment metadata
        attachment = {
            'id': uuid.uuid4().hex,
            'filename': filename,
            'url': public_url,
            'size': file_size,
            'type': content_type,
            'uploaded_at': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Uploaded attachment {unique_filename} for user {user_id}")
        
        return jsonify({
            'success': True,
            'attachment': attachment,
            'message': 'File uploaded successfully'
        })
    
    except Exception as e:
        logger.error(f"Error uploading attachment: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to upload file'
        }), 500

@bp.route('/api/content-wiki/templates', methods=['GET'])
@auth_required
@require_permission('content_wiki')
def get_templates():
    """Get wiki page templates"""
    try:
        user_id = get_workspace_user_id()
        
        # Get template pages
        pages_ref = db.collection('users').document(user_id).collection('content_wiki')
        templates_query = pages_ref.where('is_template', '==', True)
        templates_docs = templates_query.stream()
        
        templates = []
        for doc in templates_docs:
            template_data = doc.to_dict()
            template_data['id'] = doc.id
            templates.append(template_data)
        
        # Also include system templates
        system_templates = get_system_templates()
        
        return jsonify({
            'success': True,
            'user_templates': templates,
            'system_templates': system_templates
        })
    
    except Exception as e:
        logger.error(f"Error fetching templates: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch templates'
        }), 500

@bp.route('/api/content-wiki/search', methods=['GET'])
@auth_required
@require_permission('content_wiki')
def search_wiki():
    """Search across all wiki pages"""
    try:
        query = request.args.get('q', '').lower().strip()
        user_id = get_workspace_user_id()
        
        if not query:
            return jsonify({
                'success': True,
                'results': [],
                'query': query
            })
        
        # Get all pages
        pages_ref = db.collection('users').document(user_id).collection('content_wiki')
        pages_docs = pages_ref.stream()
        
        results = []
        for doc in pages_docs:
            page_data = doc.to_dict()
            page_data['id'] = doc.id
            
            # Calculate relevance score
            score = 0
            title = (page_data.get('title', '') or '').lower()
            content = (page_data.get('content', '') or '').lower()
            
            # Remove HTML tags for content search
            clean_content = re.sub('<[^<]+?>', '', content)
            
            # Title matches are worth more
            if query in title:
                score += 10
                if title.startswith(query):
                    score += 5
            
            # Content matches
            if query in clean_content:
                score += 5
                # Count occurrences (limited to avoid spam)
                score += min(clean_content.count(query), 5)
            
            # Tag matches
            tags = page_data.get('tags', []) or []
            for tag in tags:
                if query in tag.lower():
                    score += 3
            
            if score > 0:
                results.append({
                    'page': page_data,
                    'score': score,
                    'preview': get_content_preview(clean_content, query)
                })
        
        # Sort by relevance score
        results.sort(key=lambda x: x['score'], reverse=True)
        
        # Limit to top 20 results
        results = results[:20]
        
        return jsonify({
            'success': True,
            'results': results,
            'query': query,
            'total': len(results)
        })
    
    except Exception as e:
        logger.error(f"Error searching wiki: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to search wiki'
        }), 500

@bp.route('/api/content-wiki/export', methods=['POST'])
@auth_required
@require_permission('content_wiki')
def export_wiki():
    """Export wiki pages in various formats"""
    try:
        data = request.json or {}
        format_type = data.get('format', 'json').lower()
        page_ids = data.get('page_ids', [])
        include_attachments = data.get('include_attachments', False)
        user_id = get_workspace_user_id()
        
        # Get pages from Firebase
        pages_ref = db.collection('users').document(user_id).collection('content_wiki')
        
        pages_list = []
        if page_ids:
            # Get specific pages
            for page_id in page_ids:
                page_doc = pages_ref.document(page_id).get()
                if page_doc.exists:
                    page_data = page_doc.to_dict()
                    page_data['id'] = page_doc.id
                    pages_list.append(page_data)
        else:
            # Get all pages
            pages_docs = pages_ref.stream()
            for doc in pages_docs:
                page_data = doc.to_dict()
                page_data['id'] = doc.id
                pages_list.append(page_data)
        
        # Sort pages by category and title
        pages_list.sort(key=lambda x: (x.get('category', 'z'), x.get('title', '')))
        
        if format_type == 'json':
            export_data = {
                'exported_at': datetime.now(timezone.utc).isoformat(),
                'pages': pages_list,
                'categories': PRESET_CATEGORIES
            }
            
            if include_attachments:
                export_data['include_attachments'] = True
            
            return jsonify({
                'success': True,
                'data': export_data,
                'format': 'json',
                'count': len(pages_list)
            })
        
        elif format_type == 'markdown':
            # Convert to markdown format
            markdown_content = "# Content Wiki Export\n\n"
            markdown_content += f"*Exported on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*\n\n"
            markdown_content += "---\n\n"
            
            # Group by category
            pages_by_category = {}
            for page in pages_list:
                category = page.get('category', 'uncategorized')
                if category not in pages_by_category:
                    pages_by_category[category] = []
                pages_by_category[category].append(page)
            
            # Order categories based on PRESET_CATEGORIES
            category_order = {cat['id']: idx for idx, cat in enumerate(PRESET_CATEGORIES)}
            sorted_categories = sorted(pages_by_category.keys(), 
                                     key=lambda x: category_order.get(x, 999))
            
            for category in sorted_categories:
                pages = pages_by_category[category]
                
                # Find category name and icon
                category_info = next((cat for cat in PRESET_CATEGORIES if cat['id'] == category), None)
                if category_info:
                    category_name = f"{category_info['icon']} {category_info['name']}"
                else:
                    category_name = category.title()
                
                markdown_content += f"## {category_name}\n\n"
                
                for page in pages:
                    title = page.get('title', 'Untitled')
                    content = page.get('content', '')
                    tags = page.get('tags', [])
                    updated = page.get('updated_at', '')
                    version = page.get('version', 1)
                    
                    # Remove HTML tags from content
                    clean_content = re.sub('<[^<]+?>', '', content)
                    # Convert multiple spaces to single space
                    clean_content = re.sub(r'\s+', ' ', clean_content).strip()
                    
                    markdown_content += f"### {title}\n\n"
                    
                    if tags:
                        markdown_content += f"**Tags:** {', '.join(tags)}\n"
                    
                    markdown_content += f"**Version:** {version} | **Last Updated:** {updated[:10] if updated else 'Unknown'}\n\n"
                    markdown_content += f"{clean_content}\n\n"
                    
                    if page.get('attachments'):
                        markdown_content += "**Attachments:**\n"
                        for att in page['attachments']:
                            markdown_content += f"- [{att['filename']}]({att['url']})\n"
                        markdown_content += "\n"
                    
                    markdown_content += "---\n\n"
            
            return jsonify({
                'success': True,
                'data': markdown_content,
                'format': 'markdown',
                'count': len(pages_list)
            })
        
        elif format_type == 'html':
            # Convert to HTML format for better presentation
            html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Content Wiki Export</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 900px; margin: 0 auto; padding: 2rem; }
        h1 { color: #8B5CF6; }
        h2 { color: #3B82F6; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }
        h3 { color: #1f2937; margin-top: 2rem; }
        .meta { font-size: 0.875rem; color: #6b7280; margin-bottom: 1rem; }
        .tags { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem; }
        .tag { background: #f3f4f6; padding: 0.25rem 0.75rem; border-radius: 20px; font-size: 0.875rem; }
        .content { line-height: 1.6; margin-bottom: 2rem; }
        .attachments { background: #f9fafb; padding: 1rem; border-radius: 8px; margin-top: 1rem; }
        hr { margin: 3rem 0; border: none; border-top: 1px solid #e5e7eb; }
    </style>
</head>
<body>
    <h1>Content Wiki Export</h1>
    <p class="meta">Exported on """ + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC') + """</p>
"""
            
            # Group by category
            pages_by_category = {}
            for page in pages_list:
                category = page.get('category', 'uncategorized')
                if category not in pages_by_category:
                    pages_by_category[category] = []
                pages_by_category[category].append(page)
            
            # Order categories
            category_order = {cat['id']: idx for idx, cat in enumerate(PRESET_CATEGORIES)}
            sorted_categories = sorted(pages_by_category.keys(), 
                                     key=lambda x: category_order.get(x, 999))
            
            for category in sorted_categories:
                pages = pages_by_category[category]
                
                # Find category info
                category_info = next((cat for cat in PRESET_CATEGORIES if cat['id'] == category), None)
                if category_info:
                    category_name = f"{category_info['icon']} {category_info['name']}"
                else:
                    category_name = category.title()
                
                html_content += f"<h2>{category_name}</h2>\n"
                
                for page in pages:
                    title = page.get('title', 'Untitled')
                    content = page.get('content', '')
                    tags = page.get('tags', [])
                    
                    html_content += f"<h3>{title}</h3>\n"
                    
                    if tags:
                        html_content += '<div class="tags">\n'
                        for tag in tags:
                            html_content += f'<span class="tag">{tag}</span>\n'
                        html_content += '</div>\n'
                    
                    html_content += f'<div class="content">{content}</div>\n'
                    
                    if page.get('attachments'):
                        html_content += '<div class="attachments">\n'
                        html_content += '<strong>Attachments:</strong><br>\n'
                        for att in page['attachments']:
                            html_content += f'<a href="{att["url"]}">{att["filename"]}</a><br>\n'
                        html_content += '</div>\n'
                    
                    html_content += '<hr>\n'
            
            html_content += """
</body>
</html>"""
            
            return jsonify({
                'success': True,
                'data': html_content,
                'format': 'html',
                'count': len(pages_list)
            })
        
        else:
            return jsonify({
                'success': False,
                'error': f'Export format {format_type} not supported. Use "json", "markdown", or "html".'
            }), 400
    
    except Exception as e:
        logger.error(f"Error exporting wiki: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to export wiki'
        }), 500

# Helper functions

def generate_slug(title):
    """Generate URL-friendly slug from title"""
    # Convert to lowercase
    slug = title.lower()
    # Replace spaces with hyphens
    slug = re.sub(r'\s+', '-', slug)
    # Remove special characters (keep letters, numbers, hyphens)
    slug = re.sub(r'[^\w\-]', '', slug)
    # Remove consecutive hyphens
    slug = re.sub(r'\-+', '-', slug)
    # Strip hyphens from ends
    slug = slug.strip('-')
    
    return slug or 'untitled'

def get_content_preview(content, query, preview_length=150):
    """Get a preview of content with query highlighted"""
    # Find the position of the query
    pos = content.lower().find(query)
    
    if pos == -1:
        # Query not found, return beginning of content
        preview = content[:preview_length]
        if len(content) > preview_length:
            preview += '...'
    else:
        # Show content around the query
        start = max(0, pos - 50)
        end = min(len(content), pos + 100)
        preview = content[start:end]
        
        if start > 0:
            preview = '...' + preview
        if end < len(content):
            preview = preview + '...'
    
    return preview

def get_system_templates():
    """Get predefined system templates"""
    return [
        {
            'id': 'brand-guidelines',
            'title': 'Brand Guidelines Template',
            'category': 'brand',
            'content': '''
                <h2>Brand Identity</h2>
                <h3>Mission Statement</h3>
                <p>[Your mission statement here]</p>
                
                <h3>Brand Values</h3>
                <ul>
                    <li>Value 1: [Description]</li>
                    <li>Value 2: [Description]</li>
                    <li>Value 3: [Description]</li>
                </ul>
                
                <h2>Visual Identity</h2>
                <h3>Logo Usage</h3>
                <p>[Logo guidelines and rules]</p>
                
                <h3>Color Palette</h3>
                <ul>
                    <li>Primary Color: #[HEX]</li>
                    <li>Secondary Color: #[HEX]</li>
                    <li>Accent Color: #[HEX]</li>
                </ul>
                
                <h3>Typography</h3>
                <p>Primary Font: [Font Name]</p>
                <p>Secondary Font: [Font Name]</p>
                
                <h2>Voice & Tone</h2>
                <p>[Brand voice description]</p>
            ''',
            'is_system': True
        },
        {
            'id': 'content-standards',
            'title': 'Content Standards Template',
            'category': 'content',
            'content': '''
                <h2>Content Guidelines</h2>
                
                <h3>Writing Style</h3>
                <ul>
                    <li>Tone: [Professional/Casual/Friendly]</li>
                    <li>Voice: [First person/Third person]</li>
                    <li>Language: [Simple/Technical]</li>
                </ul>
                
                <h3>Video Standards</h3>
                <ul>
                    <li>Resolution: [1080p/4K]</li>
                    <li>Frame Rate: [24/30/60 fps]</li>
                    <li>Aspect Ratio: [16:9/9:16]</li>
                    <li>Duration: [Target length]</li>
                </ul>
                
                <h3>Thumbnail Guidelines</h3>
                <ul>
                    <li>Dimensions: 1280x720px</li>
                    <li>File Format: JPG/PNG</li>
                    <li>Text Size: [Minimum size]</li>
                </ul>
                
                <h3>SEO Best Practices</h3>
                <p>[SEO guidelines for titles, descriptions, tags]</p>
            ''',
            'is_system': True
        },
        {
            'id': 'editor-letter',
            'title': 'Letter to Editors Template',
            'category': 'team',
            'content': '''
                <h2>Letter to Video Editors</h2>
                
                <h3>Project Overview</h3>
                <p>[Brief description of your content and channel]</p>
                
                <h3>Editing Style Guidelines</h3>
                <ul>
                    <li>Pacing: [Fast/Medium/Slow]</li>
                    <li>Transitions: [Types to use]</li>
                    <li>Music: [Style preferences]</li>
                    <li>Effects: [Guidelines for effects usage]</li>
                </ul>
                
                <h3>Brand Elements to Include</h3>
                <ul>
                    <li>Intro: [Description]</li>
                    <li>Outro: [Description]</li>
                    <li>Lower Thirds: [Style guide]</li>
                    <li>Watermark: [Position and opacity]</li>
                </ul>
                
                <h3>Technical Requirements</h3>
                <ul>
                    <li>Export Settings: [Specific requirements]</li>
                    <li>File Naming: [Convention to follow]</li>
                    <li>Delivery Method: [How to deliver files]</li>
                </ul>
                
                <h3>Do's and Don'ts</h3>
                <p><strong>Do:</strong></p>
                <ul>
                    <li>[List of things to do]</li>
                </ul>
                
                <p><strong>Don't:</strong></p>
                <ul>
                    <li>[List of things to avoid]</li>
                </ul>
            ''',
            'is_system': True
        }
    ]

@bp.route('/api/content-wiki/storage', methods=['GET'])
@auth_required
@require_permission('content_wiki')
def get_storage_usage():
    """Get storage usage for the current workspace"""
    try:
        user_id = get_workspace_user_id()

        # Get all pages (including attachments)
        pages_ref = db.collection('users').document(user_id).collection('content_wiki')
        pages = pages_ref.stream()

        total_bytes = 0

        for page in pages:
            page_data = page.to_dict()

            # Add file size if it's a file
            if page_data.get('is_file') and page_data.get('size'):
                total_bytes += page_data.get('size', 0)

            # Add attachment sizes
            if 'attachments' in page_data:
                for attachment in page_data.get('attachments', []):
                    total_bytes += attachment.get('size', 0)

        # Convert to MB
        total_mb = round(total_bytes / (1024 * 1024), 2)
        max_mb = 1024  # 1GB limit
        percentage = round((total_bytes / (max_mb * 1024 * 1024)) * 100, 2)

        return jsonify({
            'success': True,
            'storage': {
                'used_bytes': total_bytes,
                'used_mb': total_mb,
                'max_mb': max_mb,
                'percentage': percentage
            }
        })

    except Exception as e:
        logger.error(f"Error getting storage usage: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500