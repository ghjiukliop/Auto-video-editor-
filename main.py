import argparse
import json
import logging
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple

import config
from tqdm import tqdm
from modules.extract_audio import extract_audio_to_wav
from modules.merge_video import merge_video_with_audio_and_subtitles
from modules.separate_audio import separate_audio_demucs
from modules.speech_to_text import transcribe_to_srt
from modules.tts import build_ai_voice_from_srt

from utils.file_utils import (
    cleanup_dir,
    create_video_temp_dir,
    ensure_directories,
    is_already_processed,
    list_mp4_files,
    output_video_path,
)


logger = logging.getLogger("video_pipeline")
DEBUG_LOG_PATH = Path(__file__).resolve().parent / "debug-a62165.log"
DEBUG_SESSION_ID = "a62165"


def _debug_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": DEBUG_SESSION_ID,
        "id": f"log_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}",
        "timestamp": int(time.time() * 1000),
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
    }
    with DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def setup_logging() -> None:
    # Ensure Unicode logs/subtitles text can be printed on Windows consoles.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch video AI voiceover pipeline.")
    parser.add_argument("--lang", choices=["vi", "en", "zh", "auto"], default="auto")
    parser.add_argument("--voice", default=config.TTS_VOICE)
    parser.add_argument("--model", default=config.WHISPER_MODEL)
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel workers for batch processing (default: 1).",
    )
    return parser.parse_args()


def process_single_video(
    video_path_str: str,
    whisper_model: str,
    lang: str,
    tts_voice: str,
) -> Tuple[str, bool, str]:
    video_path = Path(video_path_str)
    run_id = f"{video_path.stem}_{int(time.time())}"
    work_dir = create_video_temp_dir(config.TEMP_FOLDER, video_path)
    output_path = output_video_path(config.OUTPUT_FOLDER, video_path)

    try:
        # #region agent log
        _debug_log(
            run_id=run_id,
            hypothesis_id="H2",
            location="main.py:process_single_video:entry",
            message="Video processing started",
            data={"video_path": str(video_path), "work_dir": str(work_dir), "demucs_model": config.DEMUC_MODEL},
        )
        # #endregion
        logger.info("Processing video: %s", video_path.name)
        extracted_wav = work_dir / "extracted.wav"
        subtitles_srt = work_dir / "subtitles.srt"
        ai_voice_wav = work_dir / "ai_voice.wav"
        chunks_dir = work_dir / "tts_chunks"
        demucs_out = work_dir / "demucs"

        extract_audio_to_wav(video_path, extracted_wav)
        vocals_path, no_vocals_path = separate_audio_demucs(
            extracted_wav, demucs_out, model_name=config.DEMUC_MODEL
        )
        transcribe_to_srt(vocals_path, subtitles_srt, model_name=whisper_model, lang=lang)
        build_ai_voice_from_srt(
            srt_path=subtitles_srt,
            output_voice_path=ai_voice_wav,
            temp_chunks_dir=chunks_dir,
            voice=tts_voice,
            rate=config.TTS_RATE,
            pitch=config.TTS_PITCH,
        )
        merge_video_with_audio_and_subtitles(
            input_video_path=video_path,
            bgm_path=no_vocals_path,
            ai_voice_path=ai_voice_wav,
            subtitles_path=subtitles_srt,
            output_video_path=output_path,
            bgm_volume=config.BGM_VOLUME,
            voice_volume=config.VOICE_VOLUME,
        )
        return video_path.name, True, f"Output: {output_path}"
    except Exception as exc:
        # #region agent log
        _debug_log(
            run_id=run_id,
            hypothesis_id="H3",
            location="main.py:process_single_video:exception",
            message="Video processing failed",
            data={"exception_type": type(exc).__name__, "exception_message": str(exc)},
        )
        # #endregion
        return video_path.name, False, f"{type(exc).__name__}: {exc}"
    finally:
        cleanup_dir(work_dir)


def run_batch(videos: List[Path], args: argparse.Namespace) -> None:
    pending = [v for v in videos if not is_already_processed(config.OUTPUT_FOLDER, v)]
    skipped = [v for v in videos if is_already_processed(config.OUTPUT_FOLDER, v)]

    for video in skipped:
        logger.info("Skipping already processed: %s", video.name)

    if not pending:
        logger.info("No new videos to process.")
        return

    logger.info("Starting batch with %d video(s), workers=%d", len(pending), args.workers)

    successes = 0
    failures = 0

    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(
                    process_single_video,
                    str(video),
                    args.model,
                    args.lang,
                    args.voice,
                ): video
                for video in pending
            }
            for future in tqdm(as_completed(futures), total=len(futures), desc="Processing"):
                video_name, ok, message = future.result()
                if ok:
                    successes += 1
                    logger.info("Done: %s | %s", video_name, message)
                else:
                    failures += 1
                    logger.error("Failed: %s | %s", video_name, message)
    else:
        for video in tqdm(pending, desc="Processing"):
            video_name, ok, message = process_single_video(
                str(video),
                whisper_model=args.model,
                lang=args.lang,
                tts_voice=args.voice,
            )
            if ok:
                successes += 1
                logger.info("Done: %s | %s", video_name, message)
            else:
                failures += 1
                logger.error("Failed: %s | %s", video_name, message)

    logger.info("Batch complete. Success=%d | Failed=%d | Skipped=%d", successes, failures, len(skipped))


def print_run_instructions() -> None:
    print("\nRun instructions:")
    print("1) Install FFmpeg (system requirement) and ensure `ffmpeg` is in PATH.")
    print("2) pip install -r requirements.txt")
    print("3) python main.py")


def main() -> None:
    setup_logging()
    args = parse_args()
    ensure_directories([config.INPUT_FOLDER, config.OUTPUT_FOLDER, config.TEMP_FOLDER])

    videos = list_mp4_files(config.INPUT_FOLDER)
    if not videos:
        logger.info("No .mp4 files found in %s", config.INPUT_FOLDER)
        print_run_instructions()
        return

    run_batch(videos, args)
    print_run_instructions()


if __name__ == "__main__":
    main()
