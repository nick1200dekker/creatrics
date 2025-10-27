"""
Caption Correction Module
Handles downloading, correcting, and re-uploading YouTube captions with AI
"""
import logging
import re
import io
from typing import Dict, Any, List, Tuple, Optional
from app.system.ai_provider.ai_provider import get_ai_provider
from app.scripts.optimize_video.prompts import load_prompt

logger = logging.getLogger(__name__)


class CaptionCorrector:
    """Corrects YouTube captions with AI-powered grammar and punctuation improvements"""

    def correct_english_captions(self, video_id: str, user_id: str, user_subscription: str = None, preview_only: bool = True) -> Dict[str, Any]:
        """
        Download English captions, correct grammar/remove filler words, and optionally re-upload

        Args:
            video_id: YouTube video ID
            user_id: User ID for authentication
            user_subscription: User's subscription plan for AI provider selection
            preview_only: If True, only generate corrected captions without uploading (default: True)

        Returns:
            Dict with success status and details
        """
        try:
            from app.utils.youtube_client import get_user_youtube_client

            # Get authenticated YouTube client
            youtube = get_user_youtube_client(user_id)
            if not youtube:
                return {
                    'success': False,
                    'error': 'YouTube account not connected',
                    'error_type': 'no_youtube_connection'
                }

            # List captions for the video
            captions_response = youtube.captions().list(
                part='snippet',
                videoId=video_id
            ).execute()

            if not captions_response.get('items'):
                return {
                    'success': False,
                    'error': 'No captions found for this video',
                    'error_type': 'no_captions'
                }

            # Find English caption track (prefer automatic)
            english_caption = None
            for caption in captions_response['items']:
                lang = caption['snippet'].get('language', '')
                track_kind = caption['snippet'].get('trackKind', '')

                # Prefer ASR (automatic) English captions
                if lang.startswith('en') and track_kind == 'ASR':
                    english_caption = caption
                    break

            # Fallback to any English caption
            if not english_caption:
                for caption in captions_response['items']:
                    lang = caption['snippet'].get('language', '')
                    if lang.startswith('en'):
                        english_caption = caption
                        break

            if not english_caption:
                return {
                    'success': False,
                    'error': 'No English captions found',
                    'error_type': 'no_english_captions'
                }

            caption_id = english_caption['id']
            logger.info(f"Downloading English caption track {caption_id} for video {video_id}")

            # Download caption in SRT format (200 units)
            caption_data = youtube.captions().download(
                id=caption_id,
                tfmt='srt'
            ).execute()

            # Decode SRT content
            srt_content = caption_data.decode('utf-8')

            # ===== DEBUG: Print raw SRT to see what YouTube gives us =====
            logger.info("=" * 80)
            logger.info("RAW SRT DATA FROM YOUTUBE (first 2000 chars):")
            logger.info("=" * 80)
            logger.info(srt_content[:2000])
            logger.info("=" * 80)

            # Send raw SRT directly to AI for correction
            logger.info(f"Sending raw SRT to AI for correction ({len(srt_content)} chars)")
            corrected_srt, token_usage = self._correct_srt_with_ai(srt_content, user_id, user_subscription)

            if not corrected_srt:
                return {
                    'success': False,
                    'error': 'AI correction failed'
                }

            # Log corrected SRT sample
            logger.info("=" * 80)
            logger.info("CORRECTED SRT (first 2000 chars):")
            logger.info("=" * 80)
            logger.info(corrected_srt[:2000])
            logger.info("=" * 80)

            # Count segments in corrected SRT
            corrected_segment_count = corrected_srt.count('\n\n') + 1

            # If preview_only, return the corrected SRT without uploading
            if preview_only:
                logger.info(f"Preview mode: Returning corrected captions without uploading ({corrected_segment_count} segments)")
                return {
                    'success': True,
                    'preview': True,
                    'message': 'Captions corrected (preview mode)',
                    'original_srt': srt_content,  # Include original for comparison
                    'corrected_srt': corrected_srt,
                    'corrected_segments': corrected_segment_count,
                    'quota_used': 200,  # Only download quota used
                    'token_usage': token_usage  # For credit deduction
                }

            # Otherwise, upload to YouTube
            logger.info(f"Uploading corrected captions to YouTube...")

            # Find the highest version number of existing "AI Corrected" tracks
            highest_version = 0
            import re

            for caption in captions_response['items']:
                caption_name = caption['snippet'].get('name', '')
                # Match "English (AI Corrected X)" pattern
                match = re.match(r'English \(AI Corrected (\d+)\)', caption_name)
                if match:
                    version = int(match.group(1))
                    highest_version = max(highest_version, version)

            # Increment version for new track
            new_version = highest_version + 1
            new_caption_name = f'English (AI Corrected {new_version})'

            logger.info(f"Creating new caption track: {new_caption_name}")

            # Upload corrected captions as a new track (400 units)
            caption_file = io.BytesIO(corrected_srt.encode('utf-8'))

            from googleapiclient.http import MediaIoBaseUpload

            insert_result = youtube.captions().insert(
                part='snippet',
                body={
                    'snippet': {
                        'videoId': video_id,
                        'language': 'en',
                        'name': new_caption_name,
                        'isDraft': False
                    }
                },
                media_body=MediaIoBaseUpload(caption_file, mimetype='application/octet-stream')
            ).execute()

            logger.info(f"Successfully uploaded corrected captions for video {video_id}")

            # Calculate quota used
            quota_used = 200  # Download
            if existing_corrected_caption:
                quota_used += 50  # Delete old track
            quota_used += 400  # Insert new track

            return {
                'success': True,
                'preview': False,
                'message': 'English captions corrected and uploaded',
                'corrected_segments': corrected_segment_count,
                'quota_used': quota_used,
                'token_usage': token_usage  # For credit deduction
            }

        except Exception as e:
            logger.error(f"Error correcting captions for video {video_id}: {e}")

            # Check for YouTube quota exceeded error
            error_str = str(e)
            if 'quotaExceeded' in error_str or 'exceeded your quota' in error_str:
                return {
                    'success': False,
                    'error': 'YouTube API quota exceeded. Please try again tomorrow.',
                    'error_type': 'quota_exceeded'
                }

            return {
                'success': False,
                'error': str(e)
            }

    def apply_corrected_captions(self, video_id: str, user_id: str, corrected_srt: str) -> Dict[str, Any]:
        """
        Upload previously corrected captions to YouTube

        Args:
            video_id: YouTube video ID
            user_id: User ID for authentication
            corrected_srt: The corrected SRT content to upload

        Returns:
            Dict with success status and details
        """
        try:
            from app.utils.youtube_client import get_user_youtube_client
            from googleapiclient.http import MediaIoBaseUpload

            # Get authenticated YouTube client
            youtube = get_user_youtube_client(user_id)
            if not youtube:
                return {
                    'success': False,
                    'error': 'YouTube account not connected',
                    'error_type': 'no_youtube_connection'
                }

            # List captions to check for existing corrected tracks
            captions_response = youtube.captions().list(
                part='snippet',
                videoId=video_id
            ).execute()

            # Find the highest version number of existing "AI Corrected" tracks
            quota_used = 0
            highest_version = 0
            import re

            for caption in captions_response.get('items', []):
                caption_name = caption['snippet'].get('name', '')
                # Match "English (AI Corrected X)" pattern
                match = re.match(r'English \(AI Corrected (\d+)\)', caption_name)
                if match:
                    version = int(match.group(1))
                    highest_version = max(highest_version, version)

            # Increment version for new track
            new_version = highest_version + 1
            new_caption_name = f'English (AI Corrected {new_version})'

            logger.info(f"Creating new caption track: {new_caption_name}")

            # Upload corrected captions as a new track (400 units)
            caption_file = io.BytesIO(corrected_srt.encode('utf-8'))

            insert_result = youtube.captions().insert(
                part='snippet',
                body={
                    'snippet': {
                        'videoId': video_id,
                        'language': 'en',
                        'name': new_caption_name,
                        'isDraft': False
                    }
                },
                media_body=MediaIoBaseUpload(caption_file, mimetype='application/octet-stream')
            ).execute()

            logger.info(f"Successfully uploaded corrected captions for video {video_id}")
            quota_used += 400

            return {
                'success': True,
                'message': 'Corrected captions uploaded to YouTube',
                'quota_used': quota_used
            }

        except Exception as e:
            logger.error(f"Error uploading captions for video {video_id}: {e}")

            # Check for YouTube quota exceeded error
            error_str = str(e)
            if 'quotaExceeded' in error_str or 'exceeded your quota' in error_str:
                return {
                    'success': False,
                    'error': 'YouTube API quota exceeded. Please try again tomorrow.',
                    'error_type': 'quota_exceeded'
                }

            return {
                'success': False,
                'error': str(e)
            }

    def _parse_srt(self, srt_content: str) -> List[Dict[str, str]]:
        """Parse SRT format into segments with timestamps"""
        segments = []

        blocks = srt_content.strip().split('\n\n')
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                # Line 0: sequence number
                # Line 1: timestamp (00:00:00,000 --> 00:00:05,000)
                # Lines 2+: text
                try:
                    timestamp_line = lines[1]
                    start_time, end_time = timestamp_line.split(' --> ')
                    text = ' '.join(lines[2:])

                    segments.append({
                        'start': start_time.strip(),
                        'end': end_time.strip(),
                        'text': text.strip()
                    })
                except:
                    continue

        return segments

    def _correct_srt_with_ai(self, srt_content: str, user_id: str, user_subscription: str = None) -> Tuple[Optional[str], Optional[Dict]]:
        """Send raw SRT to AI for correction. Returns (corrected_srt, token_usage)"""
        try:
            ai_provider = get_ai_provider(
                script_name='optimize_video/caption_correction',
                user_subscription=user_subscription
            )
            if not ai_provider:
                logger.error("AI provider not available for caption correction")
                return None, None

            # Get provider name to determine if batching is needed
            provider_name = ai_provider.__class__.__name__ if hasattr(ai_provider, '__class__') else 'unknown'

            # Check if we need to batch for DeepSeek (limit ~7500 tokens = ~30k chars)
            if 'deepseek' in provider_name.lower() and len(srt_content) > 25000:
                logger.info(f"Large SRT ({len(srt_content)} chars) - using batching for DeepSeek")
                return self._correct_srt_batched(srt_content, user_id, user_subscription, ai_provider)

            system_prompt = """You are a caption correction expert. You receive SRT subtitle files and fix them.

TASK: Fix word errors, add punctuation, capitalize properly, remove filler words, fix overlapping timestamps, and break sentences cleanly.

RULES:
1. Keep EXACT same SRT format (sequence numbers, timestamps, blank lines)
2. Fix TEXT content (grammar, punctuation, capitalization)
3. **FIX OVERLAPPING TIMESTAMPS** - if segment N+1 starts before segment N ends, adjust segment N's end time to be 50-100ms before segment N+1 starts
4. Fix misheard words (e.g., "Though" → "So", "their" → "there")
5. Add punctuation: periods, commas, question marks, exclamation points
6. Capitalize: sentence starts, "I", proper nouns (Clash Royale, Mini Pekka, etc.)
7. Remove filler words: "um", "uh", "like" (when filler), "you know"
8. Keep all subtitle entries - don't merge or skip any
9. **CRITICAL: Move words to start of next line when sentence ends mid-line**
   - If a line ends with "can't you? Let's", move "Let's" to start of next line
   - Each line should end at natural pause or sentence end when possible
   - New sentences should start at beginning of their own line

EXAMPLE OF FIXING OVERLAPPING TIMESTAMPS:
WRONG (segment 2 starts at 1.7s while segment 1 ends at 2.8s):
1
00:00:00,040 --> 00:00:02,885
Though you're not sure which cards

2
00:00:01,718 --> 00:00:04,942
to upgrade in Clash Royale, I'm

CORRECT (segment 1 ends before segment 2 starts):
1
00:00:00,040 --> 00:00:01,668
So you're not sure which cards

2
00:00:01,718 --> 00:00:04,942
to upgrade in Clash Royale? I'm

EXAMPLE OF SENTENCE REFLOW:
WRONG:
14
00:00:23,559 --> 00:00:26,639
game and which ones can't you? Let's

15
00:00:25,359 --> 00:00:28,579
jump in. Right from the start, you

CORRECT:
14
00:00:23,559 --> 00:00:25,309
game and which ones can't you?

15
00:00:25,359 --> 00:00:28,579
Let's jump in. Right from the start, you

OUTPUT: Return the complete corrected SRT file with NO overlapping timestamps and clean sentence breaks."""

            user_prompt = f"""Correct this SRT subtitle file. Fix word errors, add punctuation, capitalize, remove fillers, and FIX OVERLAPPING TIMESTAMPS.

IMPORTANT: Check each timestamp - if segment N+1 starts before segment N ends, adjust segment N's end time to be 50-100ms before segment N+1 starts.

SRT FILE:
{srt_content}

Return the corrected SRT file with NO overlapping timestamps:"""

            logger.info(f"Sending {len(srt_content)} chars to AI for SRT correction")

            # Calculate reasonable max_tokens based on provider and input size
            # Rough estimate: 1 token ≈ 4 characters
            estimated_output_tokens = len(srt_content) // 3  # Conservative estimate for output

            # Get provider name to set appropriate limits
            provider_name = ai_provider.__class__.__name__ if hasattr(ai_provider, '__class__') else 'unknown'

            # Cap at provider-specific limits (with safety margin)
            if 'deepseek' in provider_name.lower():
                max_tokens = min(7500, estimated_output_tokens)  # DeepSeek max: 8192
            elif 'openai' in provider_name.lower():
                max_tokens = min(15000, estimated_output_tokens)  # OpenAI max: 16384
            elif 'claude' in provider_name.lower():
                max_tokens = min(7500, estimated_output_tokens)  # Claude: use reasonable limit
            else:  # Google Gemini and others
                max_tokens = min(60000, estimated_output_tokens)  # Gemini supports 65k

            logger.info(f"Using max_tokens={max_tokens} for caption correction (provider: {provider_name})")

            response = ai_provider.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=max_tokens  # Provider-aware token limit
            )

            corrected_srt = response.get('content', '') if isinstance(response, dict) else str(response)

            # Get token usage
            usage = response.get('usage', {})
            provider_enum = response.get('provider_enum')

            token_usage = {
                'input_tokens': usage.get('input_tokens', 0),
                'output_tokens': usage.get('output_tokens', 0),
                'model': response.get('model', 'unknown'),
                'provider_enum': provider_enum.value if provider_enum else None
            }

            return corrected_srt, token_usage

        except Exception as e:
            logger.error(f"Error correcting SRT with AI: {e}")
            return None, None

    def _correct_caption_text_with_context(self, text: str, user_id: str, user_subscription: str = None,
                                           marker_count: int = 0, max_marker: int = 0) -> Tuple[Optional[str], Optional[Dict]]:
        """Use AI to correct grammar and remove filler words for a batch of caption lines. Returns (corrected_text, token_usage)"""
        try:
            ai_provider = get_ai_provider(
                script_name='optimize_video/caption_correction',
                user_subscription=user_subscription
            )
            if not ai_provider:
                logger.error("AI provider not available for caption correction")
                return None, None

            system_prompt_template = load_prompt('caption_correction_system.txt')
            user_prompt_template = load_prompt('caption_correction_user.txt')

            system_prompt = system_prompt_template
            user_prompt = user_prompt_template.format(
                caption_text=text,
                marker_count=marker_count,
                max_marker=max_marker
            )

            logger.info(f"Caption correction: Expecting {marker_count} markers (0-{max_marker})")

            response = ai_provider.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=min(4000, len(text.split()) * 2)  # Ensure enough tokens for output
            )

            corrected_text = response.get('content', '') if isinstance(response, dict) else str(response)

            # Get token usage (don't deduct here - will be handled centrally)
            usage = response.get('usage', {})
            provider_enum = response.get('provider_enum')

            token_usage = {
                'input_tokens': usage.get('input_tokens', 0),
                'output_tokens': usage.get('output_tokens', 0),
                'model': response.get('model', 'unknown'),
                'provider_enum': provider_enum.value if provider_enum else None
            }

            return corrected_text, token_usage

        except Exception as e:
            logger.error(f"Error correcting caption text: {e}")
            return None, None

    def _correct_srt_batched(self, srt_content: str, user_id: str, user_subscription: str, ai_provider) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Correct large SRT files by splitting into batches for DeepSeek
        Returns (corrected_srt, combined_token_usage)
        """
        try:
            # Split SRT into individual entries
            srt_entries = srt_content.strip().split('\n\n')
            logger.info(f"Splitting {len(srt_entries)} SRT entries into batches")

            # Target ~20k chars per batch (safe for DeepSeek 7500 token limit)
            batch_size_chars = 20000
            batches = []
            current_batch = []
            current_size = 0

            for entry in srt_entries:
                entry_size = len(entry)
                if current_size + entry_size > batch_size_chars and current_batch:
                    # Start new batch
                    batches.append('\n\n'.join(current_batch))
                    current_batch = [entry]
                    current_size = entry_size
                else:
                    current_batch.append(entry)
                    current_size += entry_size + 2  # +2 for \n\n

            # Add last batch
            if current_batch:
                batches.append('\n\n'.join(current_batch))

            logger.info(f"Created {len(batches)} batches for processing")

            # Process each batch
            corrected_batches = []
            total_input_tokens = 0
            total_output_tokens = 0
            model_name = 'unknown'

            system_prompt = """You are a caption correction expert. You receive SRT subtitle files and fix them.

TASK: Fix word errors, add punctuation, capitalize properly, remove filler words, fix overlapping timestamps, and break sentences cleanly.

RULES:
1. Keep EXACT same SRT format (sequence numbers, timestamps, blank lines)
2. Fix TEXT content (grammar, punctuation, capitalization)
3. **FIX OVERLAPPING TIMESTAMPS** - if segment N+1 starts before segment N ends, adjust segment N's end time to be 50-100ms before segment N+1 starts
4. Fix misheard words (e.g., "Though" → "So", "their" → "there")
5. Add punctuation: periods, commas, question marks, exclamation points
6. Capitalize: sentence starts, "I", proper nouns (Clash Royale, Mini Pekka, etc.)
7. Remove filler words: "um", "uh", "like" (when filler), "you know"
8. Keep all subtitle entries - don't merge or skip any
9. **CRITICAL: Move words to start of next line when sentence ends mid-line**
   - If a line ends with "can't you? Let's", move "Let's" to start of next line
   - Each line should end at natural pause or sentence end when possible
   - New sentences should start at beginning of their own line

OUTPUT: Return the complete corrected SRT with NO overlapping timestamps and clean sentence breaks."""

            for i, batch in enumerate(batches, 1):
                logger.info(f"Processing batch {i}/{len(batches)} ({len(batch)} chars)")

                user_prompt = f"""Correct this SRT subtitle file segment. Fix word errors, add punctuation, capitalize, remove fillers, and FIX OVERLAPPING TIMESTAMPS.

IMPORTANT: Check each timestamp - if segment N+1 starts before segment N ends, adjust segment N's end time to be 50-100ms before segment N+1 starts.

SRT SEGMENT:
{batch}

Return the corrected SRT segment with NO overlapping timestamps:"""

                response = ai_provider.create_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=7000  # Safe for DeepSeek
                )

                corrected_batch = response.get('content', '') if isinstance(response, dict) else str(response)
                corrected_batches.append(corrected_batch.strip())

                # Accumulate token usage
                usage = response.get('usage', {})
                total_input_tokens += usage.get('input_tokens', 0)
                total_output_tokens += usage.get('output_tokens', 0)
                model_name = response.get('model', model_name)

            # Combine batches - need to renumber SRT entries
            logger.info(f"Combining {len(corrected_batches)} batches and renumbering")
            combined_srt = self._combine_and_renumber_srt_batches(corrected_batches)

            # Prepare combined token usage
            provider_enum = ai_provider.provider if hasattr(ai_provider, 'provider') else None
            token_usage = {
                'input_tokens': total_input_tokens,
                'output_tokens': total_output_tokens,
                'model': model_name,
                'provider_enum': provider_enum.value if provider_enum else None
            }

            logger.info(f"Batched correction complete: {total_input_tokens} input + {total_output_tokens} output tokens")
            return combined_srt, token_usage

        except Exception as e:
            logger.error(f"Error in batched SRT correction: {e}")
            return None, None

    def _combine_and_renumber_srt_batches(self, batches: List[str]) -> str:
        """Combine SRT batches and renumber entries sequentially"""
        all_entries = []

        for batch in batches:
            # Split batch into individual entries
            entries = batch.strip().split('\n\n')
            for entry in entries:
                if entry.strip():
                    all_entries.append(entry.strip())

        # Renumber all entries
        renumbered = []
        for i, entry in enumerate(all_entries, 1):
            lines = entry.split('\n')
            if len(lines) >= 3:
                # Replace first line (sequence number) with correct number
                lines[0] = str(i)
                renumbered.append('\n'.join(lines))

        return '\n\n'.join(renumbered)

    def _generate_srt(self, segments: List[Dict[str, str]]) -> str:
        """Generate SRT format from segments"""
        srt_lines = []

        for i, seg in enumerate(segments, 1):
            srt_lines.append(str(i))
            srt_lines.append(f"{seg['start']} --> {seg['end']}")
            srt_lines.append(seg['text'])
            srt_lines.append('')  # Empty line between segments

        return '\n'.join(srt_lines)
