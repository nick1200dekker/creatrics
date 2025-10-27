"""
VTT Parser Module
Unified parser that extracts per-word timestamps, segment timestamps, and plain text from VTT
"""
import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class VTTParser:
    """Unified VTT parser for all optimization features"""

    @staticmethod
    def parse_vtt(vtt_content: str) -> Dict[str, Any]:
        """
        Parse VTT content into 3 formats:
        1. per_word: For caption correction (with <c> tags timestamps)
        2. segments_with_time: For description/chapters (segment timestamps + text)
        3. plain_text: For title/tags generation (no timestamps)

        Args:
            vtt_content: Raw VTT string from YouTube/RapidAPI

        Returns:
            Dict with all 3 parsed formats
        """
        try:
            # Parse per-word timestamps (for captions)
            per_word = VTTParser._parse_per_word_timestamps(vtt_content)

            # Parse segment timestamps (for description/chapters)
            segments_with_time = VTTParser._parse_segment_timestamps(vtt_content)

            # Extract plain text (for title/tags)
            plain_text = VTTParser._extract_plain_text(segments_with_time)

            logger.info(f"VTT parsed: {len(per_word)} words, {len(segments_with_time)} segments, {len(plain_text)} chars plain text")

            return {
                'per_word': per_word,
                'segments_with_time': segments_with_time,
                'plain_text': plain_text,
                'has_per_word_timestamps': len(per_word) > 0
            }

        except Exception as e:
            logger.error(f"Error parsing VTT: {e}")
            return {
                'per_word': [],
                'segments_with_time': [],
                'plain_text': '',
                'has_per_word_timestamps': False
            }

    @staticmethod
    def _parse_per_word_timestamps(vtt_content: str) -> List[Dict[str, Any]]:
        """
        Extract per-word timestamps from <c> tags
        Example: <00:00:00.280><c> hired</c> -> {'word': 'hired', 'start': 0.280}
        Also handles: new<00:00:07.040><c> player</c> (word before timestamp)
        """
        words_with_timestamps = []

        lines = vtt_content.split('\n')
        for line in lines:
            # Skip if no <c> tags
            if '<c>' not in line:
                continue

            # First, check for words BEFORE the first timestamp (e.g., "new<00:00:07.040><c> player</c>" or " I<00:00:00.280><c> hired</c>")
            # Extract any word that appears before the first < character (including single letters like "I")
            # Pattern allows optional leading whitespace
            prefix_word_match = re.search(r'^\s*([a-zA-Z\']+)<\d{2}:', line)
            if prefix_word_match:
                prefix_word = prefix_word_match.group(1).strip()

                # Get the timestamp of the FIRST tagged word that follows
                first_timestamp_match = re.search(r'<(\d{2}):(\d{2}):(\d{2})\.(\d{3})>', line)
                if first_timestamp_match:
                    h, m, s, ms = first_timestamp_match.groups()
                    # Use the same timestamp as the following word (or slightly earlier)
                    timestamp_seconds = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0 - 0.1
                    words_with_timestamps.append({
                        'word': prefix_word,
                        'start': max(0, timestamp_seconds)  # Don't go negative
                    })

            # Then extract all timestamped words: <00:00:00.280><c> hired</c>
            tagged_pattern = r'<(\d{2}):(\d{2}):(\d{2})\.(\d{3})><c>\s*([^<]+)</c>'
            tagged_matches = re.findall(tagged_pattern, line)

            for match in tagged_matches:
                h, m, s, ms, word = match
                timestamp_seconds = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
                words_with_timestamps.append({
                    'word': word.strip(),
                    'start': timestamp_seconds
                })

        return words_with_timestamps

    @staticmethod
    def _parse_segment_timestamps(vtt_content: str) -> List[Dict[str, Any]]:
        """
        Extract segment timestamps and text (for description/chapters)

        YouTube VTT shows progressive text building:
        - Lines WITH <c> tags = NEW words being added (extract these)
        - Lines WITHOUT <c> tags = accumulated display text (skip to avoid duplicates)

        Example VTT:
        00:00:02.000 --> 00:00:03.310
        I hired the coach in Clash Royale and
        he's<00:00:02.159><c> going</c><00:00:02.320><c> to</c>

        We extract: "he's going to" (only NEW content with <c> tags)
        """
        segments = []
        lines = vtt_content.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Look for timestamp line (contains " --> ")
            if ' --> ' in line:
                # Parse timestamp
                timestamp_match = re.match(r'(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2}\.\d{3})', line)

                if timestamp_match:
                    start_time = timestamp_match.group(1)
                    end_time = timestamp_match.group(2)

                    # Get text from next lines (until blank line or next timestamp)
                    text_parts = []
                    has_new_content = False
                    i += 1

                    while i < len(lines):
                        next_line = lines[i].strip()

                        # Stop at blank line or next timestamp
                        if not next_line or ' --> ' in next_line:
                            break

                        # ONLY process lines that have <c> tags (new content being added)
                        if '<c>' in next_line:
                            has_new_content = True

                            # Extract text before first timestamp tag (if any) - e.g., "new<00:00:07.040>" or " I<00:00:00.280>"
                            # This handles prefix words that appear before the first timestamp
                            prefix_match = re.search(r'^\s*([a-zA-Z\']+)<\d{2}:', next_line)
                            if prefix_match:
                                prefix_text = prefix_match.group(1).strip()
                                if prefix_text:
                                    text_parts.append(prefix_text)

                            # Extract all words inside <c> tags
                            c_tag_words = re.findall(r'<c>\s*([^<]+)</c>', next_line)
                            text_parts.extend([w.strip() for w in c_tag_words if w.strip()])

                        i += 1

                    # Only add segments that have NEW content (lines with <c> tags)
                    if has_new_content and text_parts:
                        text = ' '.join(text_parts)
                        segments.append({
                            'start': start_time,
                            'end': end_time,
                            'text': text
                        })

                    continue

            i += 1

        return segments

    @staticmethod
    def _extract_plain_text(segments_with_time: List[Dict[str, Any]]) -> str:
        """
        Extract plain text from segments (for title/tags)
        """
        text_parts = [seg['text'] for seg in segments_with_time if seg.get('text')]
        return ' '.join(text_parts)

    @staticmethod
    def format_segments_for_ai(segments_with_time: List[Dict[str, Any]], max_segments: int = None) -> str:
        """
        Format segments with timestamps for AI (description/chapters)
        Example output:
        00:00:00.120 --> 00:00:01.990 I hired the coach in Clash Royale and
        00:00:02.000 --> 00:00:03.310 he's going to help me with my deck
        """
        segments_to_use = segments_with_time[:max_segments] if max_segments else segments_with_time

        formatted_lines = []
        for seg in segments_to_use:
            formatted_lines.append(f"{seg['start']} --> {seg['end']} {seg['text']}")

        return '\n'.join(formatted_lines)
