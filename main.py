#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MAIN PIPELINE: Toàn bộ quy trình tự động từ video đầu vào
========================================================
1. Tìm video trong input/VideoInput
2. Tách audio → input/AudioInput
3. Tạo SRT (Whisper) → input/SrtInput
4. Dịch SRT → output/SrtOutput
5. Compose video → output_videos

✨ SMART FEATURES:
- Quét toàn bộ project để xem đã làm được tới bước nào
- Tiếp tục từ bước tiếp theo (không làm lại từ đầu)
- Hiển thị status chi tiết của từng video
- Real-time progress tracking (STEP 1-4)
- Auto-resume + auto-continue đến hoàn tất
"""
import sys
import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import subprocess
import logging
from dataclasses import dataclass
from enum import Enum
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============ SETUP ĐƯỜNG DẪN ============
PROJECT_ROOT = Path(__file__).parent.absolute()
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

INPUT_VIDEO_DIR = PROJECT_ROOT / "input" / "VideoInput"
INPUT_AUDIO_DIR = PROJECT_ROOT / "input" / "AudioInput"
INPUT_SRT_DIR = PROJECT_ROOT / "input" / "SrtInput"
OUTPUT_SRT_DIR = PROJECT_ROOT / "output" / "SrtOutput"
OUTPUT_AUDIO_DIR = PROJECT_ROOT / "output" / "AudioOutput"
OUTPUT_VIDEO_DIR = PROJECT_ROOT / "output_videos"
TEMP_DIR = PROJECT_ROOT / "temp"

# Tạo các thư mục
for dir_path in [INPUT_VIDEO_DIR, INPUT_AUDIO_DIR, INPUT_SRT_DIR, OUTPUT_SRT_DIR, OUTPUT_AUDIO_DIR, OUTPUT_VIDEO_DIR, TEMP_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ============ IMPORT CÁC MODULE ============
try:
    from modules.extract_audio_optimized import extract_audio_to_wav
    from modules.speech_to_text import transcribe_to_srt, translate_full_text
    from modules.translator import translate_srt_2pass
    from utils.audio_utils import parse_srt, SRTSegment, ms_to_srt_time
except ImportError as e:
    logger.error(f"❌ Lỗi import module: {e}")
    sys.exit(1)

# ============ ĐỊNH NGHĨA ENUM ============
class ProcessStep(Enum):
    """Các bước xử lý"""
    AUDIO_EXTRACT = 1
    SRT_CREATE = 2
    SRT_TRANSLATE = 3
    VIDEO_COMPOSE = 4
    COMPLETED = 5

@dataclass
class VideoStatus:
    """Status của một video"""
    video_path: Path
    video_name: str
    next_step: ProcessStep
    audio_path: Optional[Path] = None
    srt_path: Optional[Path] = None
    translated_srt_path: Optional[Path] = None
    final_video_path: Optional[Path] = None
    
    def __str__(self):
        """Display status"""
        if self.next_step == ProcessStep.AUDIO_EXTRACT:
            return f"⏳ [BƯỚC 1] Cần tách audio"
        elif self.next_step == ProcessStep.SRT_CREATE:
            return f"⏳ [BƯỚC 2] Cần tạo SRT (Whisper)"
        elif self.next_step == ProcessStep.SRT_TRANSLATE:
            return f"⏳ [BƯỚC 3] Cần dịch SRT"
        elif self.next_step == ProcessStep.VIDEO_COMPOSE:
            return f"⏳ [BƯỚC 4] Cần compose video"
        else:
            return f"✅ [HOÀN TẤT] Tất cả bước đã xong"

# ============ PROGRESS TRACKING ============
def get_step_4_progress(video_name: str) -> Tuple[int, int]:
    """
    Check progress của STEP 4 (Video Compose)
    
    Return: (progress_percent, status_string)
    """
    # Kiểm tra final video
    final_video = OUTPUT_VIDEO_DIR / f"{video_name}_final.mp4"
    
    if final_video.exists():
        size_mb = final_video.stat().st_size / (1024*1024)
        if size_mb > 1:
            return 100, "✅ Hoàn tất"
        else:
            return 50, f"⏳ Đang tạo ({size_mb:.1f}MB)"
    
    # Kiểm tra intermediate files
    audio_output = OUTPUT_AUDIO_DIR / video_name / "final_merged.wav"
    if audio_output.exists():
        return 50, "⏳ Đang compose"
    
    return 0, "⏳ Chờ"


def detect_pipeline_progress(video_status: VideoStatus) -> Dict[str, str]:
    """
    ✨ DETECTOR: Xác định chính xác pipeline đã chạy tới đâu.
    
    Return: {
        "step": "SRT_CREATE" or "SRT_TRANSLATE" or ...,
        "status": "✅ DONE" or "⏳ IN_PROGRESS" or "❌ FAILED"
        "detail": "Chi tiết thêm"
    }
    """
    video_name = video_status.video_name
    
    result = {
        "STEP_1_AUDIO": {"status": "❌ TODO", "detail": ""},
        "STEP_2_WHISPER": {"status": "❌ TODO", "detail": ""},
        "STEP_3_TRANSLATE": {"status": "❌ TODO", "detail": ""},
        "STEP_4_COMPOSE": {"status": "❌ TODO", "detail": ""},
    }
    
    # STEP 1: Audio Extract
    audio_path = INPUT_AUDIO_DIR / f"{video_name}.wav"
    if audio_path.exists() and audio_path.stat().st_size > 100:
        result["STEP_1_AUDIO"]["status"] = "✅ DONE"
        result["STEP_1_AUDIO"]["detail"] = f"{audio_path.stat().st_size / (1024*1024):.1f}MB"
    else:
        result["STEP_1_AUDIO"]["status"] = "⏳ PENDING"
    
    # STEP 2: Whisper
    srt_path = INPUT_SRT_DIR / f"{video_name}.srt"
    if srt_path.exists() and srt_path.stat().st_size > 100:
        result["STEP_2_WHISPER"]["status"] = "✅ DONE"
        # Đếm segments
        with open(srt_path, encoding='utf-8') as f:
            segments = len([l for l in f.readlines() if l.strip() and l[0].isdigit()])
        result["STEP_2_WHISPER"]["detail"] = f"{segments} segments"
    elif audio_path.exists():
        result["STEP_2_WHISPER"]["status"] = "⏳ PENDING"
    
    # STEP 3: Translate
    translated_path = OUTPUT_SRT_DIR / f"{video_name}_translated.srt"
    if translated_path.exists() and translated_path.stat().st_size > 100:
        result["STEP_3_TRANSLATE"]["status"] = "✅ DONE"
        with open(translated_path, encoding='utf-8') as f:
            segments = len([l for l in f.readlines() if l.strip() and l[0].isdigit()])
        result["STEP_3_TRANSLATE"]["detail"] = f"{segments} segments (VN)"
    elif srt_path.exists():
        result["STEP_3_TRANSLATE"]["status"] = "⏳ PENDING"
    
    # STEP 4: Compose
    final_video = OUTPUT_VIDEO_DIR / f"{video_name}_final.mp4"
    if final_video.exists() and final_video.stat().st_size > 1000000:
        result["STEP_4_COMPOSE"]["status"] = "✅ DONE"
        result["STEP_4_COMPOSE"]["detail"] = f"{final_video.stat().st_size / (1024*1024):.1f}MB"
    elif translated_path.exists():
        result["STEP_4_COMPOSE"]["status"] = "⏳ PENDING"
    
    return result


def print_pipeline_status(video_name: str, progress: Dict[str, str]):
    """In status pipeline chi tiết"""
    print(f"\n🔄 Progress: {video_name}")
    print("─" * 70)
    
    for step, info in progress.items():
        status = info["status"]
        detail = info["detail"]
        step_display = step.replace("_", " ")
        
        if detail:
            print(f"   {status} {step_display}: {detail}")
        else:
            print(f"   {status} {step_display}")
    
    print("─" * 70)

    tts_dir = Path("output/AudioOutput") / video_name
    
    # Lấy số file cần tạo từ SRT
    srt_file = OUTPUT_SRT_DIR / f"{video_name}_translated.srt"
    if not srt_file.exists():
        return 0, 0
    
    try:
        with open(srt_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # Đếm số lần xuất hiện index dòng (format SRT: 1\n00:00:00,000)
            total = content.count('\n\n') + 1
    except:
        total = 0
    
    # Đếm số file WAV đã tạo
    if not tts_dir.exists():
        created = 0
    else:
        created = len([f for f in tts_dir.glob("*.wav") if not f.name.startswith("final_")])
    
    return created, total

def display_step_progress(video_name: str, video_status: VideoStatus):
    """
    ✨ IMPROVED: Hiển thị progress chi tiết của 4 bước pipeline
    
    Dùng improved detector để xác định chính xác progress
    """
    # Dùng detector để lấy chi tiết progress
    progress = detect_pipeline_progress(video_status)
    print_pipeline_status(video_name, progress)

def monitor_tts_progress(video_name: str, interval: int = 10):
    """
    Monitor TTS progress real-time
    Kiểm tra mỗi `interval` giây
    """
    print(f"\n⏱️  Monitoring TTS progress (checking every {interval}s)...")
    print("   Press Ctrl+C to continue to next step manually\n")
    
    last_count = 0
    start_time = time.time()
    
    try:
        while True:
            created, total = get_step_4_progress(video_name)
            
            if created > last_count:
                percent = int((created / total * 100)) if total > 0 else 0
                elapsed = int(time.time() - start_time)
                
                if created > 0:
                    rate = created / (elapsed + 1)  # files per second
                    remaining = (total - created) / (rate + 0.001) if rate > 0 else 0
                    print(f"   📊 TTS: {created}/{total} ({percent}%) | Rate: {rate:.1f} file/s | ETA: {int(remaining)}s")
                
                last_count = created
                
                # Check if done
                if created == total and total > 0:
                    print(f"   ✅ TTS complete! {total} files created")
                    break
            
            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\n   ⏩ Skipped to next step (current: {created}/{total} files)")
        pass

# ============ TÌM VIDEO ============
def find_videos() -> List[Path]:
    """Tìm tất cả video trong input/VideoInput"""
    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.m4v'}
    videos = []
    
    if not INPUT_VIDEO_DIR.exists():
        logger.error(f"❌ Thư mục không tồn tại: {INPUT_VIDEO_DIR}")
        return []
    
    for file in INPUT_VIDEO_DIR.iterdir():
        if file.suffix.lower() in VIDEO_EXTENSIONS and file.is_file():
            videos.append(file)
    
    return sorted(videos)

# ============ QUÉT STATUS ============
def scan_project_status(video_path: Path) -> VideoStatus:
    """
    ✨ IMPROVED DETECTOR: Quét project để xem video đã làm được tới bước nào.
    
    Kiểm tra file artifacts để xác định progress:
    - STEP 1: input/AudioInput/{video_name}.wav exists?
    - STEP 2: input/SrtInput/{video_name}.srt exists?
    - STEP 3: output/SrtOutput/{video_name}_translated.srt exists?
    - STEP 4: output_videos/{video_name}_final.mp4 exists?
    
    Trả về status + bước tiếp theo cần làm.
    """
    video_name = video_path.stem
    
    # Kiểm tra các file artifacts
    audio_path = INPUT_AUDIO_DIR / f"{video_name}.wav"
    srt_path = INPUT_SRT_DIR / f"{video_name}.srt"
    translated_srt_path = OUTPUT_SRT_DIR / f"{video_name}_translated.srt"
    final_video_path = OUTPUT_VIDEO_DIR / f"{video_name}_final.mp4"
    
    # Validate file sizes (không phải file empty)
    def file_is_valid(path, min_size=100):
        """Check if file exists và có kích thước > min_size"""
        return path.exists() and path.stat().st_size > min_size
    
    # Xác định bước tiếp theo
    if not file_is_valid(audio_path):
        next_step = ProcessStep.AUDIO_EXTRACT
        status_detail = "⏳ Cần tách audio"
    elif not file_is_valid(srt_path):
        next_step = ProcessStep.SRT_CREATE
        status_detail = "⏳ Cần tạo SRT (Whisper)"
    elif not file_is_valid(translated_srt_path):
        next_step = ProcessStep.SRT_TRANSLATE
        status_detail = "⏳ Cần dịch SRT"
    elif not file_is_valid(final_video_path, min_size=1000000):
        next_step = ProcessStep.VIDEO_COMPOSE
        status_detail = "⏳ Cần compose video"
    else:
        next_step = ProcessStep.COMPLETED
        status_detail = "✅ Hoàn tất"
    
    logger.debug(f"📊 {video_name}: {status_detail}")
    
    return VideoStatus(
        video_path=video_path,
        video_name=video_name,
        next_step=next_step,
        audio_path=audio_path if file_is_valid(audio_path) else None,
        srt_path=srt_path if file_is_valid(srt_path) else None,
        translated_srt_path=translated_srt_path if file_is_valid(translated_srt_path) else None,
        final_video_path=final_video_path if file_is_valid(final_video_path, min_size=1000000) else None,
    )


# ============ HIỂN THỊ STATUS ============
def print_project_overview(statuses: List[VideoStatus]):
    """Hiển thị tổng quan status của toàn bộ videos"""
    print(f"\n{'='*70}")
    print(f"📊 TỔNG QUAN PROJECT - {len(statuses)} VIDEO(S)")
    print(f"{'='*70}\n")
    
    step_counts = {
        ProcessStep.AUDIO_EXTRACT: 0,
        ProcessStep.SRT_CREATE: 0,
        ProcessStep.SRT_TRANSLATE: 0,
        ProcessStep.VIDEO_COMPOSE: 0,
        ProcessStep.COMPLETED: 0,
    }
    
    for status in statuses:
        step_counts[status.next_step] += 1
        
        # Icon + status
        if status.next_step == ProcessStep.COMPLETED:
            icon = "✅"
        elif status.next_step == ProcessStep.AUDIO_EXTRACT:
            icon = "⏳"
        elif status.next_step == ProcessStep.SRT_CREATE:
            icon = "⏳"
        elif status.next_step == ProcessStep.SRT_TRANSLATE:
            icon = "⏳"
        else:
            icon = "⏳"
        
        print(f"{icon} {status.video_name}")
        print(f"   {status}")
        
        # Chi tiết files hiện tại
        if status.audio_path:
            print(f"   ✓ Audio: {status.audio_path.name}")
        if status.srt_path:
            print(f"   ✓ SRT: {status.srt_path.name}")
        if status.translated_srt_path:
            print(f"   ✓ Translated: {status.translated_srt_path.name}")
        if status.final_video_path:
            print(f"   ✓ Final: {status.final_video_path.name}")
        print()
    
    # Tóm tắt
    print(f"{'─'*70}")
    print(f"📈 Tóm tắt:")
    print(f"   ✅ Hoàn tất: {step_counts[ProcessStep.COMPLETED]}")
    print(f"   ⏳ Chờ xử lý: {sum([step_counts[ProcessStep.AUDIO_EXTRACT], step_counts[ProcessStep.SRT_CREATE], step_counts[ProcessStep.SRT_TRANSLATE], step_counts[ProcessStep.VIDEO_COMPOSE]])}")
    if step_counts[ProcessStep.AUDIO_EXTRACT] > 0:
        print(f"      - Cần tách audio: {step_counts[ProcessStep.AUDIO_EXTRACT]}")
    if step_counts[ProcessStep.SRT_CREATE] > 0:
        print(f"      - Cần tạo SRT: {step_counts[ProcessStep.SRT_CREATE]}")
    if step_counts[ProcessStep.SRT_TRANSLATE] > 0:
        print(f"      - Cần dịch: {step_counts[ProcessStep.SRT_TRANSLATE]}")
    if step_counts[ProcessStep.VIDEO_COMPOSE] > 0:
        print(f"      - Cần compose: {step_counts[ProcessStep.VIDEO_COMPOSE]}")
    print(f"{'='*70}\n")

# ============ TÁCH AUDIO ============
def extract_audio(video_path: Path, audio_path: Path) -> bool:
    """Tách audio từ video"""
    logger.info(f"🔊 Tách audio từ video...")
    try:
        result = extract_audio_to_wav(video_path, audio_path)
        logger.info(f"✅ Tách audio xong: {audio_path.name}")
        return True
    except Exception as e:
        logger.error(f"❌ Lỗi tách audio: {e}")
        raise

# ============ TẠO SRT (WHISPER) ============
def create_srt(audio_path: Path, srt_output: Path) -> bool:
    """
    Tạo SRT từ audio bằng Whisper.
    
    ✨ NEW: Hỗ trợ Segment Mode
    - Nếu SRT input có sẵn ở INPUT_SRT_DIR, sẽ dùng segment mode
    - Whisper sẽ xử lý từng segment audio riêng biệt
    """
    logger.info(f"🎤 Tạo SRT bằng Whisper (tùy theo độ dài video, có thể mất 5-30 phút)...")
    
    # Kiểm tra xem có SRT input không
    video_name = srt_output.stem
    srt_input = INPUT_SRT_DIR / f"{video_name}.srt"
    use_segment_mode = srt_input.exists()
    
    if use_segment_mode:
        logger.info(f"✨ Phát hiện SRT input, sử dụng Segment Mode (Whisper xử lý từng segment riêng)")
    else:
        logger.info(f"ℹ️ Không tìm SRT input, sử dụng Full-Audio Mode (Whisper xử lý toàn bộ audio)")
    
    try:
        result = transcribe_to_srt(
            audio_path=audio_path,
            output_srt_path=srt_output,
            model_name="base",
            lang="zh",
            srt_input_path=srt_input if use_segment_mode else None,
            use_segment_mode=use_segment_mode
        )
        logger.info(f"✅ Tạo SRT xong: {srt_output.name}")
        return True
    except Exception as e:
        logger.error(f"❌ Lỗi tạo SRT: {e}")
        raise

# ============ DỊCH SRT ============
def translate_srt(srt_path: Path) -> bool:
    """
    Dịch SRT bằng 2-PASS WORKFLOW (Gemini API)
    
    Sử dụng module translator.py:
    - PASS 1: Gemini 2.0 Flash phân tích Glossary (POV, Nhân vật, Xưung hô, Style, Keywords)
    - PASS 2: Gemini 2.0 Flash dịch từng batch theo Glossary
    
    ✨ Dùng Gemini API với exponential backoff rate limiting
    
    Args:
        srt_path: Path tới SRT input (INPUT_SRT_DIR/{video_name}.srt)
    
    Returns:
        True nếu thành công
    """
    logger.info(f"🌐 Dịch SRT sang Việt (2-PASS GEMINI WORKFLOW)...")
    
    if not srt_path.exists():
        logger.error(f"❌ Không tìm SRT input: {srt_path}")
        raise FileNotFoundError(f"SRT file not found: {srt_path}")
    
    try:
        # Output path
        output_srt_path = OUTPUT_SRT_DIR / f"{srt_path.stem}_translated.srt"
        output_srt_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Gọi translate_srt_2pass từ translator module
        success = translate_srt_2pass(
            input_srt_path=str(srt_path),
            output_srt_path=str(output_srt_path),
            working_dir=str(PROJECT_ROOT)
        )
        
        if success:
            logger.info(f"✅ Dịch SRT xong: {output_srt_path.name}")
            return True
        else:
            logger.error("❌ Dịch SRT thất bại (2-PASS OLLAMA WORKFLOW failed)")
            return False
        
    except Exception as e:
        logger.error(f"❌ Lỗi dịch: {e}")
        raise




# ============ COMPOSE VIDEO ============
def compose_video(video_path: Path, srt_path: Path) -> bool:
    """Compose video: remove audio cũ + add TTS + add subtitle"""
    logger.info(f"🎬 Compose video (TTS + Subtitle)...")
    
    try:
        result = subprocess.run(
            [sys.executable, "pipeline_full.py", str(video_path), str(srt_path)],
            capture_output=False,
            timeout=7200
        )
        
        if result.returncode != 0:
            logger.error(f"❌ Lỗi compose video")
            raise RuntimeError("Pipeline script returned error")
        
        output_video = OUTPUT_VIDEO_DIR / f"{video_path.stem}_final.mp4"
        if output_video.exists():
            logger.info(f"✅ Video hoàn tất: {output_video.name}")
            return True
        else:
            logger.warning(f"⚠️ Không tìm thấy output video (có thể pipeline chỉ xử lý từng bước)")
            return False
    except Exception as e:
        logger.error(f"❌ Lỗi compose: {e}")
        raise

# ============ XỬ LÝ THEO BƯỚC ============
def process_video_from_step(status: VideoStatus) -> bool:
    """Xử lý video từ bước tiếp theo"""
    
    if status.next_step == ProcessStep.AUDIO_EXTRACT:
        extract_audio(status.video_path, status.audio_path or INPUT_AUDIO_DIR / f"{status.video_name}.wav")
        # Tiếp tục bước tiếp theo
        return process_video_from_step(scan_project_status(status.video_path))
    
    elif status.next_step == ProcessStep.SRT_CREATE:
        audio_path = status.audio_path or INPUT_AUDIO_DIR / f"{status.video_name}.wav"
        srt_output = INPUT_SRT_DIR / f"{status.video_name}.srt"
        create_srt(audio_path, srt_output)
        # Tiếp tục bước tiếp theo
        return process_video_from_step(scan_project_status(status.video_path))
    
    elif status.next_step == ProcessStep.SRT_TRANSLATE:
        srt_path = status.srt_path or INPUT_SRT_DIR / f"{status.video_name}.srt"
        translate_srt(srt_path)
        # Tiếp tục bước tiếp theo
        return process_video_from_step(scan_project_status(status.video_path))
    
    elif status.next_step == ProcessStep.VIDEO_COMPOSE:
        video_path = status.video_path
        translated_srt = status.translated_srt_path or OUTPUT_SRT_DIR / f"{status.video_name}_translated.srt"
        compose_video(video_path, translated_srt)
        # Kiểm tra bước tiếp theo
        return process_video_from_step(scan_project_status(status.video_path))
    
    elif status.next_step == ProcessStep.COMPLETED:
        logger.info(f"✅ Video {status.video_name} đã hoàn tất tất cả bước")
        return True

# ============ MAIN ============
def main():
    """Chạy toàn bộ pipeline"""
    print("\n" + "="*70)
    print("🎬 YOUTUBE AUTOMATION PIPELINE - SMART RESUME")
    print("="*70 + "\n")
    
    # 1. Tìm video
    videos = find_videos()
    if not videos:
        logger.error(f"❌ Không tìm thấy video nào trong: {INPUT_VIDEO_DIR}")
        logger.info(f"   Vui lòng đặt video vào thư mục trên")
        return
    
    logger.info(f"✅ Tìm thấy {len(videos)} video")
    
    # 2. Quét status toàn bộ project
    print(f"\n🔍 Đang quét project...\n")
    statuses: List[VideoStatus] = []
    for video in videos:
        status = scan_project_status(video)
        statuses.append(status)
    
    # 3. Hiển thị tổng quan
    print_project_overview(statuses)
    
    # 4. Xử lý từng video
    for idx, status in enumerate(statuses, 1):
        print(f"\n{'='*70}")
        print(f"[{idx}/{len(statuses)}] 🎥 {status.video_name}")
        print(f"{'='*70}\n")
        
        try:
            if status.next_step == ProcessStep.COMPLETED:
                logger.info(f"✅ Video đã hoàn tất tất cả bước, skip")
                display_step_progress(status.video_name, status)
                continue
            
            # Show current progress
            logger.info(f"📍 Tiếp tục từ: {status}")
            display_step_progress(status.video_name, status)
            
            # Process from current step with monitoring
            initial_status = status
            step_retry_count = {}
            max_retries_per_step = 3
            
            while initial_status.next_step != ProcessStep.COMPLETED:
                # Re-scan to get latest status
                initial_status = scan_project_status(status.video_path)
                
                if initial_status.next_step == ProcessStep.COMPLETED:
                    break
                
                # Track retries for this step
                step_key = str(initial_status.next_step)
                step_retry_count[step_key] = step_retry_count.get(step_key, 0) + 1
                
                # Check if step has failed too many times
                if step_retry_count[step_key] > max_retries_per_step:
                    logger.warning(f"⚠️  Step {initial_status.next_step} failed {step_retry_count[step_key]} times")
                    logger.info(f"   Bỏ qua video này và tiếp tục video tiếp theo...")
                    break
                
                # Show what we're about to do
                if initial_status.next_step == ProcessStep.VIDEO_COMPOSE:
                    print(f"\n⏳ Starting STEP 4: Compose video...")
                
                # Execute step with error handling
                try:
                    process_video_from_step(initial_status)
                except Exception as e:
                    logger.error(f"   Step failed: {str(e)[:100]}")
                
                # Monitor TTS if needed
                if initial_status.next_step == ProcessStep.VIDEO_COMPOSE:
                    # TTS is running in subprocess, monitor it
                    monitor_tts_progress(status.video_name, interval=15)
                
                # Re-scan after step completes
                initial_status = scan_project_status(status.video_path)
                
                # Display updated progress
                display_step_progress(status.video_name, initial_status)
                
                # Sleep to avoid hammering resources
                time.sleep(1)
            
            logger.info(f"\n✅ Hoàn tất: {status.video_name}")
            
        except Exception as e:
            logger.error(f"❌ Lỗi xử lý video {status.video_name}: {e}")
            logger.info(f"   Tiếp tục với video tiếp theo...")
            continue
    
    print(f"\n{'='*70}")
    print(f"✅ HOÀN THÀNH QUÉT VÀ XỬ LÝ TẤT CẢ VIDEO")
    print(f"{'='*70}\n")
    logger.info(f"📁 Output videos: {OUTPUT_VIDEO_DIR}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Dừng lại bởi người dùng")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Lỗi: {e}")
        sys.exit(1)
