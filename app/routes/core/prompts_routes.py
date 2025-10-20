from flask import Blueprint, render_template, request, jsonify, g, redirect, url_for
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

prompts_bp = Blueprint('prompts', __name__, url_prefix='/admin/prompts')

SCRIPTS_DIR = Path(__file__).parent.parent.parent / 'scripts'

def check_admin_access():
    """Check if user has admin access"""
    if not hasattr(g, 'user') or not g.user:
        return False

    subscription_plan = g.user.get('subscription_plan', '').lower().strip()
    return subscription_plan in ['admin', 'admin plan', 'administrator']

@prompts_bp.before_request
def require_admin():
    """Require admin access for all routes in this blueprint"""
    if not check_admin_access():
        return redirect(url_for('home.dashboard'))

@prompts_bp.route('/')
def index():
    """Display all prompt folders and files"""
    try:
        prompt_folders = []

        # Scan all script folders for prompts directories
        for folder in sorted(SCRIPTS_DIR.iterdir()):
            if folder.is_dir() and not folder.name.startswith('_'):
                prompts_dir = folder / 'prompts'
                if prompts_dir.exists() and prompts_dir.is_dir():
                    txt_files = list(prompts_dir.glob('*.txt'))
                    if txt_files:
                        prompt_folders.append({
                            'name': folder.name,
                            'path': str(folder.relative_to(SCRIPTS_DIR)),
                            'file_count': len(txt_files)
                        })

        return render_template('admin/prompts_index.html', folders=prompt_folders)

    except Exception as e:
        logger.error(f"Error loading prompt folders: {e}")
        return jsonify({'error': str(e)}), 500


@prompts_bp.route('/folder/<folder_name>')
def view_folder(folder_name):
    """View prompt files in a folder or redirect if only one file"""
    try:
        folder_path = SCRIPTS_DIR / folder_name / 'prompts'

        if not folder_path.exists():
            return jsonify({'error': 'Folder not found'}), 404

        txt_files = sorted(folder_path.glob('*.txt'))

        if not txt_files:
            return jsonify({'error': 'No prompt files found in folder'}), 404

        # If only one file, redirect directly to edit page
        if len(txt_files) == 1:
            return redirect(url_for('prompts.edit_file', folder_name=folder_name, filename=txt_files[0].name))

        # Multiple files - show folder view with list
        prompt_files = []
        for txt_file in txt_files:
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check if it's a consolidated file with sections
            has_sections = '############# ' in content
            sections = []

            if has_sections:
                # Extract section names
                for line in content.split('\n'):
                    if line.startswith('############# ') and line.endswith(' #############'):
                        section_name = line.replace('############# ', '').replace(' #############', '')
                        sections.append(section_name)

            prompt_files.append({
                'filename': txt_file.name,
                'has_sections': has_sections,
                'sections': sections,
                'line_count': len(content.split('\n'))
            })

        return render_template('admin/prompts_folder.html',
                             folder_name=folder_name,
                             files=prompt_files)

    except Exception as e:
        logger.error(f"Error loading folder {folder_name}: {e}")
        return jsonify({'error': str(e)}), 500


@prompts_bp.route('/edit/<folder_name>/<filename>')
def edit_file(folder_name, filename):
    """Edit a specific prompt file"""
    try:
        file_path = SCRIPTS_DIR / folder_name / 'prompts' / filename

        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if it's a consolidated file with sections
        has_sections = '############# ' in content
        sections = []

        if has_sections:
            # Parse sections
            current_section = None
            section_content = []

            for line in content.split('\n'):
                if line.startswith('############# ') and line.endswith(' #############'):
                    # Save previous section
                    if current_section:
                        sections.append({
                            'name': current_section,
                            'content': '\n'.join(section_content).strip()
                        })

                    # Start new section
                    current_section = line.replace('############# ', '').replace(' #############', '')
                    section_content = []
                else:
                    section_content.append(line)

            # Save last section
            if current_section:
                sections.append({
                    'name': current_section,
                    'content': '\n'.join(section_content).strip()
                })

        return render_template('admin/prompts_edit.html',
                             folder_name=folder_name,
                             filename=filename,
                             content=content,
                             has_sections=has_sections,
                             sections=sections)

    except Exception as e:
        logger.error(f"Error loading file {folder_name}/{filename}: {e}")
        return jsonify({'error': str(e)}), 500


@prompts_bp.route('/save', methods=['POST'])
def save_file():
    """Save changes to a prompt file"""
    try:
        data = request.json
        folder_name = data.get('folder_name')
        filename = data.get('filename')
        content = data.get('content')

        if not all([folder_name, filename, content]):
            return jsonify({'error': 'Missing required fields'}), 400

        file_path = SCRIPTS_DIR / folder_name / 'prompts' / filename

        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404

        # Save the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"Saved prompt file: {folder_name}/{filename}")

        return jsonify({
            'success': True,
            'message': f'Successfully saved {filename}'
        })

    except Exception as e:
        logger.error(f"Error saving file: {e}")
        return jsonify({'error': str(e)}), 500
