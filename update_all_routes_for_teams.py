#!/usr/bin/env python3
"""
Script to update all routes in the app to support team workspaces
This will:
1. Add workspace permission imports
2. Replace g.user.get('id') with get_workspace_user_id()
3. Add @require_permission decorators
"""

import os
import re
import sys

# Map of route files to their required permissions
ROUTE_PERMISSIONS = {
    'app/routes/content_wiki/content_wiki_routes.py': 'content_wiki',
    'app/routes/video_script/video_script_routes.py': 'video_script',
    'app/routes/video_title/video_title_routes.py': 'video_title',
    'app/routes/video_tags/video_tags_routes.py': 'video_tags',
    'app/routes/video_description/video_description_routes.py': 'video_description',
    'app/routes/thumbnail/thumbnail_routes.py': 'thumbnail',
    'app/routes/competitors/competitors_routes.py': 'competitors',
    'app/routes/analytics/analytics_routes.py': 'analytics',
    'app/routes/x_post_editor/x_post_editor_routes.py': 'x_post_editor',
    'app/routes/reply_guy/routes.py': 'reply_guy',
    'app/routes/clip_spaces/routes.py': 'clip_spaces',
    'app/routes/niche/routes.py': 'niche',
}

def update_file(filepath, permission_name):
    """Update a single route file for workspace support"""

    if not os.path.exists(filepath):
        print(f"  ⚠️  File not found: {filepath}")
        return False

    with open(filepath, 'r') as f:
        content = f.read()

    original_content = content

    # 1. Check if already has permissions import
    if 'from app.system.auth.permissions import' not in content:
        # Add import after auth_required import
        import_pattern = r'(from app\.system\.auth\.middleware import auth_required)'
        replacement = r'\1\nfrom app.system.auth.permissions import get_workspace_user_id, check_workspace_permission, require_permission'
        content = re.sub(import_pattern, replacement, content)

    # 2. Replace all instances of g.user.get('id') or g.user['id']
    patterns_to_replace = [
        (r"g\.user\.get\('id'\)", "get_workspace_user_id()"),
        (r'g\.user\.get\("id"\)', "get_workspace_user_id()"),
        (r"g\.user\['id'\]", "get_workspace_user_id()"),
        (r'g\.user\["id"\]', "get_workspace_user_id()"),
        (r"str\(g\.user\.get\('id'\)\)", "get_workspace_user_id()"),
        (r'str\(g\.user\["id"\]\)', "get_workspace_user_id()"),
        (r"g\.user_id", "get_workspace_user_id()"),
        (r"getattr\(g, 'user_id', None\)", "get_workspace_user_id()"),
    ]

    for pattern, replacement in patterns_to_replace:
        content = re.sub(pattern, replacement, content)

    # 3. Add @require_permission decorator after @auth_required
    # Only if not already present
    if f"@require_permission('{permission_name}')" not in content:
        # Find all @auth_required decorators followed by def
        pattern = r'(@auth_required)\n(def \w+)'
        replacement = rf'\1\n@require_permission(\'{permission_name}\')\n\2'
        content = re.sub(pattern, replacement, content)

    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  ✅ Updated: {filepath}")
        return True
    else:
        print(f"  ⏭️  No changes needed: {filepath}")
        return False

def main():
    print("\n" + "="*60)
    print("UPDATING ALL ROUTES FOR TEAM WORKSPACE SUPPORT")
    print("="*60 + "\n")

    updated_count = 0

    for filepath, permission in ROUTE_PERMISSIONS.items():
        print(f"\nProcessing {permission}...")
        if update_file(filepath, permission):
            updated_count += 1

    # Also check for simple __init__.py route files
    simple_routes = {
        'app/routes/content_wiki/__init__.py': 'content_wiki',
        'app/routes/video_script/__init__.py': 'video_script',
        'app/routes/video_title/__init__.py': 'video_title',
        'app/routes/video_tags/__init__.py': 'video_tags',
        'app/routes/video_description/__init__.py': 'video_description',
        'app/routes/thumbnail/__init__.py': 'thumbnail',
        'app/routes/competitors/__init__.py': 'competitors',
        'app/routes/analytics/__init__.py': 'analytics',
        'app/routes/x_post_editor/__init__.py': 'x_post_editor',
        'app/routes/reply_guy/__init__.py': 'reply_guy',
        'app/routes/clip_spaces/__init__.py': 'clip_spaces',
        'app/routes/niche/__init__.py': 'niche',
    }

    for filepath, permission in simple_routes.items():
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                content = f.read()
            # Only process if it has actual route definitions
            if '@bp.route' in content or '@auth_required' in content:
                print(f"\nProcessing {permission} __init__.py...")
                if update_file(filepath, permission):
                    updated_count += 1

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Files updated: {updated_count}")
    print("\n✅ All routes have been updated for team workspace support!")
    print("\nNOTE: The app needs to be restarted for these changes to take effect.")

    return 0

if __name__ == "__main__":
    sys.exit(main())