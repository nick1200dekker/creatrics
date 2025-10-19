"""
Video Script Generator Module
Handles video script generation for both long-form and shorts content
Supports full script and bullet points format
"""
import os
import logging
import json
from typing import Dict, List, Optional
from pathlib import Path
from app.system.ai_provider.ai_provider import get_ai_provider

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VideoScriptGenerator:
    """Video Script Generator with AI support"""

    def __init__(self):
        self.script_types = ['long_form_full', 'long_form_bullet', 'short_full', 'short_bullet']

    def get_prompt_template(self, video_type: str, script_format: str) -> str:
        """Get the prompt template for script generation"""
        try:
            current_dir = Path(__file__).parent
            prompt_file = current_dir / f'{video_type}_{script_format}_prompt.txt'

            if not prompt_file.exists():
                logger.error(f"Prompt file not found: {prompt_file}")
                return None

            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading prompt template: {e}")
            return None

    def generate_script(self, concept: str, video_type: str = 'long',
                       script_format: str = 'full', duration: int = None, user_id: str = None) -> Dict:
        """
        Generate video script using AI

        Args:
            concept: Video concept or topic description
            video_type: Either 'long' or 'short'
            script_format: Either 'full' or 'bullet'
            duration: Target duration (minutes for long, seconds for short)
            user_id: User ID for tracking

        Returns:
            Dict with success status and generated script
        """
        try:
            # Get the appropriate prompt template
            prompt_template = self.get_prompt_template(video_type, script_format)
            if not prompt_template:
                logger.error(f"Failed to load prompt template for {video_type}_{script_format}")
                # Fall back to inline prompt generation
                prompt_template = None

            # Get AI provider
            ai_provider = get_ai_provider()

            if ai_provider:
                try:
                    # Handle best effort mode (duration is None) or specific duration
                    best_effort = duration is None
                    if best_effort:
                        # Best effort mode - let AI decide based on content
                        if video_type == 'short':
                            # Set a reasonable default for token calculation
                            duration = 30
                        else:
                            # Set a reasonable default for token calculation
                            duration = 10

                    # Use prompt template if available, otherwise use inline prompt
                    if prompt_template:
                        # Calculate word count for shorts
                        duration_words = duration * 2 if video_type == 'short' else duration * 150

                        # Format the prompt template with variables
                        simple_prompt = prompt_template.format(
                            concept=concept,
                            duration=duration,
                            duration_words=duration_words
                        )
                    else:
                        # Fallback to inline prompts (keeping existing logic)
                        if video_type == 'short':
                            duration_str = f"{duration}-second YouTube Short" if not best_effort else "YouTube Short (15-60 seconds, you decide based on content)"
                        else:
                            duration_str = f"{duration}-minute YouTube video" if not best_effort else "YouTube video (you decide the appropriate length based on content depth)"

                        # Create inline prompts as before
                        if script_format == 'bullet':
                            if video_type == 'short':
                                duration_instruction = f"- This is a VERY SHORT video ({duration} seconds only). Write 5-8 key points." if not best_effort else "- Determine the appropriate length (15-60 seconds)."

                                simple_prompt = f"""Write simple talking points for a {duration_str} based on this content:

{concept}

CRITICAL REQUIREMENTS:
{duration_instruction}
- Write ONLY the key points to cover, one per line.
- NO bullet symbols or formatting.
- Instead of full sentences, provide short, high-level TOPICS or SUBJECTS to talk about. These should be concise cues for a YouTuber to expand on while recording.

Write ONLY the talking points now:"""
                            else:
                                duration_instruction = f"- The video should be approximately {duration} minutes long." if not best_effort else "- Determine the appropriate video length based on content."

                                simple_prompt = f"""Write talking points for a {duration_str} based on this content:

{concept}

CRITICAL REQUIREMENTS:
{duration_instruction}
- Write key points to cover, one per line.
- NO bullet symbols or formatting.
- Instead of full sentences, provide short, high-level TOPICS or SUBJECTS to talk about. These should be concise cues for a YouTuber to expand on while recording.

Write ONLY the talking points now:"""
                        else:
                            if video_type == 'short':
                                duration_instruction = f"- This script must be EXACTLY {duration} seconds when read aloud (about {duration * 2} words)." if not best_effort else "- Determine the appropriate length based on the content (15-60 seconds)."

                                simple_prompt = f"""Write a complete script for a {duration_str} based on this content:

{concept}

CRITICAL REQUIREMENTS:
{duration_instruction}
- Each sentence MUST be on a new line.
- Write ONLY the words to be spoken - no formatting, no headers, no timestamps.
- Just pure flowing text for the video.

Write ONLY the spoken script text now:"""
                            else:
                                duration_instruction = f"- The script should be approximately {duration} minutes when read aloud (about {duration * 150} words)." if not best_effort else "- Determine the appropriate video length based on content (3-20 minutes)."

                                simple_prompt = f"""Write a complete script for a {duration_str} based on this information:

{concept}

CRITICAL REQUIREMENTS:
{duration_instruction}
- Each sentence MUST be on a new line.
- Write ONLY the words to be spoken - no headers, no timestamps, no formatting.
- NO section titles like "INTRO" or "CONCLUSION".
- NO markdown formatting (no ##, **, __, etc.).
- NO brackets, parentheses with notes, or stage directions.
- Just write flowing, conversational text as if reading from a teleprompter.
- Use ALL the specific details provided above.
- Start directly with the opening words and flow naturally throughout.

Write ONLY the spoken script text now:"""

                    # Calculate appropriate max tokens based on duration
                    if video_type == 'short':
                        # For shorts: ~3 tokens per word, ~2 words per second
                        max_tokens = min(1000, duration * 8)
                    else:
                        # For long form: ~3 tokens per word, ~150 words per minute
                        # Increased multiplier for more complete scripts
                        max_tokens = min(8000, duration * 500)

                    # Generate using AI provider with simple prompt
                    response = ai_provider.create_completion(
                        messages=[
                            {"role": "user", "content": simple_prompt}
                        ],
                        temperature=0.8,
                        max_tokens=max_tokens
                    )

                    # Get the content - handle both dict and string responses
                    if isinstance(response, dict):
                        response_content = response.get('content', '')
                    else:
                        response_content = str(response)

                    # Clean up any formatting that might have slipped through
                    import re
                    clean_content = response_content
                    
                    # Only do minimal cleaning to preserve content
                    # Remove markdown bold/italic (but be more careful)
                    clean_content = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean_content)  # **text** -> text
                    clean_content = re.sub(r'\*([^*]+)\*', r'\1', clean_content)      # *text* -> text
                    clean_content = re.sub(r'__([^_]+)__', r'\1', clean_content)      # __text__ -> text
                    clean_content = re.sub(r'_([^_]+)_', r'\1', clean_content)        # _text_ -> text
                    
                    # Remove timestamps only if they're clearly timestamps
                    clean_content = re.sub(r'\[\d{1,2}:\d{2}(?:-\d{1,2}:\d{2})?\]', '', clean_content)
                    
                    # Remove obvious section headers (very conservative)
                    clean_content = re.sub(r'^(INTRODUCTION|CONCLUSION|OUTRO|INTRO):?\s*$', '', clean_content, flags=re.MULTILINE)
                    
                    # Remove bullet symbols only at start of lines
                    clean_content = re.sub(r'^[•\-\*]\s+', '', clean_content, flags=re.MULTILINE)
                    
                    # Clean up excessive line breaks
                    clean_content = re.sub(r'\n{3,}', '\n\n', clean_content)
                    clean_content = clean_content.strip()

                    # Format based on script type
                    if script_format == 'bullet':
                        # Split into lines for bullet points
                        lines = clean_content.split('\n')
                        bullets = [line.strip() for line in lines if line.strip() and len(line.strip()) > 5]
                        script = {'bullets': bullets if bullets else ['Generated script content']}
                    else:
                        # Return as clean script text
                        script = clean_content if clean_content else 'Generated script content'

                    # Get actual token usage from AI provider response
                    token_usage = response.get('usage', {}) if isinstance(response, dict) else {}

                    return {
                        'success': True,
                        'script': script,
                        'used_ai': True,
                        'token_usage': {
                            'model': response.get('model', 'ai_provider') if isinstance(response, dict) else 'ai_provider',
                            'input_tokens': token_usage.get('input_tokens', 0),
                            'output_tokens': token_usage.get('output_tokens', 0)
                        }
                    }

                except Exception as e:
                    logger.error(f"AI generation failed with error: {str(e)}")
                    logger.error(f"Failed response preview: {str(response_content)[:200] if 'response_content' in locals() else 'No response'}")
                    # Fall through to fallback

            # Fallback: Generate without AI
            if duration is None:
                duration = 30 if video_type == 'short' else 10
            script = self.generate_fallback_script(concept, video_type, script_format, duration)

            return {
                'success': True,
                'script': script,
                'used_ai': False,
                'token_usage': {
                    'model': 'fallback',
                    'input_tokens': 0,
                    'output_tokens': 0
                }
            }

        except Exception as e:
            logger.error(f"Error generating script: {e}")
            return {
                'success': False,
                'error': str(e),
                'script': None
            }

    def parse_ai_response_old_not_used(self, response: str, script_format: str) -> any:
        """Parse AI response to extract script"""
        try:
            # Clean the response first
            response = response.strip()

            # Check if response is too short to be valid JSON
            if len(response) < 20:
                logger.warning(f"Response too short to be valid JSON: {response}")
                return None

            # Remove any markdown code blocks
            if response.startswith('```'):
                response = re.sub(r'^```(?:json)?\n?', '', response)
                response = re.sub(r'\n?```$', '', response)

            # First try direct JSON parse
            try:
                data = json.loads(response)
                if script_format == 'bullet' and 'bullets' in data:
                    return data
                elif script_format == 'full' and 'sections' in data:
                    return data
            except json.JSONDecodeError as e:
                logger.debug(f"Direct JSON parse failed: {e}")

            # Try to find JSON in the response
            import re

            # Look for JSON object with sections or bullets
            if script_format == 'bullet':
                # Try to find bullets array
                bullets_match = re.search(r'"bullets"\s*:\s*\[(.*?)\]', response, re.DOTALL)
                if bullets_match:
                    try:
                        bullets_str = '[' + bullets_match.group(1) + ']'
                        bullets = json.loads(bullets_str)
                        return {'bullets': bullets}
                    except:
                        pass
            else:
                # Try to find sections array
                sections_match = re.search(r'"sections"\s*:\s*\[(.*?)\](?:\s*\}|$)', response, re.DOTALL)
                if sections_match:
                    try:
                        sections_str = '[' + sections_match.group(1) + ']'
                        sections = json.loads(sections_str)
                        return {'sections': sections}
                    except:
                        pass

            # More aggressive JSON extraction
            json_patterns = [
                r'\{[^{}]*"(?:sections|bullets)"[^{}]*\[.*?\][^{}]*\}',  # Object with array
                r'\{.*?"(?:sections|bullets)".*?\}',  # Any object with sections/bullets
            ]

            for pattern in json_patterns:
                json_match = re.search(pattern, response, re.DOTALL)
                if json_match:
                    try:
                        # Clean up common JSON issues
                        json_str = json_match.group()
                        # Remove trailing commas
                        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                        # Fix missing quotes
                        json_str = re.sub(r'(\w+):', r'"\1":', json_str)

                        data = json.loads(json_str)
                        if script_format == 'bullet' and 'bullets' in data:
                            return data
                        elif script_format == 'full' and 'sections' in data:
                            return data
                    except:
                        continue

            # Fallback parsing for non-JSON response
            if script_format == 'bullet':
                lines = response.split('\n')
                bullets = []
                for line in lines:
                    cleaned = line.strip()
                    if cleaned and not cleaned.startswith('#'):
                        # Remove bullet point markers
                        cleaned = re.sub(r'^[\-\*\•\d\.]+\s*', '', cleaned)
                        if cleaned:
                            bullets.append(cleaned)
                return {'bullets': bullets[:15]}  # Limit to 15 points

            else:  # full script
                # Parse as sections
                sections = []
                current_section = None
                current_content = []

                lines = response.split('\n')
                for line in lines:
                    if line.strip().startswith('#') or line.strip().isupper():
                        # New section
                        if current_section:
                            sections.append({
                                'title': current_section,
                                'content': '\n'.join(current_content).strip()
                            })
                        current_section = line.strip('#').strip()
                        current_content = []
                    else:
                        current_content.append(line)

                # Add last section
                if current_section:
                    sections.append({
                        'title': current_section,
                        'content': '\n'.join(current_content).strip()
                    })

                if not sections:
                    # Treat entire response as one section
                    sections = [{'title': 'Script', 'content': response}]

                return {'sections': sections}

        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            logger.error(f"Response that failed: {response[:200] if response else 'No response'}")
            # Return None to indicate parsing failed
            return None

    def generate_fallback_script(self, concept: str, video_type: str, script_format: str, duration: int = None) -> any:
        """Generate fallback script when AI is not available"""

        topic = concept[:100] if concept else "Your Topic"
        if duration is None:
            duration = 30 if video_type == 'short' else 10

        # Create duration-aware text
        if video_type == 'short':
            duration_text = f"{duration} seconds"
        else:
            duration_text = f"{duration} minutes"

        if video_type == 'short' and script_format == 'bullet':
            return {
                'bullets': [
                    f"Hook: Start with a question or bold statement about {topic}",
                    "Show the problem or pain point immediately (0-3 seconds)",
                    "Tease the solution - what you're about to reveal",
                    f"Main point 1: Key insight about {topic}",
                    "Quick demonstration or example (visual)",
                    "Main point 2: Additional value or tip",
                    "Show results or transformation",
                    "Call to action: Follow for more / Save this / Share",
                    "End with a cliffhanger or promise for next video"
                ]
            }
        elif video_type == 'short' and script_format == 'full':
            return {
                'sections': [
                    {
                        'title': 'HOOK (0-3 seconds)',
                        'content': f"Stop scrolling! Did you know that {topic} can completely change how you [outcome]? Watch this..."
                    },
                    {
                        'title': 'PROBLEM (3-10 seconds)',
                        'content': f"Most people struggle with {topic} because they don't know this one simple trick. They waste hours trying to figure it out on their own."
                    },
                    {
                        'title': 'SOLUTION (10-40 seconds)',
                        'content': f"Here's exactly how to master {topic}: Step 1... Step 2... Step 3... See how easy that was?"
                    },
                    {
                        'title': 'RESULT (40-55 seconds)',
                        'content': "Look at these amazing results! This is what's possible when you apply what I just showed you."
                    },
                    {
                        'title': 'CTA (55-60 seconds)',
                        'content': "Follow for more tips like this! Save this video so you don't forget, and comment below if you tried it!"
                    }
                ]
            }
        elif video_type == 'long' and script_format == 'bullet':
            return {
                'bullets': [
                    f"Introduction: Welcome viewers and introduce {topic}",
                    "Hook: Why this topic matters to the viewer",
                    "Preview what you'll cover in this video",
                    f"Background: Context and importance of {topic}",
                    "Main Point 1: Core concept with detailed explanation",
                    "Example or case study for Point 1",
                    "Main Point 2: Additional insight or technique",
                    "Demonstration or tutorial segment",
                    "Main Point 3: Advanced tips or common mistakes",
                    "Real-world application examples",
                    "Address common questions or objections",
                    "Summarize key takeaways",
                    "Call to action: Like, subscribe, comment",
                    "Tease next video or related content",
                    "End screen: Thanks for watching + links"
                ]
            }
        else:  # long form full script
            # Parse the concept to extract key information
            concept_lines = concept.split('\n')
            main_topic = concept_lines[0] if concept_lines else topic
            details = '\n'.join(concept_lines[1:]) if len(concept_lines) > 1 else ''

            # Calculate content for target duration
            words_needed = duration * 150
            intro_words = int(words_needed * 0.1)  # 10% for intro
            main_words = int(words_needed * 0.7)    # 70% for main content
            conclusion_words = int(words_needed * 0.1)  # 10% for conclusion

            return {
                'sections': [
                    {
                        'title': 'INTRODUCTION',
                        'content': f"Hey everyone, welcome back to the channel! Today we're diving deep into {main_topic}. "
                                  f"This is a topic that's been generating a lot of buzz lately, and I've got all the details you need to know. "
                                  f"We're going to break down everything that's been revealed, what it means for you, and why this matters. "
                                  f"So grab a drink, get comfortable, and let's jump right into it!"
                    },
                    {
                        'title': 'HOOK & PREVIEW',
                        'content': f"So here's what happened: {main_topic}. This is huge news that affects everyone in the community. "
                                  f"In this video, we'll cover all the leaked information, analyze what it means, and discuss the impact. "
                                  f"I'll share my thoughts on why this is significant and what you should be looking out for. "
                                  f"Trust me, you don't want to miss any of this - there are some really exciting developments here!"
                    },
                    {
                        'title': 'MAIN CONTENT - PART 1',
                        'content': f"Let's start with what we know for certain about {main_topic}. {details[:500] if details else 'The details are fascinating.'} "
                                  f"This information comes from reliable sources and has been confirmed by multiple people in the community. "
                                  f"What makes this particularly interesting is the timing and the way it was revealed. "
                                  f"Let me break down each component so you understand the full picture."
                    },
                    {
                        'title': 'MAIN CONTENT - PART 2',
                        'content': f"Now, let's dig deeper into the implications of this news. {details[500:1000] if len(details) > 500 else 'There are several key points to consider.'} "
                                  f"This changes things in several important ways that you need to be aware of. "
                                  f"First, it affects how we approach the game going forward. Second, it opens up new opportunities. "
                                  f"And third, it addresses concerns that many players have had for months."
                    },
                    {
                        'title': 'MAIN CONTENT - PART 3',
                        'content': f"Let's talk strategy and what this means for you specifically. {details[1000:] if len(details) > 1000 else 'Here are the key takeaways.'} "
                                  f"Whether you're a new player, a returning player, or a veteran, this impacts you differently. "
                                  f"For new players, this is an excellent opportunity to catch up. For veterans, it's a chance to complete collections. "
                                  f"And for everyone, it's a limited-time event that won't come around again soon."
                    },
                    {
                        'title': 'CONCLUSION & CTA',
                        'content': f"So that covers everything about {main_topic}! This is definitely one of the most exciting developments we've seen recently. "
                                  f"Remember, this is time-sensitive information, so make sure you're prepared when it launches. "
                                  f"If you found this breakdown helpful, please hit that like button - it really helps the channel grow. "
                                  f"Subscribe and ring the bell so you don't miss any updates, and drop a comment with your thoughts! "
                                  f"What are you most excited about? Let me know below. Thanks for watching, and I'll see you in the next one!"
                    }
                ]
            }

    def get_fallback_prompt(self, video_type: str, script_format: str) -> str:
        """Get fallback prompt if file is not found"""
        if video_type == 'short' and script_format == 'bullet':
            return """Generate a 60-second video script in bullet points for:
            {concept}

            Include:
            - Strong hook (0-3 seconds)
            - Problem/pain point
            - Solution steps
            - Results/transformation
            - Call to action

            Format as JSON with 'bullets' array."""

        elif video_type == 'short' and script_format == 'full':
            return """Generate a 60-second video script for:
            {concept}

            Include sections:
            - HOOK (0-3 seconds)
            - PROBLEM (3-10 seconds)
            - SOLUTION (10-40 seconds)
            - RESULT (40-55 seconds)
            - CTA (55-60 seconds)

            Format as JSON with 'sections' array, each with 'title' and 'content'."""

        elif video_type == 'long' and script_format == 'bullet':
            return """Generate a long-form video script outline in bullet points for:
            {concept}

            Include:
            - Introduction and hook
            - Main points (at least 3)
            - Examples and demonstrations
            - Common mistakes
            - Conclusion and CTA

            Format as JSON with 'bullets' array."""

        else:  # long form full
            return """Generate a complete long-form video script for:
            {concept}

            Include sections:
            - INTRODUCTION
            - HOOK & PREVIEW
            - MAIN CONTENT (multiple parts)
            - CONCLUSION & CTA

            Format as JSON with 'sections' array, each with 'title' and 'content'."""