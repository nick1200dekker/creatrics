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
        NOW SUPPORTS BOTH PUBLIC AND PRIVATE VIDEOS by using cached VTT data

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

            # Get authenticated YouTube client (for uploading)
            youtube = get_user_youtube_client(user_id)
            if not youtube:
                return {
                    'success': False,
                    'error': 'YouTube account not connected',
                    'error_type': 'no_youtube_connection'
                }

            # Use cached VTT data from video_optimizer (avoids redundant downloads)
            # This works for both public AND private videos!
            logger.info("=" * 80)
            logger.info("CAPTION CORRECTION - FETCHING VTT DATA:")
            logger.info("=" * 80)

            from app.scripts.optimize_video.video_optimizer import VideoOptimizer

            optimizer = VideoOptimizer()
            vtt_data = optimizer._fetch_and_cache_vtt(video_id, user_id)

            if not vtt_data:
                return {
                    'success': False,
                    'error': 'No captions available for this video',
                    'error_type': 'no_captions'
                }

            per_word = vtt_data['per_word']
            segments_with_time = vtt_data['segments_with_time']
            has_word_timestamps = vtt_data['has_per_word_timestamps']

            logger.info(f"✓ Using cached VTT data for video {video_id}")
            logger.info(f"✓ Per-word timestamps: {len(per_word)} words")
            logger.info(f"✓ Segments: {len(segments_with_time)}")
            logger.info(f"✓ Has per-word timestamps: {has_word_timestamps}")

            if per_word:
                logger.info(f"First 5 per-word entries: {per_word[:5]}")

            logger.info("=" * 80)

            # Generate original SRT for preview comparison
            # If we have per-word timestamps, create a clean original from those (no duplicates)
            # Otherwise, use segments (which may have YouTube's duplicate text)
            if has_word_timestamps and per_word:
                # Create clean original SRT from per-word data (groups ~6-8 words per segment)
                srt_content = self._create_original_srt_from_words(per_word)
            else:
                # Fallback: use segments (may have duplicates from YouTube VTT)
                srt_content = self._segments_to_srt(segments_with_time)

            if has_word_timestamps and per_word:
                logger.info(f"Using per-word timestamps - {len(per_word)} words extracted")

                # Send word-level data to AI for caption creation
                corrected_srt, token_usage = self._correct_captions_with_word_timestamps(per_word, user_id, user_subscription)

            else:
                logger.info("No per-word timestamps available - using segment-level correction")

                if not segments_with_time:
                    return {
                        'success': False,
                        'error': 'No transcript segments available',
                        'error_type': 'no_segments'
                    }

                # Send SRT to AI for correction (old method)
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

    def _create_original_srt_from_words(self, per_word: List[Dict[str, Any]]) -> str:
        """
        Create a clean original SRT from per-word timestamps (no duplicates)
        Groups words into natural segments of 6-8 words each

        Args:
            per_word: List of {'word': 'text', 'start': timestamp_seconds}

        Returns:
            SRT format string with clean segments
        """
        try:
            if not per_word:
                return ""

            # Helper function to convert seconds to SRT timestamp
            def format_timestamp(seconds):
                h = int(seconds // 3600)
                m = int((seconds % 3600) // 60)
                s = int(seconds % 60)
                ms = int((seconds % 1) * 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            segments = []
            words_per_segment = 7  # Average ~6-8 words per segment

            # Group words into segments
            for i in range(0, len(per_word), words_per_segment):
                segment_words = per_word[i:i + words_per_segment]

                # Start time = first word's timestamp
                start_time = segment_words[0]['start']

                # End time = next segment's first word timestamp (or last word + 0.5s)
                if i + words_per_segment < len(per_word):
                    end_time = per_word[i + words_per_segment]['start']
                else:
                    # Last segment: use last word's timestamp + 0.5 seconds
                    end_time = segment_words[-1]['start'] + 0.5

                # Join words into text
                text = ' '.join([w['word'] for w in segment_words])

                segments.append({
                    'start': format_timestamp(start_time),
                    'end': format_timestamp(end_time),
                    'text': text
                })

            # Convert segments to SRT format
            srt_lines = []
            for i, seg in enumerate(segments, 1):
                srt_lines.append(str(i))
                srt_lines.append(f"{seg['start']} --> {seg['end']}")
                srt_lines.append(seg['text'])
                srt_lines.append('')  # Empty line between segments

            logger.info(f"Created clean original SRT from {len(per_word)} words -> {len(segments)} segments")
            return '\n'.join(srt_lines)

        except Exception as e:
            logger.error(f"Error creating original SRT from words: {e}")
            return ""

    def _convert_vtt_to_srt(self, vtt_content: str) -> str:
        """
        Convert WebVTT format to SRT format
        For simple VTT (no word timestamps): Just convert format
        For complex VTT (with <c> tags): Strip tags and deduplicate
        """
        try:
            import re

            lines = vtt_content.split('\n')
            srt_lines = []
            segment_number = 1
            skip_header = True

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # Skip VTT header
                if skip_header:
                    if line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
                        i += 1
                        continue
                    elif line == '':
                        i += 1
                        continue
                    else:
                        skip_header = False

                # Skip empty lines and NOTE blocks
                if not line or line.startswith('NOTE'):
                    i += 1
                    continue

                # Check if this is a timestamp line (contains -->)
                if '-->' in line:
                    # Strip out VTT metadata (align:start position:0%, etc.)
                    timestamp_parts = line.split()
                    if len(timestamp_parts) >= 3:
                        start_time = timestamp_parts[0].replace('.', ',')
                        end_time = timestamp_parts[2].replace('.', ',')
                        timestamp_line = f"{start_time} --> {end_time}"
                    else:
                        timestamp_line = line.replace('.', ',')

                    # Get the text (next non-empty lines)
                    i += 1
                    text_lines = []
                    while i < len(lines) and lines[i].strip():
                        text = lines[i].strip()

                        # Strip out VTT timing tags if present
                        text = re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', text)
                        text = re.sub(r'</?c>', '', text)

                        if text:
                            text_lines.append(text)
                        i += 1

                    # Write SRT segment if we have text
                    if text_lines:
                        srt_lines.append(str(segment_number))
                        srt_lines.append(timestamp_line)
                        srt_lines.extend(text_lines)
                        srt_lines.append('')  # Empty line between segments
                        segment_number += 1
                else:
                    i += 1

            return '\n'.join(srt_lines)

        except Exception as e:
            logger.error(f"Error converting VTT to SRT: {e}")
            # Fallback: try to use VTT as-is
            return vtt_content

    def _timestamp_to_ms(self, timestamp: str) -> int:
        """Convert SRT timestamp to milliseconds"""
        # Format: 00:00:01,550
        time_part, ms_part = timestamp.split(',')
        h, m, s = map(int, time_part.split(':'))
        ms = int(ms_part)
        return (h * 3600000) + (m * 60000) + (s * 1000) + ms

    def _parse_vtt_word_timestamps(self, vtt_content: str) -> List[Dict]:
        """
        Parse VTT format to extract ONLY per-word timestamps from <c> tags
        YouTube VTT format example:
        are<00:00:00.160><c> you</c><00:00:00.280><c> looking</c><00:00:00.520><c> for</c>

        First word "are" has NO <c> tag, rest have <timestamp><c> word</c> format
        """
        import re

        words_with_timestamps = []

        try:
            lines = vtt_content.split('\n')

            for line in lines:
                # Only process lines with word-level timing tags <c>
                if '<c>' not in line:
                    continue

                # Pattern 1: Find all tagged words: <00:00:00.160><c> you</c>
                tagged_pattern = r'<(\d{2}):(\d{2}):(\d{2})\.(\d{3})><c>\s*([^<]+)</c>'
                tagged_matches = re.findall(tagged_pattern, line)

                for match in tagged_matches:
                    h, m, s, ms, word = match
                    timestamp_seconds = (int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0)
                    words_with_timestamps.append({
                        'word': word.strip(),
                        'start': timestamp_seconds
                    })

                # Pattern 2: Handle first word (no <c> tag): are<00:00:00.160>
                # Extract word before first <
                first_word_match = re.match(r'^([a-zA-Z\'\-]+)<\d{2}:\d{2}:\d{2}\.\d{3}>', line)
                if first_word_match:
                    first_word = first_word_match.group(1).strip()
                    # Get timestamp from first tagged word (they appear in order)
                    first_timestamp_match = re.search(r'<(\d{2}):(\d{2}):(\d{2})\.(\d{3})>', line)
                    if first_timestamp_match:
                        h, m, s, ms = first_timestamp_match.groups()
                        # Estimate first word is ~100-200ms before first timestamp
                        timestamp_seconds = (int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0) - 0.12
                        words_with_timestamps.insert(0 if not words_with_timestamps else len([w for w in words_with_timestamps if w['start'] < timestamp_seconds]), {
                            'word': first_word,
                            'start': max(0, timestamp_seconds)  # Don't go negative
                        })

            logger.info(f"Extracted {len(words_with_timestamps)} words with PRECISE timestamps from VTT")

            # Log first 50 words for debugging
            if words_with_timestamps:
                sample = words_with_timestamps[:50]
                logger.info(f"SAMPLE WORDS FROM VTT (first 50): {sample}")

            return words_with_timestamps

        except Exception as e:
            logger.error(f"Error parsing VTT word timestamps: {e}")
            return []

    def _correct_captions_with_word_timestamps(self, words: List[Dict], user_id: str, user_subscription: str = None) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Create corrected SRT captions using per-word timestamps from VTT
        The AI will use timing gaps to determine natural sentence breaks
        Automatically batches if word list is too large
        """
        try:
            # Format word list as numbered list with timestamps
            # 1. though (00:00:00,120)
            # 2. you're (00:00:00,240)
            def format_timestamp(seconds):
                h = int(seconds // 3600)
                m = int((seconds % 3600) // 60)
                s = int(seconds % 60)
                ms = int((seconds % 1) * 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            word_list_text = "\n".join([f"{i+1}. {w['word']} ({format_timestamp(w['start'])})" for i, w in enumerate(words)])

            logger.info(f"Word list size: {len(word_list_text)} chars, {len(words)} words")
            logger.info(f"SENDING TO AI - First 500 chars:\n{word_list_text[:500]}")
            logger.info(f"================================================================================")
            logger.info(f"FULL SYSTEM PROMPT:")
            logger.info(f"================================================================================")

            # Check if we need to batch (DeepSeek has ~25k char limit)
            if len(word_list_text) > 20000:
                logger.info(f"Word list too large ({len(word_list_text)} chars), using batched processing")
                return self._correct_captions_batched(words, user_id, user_subscription)

            logger.info(f"================================================================================")
            logger.info(f"FULL SYSTEM PROMPT:")
            logger.info(f"================================================================================")

            # Single request for smaller files
            system_prompt = """You are a caption expert. You receive a NUMBERED list of words with their EXACT spoken timestamps.

YOUR TASK:
1. Fix misheard words (e.g., "Though" → "So")
2. Add proper punctuation (periods, commas, question marks)
3. Capitalize properly (sentence starts, "I", proper nouns)
4. Remove filler words ("um", "uh", "you know")
5. Group words into natural caption segments (4-10 words based on natural flow)
6. Use the EXACT timestamps from the list - just look up the word number

HOW TO CREATE TIMESTAMPS:
- If you group words 1-5: start time = word 1's timestamp, end time = word 6's timestamp
- If you group words 6-10: start time = word 6's timestamp, end time = word 11's timestamp
- For last segment: use last word's timestamp + 0.5 seconds for end time

CRITICAL RULES FOR BREAKING SEGMENTS:
- ALWAYS start a new segment after a period (.)
- Break on commas if segment would be too long (>10 words)
- Keep 4-10 words per segment based on natural phrasing
- Shorter segments for questions or emphasis
- Longer segments for flowing narration

EXAMPLE INPUT:
1. are (00:00:00,040)
2. you (00:00:00,160)
3. looking (00:00:00,280)
4. for (00:00:00,520)
5. the (00:00:00,680)
6. best (00:00:00,960)
7. Clash (00:00:01,240)
8. Royale (00:00:01,879)
9. deck (00:00:02,399)
10. Check (00:00:03,000)
11. out (00:00:03,200)
12. this (00:00:03,400)

EXAMPLE OUTPUT:

Segment 1: Group words 1-6 "are you looking for the best"
Start = word 1's time = 00:00:00,040
End = word 7's time = 00:00:01,240

1
00:00:00,040 --> 00:00:01,240
Are you looking for the best

Segment 2: Group words 7-9 "Clash Royale deck."
Start = word 7's time = 00:00:01,240
End = word 10's time = 00:00:03,000

2
00:00:01,240 --> 00:00:03,000
Clash Royale deck.

Segment 3: Group words 10-12 "Check out this"
Start = word 10's time = 00:00:03,000
End = word 13's time (if exists, else word 12 + 0.5s)

3
00:00:03,000 --> 00:00:03,900
Check out this.

OUTPUT: Return ONLY the SRT file. NO explanations."""

            logger.info(system_prompt)
            logger.info(f"================================================================================")

            user_prompt = f"""Create corrected SRT captions from this numbered word list. Use the exact timestamps - just look up the word number.

NUMBERED WORD LIST:
{word_list_text}

Return ONLY the SRT file:"""

            logger.info(f"Sending {len(words)} words to AI ({len(word_list_text)} chars)")

            # Get AI provider
            from app.system.ai_provider.ai_provider import AIProviderManager
            from app.system.services.firebase_service import UserService

            user = UserService.get_user(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return None, None

            ai_provider_manager = AIProviderManager(user_subscription=user_subscription)

            # Calculate max_tokens (rough estimate: input chars / 3 for output)
            estimated_output_tokens = len(word_list_text) // 3
            max_tokens = min(estimated_output_tokens, 8000)

            response = ai_provider_manager.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=max_tokens
            )

            corrected_srt = response['content']
            token_usage = response.get('usage', {})

            logger.info(f"AI returned {len(corrected_srt)} chars of corrected SRT")
            logger.info(f"Token usage: {token_usage}")
            logger.info(f"AI RESPONSE - First 1000 chars:\n{corrected_srt[:1000]}")

            return corrected_srt, token_usage

        except Exception as e:
            logger.error(f"Error correcting captions with word timestamps: {e}")
            return None, None

    def _correct_captions_batched(self, words: List[Dict], user_id: str, user_subscription: str) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Batch process large word lists for caption correction
        Splits into ~300 word chunks to stay under DeepSeek limits
        """
        try:
            from app.system.ai_provider.ai_provider import AIProviderManager
            from app.system.services.firebase_service import UserService

            user = UserService.get_user(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return None, None

            ai_provider_manager = AIProviderManager(user_subscription=user_subscription)

            # Split words into batches of ~800 words (~19K chars each with inline timestamps)
            # DeepSeek supports 32K tokens input, ~8K tokens output
            # 800 words with inline format = ~19K chars + prompts = safe within limits
            batch_size = 800
            batches = [words[i:i + batch_size] for i in range(0, len(words), batch_size)]
            logger.info(f"Split {len(words)} words into {len(batches)} batches of ~{batch_size} words each")

            system_prompt = """You are a caption expert. You receive a NUMBERED list of words with their EXACT spoken timestamps.

YOUR TASK:
1. Fix misheard words (e.g., "Though" → "So")
2. Add proper punctuation (periods, commas, question marks)
3. Capitalize properly (sentence starts, "I", proper nouns)
4. Remove filler words ("um", "uh", "you know")
5. Group words into natural caption segments (4-10 words based on natural flow)
6. Use the EXACT timestamps from the list - just look up the word number

HOW TO CREATE TIMESTAMPS:
- If you group words 1-5: start time = word 1's timestamp, end time = word 6's timestamp
- If you group words 6-10: start time = word 6's timestamp, end time = word 11's timestamp
- For last segment: use last word's timestamp + 0.5 seconds for end time

CRITICAL RULES FOR BREAKING SEGMENTS:
- ALWAYS start a new segment after a period (.)
- Break on commas if segment would be too long (>10 words)
- Keep 4-10 words per segment based on natural phrasing
- Shorter segments for questions or emphasis
- Longer segments for flowing narration

EXAMPLE INPUT:
1. are (00:00:00,040)
2. you (00:00:00,160)
3. looking (00:00:00,280)
4. for (00:00:00,520)
5. the (00:00:00,680)
6. best (00:00:00,960)
7. Clash (00:00:01,240)
8. Royale (00:00:01,879)
9. deck (00:00:02,399)
10. Check (00:00:03,000)
11. out (00:00:03,200)
12. this (00:00:03,400)

EXAMPLE OUTPUT:

Segment 1: Group words 1-6 "are you looking for the best"
Start = word 1's time = 00:00:00,040
End = word 7's time = 00:00:01,240

1
00:00:00,040 --> 00:00:01,240
Are you looking for the best

Segment 2: Group words 7-9 "Clash Royale deck."
Start = word 7's time = 00:00:01,240
End = word 10's time = 00:00:03,000

2
00:00:01,240 --> 00:00:03,000
Clash Royale deck.

Segment 3: Group words 10-12 "Check out this"
Start = word 10's time = 00:00:03,000
End = word 13's time (if exists, else word 12 + 0.5s)

3
00:00:03,000 --> 00:00:03,900
Check out this.

OUTPUT: Return ONLY the SRT file. NO explanations."""

            all_segments = []
            total_input_tokens = 0
            total_output_tokens = 0
            model_name = 'unknown'

            # Helper function to format timestamps
            def format_timestamp(seconds):
                h = int(seconds // 3600)
                m = int((seconds % 3600) // 60)
                s = int(seconds % 60)
                ms = int((seconds % 1) * 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            # Log system prompt once
            if True:  # Only log on first batch
                logger.info(f"================================================================================")
                logger.info(f"BATCHED SYSTEM PROMPT:")
                logger.info(f"================================================================================")
                logger.info(system_prompt)
                logger.info(f"================================================================================")

            # Track global word index across batches
            word_offset = 0

            for batch_num, batch_words in enumerate(batches, 1):
                word_list_text = "\n".join([f"{word_offset + i + 1}. {w['word']} ({format_timestamp(w['start'])})" for i, w in enumerate(batch_words)])

                user_prompt = f"""Create corrected SRT captions from this numbered word list. Use the exact timestamps - just look up the word number.

NUMBERED WORD LIST:
{word_list_text}

Return ONLY the SRT file:"""

                logger.info(f"Processing batch {batch_num}/{len(batches)} ({len(batch_words)} words, {len(word_list_text)} chars)")
                logger.info(f"BATCH {batch_num} - First 300 chars sent to AI:\n{word_list_text[:300]}")

                response = ai_provider_manager.create_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=7000
                )

                batch_srt = response['content'].strip()
                usage = response.get('usage', {})

                # Track token usage
                total_input_tokens += usage.get('prompt_tokens', 0)
                total_output_tokens += usage.get('completion_tokens', 0)
                model_name = usage.get('model', model_name)

                # Clean up AI response (remove any text before first SRT block)
                if '\n\n' in batch_srt:
                    # Find first block with timestamp
                    blocks = batch_srt.split('\n\n')
                    first_valid_block_idx = 0
                    for i, block in enumerate(blocks):
                        if ' --> ' in block:
                            first_valid_block_idx = i
                            break
                    batch_srt = '\n\n'.join(blocks[first_valid_block_idx:])

                # Parse segments from this batch
                segments = self._parse_srt(batch_srt)
                all_segments.extend(segments)

                logger.info(f"Batch {batch_num} complete: {len(segments)} segments generated")
                logger.info(f"BATCH {batch_num} - AI returned first 800 chars:\n{batch_srt[:800]}")
                if segments:
                    logger.info(f"BATCH {batch_num} - First parsed segment: {segments[0]}")

                # Update word offset for next batch
                word_offset += len(batch_words)

            # Combine all segments into final SRT
            final_srt = self._segments_to_srt(all_segments)

            combined_usage = {
                'prompt_tokens': total_input_tokens,
                'completion_tokens': total_output_tokens,
                'total_tokens': total_input_tokens + total_output_tokens,
                'model': model_name
            }

            logger.info(f"Batched processing complete: {len(all_segments)} total segments")
            logger.info(f"Combined token usage: {combined_usage}")

            return final_srt, combined_usage

        except Exception as e:
            logger.error(f"Error in batched caption correction: {e}")
            return None, None

    def _segments_to_srt(self, segments: List[Dict[str, str]]) -> str:
        """Convert segment list back to SRT format"""
        srt_lines = []
        for i, seg in enumerate(segments, 1):
            srt_lines.append(str(i))

            # Handle both old format (timestamp) and new format (start/end)
            if 'timestamp' in seg:
                srt_lines.append(seg['timestamp'])
            elif 'start' in seg and 'end' in seg:
                # Convert VTT timestamps (00:00:00.120) to SRT format (00:00:00,120)
                start_srt = seg['start'].replace('.', ',')
                end_srt = seg['end'].replace('.', ',')
                srt_lines.append(f"{start_srt} --> {end_srt}")
            else:
                # Fallback
                srt_lines.append("00:00:00,000 --> 00:00:01,000")

            srt_lines.append(seg['text'])
            srt_lines.append('')  # Empty line between segments
        return '\n'.join(srt_lines)

    def _parse_srt(self, srt_content: str) -> List[Dict[str, str]]:
        """Parse SRT format into segments with timestamps"""
        segments = []

        blocks = srt_content.strip().split('\n\n')
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 2:
                continue

            try:
                # Find the timestamp line (contains " --> ")
                timestamp_line = None
                text_lines = []

                for i, line in enumerate(lines):
                    if ' --> ' in line:
                        timestamp_line = line
                        # Everything after this line is text
                        text_lines = lines[i+1:]
                        break

                if not timestamp_line or not text_lines:
                    logger.warning(f"Skipping malformed SRT block: {block[:100]}")
                    continue

                text = ' '.join(text_lines)

                segments.append({
                    'timestamp': timestamp_line.strip(),
                    'text': text.strip()
                })
            except Exception as e:
                logger.warning(f"Failed to parse SRT block: {e}")
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
