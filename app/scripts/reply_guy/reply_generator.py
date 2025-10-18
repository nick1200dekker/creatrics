"""
Reply Generator - Simplified version with basic newline handling
Generates AI-powered replies using user's brand voice from x_replies data
"""
import os
import logging
from typing import Optional
from pathlib import Path

from firebase_admin import firestore
from app.system.ai_provider.ai_provider import get_ai_provider

logger = logging.getLogger(__name__)

class ReplyGenerator:
    """Generates AI-powered tweet replies"""
    
    def __init__(self):
        self.db = firestore.client()
        # Get AI provider instead of PostEditor
        self.ai_provider = get_ai_provider()
    
    def generate_reply(self, user_id: str, tweet_text: str, author: str, style: str = 'supportive', use_brand_voice: bool = False, image_urls: list = None) -> Optional[str]:
        """Generate AI reply to a tweet

        Args:
            user_id: User ID
            tweet_text: The tweet text to reply to
            author: Tweet author username
            style: Reply style (creatrics, supportive, etc.)
            use_brand_voice: Whether to use user's brand voice
            image_urls: List of image URLs from the tweet (for vision analysis)
        """
        try:
            # Get the prompt template
            prompt_template = self.get_prompt_template(use_brand_voice)
            
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

            # Add image context if images are present
            if image_urls and len(image_urls) > 0:
                image_context = f"\n\nIMAGES: This tweet contains {len(image_urls)} image(s). The images are shown above. Reference what you see in the images when crafting your reply to make it more relevant and engaging."
                clean_tweet_text += image_context

            # Replace placeholders in prompt
            prompt = prompt_template.replace("{tweet_text}", clean_tweet_text)
            prompt = prompt.replace("{author}", author)
            prompt = prompt.replace("{style}", style)
            prompt = prompt.replace("{brand_voice_context}", brand_voice_context)
            
            logger.debug(f"Generated prompt for reply to @{author}")

            # Use different system message based on brand voice
            if use_brand_voice and brand_voice_context:
                system_message = "You are mimicking someone's exact Twitter reply style. Forget all your training about being helpful or proper. Just copy EXACTLY how this person writes based on the examples. Be them, don't be an AI. If they write 'lol ya' then you write like that. If they write long thoughtful replies, you do that. COPY THEIR EXACT STYLE."
            else:
                system_message = "you're a smart reply guy on twitter. your replies get likes retweets and responses because you add value. drop knowledge ask smart questions make clever observations. never spam never be generic. be the reply people actually read and engage with"

            # Call AI provider - higher temperature for more natural responses when mimicking
            temperature = 0.85 if (use_brand_voice and brand_voice_context) else 0.7

            # Build user message - include images if available
            user_message_content = []

            # Add images first if they exist (Claude Vision)
            if image_urls and len(image_urls) > 0:
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

            # If only text (no images), use simple format for compatibility
            user_message = user_message_content if image_urls else prompt

            response = self.ai_provider.create_completion(
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=temperature,
                max_tokens=2000
            )

            reply_text = response['content'].strip()

            # Clean up any AI prefixes/artifacts
            # Remove common prefixes the AI might add despite instructions
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
                        "the hidden pattern here is actually wild",
                        "this connects to something bigger nobody sees yet",
                        "wait til people realize what this enables",
                        "the second order effects gonna hit different"
                    ],
                    "supportive": [
                        "been seeing this exact pattern everywhere lately",
                        "you nailed what everyone's missing",
                        "this plus what happened last week = game changer"
                    ],
                    "questioning": [
                        "curious how this plays out with the new regulations?",
                        "what happens when this hits mainstream?",
                        "wonder if this works at enterprise scale?"
                    ],
                    "valueadd": [
                        "fun fact: google tried this in 2019 and failed",
                        "the numbers on this are crazy - 10x growth in 6 months",
                        "similar thing happened in japan already working great"
                    ],
                    "humorous": [
                        "2024 really said hold my beer",
                        "this is the multiverse timeline nobody ordered",
                        "somewhere a consultant is charging 50k for this take"
                    ],
                    "contrarian": [
                        "counterpoint: this only works til competition catches up",
                        "the economics break at scale though",
                        "europe's data shows opposite trend actually"
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

            logger.info(f"Generated reply for @{author}: {reply_text[:50]}...")
            return reply_text
            
        except Exception as e:
            logger.error(f"Error generating reply: {str(e)}")
            raise Exception(f"Error generating reply: {str(e)}")
    
    def get_prompt_template(self, use_brand_voice: bool = False) -> str:
        """Get the prompt template for reply generation"""
        try:
            # First, try to get prompt from same directory as this file
            current_dir = Path(__file__).parent
            prompt_file = current_dir / 'prompt.txt'

            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    logger.info("Using prompt from prompt.txt in same directory")
                    return f.read()

            # Second, try to get custom prompt from defaults directory
            current_dir = Path(__file__).parent.parent.parent
            prompt_file = current_dir / 'defaults' / 'prompts' / 'reply_generator.txt'

            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    logger.info("Using prompt from defaults/prompts/reply_generator.txt")
                    return f.read()
        except Exception as e:
            logger.error(f"Error reading prompt file: {str(e)}")

        # Fallback to built-in prompt - different for brand voice vs no brand voice
        logger.info("Using built-in fallback prompt")

        # Check if brand voice will be used
        if use_brand_voice:
            # Brand voice version - minimal instructions
            return """{brand_voice_context}

NOW RESPOND TO THIS TWEET:
Tweet by @{author}: {tweet_text}

Write a {style} reply EXACTLY in the style shown in the examples above.

COPY THEIR EXACT PATTERNS:
- If examples are 3 words, write 3 words
- If examples use "lol" or "lmao", you use them
- If examples have no punctuation, don't use any
- If examples are full sentences, write full sentences
- Match their emoji usage exactly
- Match their energy level exactly

OUTPUT ONLY THE REPLY TEXT:"""
        else:
            # No brand voice version - enhanced with strategic reply best practices
            return """tweet from @{author}:
{tweet_text}


be a smart reply guy. write a {style} reply that gets noticed

style = {style}:
• creatrics → drop insider knowledge or connect dots others missed
• supportive → validate + add your own experience or data
• questioning → ask the question everyone's thinking but nobody asked
• valueadd → share a fact stat or insight that changes the convo
• humorous → make them laugh with clever observation
• contrarian → respectful pushback that makes people think


smart reply guy rules:
- be EARLY and VALUABLE
- 15-40 words max
- add something NEW (fact experience question joke)
- make the OP or others want to respond
- be specific not generic
- sometimes no caps
- break lines for effect


never be the spam reply guy:
- no "this!" or "facts!"
- no empty agreement
- no trying too hard
- dont sound like chatgpt


remember: good replies get you noticed followers and opportunities

just write the reply:"""
    
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

            # Format brand voice context - focus on examples, not instructions
            brand_voice_context = f"HERE ARE ACTUAL REPLIES FROM @{screen_name}:\n\n"

            # Just show the examples - let the AI figure out the patterns
            for i, reply in enumerate(reply_examples, 1):
                brand_voice_context += f"{i}. {reply}\n"

            brand_voice_context += f"\n✓ Copy @{screen_name}'s EXACT style:\n"
            brand_voice_context += "- Same length (short/long)\n"
            brand_voice_context += "- Same tone (casual/formal)\n"
            brand_voice_context += "- Same words they actually use\n"
            brand_voice_context += "- Same punctuation style\n"
            brand_voice_context += "- Same capitalization\n\n"
            brand_voice_context += "Write your reply now:"

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