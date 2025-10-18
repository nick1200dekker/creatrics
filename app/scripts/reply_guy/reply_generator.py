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
    
    def generate_reply(self, user_id: str, tweet_text: str, author: str, style: str = 'supportive', use_brand_voice: bool = False) -> Optional[str]:
        """Generate AI reply to a tweet"""
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
                system_message = "You are a helpful assistant that generates authentic, human-like replies to tweets. Focus on being concise, engaging, and natural."

            # Call AI provider - higher temperature for more natural responses when mimicking
            temperature = 0.85 if (use_brand_voice and brand_voice_context) else 0.7

            response = self.ai_provider.create_completion(
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
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
            ]

            for prefix in prefixes_to_remove:
                if reply_text.startswith(prefix):
                    reply_text = reply_text[len(prefix):].strip()

            # Remove surrounding quotes if present
            if (reply_text.startswith('"') and reply_text.endswith('"')) or \
               (reply_text.startswith("'") and reply_text.endswith("'")):
                reply_text = reply_text[1:-1].strip()

            # Ensure reply doesn't exceed X's character limit
            if len(reply_text) > 280:
                reply_text = reply_text[:277] + "..."

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
            return """CONTEXT: You're replying to a tweet to maximize engagement and visibility. This reply will appear in a high-traffic conversation thread.

TWEET TO REPLY TO:
@{author}: {tweet_text}

YOUR MISSION: Generate the BEST POSSIBLE {style} reply based on this tweet.

STYLE APPROACH:
- Creatrics (default): Craft the absolute best strategic reply that maximizes engagement while adding genuine value
- Supportive: Encouraging and builds on their point positively
- Questioning: Ask a thought-provoking question that drives discussion
- Value-Add: Provide useful insight, data, or perspective that enhances the conversation
- Humorous: Add wit or humor that feels natural (not forced)
- Contrarian: Respectfully challenge with a fresh perspective

CRITICAL RULES - MUST NOT LOOK AI-GENERATED:
1. BE HUMAN: Write like a real person, not an AI assistant
   - Use casual language, contractions (you're, don't, can't)
   - NO corporate speak or overly polite phrases
   - NO "Great point!" or "I appreciate your perspective" - too formal
   - Natural flow, not structured or templated

2. TIMING & RECENCY:
   - This is a FRESH tweet (you're in the golden 15-minute window)
   - Early quality replies get 300% more visibility
   - Make it count

3. ADD UNIQUE VALUE:
   - Insight, humor, or useful information only
   - No generic agreement or obvious statements
   - Ask yourself: "Would I actually post this?"

4. LENGTH & ENGAGEMENT:
   - 8-25 words is the sweet spot (not too short, not essay-length)
   - Make people want to respond or engage
   - Conversational, not preachy

5. AVOID "REPLY GUY" TRAPS:
   - Don't be overly familiar or presumptuous
   - No unsolicited advice unless directly relevant
   - Match the energy/tone of the original tweet

6. AUTHENTICITY MARKERS:
   - Occasional typos or informal grammar are GOOD (shows you're human)
   - Use "nah" instead of "no", "ya" instead of "yes" when casual
   - Real people use "lol", "fr", "tbh", "lowkey" naturally (when appropriate)
   - Sentence fragments are fine ("Facts." "This." "Exactly.")

7. PERSONALITY INDICATORS (pick 1-2 max):
   - Light emoji use (1-2 max, only if it fits)
   - Personal anecdotes ("had this happen to me")
   - Rhetorical questions
   - Brief reactions ("wild", "insane", "makes sense")

CRITICAL OUTPUT INSTRUCTIONS:
- Output ONLY the reply text that will be posted
- NO prefixes like "<@reply>" or "Reply:" or "Response:"
- NO quotation marks around the reply
- NO explanations or meta-commentary
- Just the raw reply text ready to post directly

Example of CORRECT output:
that's wild, didn't expect those numbers

Example of INCORRECT output:
<@reply> that's wild, didn't expect those numbers
Reply: that's wild, didn't expect those numbers
"that's wild, didn't expect those numbers"

OUTPUT THE REPLY NOW:"""
    
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

            # If we don't have enough reply examples, also check their posts
            if len(reply_examples) < 5:
                logger.info(f"Only {len(reply_examples)} reply examples found, checking posts too...")
                posts_ref = self.db.collection('users').document(str(user_id)).collection('x_posts').document('timeline')
                posts_doc = posts_ref.get()

                if posts_doc.exists:
                    posts_data = posts_doc.to_dict()
                    if posts_data and 'posts' in posts_data:
                        posts_list = posts_data['posts']
                        if isinstance(posts_list, list):
                            for post in posts_list[:10]:  # Get up to 10 posts
                                if isinstance(post, dict) and 'text' in post:
                                    post_text = post['text']
                                    if post_text and len(post_text.strip()) > 10:
                                        import re
                                        clean_text = re.sub(r'https?://\S+', '', post_text).strip()
                                        if clean_text and clean_text not in reply_examples:
                                            reply_examples.append(clean_text)

            if not reply_examples:
                logger.info(f"No meaningful examples found for user {user_id}")
                return ""

            # Limit to most recent 15 high-quality examples to save tokens
            reply_examples = reply_examples[:15]

            # Format brand voice context - focus on examples, not instructions
            brand_voice_context = f"HERE ARE EXAMPLES OF HOW @{screen_name} ACTUALLY REPLIES:\n\n"

            # Just show the examples - let the AI figure out the patterns
            for i, reply in enumerate(reply_examples, 1):
                brand_voice_context += f"Example {i}: {reply}\n"

            brand_voice_context += "\nNow write a reply EXACTLY in this same style. Don't be an AI assistant, BE this person:"

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