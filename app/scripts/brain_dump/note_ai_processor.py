"""
Brain Dump AI Processor
Handles AI operations for note modification and transcript processing
"""
import logging
from pathlib import Path
from app.system.ai_provider.ai_provider import get_ai_provider
from app.system.credits.credits_manager import CreditsManager

logger = logging.getLogger(__name__)

# Get prompts directory
PROMPTS_DIR = Path(__file__).parent / 'prompts'


def load_prompt(filename: str, section: str = None) -> str:
    """Load a prompt from text file, optionally extracting a specific section"""
    try:
        prompt_path = PROMPTS_DIR / filename
        with open(prompt_path, 'r', encoding='utf-8') as f:
            content_data = f.read()

        # If no section specified, return full content
        if not section:
            return content_data.strip()

        # Extract specific section
        section_marker = f"############# {section} #############"
        if section_marker not in content_data:
            logger.error(f"Section '{section}' not found in {filename}")
            raise ValueError(f"Section '{section}' not found")

        # Find the start of this section
        start_idx = content_data.find(section_marker)
        if start_idx == -1:
            raise ValueError(f"Section '{section}' not found")

        # Skip past the section marker and newline
        content_start = start_idx + len(section_marker)
        if content_start < len(content_data) and content_data[content_start] == '\n':
            content_start += 1

        # Find the next section marker (if any)
        next_section = content_data.find("\n#############", content_start)

        if next_section == -1:
            # This is the last section
            section_content = content_data[content_start:]
        else:
            # Extract until next section
            section_content = content_data[content_start:next_section]

        return section_content.strip()
    except Exception as e:
        logger.error(f"Error loading prompt {filename}, section {section}: {e}")
        raise


def modify_note_with_ai(content: str, prompt: str, user_id: str, model: str = None) -> dict:
    """
    Modify note content using AI with proper credit management

    Args:
        content: Original note content
        prompt: User's modification request
        user_id: User ID for credit management
        model: AI model name (optional, uses current provider default)

    Returns:
        dict with status, modified_content, and credits_used
    """
    try:
        if not content:
            return {'status': 'error', 'error': 'No content provided'}

        if not prompt:
            return {'status': 'error', 'error': 'No modification prompt provided'}

        # Initialize credits manager and AI provider
        credits_manager = CreditsManager()
        ai_provider = get_ai_provider()
        model_name = model or ai_provider.default_model

        # Step 1: Check credits before generation
        combined_text = f"{prompt}\n{content}"
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=combined_text,
            model_name=model_name
        )

        required_credits = cost_estimate['final_cost'] * 2  # Multiply by 2 for output
        current_credits = credits_manager.get_user_credits(user_id)
        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )

        if not credit_check.get('sufficient', False):
            return {
                "status": "error",
                "error": "Insufficient credits",
                "error_type": "insufficient_credits"
            }

        # Load prompts from files
        system_prompt = load_prompt('prompts.txt', 'MODIFY_NOTE_SYSTEM')
        user_prompt_template = load_prompt('prompts.txt', 'MODIFY_NOTE_USER')
        user_prompt = user_prompt_template.format(prompt=prompt, content=content)

        # Generate the modified content
        response = ai_provider.create_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        # Get the content
        if isinstance(response, dict):
            modified_content = response.get('content', '')
            token_usage = response.get('usage', {})
        else:
            modified_content = str(response)
            token_usage = {}

        if not modified_content:
            return {'status': 'error', 'error': 'Failed to generate modified content'}

        # Step 2: Deduct credits after successful generation
        try:
            input_tokens = token_usage.get('prompt_tokens', len(combined_text.split()) * 1.3)
            output_tokens = token_usage.get('completion_tokens', len(modified_content.split()) * 1.3)

            deduction_result = credits_manager.deduct_llm_credits(
                user_id=user_id,
                model_name=model_name,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                description=f"Brain Dump AI Modification: {prompt[:50]}{'...' if len(prompt) > 50 else ''}",
                feature_id="brain_dump_ai_modify"
            )

            if not deduction_result['success']:
                logger.error(f"Failed to deduct credits for user {user_id}: {deduction_result.get('message')}")
            else:
                logger.info(f"Credits deducted for Brain Dump AI modification: {deduction_result.get('credits_deducted', 0)} credits")

            credits_deducted = deduction_result.get('credits_deducted', 0)
        except Exception as credit_error:
            logger.error(f"Error deducting credits: {credit_error}")
            credits_deducted = 0

        return {
            'status': 'success',
            'modified_content': modified_content.strip(),
            'original_prompt': prompt,
            'credits_used': credits_deducted
        }

    except Exception as e:
        logger.error(f"Error modifying note with AI: {e}")
        return {'status': 'error', 'error': str(e)}


def process_transcript_with_ai(transcript: str, prompt: str, user_id: str, model: str = None) -> dict:
    """
    Process video transcript with AI based on user prompt

    Args:
        transcript: Video transcript text
        prompt: User's processing request
        user_id: User ID for credit management
        model: AI model name (optional, uses current provider default)

    Returns:
        dict with status, result, and credits_used
    """
    try:
        if not transcript:
            return {'status': 'error', 'error': 'No transcript provided'}

        if not prompt:
            return {'status': 'error', 'error': 'No prompt provided'}

        # Initialize credits manager and AI provider
        credits_manager = CreditsManager()
        ai_provider = get_ai_provider()
        model_name = model or ai_provider.default_model

        # Step 1: Check credits before generation
        combined_text = f"{prompt}\n{transcript}"
        cost_estimate = credits_manager.estimate_llm_cost_from_text(
            text_content=combined_text,
            model_name=model_name
        )

        required_credits = cost_estimate['final_cost'] * 2
        current_credits = credits_manager.get_user_credits(user_id)
        credit_check = credits_manager.check_sufficient_credits(
            user_id=user_id,
            required_credits=required_credits
        )

        if not credit_check.get('sufficient', False):
            return {
                "status": "error",
                "error": "Insufficient credits",
                "error_type": "insufficient_credits"
            }

        # Load prompts from files
        system_prompt = load_prompt('prompts.txt', 'PROCESS_TRANSCRIPT_SYSTEM')
        user_prompt_template = load_prompt('prompts.txt', 'PROCESS_TRANSCRIPT_USER')
        user_prompt = user_prompt_template.format(prompt=prompt, transcript=transcript)

        # Generate the response
        response = ai_provider.create_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        # Get the content
        if isinstance(response, dict):
            result_content = response.get('content', '')
            token_usage = response.get('usage', {})
        else:
            result_content = str(response)
            token_usage = {}

        if not result_content:
            return {'status': 'error', 'error': 'Failed to process transcript'}

        # Step 2: Deduct credits after successful generation
        try:
            input_tokens = token_usage.get('prompt_tokens', len(combined_text.split()) * 1.3)
            output_tokens = token_usage.get('completion_tokens', len(result_content.split()) * 1.3)

            deduction_result = credits_manager.deduct_llm_credits(
                user_id=user_id,
                model_name=model_name,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                description=f"Video Transcript AI Processing: {prompt[:50]}{'...' if len(prompt) > 50 else ''}",
                feature_id="video_transcript_ai_process"
            )

            if not deduction_result['success']:
                logger.error(f"Failed to deduct credits for user {user_id}: {deduction_result.get('message')}")
            else:
                logger.info(f"Credits deducted for transcript processing: {deduction_result.get('credits_deducted', 0)} credits")

            credits_deducted = deduction_result.get('credits_deducted', 0)
        except Exception as credit_error:
            logger.error(f"Error deducting credits: {credit_error}")
            credits_deducted = 0

        return {
            'status': 'success',
            'result': result_content.strip(),
            'prompt': prompt,
            'credits_used': credits_deducted
        }

    except Exception as e:
        logger.error(f"Error processing transcript with AI: {e}")
        return {'status': 'error', 'error': str(e)}
