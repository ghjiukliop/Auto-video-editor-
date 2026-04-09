import asyncio
import logging
import time
from pathlib import Path
from typing import List

import edge_tts
from pydub import AudioSegment

from utils.audio_utils import SRTSegment, parse_srt

logger = logging.getLogger("video_pipeline")

# Danh sách giọng đọc ổn định nhất cho tiếng Việt
FALLBACK_VOICES = ("vi-VN-HoaiMyNeural")

async def _generate_tts_chunk(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    output_path: Path,
) -> None:
    # Thêm dòng log để kiểm tra văn bản đang được gửi đi
    logger.debug(f"Đang gửi văn bản tới Microsoft: {text[:50]}...")
    communicator = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await asyncio.wait_for(communicator.save(str(output_path)), timeout=30) # Tăng timeout lên 30s

def _render_chunk_sync(text: str, voice: str, rate: str, pitch: str, output_path: Path) -> None:
    last_exc: Exception | None = None
    candidate_voices = [voice] + [v for v in FALLBACK_VOICES if v != voice]
    
    for candidate_voice in candidate_voices:
        # SỬA LỖI: Thay đổi range(1, 2) thành range(3) để thực sự có 3 lần thử lại
        for attempt in range(1, 4): 
            try:
                asyncio.run(
                    _generate_tts_chunk(
                        text, voice=candidate_voice, rate=rate, pitch=pitch, output_path=output_path
                    )
                )
                # Kiểm tra nếu file được tạo ra nhưng dung lượng bằng 0
                if not output_path.exists() or output_path.stat().st_size == 0:
                    raise ValueError("File âm thanh nhận về trống rỗng (0 bytes)")
                
                return # Thành công thì thoát
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Thử lại lần %d cho giọng %s thất bại: %s",
                    attempt, candidate_voice, exc
                )
                time.sleep(2) # Nghỉ 2 giây trước khi thử lại để tránh bị server chặn
                
    if last_exc is not None:
        raise last_exc

def _normalize_chunk_duration(segment: AudioSegment, target_ms: int) -> AudioSegment:
    if len(segment) > target_ms:
        return segment[:target_ms]
    if len(segment) < target_ms:
        return segment + AudioSegment.silent(duration=target_ms - len(segment))
    return segment

def build_ai_voice_from_srt(
    srt_path: Path,
    output_voice_path: Path,
    temp_chunks_dir: Path,
    voice: str,
    rate: str,
    pitch: str,
) -> Path:
    srt_text = srt_path.read_text(encoding="utf-8")
    segments: List[SRTSegment] = parse_srt(srt_text)
    if not segments:
        raise ValueError(f"Không tìm thấy phụ đề trong {srt_path}")

    temp_chunks_dir.mkdir(parents=True, exist_ok=True)
    total_duration_ms = max(seg.end_ms for seg in segments)
    timeline = AudioSegment.silent(duration=total_duration_ms)

    for seg in segments:
        if not seg.text.strip():
            continue
            
        chunk_path = temp_chunks_dir / f"chunk_{seg.index:04d}.mp3"
        segment_duration = max(1, seg.end_ms - seg.start_ms)
        
        try:
            _render_chunk_sync(seg.text, voice=voice, rate=rate, pitch=pitch, output_path=chunk_path)
            chunk_audio = AudioSegment.from_file(chunk_path)
            logger.info(f"Đã xử lý xong chunk {seg.index}")
        except Exception as exc:
            # Nếu 1 chunk lỗi, ta dùng đoạn im lặng thay vì dừng cả chương trình
            logger.error("Lỗi chunk %s: %s. Dùng đoạn im lặng thay thế.", seg.index, exc)
            chunk_audio = AudioSegment.silent(duration=segment_duration)

        chunk_audio = _normalize_chunk_duration(chunk_audio, segment_duration)
        timeline = timeline.overlay(chunk_audio, position=seg.start_ms)

    output_voice_path.parent.mkdir(parents=True, exist_ok=True)
    timeline.export(output_voice_path, format="wav")
    return output_voice_path