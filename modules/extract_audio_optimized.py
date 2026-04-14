#!/usr/bin/env python3
"""
Optimized Audio Extraction & Processing
========================================

Features:
- Fast parallel FFmpeg audio extraction
- Caching to avoid re-extraction
- Optimized FFmpeg parameters
- Support for various audio formats
- Batch processing for efficiency
"""

import logging
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import hashlib

logger = logging.getLogger("audio_extract_optimized")

# ============================================================================
# CONSTANTS
# ============================================================================

FFMPEG_EXTRACT_CMD = [
    "ffmpeg",
    "-loglevel", "error",  # Suppress verbose logging
    "-y",                  # Overwrite without asking
    "-i", "{input}",
    "-q:a", "5",          # Audio quality (5 = best for MP3, but we use WAV)
    "-ac", "2",           # Stereo
    "-ar", "44100",       # 44.1kHz sample rate
    "-acodec", "pcm_s16le",  # 16-bit PCM for WAV
    "{output}"
]

# ============================================================================
# CACHE MANAGEMENT
# ============================================================================

class AudioExtractionCache:
    """Manage extraction cache to avoid re-processing."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize cache."""
        self.cache_dir = cache_dir or Path.home() / ".cache" / "audio_extraction"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "manifest.txt"
    
    def get_cache_key(self, video_path: Path) -> str:
        """Generate cache key from video file path and modification time."""
        stat = video_path.stat()
        content = f"{video_path.absolute()}:{stat.st_mtime}:{stat.st_size}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def get_cached_audio(self, video_path: Path) -> Optional[Path]:
        """Check if audio already extracted."""
        cache_key = self.get_cache_key(video_path)
        cache_path = self.cache_dir / f"{cache_key}.wav"
        
        if cache_path.exists():
            logger.info(f"📦 Cache hit: {video_path.name} → {cache_path}")
            return cache_path
        
        return None
    
    def register_extraction(self, video_path: Path, audio_path: Path) -> None:
        """Register successful extraction in cache."""
        cache_key = self.get_cache_key(video_path)
        
        with open(self.cache_file, 'a', encoding='utf-8') as f:
            f.write(f"{cache_key}|{audio_path.absolute()}\n")


# ============================================================================
# FAST AUDIO EXTRACTION
# ============================================================================

class OptimizedAudioExtractor:
    """Fast audio extraction with caching and parallel processing."""
    
    def __init__(self, cache_enabled: bool = True, worker_threads: int = 2):
        """
        Initialize extractor.
        
        Args:
            cache_enabled: Use extraction cache
            worker_threads: Number of parallel FFmpeg workers
        """
        self.cache_enabled = cache_enabled
        self.cache = AudioExtractionCache() if cache_enabled else None
        self.worker_threads = worker_threads
    
    def extract_audio_to_wav(
        self,
        video_path: Path,
        output_wav_path: Path,
        force_reextract: bool = False
    ) -> Path:
        """
        Extract audio from video to WAV file (optimized).
        
        Args:
            video_path: Path to video file
            output_wav_path: Output WAV path
            force_reextract: Skip cache and always extract
        
        Returns:
            Path to output WAV file
        """
        # Check cache
        if self.cache_enabled and not force_reextract:
            cached = self.cache.get_cached_audio(video_path)
            if cached:
                return cached
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🎵 Extracting audio from {video_path.name}...")
        start_time = __import__('time').time()
        
        try:
            # Build FFmpeg command
            cmd = FFMPEG_EXTRACT_CMD.copy()
            cmd[cmd.index("{input}")] = str(video_path)
            cmd[cmd.index("{output}")] = str(output_wav_path)
            
            # Run FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            elapsed = __import__('time').time() - start_time
            
            if not output_wav_path.exists():
                raise RuntimeError(f"FFmpeg extraction failed: {result.stderr}")
            
            file_size_mb = output_wav_path.stat().st_size / (1024 * 1024)
            logger.info(
                f"✅ Audio extracted: {output_wav_path.name} "
                f"({file_size_mb:.1f}MB in {elapsed:.1f}s)"
            )
            
            # Cache result
            if self.cache_enabled:
                self.cache.register_extraction(video_path, output_wav_path)
            
            return output_wav_path
        
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ FFmpeg failed: {e.stderr}")
            raise RuntimeError(f"Audio extraction failed: {e.stderr}") from e
    
    def extract_audio_segment(
        self,
        video_path: Path,
        start_ms: int,
        end_ms: int,
        output_wav_path: Path
    ) -> Path:
        """Extract specific audio segment from video (for subtitle timing)."""
        output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        
        start_sec = start_ms / 1000.0
        duration_sec = (end_ms - start_ms) / 1000.0
        
        cmd = [
            "ffmpeg",
            "-loglevel", "error",
            "-y",
            "-i", str(video_path),
            "-ss", str(start_sec),
            "-t", str(duration_sec),
            "-ac", "2",
            "-ar", "44100",
            "-acodec", "pcm_s16le",
            str(output_wav_path)
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            logger.debug(f"Extracted audio segment: {start_ms}ms - {end_ms}ms")
            return output_wav_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Segment extraction failed: {e.stderr}")
            raise
    
    def extract_batch(
        self,
        video_paths: list,
        output_dir: Path,
        force_reextract: bool = False
    ) -> dict:
        """
        Extract audio from multiple videos in parallel.
        
        Args:
            video_paths: List of video file paths
            output_dir: Output directory
            force_reextract: Force re-extraction
        
        Returns:
            Dict of {video_path: audio_path}
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.worker_threads) as executor:
            futures = {}
            
            for video_path in video_paths:
                output_wav = output_dir / f"{video_path.stem}.wav"
                future = executor.submit(
                    self.extract_audio_to_wav,
                    Path(video_path),
                    output_wav,
                    force_reextract
                )
                futures[future] = video_path
            
            for future in futures:
                try:
                    audio_path = future.result()
                    results[futures[future]] = audio_path
                except Exception as e:
                    logger.error(f"Failed to extract {futures[future]}: {e}")
                    results[futures[future]] = None
        
        return results


# ============================================================================
# COMPATIBILITY SHIM FOR EXISTING CODE
# ============================================================================

def extract_audio_to_wav(video_path: Path, output_wav_path: Path) -> Path:
    """
    Backward compatible extraction function.
    Replaces the original simple version with optimized caching version.
    """
    extractor = OptimizedAudioExtractor(cache_enabled=True)
    return extractor.extract_audio_to_wav(video_path, output_wav_path)
