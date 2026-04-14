#!/usr/bin/env python3
"""
Optimized SRT Parsing & Manipulation
====================================

Features:
- Fast SRT parsing with minimal memory overhead
- Efficient subtitle merging/splitting
- Timing-based subtitle grouping
- Format validation and repair
- Batch operations
"""

import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
from datetime import timedelta

logger = logging.getLogger("srt_parser_optimized")

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class SRTSubtitle:
    """Optimized subtitle representation."""
    index: int
    start_time: str      # HH:MM:SS,mmm format
    end_time: str        # HH:MM:SS,mmm format
    content: str
    
    def __str__(self) -> str:
        """Format as SRT subtitle block."""
        return f"{self.index}\n{self.start_time} --> {self.end_time}\n{self.content}\n"
    
    def start_ms(self) -> int:
        """Get start time in milliseconds."""
        return _srt_time_to_ms(self.start_time)
    
    def end_ms(self) -> int:
        """Get end time in milliseconds."""
        return _srt_time_to_ms(self.end_time)
    
    def update_timing(self, start_ms: int, end_ms: int) -> None:
        """Update timing in milliseconds."""
        self.start_time = _ms_to_srt_time(start_ms)
        self.end_time = _ms_to_srt_time(end_ms)


# ============================================================================
# TIME CONVERSION UTILITIES
# ============================================================================

def _srt_time_to_ms(time_str: str) -> int:
    """Convert SRT time format (HH:MM:SS,mmm) to milliseconds."""
    # Handle both ',' and '.' as decimal separator
    time_str = time_str.replace('.', ',')
    
    match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str)
    if not match:
        raise ValueError(f"Invalid SRT time format: {time_str}")
    
    h, m, s, ms = map(int, match.groups())
    return h * 3_600_000 + m * 60_000 + s * 1_000 + ms


def _ms_to_srt_time(ms: int) -> str:
    """Convert milliseconds to SRT time format (HH:MM:SS,mmm)."""
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1_000
    ms = ms % 1_000
    
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ============================================================================
# FAST SRT PARSER
# ============================================================================

class OptimizedSRTParser:
    """Fast and memory-efficient SRT parser."""
    
    # Pattern to match SRT blocks
    SRT_BLOCK_PATTERN = re.compile(
        r'(\d+)\s*\n'
        r'([\d:,. ]+)\s*-->\s*([\d:,. ]+)\s*\n'
        r'((?:[^\n]|\n(?!\n))*)',
        re.MULTILINE
    )
    
    @staticmethod
    def parse_file(srt_path: Path) -> List[SRTSubtitle]:
        """Parse SRT file efficiently."""
        if not srt_path.exists():
            raise FileNotFoundError(f"SRT file not found: {srt_path}")
        
        with open(srt_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        
        return OptimizedSRTParser.parse_content(content)
    
    @staticmethod
    def parse_content(content: str) -> List[SRTSubtitle]:
        """Parse SRT content from string."""
        subtitles = []
        
        for match in OptimizedSRTParser.SRT_BLOCK_PATTERN.finditer(content):
            try:
                index = int(match.group(1))
                start_time = match.group(2).strip()
                end_time = match.group(3).strip()
                content_text = match.group(4).strip()
                
                # Normalize time format
                start_time = OptimizedSRTParser._normalize_time(start_time)
                end_time = OptimizedSRTParser._normalize_time(end_time)
                
                if content_text and start_time and end_time:
                    subtitles.append(SRTSubtitle(
                        index=index,
                        start_time=start_time,
                        end_time=end_time,
                        content=content_text
                    ))
            
            except (ValueError, AttributeError) as e:
                logger.warning(f"Skipped malformed subtitle: {e}")
                continue
        
        logger.info(f"✅ Parsed {len(subtitles)} subtitles")
        return subtitles
    
    @staticmethod
    def _normalize_time(time_str: str) -> str:
        """Normalize time to HH:MM:SS,mmm format."""
        # Replace '.' with ',' for decimal separator
        time_str = time_str.replace('.', ',').strip()
        
        # Verify format matches HH:MM:SS,mmm
        if re.match(r'^\d{2}:\d{2}:\d{2},\d{3}$', time_str):
            return time_str
        
        raise ValueError(f"Invalid time format: {time_str}")


# ============================================================================
# SRT WRITER
# ============================================================================

class OptimizedSRTWriter:
    """Efficient SRT file writer."""
    
    @staticmethod
    def write_file(
        subtitles: List[SRTSubtitle],
        output_path: Path,
        reindex: bool = True
    ) -> None:
        """Write subtitles to SRT file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for idx, sub in enumerate(subtitles, start=1 if reindex else 0):
                if reindex:
                    sub.index = idx
                f.write(str(sub) + "\n")
        
        logger.info(f"💾 Wrote {len(subtitles)} subtitles to {output_path.name}")
    
    @staticmethod
    def to_content(
        subtitles: List[SRTSubtitle],
        reindex: bool = True
    ) -> str:
        """Convert subtitles to SRT content string."""
        lines = []
        
        for idx, sub in enumerate(subtitles, start=1 if reindex else 0):
            if reindex:
                sub.index = idx
            lines.append(str(sub))
        
        return "".join(lines).rstrip() + "\n"


# ============================================================================
# SRT MANIPULATION UTILITIES
# ============================================================================

class SRTManipulator:
    """Utilities for manipulating SRT files."""
    
    @staticmethod
    def merge_subtitles(
        sub_lists: List[List[SRTSubtitle]],
        time_offset_ms: List[int] = None
    ) -> List[SRTSubtitle]:
        """
        Merge multiple SRT files, adjusting timing.
        
        Args:
            sub_lists: List of subtitle lists
            time_offset_ms: Time offset for each list (in milliseconds)
        
        Returns:
            merged and re-indexed subtitles
        """
        if time_offset_ms is None:
            time_offset_ms = [0] * len(sub_lists)
        
        merged = []
        idx = 1
        
        for sub_list, offset in zip(sub_lists, time_offset_ms):
            for sub in sub_list:
                new_sub = SRTSubtitle(
                    index=idx,
                    start_time=_ms_to_srt_time(sub.start_ms() + offset),
                    end_time=_ms_to_srt_time(sub.end_ms() + offset),
                    content=sub.content
                )
                merged.append(new_sub)
                idx += 1
        
        return merged
    
    @staticmethod
    def split_by_time(
        subtitles: List[SRTSubtitle],
        split_time_ms: int
    ) -> Tuple[List[SRTSubtitle], List[SRTSubtitle]]:
        """Split subtitles at specific time."""
        before = []
        after = []
        
        for sub in subtitles:
            if sub.end_ms() <= split_time_ms:
                before.append(sub)
            elif sub.start_ms() >= split_time_ms:
                after.append(sub)
            else:
                # Subtitle spans the split point - need to split it
                before_sub = SRTSubtitle(
                    index=sub.index,
                    start_time=sub.start_time,
                    end_time=_ms_to_srt_time(split_time_ms),
                    content=sub.content
                )
                before.append(before_sub)
                
                after_sub = SRTSubtitle(
                    index=sub.index,
                    start_time=_ms_to_srt_time(split_time_ms),
                    end_time=sub.end_time,
                    content=sub.content
                )
                after.append(after_sub)
        
        return before, after
    
    @staticmethod
    def fix_overlaps(
        subtitles: List[SRTSubtitle],
        gap_ms: int = 100
    ) -> List[SRTSubtitle]:
        """Fix overlapping subtitles by adjusting timing."""
        if not subtitles:
            return subtitles
        
        fixed = [subtitles[0]]
        
        for i in range(1, len(subtitles)):
            current = subtitles[i]
            previous = fixed[-1]
            
            if current.start_ms() < previous.end_ms():
                # Overlap detected
                prev_end = previous.end_ms()
                current.update_timing(
                    start_ms=prev_end + gap_ms,
                    end_ms=max(prev_end + gap_ms + 1000, current.end_ms())
                )
                logger.debug(
                    f"Fixed overlap: subtitle {current.index} "
                    f"({_ms_to_srt_time(current.start_ms())})"
                )
            
            fixed.append(current)
        
        return fixed
    
    @staticmethod
    def filter_by_duration(
        subtitles: List[SRTSubtitle],
        min_duration_ms: int = 100,
        max_duration_ms: int = 20000
    ) -> List[SRTSubtitle]:
        """Filter subtitles by duration."""
        filtered = []
        
        for sub in subtitles:
            duration = sub.end_ms() - sub.start_ms()
            if min_duration_ms <= duration <= max_duration_ms:
                filtered.append(sub)
            else:
                logger.debug(
                    f"Filtered subtitle {sub.index}: "
                    f"duration {duration}ms outside range"
                )
        
        return filtered


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def load_srt(path: Path) -> List[SRTSubtitle]:
    """Load SRT file (convenience function)."""
    return OptimizedSRTParser.parse_file(path)


def save_srt(subtitles: List[SRTSubtitle], path: Path) -> None:
    """Save SRT file (convenience function)."""
    OptimizedSRTWriter.write_file(subtitles, path)
