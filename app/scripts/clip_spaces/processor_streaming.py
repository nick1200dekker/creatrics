import os
import json
import tempfile
import subprocess
import shutil
import requests
import m3u8
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import logging

logger = logging.getLogger(__name__)

class StreamingSpaceProcessor:
    """Alternative processor that downloads HLS segments in parallel"""
    
    def __init__(self, space_id, user_id, temp_dir, audio_path, status_callback=None):
        self.space_id = space_id
        self.user_id = user_id
        self.temp_dir = temp_dir
        self.audio_path = audio_path
        self.status_callback = status_callback
        self.segments_dir = os.path.join(temp_dir, 'segments')
        os.makedirs(self.segments_dir, exist_ok=True)
    
    def update_status(self, message, progress):
        """Update processing status"""
        if self.status_callback:
            self.status_callback(message, progress)
        logger.info(f"[{self.space_id}] {message} ({progress}%)")
    
    def download_audio_parallel(self, playlist_url, max_workers=10):
        """Download HLS audio using parallel segment downloads"""
        self.update_status("📥 Analyzing audio stream...", 20)
        start_time = time.time()
        
        try:
            # Load and parse the HLS playlist
            playlist = m3u8.load(playlist_url)
            segments = playlist.segments
            total_segments = len(segments)
            
            if total_segments == 0:
                raise Exception("No segments found in playlist")
            
            self.update_status(f"📥 Downloading {total_segments} audio segments...", 25)
            logger.info(f"[SPACES] Starting parallel download of {total_segments} segments with {max_workers} workers")
            
            # Download segments in parallel
            downloaded_segments = []
            failed_segments = []
            completed_count = 0
            
            def download_segment(idx, segment):
                """Download a single segment with retry"""
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # Build absolute URL for segment
                        if segment.uri.startswith('http'):
                            url = segment.uri
                        else:
                            # Relative URL - construct from playlist URL
                            base_url = '/'.join(playlist_url.split('/')[:-1])
                            url = f"{base_url}/{segment.uri}"
                        
                        filepath = os.path.join(self.segments_dir, f'segment_{idx:05d}.ts')
                        
                        # Download with timeout
                        response = requests.get(url, timeout=10, stream=True)
                        response.raise_for_status()
                        
                        # Write to file
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        
                        # Verify file was created and has content
                        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                            return idx, filepath, None
                        else:
                            raise Exception("Empty segment file")
                            
                    except Exception as e:
                        if attempt < max_retries - 1:
                            time.sleep(0.5 * (attempt + 1))  # Brief retry delay
                            continue
                        return idx, None, str(e)
                
                return idx, None, "Max retries exceeded"
            
            # Use ThreadPoolExecutor for parallel downloads
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all download tasks
                future_to_idx = {
                    executor.submit(download_segment, i, seg): i 
                    for i, seg in enumerate(segments)
                }
                
                # Process completed downloads
                for future in as_completed(future_to_idx):
                    idx, filepath, error = future.result()
                    completed_count += 1
                    
                    if filepath:
                        downloaded_segments.append((idx, filepath))
                    else:
                        failed_segments.append((idx, error))
                        logger.warning(f"Failed to download segment {idx}: {error}")
                    
                    # Update progress
                    progress = 25 + int((completed_count / total_segments) * 25)
                    self.update_status(
                        f"📥 Downloaded {len(downloaded_segments)}/{total_segments} segments", 
                        progress
                    )
                    
                    # Log progress every 10% or 100 segments
                    if completed_count % max(total_segments // 10, 100) == 0:
                        success_rate = len(downloaded_segments) / completed_count if completed_count > 0 else 0
                        logger.info(f"[SPACES] Progress: {completed_count}/{total_segments} segments "
                                  f"({len(downloaded_segments)} success, {len(failed_segments)} failed, "
                                  f"{success_rate*100:.1f}% success rate)")
            
            # Check if we have enough segments (allow up to 5% failure)
            success_rate = len(downloaded_segments) / total_segments
            if success_rate < 0.95:
                raise Exception(
                    f"Too many failed segments: {len(failed_segments)}/{total_segments} "
                    f"({(1-success_rate)*100:.1f}% failure rate)"
                )
            
            # Sort segments by index for proper ordering
            downloaded_segments.sort(key=lambda x: x[0])
            
            # Create concat file for ffmpeg
            self.update_status("🔄 Assembling audio file...", 55)
            
            concat_file = os.path.join(self.segments_dir, 'concat.txt')
            with open(concat_file, 'w') as f:
                for _, filepath in downloaded_segments:
                    # Use relative path to avoid issues with special characters
                    rel_path = os.path.basename(filepath)
                    f.write(f"file '{rel_path}'\n")
            
            # Use ffmpeg to concatenate and convert to MP3
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-acodec', 'libmp3lame',
                '-ab', '128k',
                '-ar', '44100',
                '-ac', '2',
                '-y',
                self.audio_path
            ]
            
            # Change to segments directory for relative paths
            original_cwd = os.getcwd()
            try:
                os.chdir(self.segments_dir)
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            finally:
                os.chdir(original_cwd)
            
            if result.returncode != 0:
                raise Exception(f"Audio assembly failed: {result.stderr}")
            
            # Verify final audio file
            if not os.path.exists(self.audio_path) or os.path.getsize(self.audio_path) == 0:
                raise Exception("Failed to create audio file")
            
            # Clean up segments
            shutil.rmtree(self.segments_dir, ignore_errors=True)
            
            file_size = os.path.getsize(self.audio_path) / (1024 * 1024)
            total_time = time.time() - start_time
            segments_per_second = total_segments / total_time
            logger.info(f"[SPACES] Parallel download complete - Size: {file_size:.1f} MB, "
                       f"Time: {total_time:.1f}s, Segments: {len(downloaded_segments)}/{total_segments}, "
                       f"Speed: {segments_per_second:.1f} segments/sec")
            self.update_status(f"✅ Audio downloaded successfully ({file_size:.1f} MB)", 60)
            
            return self.audio_path
            
        except Exception as e:
            # Clean up on error
            if os.path.exists(self.segments_dir):
                shutil.rmtree(self.segments_dir, ignore_errors=True)
            raise Exception(f"Parallel download failed: {str(e)}")