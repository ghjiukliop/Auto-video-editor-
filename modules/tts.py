import asyncio
import logging
import re
from pathlib import Path
import edge_tts
from pydub import AudioSegment
from utils.audio_utils import parse_srt
from tqdm.asyncio import tqdm

logger = logging.getLogger("video_pipeline")
SEMAPHORE = asyncio.Semaphore(10)

def clean_text_for_tts(text: str) -> str:
    """Lọc bỏ ký tự lạ để tránh lỗi API"""
    text = re.sub(r'[\u4e00-\u9fff]+', '', text) # Xóa tiếng Trung nếu còn sót
    return text.strip()

async def _download_chunk_with_retry(text, voice, rate, pitch, output_path, max_retries=3):
    """Cơ chế kiểm tra lỗi và chạy lại để hoàn thiện audio"""
    safe_text = clean_text_for_tts(text)
    if not safe_text: return False

    async with SEMAPHORE:
        for attempt in range(max_retries):
            try:
                communicate = edge_tts.Communicate(text=safe_text, voice=voice, rate=rate, pitch=pitch)
                await communicate.save(str(output_path))
                
                # KIỂM TRA CHẤT LƯỢNG FILE SAU KHI TẢI
                if output_path.exists():
                    audio = AudioSegment.from_file(output_path)
                    # Nếu file < 100ms mà text dài (> 5 chữ) -> Chắc chắn lỗi tải thiếu
                    if len(audio) < 100 and len(safe_text.split()) > 5:
                        raise ValueError("Audio quá ngắn, có thể bị lỗi stream")
                    return True # Thành công
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"❌ Thất bại vĩnh viễn chunk {output_path.name}: {e}")
                else:
                    logger.warning(f"🔄 Đang thử lại chunk {output_path.name} (Lần {attempt+1})...")
                    await asyncio.sleep(2)
        return False

def _adjust_audio_to_fit(audio: AudioSegment, target_ms: int) -> AudioSegment:
    """Xử lý để đọc hết chữ, không bị nhảy qua câu khác quá nhanh"""
    current_ms = len(audio)
    if current_ms <= target_ms:
        # Nếu audio ngắn hơn thời gian quy định, bù thêm khoảng lặng (silent)
        return audio + AudioSegment.silent(duration=target_ms - current_ms)
    
    # Nếu audio dài hơn thời gian quy định (nguyên nhân gây mất tiếng)
    ratio = current_ms / target_ms
    if ratio < 1.2: # Nếu chỉ dài hơn một chút, cho phép nó lấn sang câu sau
        return audio
    else:
        # Nếu dài quá nhiều, tăng tốc độ nhẹ (tối đa 1.3x) để kịp thời gian
        # KHÔNG dùng clip[:target_ms] vì sẽ làm mất chữ cuối
        speed = min(ratio, 1.3)
        try:
            return audio.speedup(playback_speed=speed, chunk_size=50, crossfade=25)
        except:
            return audio # Nếu lỗi speedup, giữ nguyên để đọc hết chữ

async def _batch_process(segments, voice, rate, pitch, temp_dir):
    tasks = []
    for seg in segments:
        path = temp_dir / f"chunk_{seg.index:04d}.mp3"
        tasks.append(_download_chunk_with_retry(seg.text, voice, rate, pitch, path))
    await tqdm.gather(*tasks, desc="🚀 Đang tải và kiểm tra audio")

def process_all_tts(srt_path: Path, output_voice_path: Path, temp_chunks_dir: Path, voice: str, rate: str, pitch: str):
    """Hàm chính để main.py gọi"""
    srt_text = srt_path.read_text(encoding="utf-8")
    segments = parse_srt(srt_text)
    temp_chunks_dir.mkdir(parents=True, exist_ok=True)

    # Bước 1: Tải và tự động Retry nếu lỗi
    asyncio.run(_batch_process(segments, voice, rate, pitch, temp_chunks_dir))

    # Bước 2: Ghép audio thông minh
    total_duration = max(seg.end_ms for seg in segments)
    combined = AudioSegment.silent(duration=total_duration)

    for seg in tqdm(segments, desc="📦 Ghép audio không mất chữ"):
        path = temp_chunks_dir / f"chunk_{seg.index:04d}.mp3"
        if path.exists() and path.stat().st_size > 0:
            audio = AudioSegment.from_file(path)
            target_dur = seg.end_ms - seg.start_ms
            
            # ĐIỀU CHỈNH AUDIO: Đảm bảo đọc hết, lấn sân nhẹ nếu cần
            audio = _adjust_audio_to_fit(audio, target_dur)
            combined = combined.overlay(audio, position=seg.start_ms)

    combined.export(output_voice_path, format="wav")
    return output_voice_path

# Giữ alias cho main.py
build_ai_voice_from_srt = process_all_tts