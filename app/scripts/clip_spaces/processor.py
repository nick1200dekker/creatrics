import os
import json
import tempfile
import subprocess
import shutil
import requests
from app.system.ai_provider.ai_provider import get_ai_provider
import time
import logging
from pathlib import Path


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

class SpaceProcessor:
    def __init__(self, space_id, user_id, status_callback=None, user_subscription=None):
        """Initialize the Space processor"""
        self.space_id = space_id
        self.user_id = user_id
        self.temp_dir = tempfile.mkdtemp()
        self.audio_path = os.path.join(self.temp_dir, f"{space_id}.mp3")
        self.status_callback = status_callback
        self.space_data = None  # Store space data for participant mapping
        
        # Get API keys
        self.elevenlabs_api_key = os.environ.get('ELEVENLAB_API_KEY', '')
        self.scribe_model = os.environ.get('SCRIBE_MODEL', 'scribe_v1')
        
        if not self.elevenlabs_api_key:
            logger.error("ElevenLabs API key not found")
        
        # Get AI provider instead of OpenAI client
        self.ai_provider = get_ai_provider(
                script_name='clip_spaces/processor',
                user_subscription=user_subscription
            )
        
        # Load prompt templates from prompts/ directory
        self.highlight_prompt_template = load_prompt('prompts.txt', 'HIGHLIGHT_PROMPT')
        self.quotes_prompt_template = load_prompt('prompts.txt', 'QUOTES_PROMPT')

    def update_status(self, message, progress=None):
        """Update processing status"""
        if self.status_callback:
            self.status_callback(message, progress)
        print(message)
    
    def fetch_space_data(self):
        """Fetch Twitter Space data from RapidAPI"""
        self.update_status("🔍 Finding Space...", 10)
        
        # Get X API key from environment variables
        x_api_key = os.environ.get('X_RAPID_API_KEY')
        if not x_api_key:
            logger.error("X_RAPID_API_KEY not found in environment variables")
            raise ValueError("X_RAPID_API_KEY environment variable is required")
        
        # Get API host (with default fallback)
        x_api_host = os.environ.get('X_RAPID_API_HOST', 'twitter-api45.p.rapidapi.com')
        
        url = f"https://{x_api_host}/spaces.php"
        headers = {
            "x-rapidapi-key": x_api_key,
            "x-rapidapi-host": x_api_host
        }
        
        response = requests.get(url, headers=headers, params={"id": self.space_id})
        
        if response.status_code != 200:
            raise Exception(f"API request failed: {response.status_code}")
        
        space_data = response.json()
        if 'playlist' not in space_data:
            raise Exception('Invalid Space ID or Space not found')
        
        # Store space data for participant mapping
        self.space_data = space_data
        
        self.update_status("✅ Space found successfully", 15)
        return space_data
    
    def download_and_get_duration(self, playlist_url):
        """Download audio and return duration"""
        # Check if we should use parallel download for Cloud Run
        use_parallel = os.environ.get('SPACES_PARALLEL_DOWNLOAD', 'false').lower() == 'true'
        
        if use_parallel:
            try:
                from .processor_streaming import StreamingSpaceProcessor
                streaming_processor = StreamingSpaceProcessor(
                    self.space_id, self.user_id, self.temp_dir, 
                    self.audio_path, self.update_status
                )
                streaming_processor.download_audio_parallel(playlist_url)
            except Exception as e:
                logger.warning(f"Parallel download failed, falling back to sequential: {e}")
                self.download_audio(playlist_url)
        else:
            self.download_audio(playlist_url)
            
        return self.get_audio_duration(self.audio_path)
    
    def download_audio(self, playlist_url):
        """Download audio using ffmpeg HLS conversion with retry logic"""
        max_retries = 3
        
        logger.info(f"[SPACES] Starting audio download from: {playlist_url}")
        start_time = time.time()
        
        for attempt in range(max_retries):
            try:
                attempt_start = time.time()
                if attempt == 0:
                    self.update_status("📥 Downloading audio...", 20)
                else:
                    self.update_status(f"📥 Downloading audio (attempt {attempt + 1}/{max_retries})...", 20)
                
                logger.info(f"[SPACES] Download attempt {attempt + 1} starting")
                
                # Enhanced ffmpeg command with better network handling
                cmd = [
                    'ffmpeg',
                    '-timeout', '5000000',          # 5 seconds timeout for HTTP operations
                    '-reconnect', '1',              # Enable reconnection on network errors
                    '-reconnect_streamed', '1',     # Reconnect even for streamed content
                    '-reconnect_delay_max', '5',    # Max 5 seconds between reconnect attempts
                    '-i', playlist_url,
                    '-vn',                          # No video
                    '-acodec', 'libmp3lame',        # MP3 codec
                    '-ab', '128k',                  # Audio bitrate
                    '-ar', '44100',                 # Sample rate
                    '-ac', '2',                     # Stereo
                    '-y',                           # Overwrite output
                    '-progress', 'pipe:1',          # Output progress to stdout
                    self.audio_path
                ]
                
                # Log the command being run
                logger.info(f"[SPACES] Running ffmpeg command: {' '.join(cmd[:6])}... (truncated)")

                # Use longer timeout for Cloud Run (30 minutes per attempt)
                # Configurable via environment variable, default 1800 seconds (30 min)
                download_timeout = int(os.environ.get('SPACES_DOWNLOAD_TIMEOUT', '1800'))
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=download_timeout)
                
                if result.returncode == 0 and self._verify_audio_file():
                    file_size = os.path.getsize(self.audio_path) / (1024 * 1024)
                    download_time = time.time() - attempt_start
                    total_time = time.time() - start_time
                    logger.info(f"[SPACES] Download successful - Size: {file_size:.2f} MB, Time: {download_time:.1f}s (Total: {total_time:.1f}s)")
                    self.update_status(f"✅ Audio downloaded successfully ({file_size:.2f} MB)", 40)
                    return self.audio_path
                
                # If download failed but we have retries left
                if attempt < max_retries - 1:
                    error_msg = result.stderr[-500:] if result.stderr else "Unknown error"
                    logger.warning(f"[SPACES] Download failed on attempt {attempt + 1}: {error_msg}")
                    self.update_status(f"⚠️ Download failed, retrying... ({error_msg})", 20)
                    time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                    continue
                else:
                    logger.error(f"[SPACES] Download failed after all attempts: {result.stderr}")
                    raise Exception(f"Audio download failed: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                timeout_duration = time.time() - attempt_start
                logger.error(f"[SPACES] Download timeout on attempt {attempt + 1} after {timeout_duration:.1f}s")
                if attempt < max_retries - 1:
                    self.update_status(f"⏱️ Download timeout, retrying...", 20)
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise Exception(f"Audio download timed out after {max_retries} attempts")
            except Exception as e:
                if attempt < max_retries - 1 and "timeout" in str(e).lower():
                    self.update_status(f"⏱️ Network timeout, retrying...", 20)
                    time.sleep(2 ** attempt)
                    continue
                raise
        
        raise Exception(f"Audio download failed after {max_retries} attempts")
    
    def _verify_audio_file(self):
        """Verify audio file is valid"""
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', 
                   '-show_streams', self.audio_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return any(s.get('codec_type') == 'audio' for s in data.get('streams', []))
        except:
            pass
        return False
    
    def get_audio_duration(self, audio_path):
        """Get audio duration in seconds"""
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
               '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to get duration: {result.stderr}")
        
        duration = float(result.stdout.strip())
        return duration
    
    def transcribe_audio(self):
        """Transcribe audio using ElevenLabs Scribe"""
        self.update_status("🎤 Transcribing audio...", 50)
        
        duration_seconds = self.get_audio_duration(self.audio_path)
        file_size = os.path.getsize(self.audio_path) / (1024 * 1024)
        
        # Make API request
        url = "https://api.elevenlabs.io/v1/speech-to-text"
        headers = {"xi-api-key": self.elevenlabs_api_key}
        
        with open(self.audio_path, 'rb') as audio_file:
            files = {'file': (f'{self.space_id}.mp3', audio_file, 'audio/mpeg')}
            data = {
                'model_id': self.scribe_model,
                'diarize': 'true',
                'num_speakers': '6',
                'timestamps_granularity': 'word'
            }
            
            response = requests.post(url, headers=headers, files=files, data=data, timeout=600)
        
        if response.status_code != 200:
            raise Exception(f"Transcription failed: {response.status_code} - {response.text}")
        
        transcription_data = response.json()
        self.update_status("✅ Transcription completed successfully", 70)
        
        # Create segments from speaker diarization
        segments = self._create_segments_from_speakers(transcription_data.get('words', []))
        
        if not segments:
            raise Exception("No segments created from transcription")
        
        # Format output
        structured_transcript = self._create_structured_transcript(segments)
        formatted_transcript = self._format_display_transcript(segments)
        
        self.update_status("🔑 Processing transcript data...", 75)
        estimated_tokens = {
            'input_tokens': int((duration_seconds / 60) * 10),
            'output_tokens': int(len(formatted_transcript) / 4),
            'model': self.scribe_model
        }
        
        self.update_status("✅ Transcript processing completed", 80)
        return (structured_transcript, formatted_transcript), estimated_tokens
    
    def _create_segments_from_speakers(self, words):
        """Create segments based on speaker diarization"""
        segments = []
        current_words = []
        current_speaker = None
        start_time = None
        end_time = None
        
        for word_data in words:
            if word_data.get('type') != 'word':
                continue
            
            word_text = word_data.get('text', '').strip()
            speaker_id = word_data.get('speaker_id')
            word_start = word_data.get('start', 0)
            word_end = word_data.get('end', 0)
            
            if not word_text:
                continue
            
            # Check if speaker changed
            if current_speaker != speaker_id:
                # Save previous segment
                if current_words and current_speaker:
                    segments.append({
                        'text': ' '.join(current_words).strip(),
                        'start_time': start_time,
                        'end_time': end_time,
                        'speaker': current_speaker
                    })
                
                # Start new segment
                current_words = [word_text]
                current_speaker = speaker_id or 'Unknown Speaker'
                start_time = word_start
                end_time = word_end
            else:
                # Continue current segment
                current_words.append(word_text)
                end_time = word_end
        
        # Add final segment
        if current_words and current_speaker:
            segments.append({
                'text': ' '.join(current_words).strip(),
                'start_time': start_time,
                'end_time': end_time,
                'speaker': current_speaker
            })
        
        return segments
    
    def _create_structured_transcript(self, segments):
        """Create structured data for AI processing"""
        structured_segments = []
        
        for i, segment in enumerate(segments):
            text = segment.get('text', '').strip()
            if not text:
                continue
            
            start_time = segment.get('start_time', 0)
            end_time = segment.get('end_time', 0)
            
            structured_segments.append({
                'segment_id': i + 1,
                'speaker': segment.get('speaker', f'Speaker {i+1}'),
                'start_time': start_time,
                'end_time': end_time,
                'start_timestamp': self._format_timestamp(start_time),
                'end_timestamp': self._format_timestamp(end_time),
                'text': text
            })
        
        return structured_segments
    
    def _format_display_transcript(self, segments):
        """Format transcript for display with cleaner formatting"""
        formatted_lines = []
        
        for segment in segments:
            text = segment.get('text', '').strip()
            if not text:
                continue
            
            start_ts = self._format_timestamp(segment.get('start_time', 0))
            end_ts = self._format_timestamp(segment.get('end_time', 0))
            speaker = segment.get('speaker', 'Unknown Speaker')
            
            # Clean formatting - not everything bold
            line = f"{start_ts} - {end_ts}\n**{speaker}:**\n{text}"
            formatted_lines.append(line)
        
        return "\n\n".join(formatted_lines)
    
    def _format_timestamp(self, seconds):
        """Format seconds to MM:SS.MS (matches audio player format)"""
        if seconds is None or seconds < 0:
            return "00:00.00"
            
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        
        # Format as MM:SS.MS to match the audio player
        return f"{minutes:02d}:{remaining_seconds:05.2f}"
    
    def generate_summary(self, transcript_data):
        """Generate comprehensive summary"""
        self.update_status("📝 Generating AI summary...", 85)
        
        if isinstance(transcript_data, tuple):
            structured_segments, display_transcript = transcript_data
        else:
            structured_segments = []
            display_transcript = transcript_data
        
        # Generate both summaries
        general_summary, general_tokens = self._generate_general_summary(structured_segments)
        detailed_summary, detailed_tokens = self._generate_detailed_summary(structured_segments)
        
        # Combine results
        combined_summary = f"""# Twitter Space Summary

## Overview
{general_summary}

## Key Highlights and Quotes
{detailed_summary}
"""
        
        total_tokens = {
            'input_tokens': general_tokens['input_tokens'] + detailed_tokens['input_tokens'],
            'output_tokens': general_tokens['output_tokens'] + detailed_tokens['output_tokens'],
            'model': self.ai_provider.default_model
        }
        
        self.update_status("✅ Summary generated successfully", 95)
        return combined_summary, total_tokens
    
    def _generate_general_summary(self, structured_segments):
        """Generate general summary using AI provider"""
        # Format segments for AI
        ai_text = "\n\n".join([
            f"[{seg['start_timestamp']} - {seg['end_timestamp']}] {seg['speaker']}: {seg['text']}"
            for seg in structured_segments
        ])
        
        system_prompt = load_prompt('prompts.txt', 'SUMMARY_SYSTEM')
        user_prompt_template = load_prompt('prompts.txt', 'SUMMARY_USER')
        user_prompt = user_prompt_template.format(ai_text=ai_text)

        # ASYNC AI call - thread is freed during AI generation!
        import asyncio

        async def _call_ai_async():
            """Wrapper to call async AI in thread pool - frees main thread!"""
            return await self.ai_provider.create_completion_async(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=7000
            )

        # Run async call - thread is freed via run_in_executor internally
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(_call_ai_async())
        finally:
            loop.close()
        
        return response['content'], {
            'input_tokens': response['usage']['input_tokens'],
            'output_tokens': response['usage']['output_tokens']
        }
    
    def _generate_detailed_summary(self, structured_segments):
        """Generate detailed highlights and quotes using separate prompts"""
        
        # Extract and format participants list for AI
        participants_text = self._format_participants_list()
        
        # Filter out very short segments and create substantial content list
        substantial_segments = []
        for seg in structured_segments:
            # Include segments with meaningful content (more than 8 words)
            word_count = len(seg['text'].split())
            if word_count > 8:  # Lower threshold to catch more potential highlights
                substantial_segments.append(f"Segment {seg['segment_id']}: [{seg['start_timestamp']} - {seg['end_timestamp']}] {seg['speaker']}: \"{seg['text']}\"")
        
        segments_text = "\n\n".join(substantial_segments)
        
        # Generate highlights
        highlight_prompt = self.highlight_prompt_template.format(
            participants_text=participants_text,
            segments_text=segments_text
        )
        
        # ASYNC AI call - thread is freed during AI generation!
        import asyncio

        async def _call_ai_async_highlights():
            """Wrapper to call async AI in thread pool - frees main thread!"""
            return await self.ai_provider.create_completion_async(
                messages=[
                    {"role": "system", "content": "You extract substantial business insights and detailed highlights from conversations. You map speaker IDs to real names when confident and focus on longer, valuable content."},
                    {"role": "user", "content": highlight_prompt}
                ],
                max_tokens=7000
            )

        # Run async call - thread is freed via run_in_executor internally
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            highlights_response = loop.run_until_complete(_call_ai_async_highlights())
        finally:
            loop.close()
        
        highlights_tokens = {
            'input_tokens': highlights_response['usage']['input_tokens'],
            'output_tokens': highlights_response['usage']['output_tokens']
        }
        
        # Generate quotes
        quotes_prompt = self.quotes_prompt_template.format(
            participants_text=participants_text,
            segments_text=segments_text
        )
        
        # ASYNC AI call - thread is freed during AI generation!
        import asyncio

        async def _call_ai_async_quotes():
            """Wrapper to call async AI in thread pool - frees main thread!"""
            return await self.ai_provider.create_completion_async(
                messages=[
                    {"role": "system", "content": "You extract powerful, quotable moments from conversations. You focus on short, punchy statements that could be headlines or tweets. You map speaker IDs to real names when confident."},
                    {"role": "user", "content": quotes_prompt}
                ],
                max_tokens=7000
            )

        # Run async call - thread is freed via run_in_executor internally
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            quotes_response = loop.run_until_complete(_call_ai_async_quotes())
        finally:
            loop.close()
        
        quotes_tokens = {
            'input_tokens': quotes_response['usage']['input_tokens'],
            'output_tokens': quotes_response['usage']['output_tokens']
        }
        
        # Combine highlights and quotes into chronological order
        all_moments = []
        
        # Parse highlights
        for line in highlights_response['content'].strip().split('\n'):
            if line.strip() and line.startswith('**['):
                all_moments.append(line.strip())
        
        # Parse quotes
        for line in quotes_response['content'].strip().split('\n'):
            if line.strip() and line.startswith('**['):
                all_moments.append(line.strip())
        
        # Sort chronologically by extracting timestamp
        def get_timestamp(line):
            try:
                # Extract MM:SS.MS from **[MM:SS.MS - MM:SS.MS]
                timestamp_part = line.split(']')[0].split('[')[1].split(' - ')[0]
                minutes, seconds = timestamp_part.split(':')
                return float(minutes) * 60 + float(seconds)
            except:
                return 0
        
        all_moments.sort(key=get_timestamp)
        
        # Join into final output
        combined_output = '\n\n'.join(all_moments)
        
        # Combine tokens
        total_tokens = {
            'input_tokens': highlights_tokens['input_tokens'] + quotes_tokens['input_tokens'],
            'output_tokens': highlights_tokens['output_tokens'] + quotes_tokens['output_tokens']
        }
        
        return combined_output, total_tokens
    
    def _format_participants_list(self):
        """Format participants list for AI prompt"""
        if not self.space_data or 'participants' not in self.space_data:
            return "No participants list available."
        
        participants_lines = []
        participants = self.space_data['participants']
        
        # Add hosts/admins
        if 'admins' in participants and participants['admins']:
            participants_lines.append("HOSTS:")
            for admin in participants['admins']:
                display_name = admin.get('display_name', 'Unknown')
                screenname = admin.get('screenname', 'unknown')
                participants_lines.append(f"- {display_name} (@{screenname})")
        
        # Add speakers
        if 'speakers' in participants and participants['speakers']:
            participants_lines.append("\nSPEAKERS:")
            for speaker in participants['speakers']:
                display_name = speaker.get('display_name', 'Unknown')
                screenname = speaker.get('screenname', 'unknown')
                participants_lines.append(f"- {display_name} (@{screenname})")
        
        if not participants_lines:
            return "No participants list available."
        
        return "\n".join(participants_lines)
    
    def trim_audio(self, start_time, end_time, output_path):
        """Trim audio to specified timeframe"""
        cmd = [
            'ffmpeg', '-i', self.audio_path, '-ss', str(start_time),
            '-to', str(end_time), '-acodec', 'copy', '-y', output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Audio trimming failed: {result.stderr}")
        
        if not os.path.exists(output_path):
            raise Exception("Failed to create trimmed audio file")
        
        file_size = os.path.getsize(output_path) / (1024 * 1024)
        return output_path
    
    def clean_up(self):
        """Clean up temporary files"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)