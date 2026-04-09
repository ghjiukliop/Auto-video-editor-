import logging
from pathlib import Path
from typing import Literal, Optional

import torch
import whisper

from utils.audio_utils import segments_to_srt

logger = logging.getLogger("video_pipeline")


def transcribe_to_srt(
    audio_path: Path,
    output_srt_path: Path,
    model_name: str,
    lang: Literal["vi", "en", "auto"] = "auto",
) -> Path:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(
        "Loading Whisper model %r on %s (CPU transcription of long audio can take a while)",
        model_name,
        device,
    )
    model = whisper.load_model(model_name, device=device)
    language: Optional[str] = None if lang == "auto" else lang
    logger.info("Transcribing %s (this can take a while on CPU)", audio_path.name)
    result = model.transcribe(
        str(audio_path),
        language=language,
        verbose=False,
        fp16=device == "cuda",
    )
    srt_text = segments_to_srt(result.get("segments", []))
    output_srt_path.write_text(srt_text, encoding="utf-8")
    logger.info("Wrote subtitles: %s", output_srt_path)
    return output_srt_path
