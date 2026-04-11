import subprocess
import logging
from pathlib import Path

logger = logging.getLogger("video_pipeline")

def merge_video_with_audio_and_subtitles(input_video_path, bgm_path, ai_voice_path, subtitles_path, output_video_path, bgm_volume, voice_volume):
    logger.info("--- Đang ghép Video bằng FFmpeg siêu tốc ---")
    
    # Lệnh trộn Voice và BGM, sau đó ghép vào Video mà không cần render lại hình ảnh (copy)
    cmd = [
        'ffmpeg', '-y',
        '-i', str(input_video_path),
        '-i', str(bgm_path),
        '-i', str(ai_voice_path),
        '-filter_complex', 
        f'[1:a]volume={bgm_volume}[bgm];[2:a]volume={voice_volume}[voice];[bgm][voice]amix=inputs=2:duration=first[audio_out]',
        '-map', '0:v:0',
        '-map', '[audio_out]',
        '-c:v', 'copy', # Copy video gốc, cực nhanh
        '-c:a', 'aac',
        '-shortest',
        str(output_video_path)
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    logger.info(f"✅ Đã tạo xong video: {output_video_path}")