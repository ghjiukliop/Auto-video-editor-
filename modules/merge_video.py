from pathlib import Path

import ffmpeg


def _escape_subtitles_path(srt_path: Path) -> str:
    normalized = srt_path.resolve().as_posix()
    return normalized.replace(":", r"\:")


def merge_video_with_audio_and_subtitles(
    input_video_path: Path,
    bgm_path: Path,
    ai_voice_path: Path,
    subtitles_path: Path,
    output_video_path: Path,
    bgm_volume: float,
    voice_volume: float,
) -> Path:
    output_video_path.parent.mkdir(parents=True, exist_ok=True)

    video_stream = ffmpeg.input(str(input_video_path))
    bgm_stream = ffmpeg.input(str(bgm_path)).audio.filter("volume", bgm_volume)
    voice_stream = ffmpeg.input(str(ai_voice_path)).audio.filter("volume", voice_volume)

    mixed_audio = ffmpeg.filter(
        [bgm_stream, voice_stream],
        "amix",
        inputs=2,
        duration="longest",
        normalize=0,
    )
    subtitled_video = video_stream.video.filter(
        "subtitles",
        _escape_subtitles_path(subtitles_path),
        charenc="UTF-8",
    )

    try:
        (
            ffmpeg.output(
                subtitled_video,
                mixed_audio,
                str(output_video_path),
                vcodec="libx264",
                acodec="aac",
                audio_bitrate="192k",
                movflags="+faststart",
                shortest=None,
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as exc:
        stderr_text = (
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, (bytes, bytearray))
            else str(exc.stderr)
        )
        raise RuntimeError(f"FFmpeg merge failed: {stderr_text}") from exc
    return output_video_path
