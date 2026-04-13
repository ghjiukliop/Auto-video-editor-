import subprocess
import logging
import sys
from pathlib import Path

logger = logging.getLogger("video_pipeline")


def _escape_subtitle_path(path: Path) -> str:
    """
    Chuyển đổi đường dẫn sang định dạng FFmpeg subtitle filter chấp nhận trên Windows.
    VD: C:\\Users\\foo\\sub.srt -> C\\:/Users/foo/sub.srt
    
    FFmpeg cần escape ký tự ':' trong ổ đĩa (C: -> C\\:)
    Và chuyển tất cả backslash thành forward slash.
    """
    path_str = str(path).replace("\\", "/")
    if sys.platform == "win32" and len(path_str) >= 2 and path_str[1] == ":":
        # C:/path -> C\:/path (escaping dấu ':')
        path_str = path_str[0] + "\\:" + path_str[2:]
    return path_str


def merge_video_with_audio_and_subtitles(
    input_video_path: Path,
    bgm_path: Path,
    ai_voice_path: Path,
    subtitles_path: Path,
    output_video_path: Path,
    bgm_volume: float,
    voice_volume: float,
) -> None:
    # --- Kiểm tra sự tồn tại của các file đầu vào trước khi chạy ---
    missing = []
    for label, p in [
        ("Video gốc", input_video_path),
        ("BGM", bgm_path),
        ("Giọng AI", ai_voice_path),
        ("Phụ đề SRT", subtitles_path),
    ]:
        if not Path(p).exists():
            missing.append(f"{label}: {p}")

    if missing:
        raise FileNotFoundError(
            "Thiếu file đầu vào trước khi ghép video:\n" + "\n".join(missing)
        )

    logger.info("--- Đang ghép Video bằng FFmpeg siêu tốc ---")

    escaped_sub = _escape_subtitle_path(subtitles_path)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_video_path),
        "-i", str(bgm_path),
        "-i", str(ai_voice_path),
        "-filter_complex",
        (
            f"[0:v]subtitles={escaped_sub}[v_sub];"
            f"[1:a]volume={bgm_volume}[bgm];"
            f"[2:a]volume={voice_volume}[voice];"
            f"[bgm][voice]amix=inputs=2:duration=first[audio_out]"
        ),
        "-map", "[v_sub]",
        "-map", "[audio_out]",
        "-c:v", "copy",   # Không re-encode video → nhanh hơn nhiều
        "-c:a", "aac",
        "-shortest",
        str(output_video_path),
    ]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")
        logger.info("✅ Đã tạo xong video lồng tiếng: %s", output_video_path)
    except subprocess.CalledProcessError as exc:
        logger.error("❌ FFmpeg thất bại (code %d):\n%s", exc.returncode, exc.stderr)
        raise RuntimeError(f"FFmpeg merge thất bại: {exc.stderr}") from exc