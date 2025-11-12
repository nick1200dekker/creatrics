"""
Reply Generator - Enhanced version with GIF suggestions
Generates AI-powered replies using user's brand voice from x_replies data
"""
import os
import logging
from typing import Optional, Dict, List
from pathlib import Path

from firebase_admin import firestore
from app.system.ai_provider.ai_provider import get_ai_provider


# Get prompts directory
PROMPTS_DIR = Path(__file__).parent / 'prompts'

def load_prompt(filename: str, section: str = None) -> str:
    """Load a prompt from text file, optionally extracting a specific section"""
    try:
        prompt_path = PROMPTS_DIR / filename
        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # If no section specified, return full content
        if not section:
            return content.strip()

        # Extract specific section
        section_marker = f"############# {section} #############"
        if section_marker not in content:
            logger.error(f"Section '{section}' not found in {filename}")
            raise ValueError(f"Section '{section}' not found")

        # Find the start of this section
        start_idx = content.find(section_marker)
        if start_idx == -1:
            raise ValueError(f"Section '{section}' not found")

        # Skip past the section marker and newline
        content_start = start_idx + len(section_marker)
        if content_start < len(content) and content[content_start] == '\n':
            content_start += 1

        # Find the next section marker (if any)
        next_section = content.find("\n#############", content_start)

        if next_section == -1:
            # This is the last section
            section_content = content[content_start:]
        else:
            # Extract until next section
            section_content = content[content_start:next_section]

        return section_content.strip()
    except Exception as e:
        logger.error(f"Error loading prompt {filename}, section {section}: {e}")
        raise
logger = logging.getLogger(__name__)

class ReplyGenerator:
    """Generates AI-powered tweet replies with GIF suggestions"""

    def __init__(self):
        self.db = firestore.client()

    def _get_ai_provider(self, user_subscription: str = None):
        """Get AI provider with user subscription context"""
        return get_ai_provider(
            script_name='reply_guy/reply_generator',
            user_subscription=user_subscription
        )

    def generate_reply(self, user_id: str, tweet_text: str, author: str, style: str = 'supportive',
                      use_brand_voice: bool = False, image_urls: list = None, user_subscription: str = None) -> Optional[Dict]:
        """Generate AI reply to a tweet with GIF suggestion

        Args:
            user_id: User ID
            tweet_text: The tweet text to reply to
            author: Tweet author username
            style: Reply style (creatrics, supportive, etc.)
            use_brand_voice: Whether to use user's brand voice
            image_urls: List of image URLs from the tweet (for vision analysis)
            user_subscription: User's subscription plan (for AI provider selection)

        Returns:
            Dict with 'reply' text and 'gif_query' for suggested GIF, or None on error
        """
        try:
            # Log image URLs received
            if image_urls and len(image_urls) > 0:
                logger.info(f"📷 Received {len(image_urls)} image(s) for tweet by @{author}: {image_urls}")
            else:
                logger.info(f"📷 No images received for tweet by @{author}")

            # Get AI provider with user subscription context
            ai_provider = self._get_ai_provider(user_subscription)

            # Get the prompt template
            prompt_template = self.get_prompt_template(use_brand_voice)

            # Check if current AI provider supports vision (do this early)
            provider_config = ai_provider.config
            supports_vision = provider_config.get('supports_vision', False)
            should_use_images = image_urls and len(image_urls) > 0 and supports_vision

            # Log if images are being skipped due to non-vision model
            if image_urls and len(image_urls) > 0 and not supports_vision:
                model_name = provider_config.get('display_name', 'current model')
                logger.info(f"Tweet has {len(image_urls)} image(s) but {model_name} doesn't support vision - using text-only reply generation")

            # Add brand voice context if requested
            brand_voice_context = ""
            if use_brand_voice:
                brand_voice_context = self.get_brand_voice_context(user_id)
                if brand_voice_context:
                    logger.info(f"Adding Brand Voice context for user {user_id}")
                else:
                    logger.info(f"Brand Voice requested but no context found for user {user_id}")

            # Convert _new_line_ back to actual newlines for the AI prompt
            clean_tweet_text = tweet_text.replace('_new_line_', '\n')

            # Add image context only if provider supports vision and images are present
            if should_use_images:
                image_context = f"\n\nIMAGES: This tweet contains {len(image_urls)} image(s). The images are shown above. Reference what you see in the images when crafting your reply to make it more relevant and engaging."
                clean_tweet_text += image_context
            elif image_urls and len(image_urls) > 0 and not supports_vision:
                # Provider doesn't support vision, but tweet has images - mention this
                image_context = f"\n\nNOTE: This tweet contains {len(image_urls)} image(s), but you cannot see them. Focus on the text content only."
                clean_tweet_text += image_context

            # Load and prepare style guide
            style_guide_template = load_prompt('prompts.txt', 'STYLE_GUIDE')
            style_guide = style_guide_template.replace("{style}", style)

            # Replace placeholders in prompt
            # Determine match instruction based on brand voice
            if use_brand_voice and brand_voice_context:
                match_instruction = " matching the exact style shown in the examples above"
                # Add spacing after brand voice context
                brand_voice_context = brand_voice_context + "\n\n"
                # When brand voice is enabled, style guide comes after (less emphasis)
                style_guide = "\n" + style_guide + "\n\n"
            else:
                match_instruction = " following the style guide below"
                # No brand voice, so style guide is primary
                style_guide = style_guide + "\n\n"

            prompt = prompt_template.replace("{tweet_text}", clean_tweet_text)
            prompt = prompt.replace("{author}", author)
            prompt = prompt.replace("{style}", style)
            prompt = prompt.replace("{brand_voice_context}", brand_voice_context)
            prompt = prompt.replace("{style_guide}", style_guide)
            prompt = prompt.replace("{match_instruction}", match_instruction)

            # Strip leading/trailing whitespace to avoid empty content blocks
            prompt = prompt.strip()

            logger.debug(f"Generated prompt for reply to @{author}")

            # Use different system message based on brand voice
            if use_brand_voice and brand_voice_context:
                system_message = "You write Twitter replies. Output ONLY the reply text, nothing else. Never say things like 'I can't write in that style' or 'Here's a similar vibe'. Just write the actual reply based on the examples given."
            else:
                system_message = "You write Twitter replies. Output ONLY the reply text, nothing else. Never add commentary or explanations."

            # Call AI provider - higher temperature for more natural responses when mimicking
            temperature = 0.85 if (use_brand_voice and brand_voice_context) else 0.7

            # Build user message - include images if available AND provider supports vision
            user_message_content = []

            # Add images first if they exist and provider supports vision
            if should_use_images:
                import requests
                import base64

                for img_url in image_urls[:4]:  # Limit to 4 images max
                    try:
                        # Download and encode image
                        response = requests.get(img_url, timeout=10)
                        response.raise_for_status()

                        # Detect media type from content-type or URL
                        content_type = response.headers.get('content-type', 'image/jpeg')
                        if 'image/' not in content_type:
                            content_type = 'image/jpeg'  # Default fallback

                        # Encode to base64
                        image_data = base64.standard_b64encode(response.content).decode('utf-8')

                        # Claude API format for images
                        user_message_content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": content_type,
                                "data": image_data
                            }
                        })
                        logger.info(f"Successfully loaded image from {img_url[:50]}...")
                    except Exception as e:
                        logger.error(f"Failed to load image {img_url}: {str(e)}")
                        # Continue with other images

            # Add text prompt
            user_message_content.append({
                "type": "text",
                "text": prompt
            })

            # Print what will be sent to AI (excluding base64 image data)
            print("=" * 80)
            print("SENDING TO AI PROVIDER:")
            print("=" * 80)
            print(f"SYSTEM MESSAGE: {system_message}")
            print("USER MESSAGE:")
            for item in user_message_content:
                if item.get('type') == 'image':
                    print("  [IMAGE - base64 data omitted]")
                elif item.get('type') == 'text':
                    print(f"  TEXT: {item.get('text')}")
            print("=" * 80)

            # Use vision completion only if images are present AND provider supports vision
            if should_use_images:
                # Format for vision API - OpenAI style
                vision_content = []

                # Add text first
                vision_content.append({
                    "type": "text",
                    "text": prompt
                })

                # Add images in OpenAI format for compatibility
                for item in user_message_content:
                    if item.get("type") == "image" and "source" in item:
                        # Convert Claude format to OpenAI format
                        source = item["source"]
                        vision_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{source['media_type']};base64,{source['data']}"
                            }
                        })

                # Use vision-capable completion for images
                response = ai_provider.create_vision_completion(
                    messages_with_images=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": vision_content}
                    ],
                    temperature=temperature,
                    max_tokens=7000
                )
            else:
                # Use regular completion for text-only
                # ASYNC AI call - thread is freed during AI generation!
                import asyncio

                async def _call_ai_async():
                    """Wrapper to call async AI in thread pool - frees main thread!"""
                    return await ai_provider.create_completion_async(
                        messages=[
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=temperature,
                        max_tokens=7000
                    )

                # Run async call - thread is freed via run_in_executor internally
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    response = loop.run_until_complete(_call_ai_async())
                finally:
                    loop.close()

            reply_text = response['content'].strip()

            # Clean up any AI prefixes/artifacts
            prefixes_to_remove = [
                '<@reply>',
                '@reply>',
                'Reply:',
                'Response:',
                'Answer:',
                'Here\'s a reply:',
                'Here is a reply:',
            ]

            for prefix in prefixes_to_remove:
                if reply_text.lower().startswith(prefix.lower()):
                    reply_text = reply_text[len(prefix):].strip()

            # Remove surrounding quotes if present
            if (reply_text.startswith('"') and reply_text.endswith('"')) or \
               (reply_text.startswith("'") and reply_text.endswith("'")):
                reply_text = reply_text[1:-1].strip()

            # Check for error-like messages and regenerate with a fallback if needed
            error_phrases = [
                "not enough content",
                "i cannot",
                "i can't",
                "unable to generate",
                "insufficient information",
                "need more context",
                "sorry",
                "apologize",
                "as an ai",
                "as a language model"
            ]

            reply_lower = reply_text.lower()
            contains_error = any(phrase in reply_lower for phrase in error_phrases)

            # If we detect an error-like response, generate a more generic but engaging reply
            if contains_error or len(reply_text) < 10:
                logger.warning(f"Detected problematic reply: {reply_text[:100]}. Using fallback approach.")

                # Fallback replies based on style that are always safe
                fallback_replies = {
                    "creatrics": [
                        "wait this is actually kinda wild",
                        "oh damn didnt think about it like that",
                        "the fact that this exists is insane",
                        "nah this is crazy fr"
                    ],
                    "supportive": [
                        "literally same",
                        "felt this in my soul",
                        "you get it"
                    ],
                    "questioning": [
                        "wait how does this even work",
                        "but what about the other thing?",
                        "is this real??"
                    ],
                    "valueadd": [
                        "reminds me of that thing from last year",
                        "saw something similar but different",
                        "pretty sure this started way earlier"
                    ],
                    "humorous": [
                        "lmaooo what",
                        "bro really said that",
                        "we live in a simulation"
                    ],
                    "contrarian": [
                        "idk about this one",
                        "ehh not really tho",
                        "nah this aint it"
                    ]
                }

                import random
                style_key = style.lower()
                if style_key not in fallback_replies:
                    style_key = "creatrics"

                reply_text = random.choice(fallback_replies[style_key])
                logger.info(f"Used fallback reply for style {style}")

            # Ensure reply doesn't exceed X's character limit
            if len(reply_text) > 280:
                # Try to cut at a natural break point
                cutoff_text = reply_text[:277]

                # Find last complete sentence or thought
                for delimiter in ['. ', '! ', '? ', '\n', ' - ', '... ']:
                    last_delimiter = cutoff_text.rfind(delimiter)
                    if last_delimiter > 200:  # Make sure we keep reasonable length
                        reply_text = cutoff_text[:last_delimiter + len(delimiter)].rstrip()
                        break
                else:
                    # If no good break point, cut at last space
                    last_space = cutoff_text.rfind(' ')
                    if last_space > 200:
                        reply_text = cutoff_text[:last_space] + "..."
                    else:
                        reply_text = cutoff_text[:277] + "..."

            # Final validation - make sure we have something reasonable
            if len(reply_text) < 5:
                reply_text = "That's an interesting perspective"

            # Now generate GIF suggestions (multiple queries)
            gif_queries = self.generate_gif_queries(reply_text, tweet_text, style, ai_provider)

            logger.info(f"Generated reply for @{author}: {reply_text[:50]}... | GIF queries: {gif_queries}")

            # Extract actual token usage from response
            token_usage = response.get('usage', {})

            return {
                'reply': reply_text,
                'gif_queries': gif_queries,  # Now returning multiple queries
                'token_usage': {
                    'input_tokens': token_usage.get('input_tokens', 0),
                    'output_tokens': token_usage.get('output_tokens', 0),
                    'total_tokens': token_usage.get('total_tokens', 0),
                    'model': response.get('model', None),
                    'provider_enum': response.get('provider_enum')
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating reply: {str(e)}")
            raise Exception(f"Error generating reply: {str(e)}")
    
    def generate_gif_queries(self, reply_text: str, tweet_text: str, style: str, ai_provider) -> List[str]:
        """Generate multiple GIF search queries based on the reply and tweet context

        Args:
            reply_text: The generated reply text
            tweet_text: The original tweet text
            style: The reply style used
            ai_provider: The AI provider instance to use

        Returns:
            A list of 1-3 word GIF search queries
        """
        try:
            # Create a prompt for multiple GIF query generation
            system_prompt = load_prompt('prompts.txt', 'GIF_QUERY_SYSTEM')
            user_prompt_template = load_prompt('prompts.txt', 'GIF_QUERY_USER')
            prompt = user_prompt_template.format(
                tweet_text=tweet_text[:200],
                reply_text=reply_text,
                style=style
            )

            # Use AI provider with lower temperature for more predictable output
            # ASYNC AI call - thread is freed during AI generation!
            import asyncio

            async def _call_ai_async():
                """Wrapper to call async AI in thread pool - frees main thread!"""
                return await ai_provider.create_completion_async(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.5,
                    max_tokens=7000
                )

            # Run async call - thread is freed via run_in_executor internally
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(_call_ai_async())
            finally:
                loop.close()

            queries_text = response['content'].strip()

            # Split into separate queries
            queries = []
            for line in queries_text.split('\n'):
                query = line.replace('"', '').replace("'", '').strip()
                if query:
                    # Validate - should be 1-3 words
                    words = query.split()
                    if len(words) > 3:
                        query = ' '.join(words[:3])
                    if query and len(query) >= 3:
                        queries.append(query)

            # If we don't have 2 queries, add fallbacks
            fallback_queries = {
                'creatrics': ['mind blown', 'impressed wow'],
                'supportive': ['thumbs up', 'agree nodding'],
                'questioning': ['confused thinking', 'curious hmm'],
                'valueadd': ['smart idea', 'brilliant genius'],
                'humorous': ['laughing', 'funny lol'],
                'contrarian': ['skeptical eyebrow', 'doubt press']
            }

            style_fallbacks = fallback_queries.get(style, ['reaction', 'thinking'])

            # Ensure we have at least 2 queries
            if len(queries) == 0:
                queries = style_fallbacks
            elif len(queries) == 1:
                queries.append(style_fallbacks[0] if style_fallbacks[0] != queries[0] else style_fallbacks[1])

            # Take only first 2 queries
            queries = queries[:2]

            logger.info(f"Generated GIF queries: {queries}")
            return queries
            
        except Exception as e:
            logger.error(f"Error generating GIF query: {str(e)}")
            # Return safe fallbacks
            return ["reaction", "thinking"]
    
    def get_prompt_template(self, use_brand_voice: bool = False) -> str:
        """Get the prompt template for reply generation"""
        try:
            # Load the main reply prompt (same for both with/without brand voice)
            logger.info("Loading prompt from prompts/prompts.txt section: MAIN_REPLY_PROMPT")
            return load_prompt('prompts.txt', 'MAIN_REPLY_PROMPT')
        except Exception as e:
            logger.error(f"Error reading prompt file: {str(e)}")

        # Fallback: use prompts.txt from prompts directory
        logger.info("Using built-in fallback prompt: MAIN_REPLY_PROMPT")
        return load_prompt('prompts.txt', 'MAIN_REPLY_PROMPT')
    
    def get_brand_voice_context(self, user_id: str) -> str:
        """Get brand voice context from user's X replies data - Enhanced version"""
        try:
            # Get user's X replies from Firestore
            doc_ref = self.db.collection('users').document(str(user_id)).collection('x_replies').limit(1)
            docs = list(doc_ref.stream())

            if not docs:
                logger.info(f"No X replies data found for user {user_id}")
                return ""

            # Get the first document (there should only be one)
            replies_data = docs[0].to_dict()

            if not replies_data:
                return ""

            # Extract reply examples from the replies array
            reply_examples = []
            screen_name = "User"

            # Check if we have the replies array structure
            if 'replies' in replies_data and isinstance(replies_data['replies'], list):
                for reply_item in replies_data['replies']:
                    if isinstance(reply_item, dict) and 'reply' in reply_item:
                        reply_info = reply_item['reply']
                        if isinstance(reply_info, dict) and 'text' in reply_info:
                            reply_text = reply_info['text']
                            if reply_text and len(reply_text.strip()) > 5:  # Only meaningful replies
                                # Simple conversion: _new_line_ to actual newlines for AI context
                                clean_text = reply_text.replace('_new_line_', '\n').strip()
                                # Remove URLs to focus on writing style
                                import re
                                clean_text = re.sub(r'https?://\S+', '', clean_text).strip()
                                if clean_text:
                                    reply_examples.append(clean_text)

                            # Get screen name from the first reply if available
                            if screen_name == "User" and 'author' in reply_info:
                                author_info = reply_info['author']
                                if isinstance(author_info, dict) and 'screen_name' in author_info:
                                    screen_name = author_info['screen_name']

            # Fallback: look for other structures (legacy support)
            if not reply_examples:
                for key, value in replies_data.items():
                    if isinstance(value, dict) and 'reply' in value:
                        reply_info = value['reply']
                        if isinstance(reply_info, dict) and 'text' in reply_info:
                            reply_text = reply_info['text']
                            if reply_text and len(reply_text.strip()) > 5:
                                clean_text = reply_text.replace('_new_line_', '\n').strip()
                                import re
                                clean_text = re.sub(r'https?://\S+', '', clean_text).strip()
                                if clean_text:
                                    reply_examples.append(clean_text)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict) and 'reply' in item:
                                reply_info = item['reply']
                                if isinstance(reply_info, dict) and 'text' in reply_info:
                                    reply_text = reply_info['text']
                                    if reply_text and len(reply_text.strip()) > 5:
                                        clean_text = reply_text.replace('_new_line_', '\n').strip()
                                        import re
                                        clean_text = re.sub(r'https?://\S+', '', clean_text).strip()
                                        if clean_text:
                                            reply_examples.append(clean_text)

            # DON'T use regular posts - they're not replies!
            # Only use actual reply examples to maintain authentic reply voice
            # If we don't have enough, just use what we have rather than mixing in non-reply content
            if len(reply_examples) < 3:
                logger.warning(f"Only {len(reply_examples)} reply examples found for user {user_id}. Need more reply data for accurate brand voice.")
                # Don't return empty - use what we have, even if limited
                if not reply_examples:
                    logger.info(f"No reply examples found - brand voice will not be used")
                    return ""

            if not reply_examples:
                logger.info(f"No meaningful examples found for user {user_id}")
                return ""

            # Limit to most recent 15 high-quality examples to save tokens
            reply_examples = reply_examples[:15]

            # Format reply examples as numbered list
            reply_examples_text = ""
            for i, reply in enumerate(reply_examples, 1):
                reply_examples_text += f"{i}. {reply}\n"

            # Load brand voice context template
            brand_voice_template = load_prompt('prompts.txt', 'BRAND_VOICE_CONTEXT')
            brand_voice_context = brand_voice_template.format(
                screen_name=screen_name,
                reply_examples=reply_examples_text
            )

            logger.info(f"Generated enhanced brand voice context for user {user_id} with {len(reply_examples)} examples")
            return brand_voice_context
            
        except Exception as e:
            logger.error(f"Error getting brand voice context: {str(e)}")
            return ""
    
    def has_brand_voice_data(self, user_id: str) -> bool:
        """Check if user has brand voice data available from X replies"""
        try:
            # Check the specific 'data' document where replies are stored
            doc_ref = self.db.collection('users').document(str(user_id)).collection('x_replies').document('data')
            doc = doc_ref.get()

            if not doc.exists:
                logger.info(f"No x_replies/data document found for user {user_id}")
                return False

            # Check if the document has meaningful reply data
            replies_data = doc.to_dict()
            if not replies_data:
                logger.info(f"x_replies/data document is empty for user {user_id}")
                return False

            logger.info(f"Found x_replies document for user {user_id}, keys: {list(replies_data.keys())}")

            # Check the main replies array structure (current format)
            if 'replies' in replies_data and isinstance(replies_data['replies'], list):
                replies_list = replies_data['replies']
                logger.info(f"Found {len(replies_list)} reply items in replies array for user {user_id}")

                for idx, reply_item in enumerate(replies_list[:5]):  # Check first 5 for debugging
                    logger.info(f"Reply item {idx} structure: {list(reply_item.keys()) if isinstance(reply_item, dict) else type(reply_item)}")
                    if isinstance(reply_item, dict) and 'reply' in reply_item:
                        reply_info = reply_item['reply']
                        logger.info(f"Reply info keys: {list(reply_info.keys()) if isinstance(reply_info, dict) else type(reply_info)}")
                        if isinstance(reply_info, dict) and 'text' in reply_info:
                            reply_text = reply_info['text']
                            logger.info(f"Found reply text (length {len(str(reply_text))}): {str(reply_text)[:50]}...")
                            if reply_text and len(str(reply_text).strip()) > 5:
                                logger.info(f"✓ Found valid brand voice data for user {user_id}")
                                return True

            logger.info(f"No meaningful reply text found in x_replies for user {user_id}")
            return False

        except Exception as e:
            logger.error(f"Error checking brand voice data: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False