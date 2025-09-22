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
                       script_format: str = 'full', user_id: str = None) -> Dict:
        """
        Generate video script using AI

        Args:
            concept: Video concept or topic description
            video_type: Either 'long' or 'short'
            script_format: Either 'full' or 'bullet'
            user_id: User ID for tracking

        Returns:
            Dict with success status and generated script
        """
        try:
            # Get the appropriate prompt template
            prompt_template = self.get_prompt_template(video_type, script_format)
            if not prompt_template:
                # Use fallback prompt
                prompt_template = self.get_fallback_prompt(video_type, script_format)

            # Skip prompt template - we'll use simple direct prompts
            # prompt = prompt_template.format(concept=concept)

            # Get AI provider
            ai_provider = get_ai_provider()

            if ai_provider:
                try:
                    # Very simple prompts giving AI complete freedom
                    if script_format == 'bullet':
                        simple_prompt = f"Write a bullet-point outline for a {'60-second YouTube Short' if video_type == 'short' else '10-minute YouTube video'} about: {concept}. Just write bullet points, nothing else."
                    else:
                        simple_prompt = f"Write a script for a {'60-second YouTube Short' if video_type == 'short' else '10-minute YouTube video'} about: {concept}. Just write the script text."

                    # Generate using AI provider with simple prompt
                    response = ai_provider.create_completion(
                        messages=[
                            {"role": "user", "content": simple_prompt}
                        ],
                        temperature=0.8,
                        max_tokens=2000 if video_type == 'long' else 800
                    )

                    # Get the content - handle both dict and string responses
                    if isinstance(response, dict):
                        response_content = response.get('content', '')
                    else:
                        response_content = str(response)

                    # Just format whatever AI gave us - no JSON parsing
                    if script_format == 'bullet':
                        # Split into lines
                        lines = response_content.strip().split('\n')
                        bullets = [line.strip() for line in lines if line.strip()]
                        script = {'bullets': bullets if bullets else ['Generated script content']}
                    else:
                        # Just return as one big script
                        script = {
                            'sections': [{
                                'title': 'Your Video Script',
                                'content': response_content.strip() if response_content.strip() else 'Generated script content'
                            }]
                        }

                    return {
                        'success': True,
                        'script': script,
                        'used_ai': True,
                        'token_usage': {
                            'model': 'ai_provider',
                            'input_tokens': len(simple_prompt.split()),
                            'output_tokens': len(response_content.split())
                        }
                    }

                except Exception as e:
                    logger.error(f"AI generation failed with error: {str(e)}")
                    logger.error(f"Failed response preview: {str(response_content)[:200] if 'response_content' in locals() else 'No response'}")
                    # Fall through to fallback

            # Fallback: Generate without AI
            script = self.generate_fallback_script(concept, video_type, script_format)

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

    def generate_fallback_script(self, concept: str, video_type: str, script_format: str) -> any:
        """Generate fallback script when AI is not available"""

        topic = concept[:100] if concept else "Your Topic"

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
            return {
                'sections': [
                    {
                        'title': 'INTRODUCTION',
                        'content': f"Hey everyone, welcome back to the channel! Today we're diving deep into {topic}. "
                                  f"If you've been wondering about {topic}, you're in the right place. "
                                  f"I'm going to share everything you need to know, including some tips that most people miss."
                    },
                    {
                        'title': 'HOOK & PREVIEW',
                        'content': f"By the end of this video, you'll understand exactly how {topic} works and how to apply it. "
                                  f"We'll cover three main points: First... Second... And third... "
                                  f"So make sure you watch until the end because the last tip is a game-changer."
                    },
                    {
                        'title': 'MAIN CONTENT - PART 1',
                        'content': f"Let's start with the basics of {topic}. [Explain core concept in detail]. "
                                  f"This is important because [explain why]. "
                                  f"For example, [give specific example or demonstration]."
                    },
                    {
                        'title': 'MAIN CONTENT - PART 2',
                        'content': f"Now that you understand the foundation, let's talk about [next aspect of {topic}]. "
                                  f"This is where most people get stuck. [Explain common problems]. "
                                  f"The solution is actually quite simple: [explain solution with steps]."
                    },
                    {
                        'title': 'MAIN CONTENT - PART 3',
                        'content': f"Finally, let's discuss the advanced techniques for {topic}. "
                                  f"These are the strategies that separate beginners from experts. "
                                  f"[Share advanced tips, tricks, and insights]."
                    },
                    {
                        'title': 'CONCLUSION & CTA',
                        'content': f"So that's everything you need to know about {topic}! "
                                  f"To recap: [summarize main points]. "
                                  f"If you found this helpful, please hit the like button and subscribe for more content like this. "
                                  f"Leave a comment below with your experience, and I'll see you in the next video!"
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