from pathlib import Path

import ffmpeg


def extract_audio_to_wav(video_path: Path, output_wav_path: Path) -> Path:
    """Trích xuất âm thanh từ video sang WAV 44100Hz stereo."""
    output_wav_path.parent.mkdir(parents=True, exist_ok=True)
    (
        ffmpeg.input(str(video_path))
        .output(str(output_wav_path), acodec="pcm_s16le", ac=2, ar=44100)
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )
    