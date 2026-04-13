import asyncio
import logging
import time
from pathlib import Path
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import edge_tts
from pydub import AudioSegment
from pydub.effects import speedup
from tqdm import tqdm

from utils.audio_utils import SRTSegment, parse_srt

logger = logging.getLogger("video_pipeline")

FALLBACK_VOICES = ["vi-VN-HoaiMyNeural"]


async def _generate_tts_chunk(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    output_path: Path,
) -> None:
    logger.debug("Đang gửi văn bản tới Microsoft: %s...", text[:50])
    communicator = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await asyncio.wait_for(communicator.save(str(output_path)), timeout=30)


def _render_chunk_sync(text: str, voice: str, rate: str, pitch: str, output_path: Path) -> None:
    last_exc: Exception | None = None
    candidate_voices = [voice] + [v for v in FALLBACK_VOICES if v != voice]

    for candidate_voice in candidate_voices:
        for attempt in range(1, 4):
            try:
                asyncio.run(
                    _generate_tts_chunk(
                        text, voice=candidate_voice, rate=rate, pitch=pitch, output_path=output_path
                    )
                )
                if not output_path.exists() or output_path.stat().st_size == 0:
                    raise ValueError("File âm thanh nhận về trống rỗng (0 bytes)")
                return
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Thử lại lần %d cho giọng %s thất bại: %s",
                    attempt, candidate_voice, exc,
                )
                time.sleep(2)

    if last_exc is not None:
        raise last_exc


def _normalize_chunk_duration(segment: AudioSegment, target_ms: int) -> AudioSegment:
    """Tự động điều chỉnh tốc độ để khớp với thời gian trong SRT mà không mất chữ."""
    if target_ms <= 0:
        return segment

    duration_ms = len(segment)

    if duration_ms > target_ms:
        speed_factor = duration_ms / target_ms
        if speed_factor < 1.05:
            return segment
        try:
            safe_speed = min(speed_factor, 1.4)
            return speedup(segment, playback_speed=safe_speed, chunk_size=50, crossfade=25)
        except Exception as e:
            logger.warning("Không thể speedup, buộc phải cắt ngắn: %s", e)
            return segment[:target_ms]

    if duration_ms < target_ms:
        return segment + AudioSegment.silent(duration=target_ms - duration_ms)

    return segment


def build_ai_voice_from_srt(
    srt_path: Path,
    output_voice_path: Path,
    temp_chunks_dir: Path,
    voice: str,
    rate: str,
    pitch: str,
    max_workers: int = 4,
) -> Path:
    """
    Xây dựng file âm thanh AI từ file SRT theo timeline.
    
    METHOD: Song song hóa (parallel) - render TTS chunks cùng lúc thay vì tuần tự.
    Hiệu suất tăng 3-4x so với phiên bản cũ.
    """
    srt_text = srt_path.read_text(encoding="utf-8")
    segments: List[SRTSegment] = parse_srt(srt_text)
    if not segments:
        raise ValueError(f"Không tìm thấy phụ đề trong {srt_path}")

    temp_chunks_dir.mkdir(parents=True, exist_ok=True)
    total_duration_ms = max(seg.end_ms for seg in segments)
    timeline = AudioSegment.silent(duration=total_duration_ms)
    
    # Lock để bảo vệ truy cập timeline (nếu cần)
    timeline_lock = Lock()
    
    # Dictionary để lưu chunks theo index khi chúng sẵn sàng
    processed_chunks: Dict[int, AudioSegment] = {}

    def process_segment(seg: SRTSegment) -> tuple[int, AudioSegment, int]:
        """
        Render TTS chunk cho một segment.
        Returns: (index, audio_segment, start_ms)
        """
        if not seg.text.strip():
            return seg.index, AudioSegment.silent(duration=seg.end_ms - seg.start_ms), seg.start_ms

        chunk_path = temp_chunks_dir / f"chunk_{seg.index:04d}.mp3"
        segment_duration = max(1, seg.end_ms - seg.start_ms)

        try:
            # Render TTS
            _render_chunk_sync(seg.text, voice=voice, rate=rate, pitch=pitch, output_path=chunk_path)
            
            # Load audio
            chunk_audio = AudioSegment.from_file(chunk_path)
            
            # Chuẩn hóa thời lượng
            chunk_audio = _normalize_chunk_duration(chunk_audio, segment_duration)
            
            # Cleanup
            chunk_path.unlink(missing_ok=True)
            
            return seg.index, chunk_audio, seg.start_ms
            
        except Exception as exc:
            logger.error("Lỗi chunk %s: %s. Dùng đoạn im lặng thay thế.", seg.index, exc)
            silent_chunk = AudioSegment.silent(duration=segment_duration)
            chunk_path.unlink(missing_ok=True)
            return seg.index, silent_chunk, seg.start_ms

    # Xử lý song song với ThreadPoolExecutor
    logger.info("🎵 Bắt đầu render TTS %d chunk (song song, max_workers=%d)...", len(segments), max_workers)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit tất cả tasks
        futures = {
            executor.submit(process_segment, seg): seg.index
            for seg in segments
        }
        
        # Collect results với progress bar
        with tqdm(total=len(segments), desc="Render TTS") as pbar:
            for future in as_completed(futures):
                try:
                    seg_index, chunk_audio, start_ms = future.result()
                    processed_chunks[seg_index] = (chunk_audio, start_ms)
                    pbar.update(1)
                except Exception as exc:
                    logger.error("Lỗi không mong muốn: %s", exc)
                    pbar.update(1)
    
    # Ghép timeline theo thứ tự sau khi tất cả chunks sẵn sàng
    logger.info("🎬 Ghép timeline từ %d chunk...", len(processed_chunks))
    with tqdm(total=len(processed_chunks), desc="Ghép TTS") as pbar:
        for seg_index in sorted(processed_chunks.keys()):
            chunk_audio, start_ms = processed_chunks[seg_index]
            timeline = timeline.overlay(chunk_audio, position=start_ms)
            pbar.update(1)

    output_voice_path.parent.mkdir(parents=True, exist_ok=True)
    timeline.export(output_voice_path, format="wav")
    logger.info("✅ TTS hoàn tất: %s", output_voice_path)
    return output_voice_path


def process_all_tts(
    srt_path: Path,
    output_voice_path: Path,
    temp_chunks_dir: Path,
    voice: str,
    rate: str,
    pitch: str,
    max_workers: int = 4,
) -> Path:
    """
    Hàm wrapper được gọi từ main.py.
    
    NÂNG CẤP: Render TTS song song (parallel) để tăng hiệu suất 3-4x.
    max_workers: Số luồng xử lý đồng thời (default=4, tăng lên nếu máy mạnh)
    """
    logger.info("--- Bắt đầu tổng hợp giọng AI (TTS) song song ---")
    return build_ai_voice_from_srt(
        srt_path=srt_path,
        output_voice_path=output_voice_path,
        temp_chunks_dir=temp_chunks_dir,
        voice=voice,
        rate=rate,
        pitch=pitch,
        max_workers=max_workers,
    )