import subprocess
import json
import time
import uuid
import shutil
import platform
from pathlib import Path
from typing import Tuple


DEBUG_LOG_PATH = Path(__file__).resolve().parent.parent / "debug-a62165.log"
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


def separate_audio_demucs(input_wav: Path, output_dir: Path, model_name: str = "htdemucs") -> Tuple[Path, Path]:
    run_id = f"{input_wav.stem}_{int(time.time())}"
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "demucs",
        "--two-stems=vocals",
        "-n",
        model_name,
        "-o",
        str(output_dir),
        str(input_wav),
    ]
    # #region agent log
    _debug_log(
        run_id=run_id,
        hypothesis_id="H1",
        location="modules/separate_audio.py:separate_audio_demucs:pre_run",
        message="About to run demucs",
        data={"command": command, "input_exists": input_wav.exists(), "input_size": input_wav.stat().st_size if input_wav.exists() else -1},
    )
    # #endregion
    stem_dir = output_dir / model_name / input_wav.stem
    vocals_path = stem_dir / "vocals.wav"
    no_vocals_path = stem_dir / "no_vocals.wav"

    def _fallback_without_separation(reason: str) -> Tuple[Path, Path]:
        stem_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_wav, vocals_path)
        shutil.copy2(input_wav, no_vocals_path)
        _debug_log(
            run_id=run_id,
            hypothesis_id="H6",
            location="modules/separate_audio.py:separate_audio_demucs:fallback_copy",
            message="Demucs unavailable; using original track for both stems",
            data={"reason": reason, "vocals_path": str(vocals_path), "no_vocals_path": str(no_vocals_path)},
        )
        return vocals_path, no_vocals_path

    if platform.system().lower().startswith("win"):
        return _fallback_without_separation("Demucs disabled on Windows for stability")

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=900)
        # #region agent log
        _debug_log(
            run_id=run_id,
            hypothesis_id="H1",
            location="modules/separate_audio.py:separate_audio_demucs:post_run_success",
            message="Demucs completed",
            data={"returncode": result.returncode, "stdout_tail": result.stdout[-1200:], "stderr_tail": result.stderr[-1200:]},
        )
        # #endregion
    except subprocess.CalledProcessError as exc:
        # #region agent log
        _debug_log(
            run_id=run_id,
            hypothesis_id="H1",
            location="modules/separate_audio.py:separate_audio_demucs:post_run_error",
            message="Demucs failed",
            data={
                "returncode": exc.returncode,
                "stdout_tail": (exc.stdout or "")[-1500:],
                "stderr_tail": (exc.stderr or "")[-1500:],
                "cwd": str(Path.cwd()),
            },
        )
        # #endregion
        stderr_text = exc.stderr or ""
        if (
            "TorchCodec is required for save_with_torchcodec" in stderr_text
            or "libtorchcodec_core4.dll" in stderr_text
            or "Could not load this library" in stderr_text
        ):
            fallback_command = [
                "demucs",
                "--two-stems=vocals",
                "--mp3",
                "--mp3-bitrate",
                "320",
                "-n",
                model_name,
                "-o",
                str(output_dir),
                str(input_wav),
            ]
            # #region agent log
            _debug_log(
                run_id=run_id,
                hypothesis_id="H5",
                location="modules/separate_audio.py:separate_audio_demucs:fallback_mp3_pre",
                message="Retrying demucs with mp3 fallback after torchcodec error",
                data={"fallback_command": fallback_command},
            )
            # #endregion
            fallback_result = subprocess.run(
                fallback_command, check=True, capture_output=True, text=True, timeout=900
            )
            # #region agent log
            _debug_log(
                run_id=run_id,
                hypothesis_id="H5",
                location="modules/separate_audio.py:separate_audio_demucs:fallback_mp3_post",
                message="Demucs mp3 fallback completed",
                data={"returncode": fallback_result.returncode, "stdout_tail": fallback_result.stdout[-1200:], "stderr_tail": fallback_result.stderr[-1200:]},
            )
            # #endregion
        else:
            return _fallback_without_separation(str(exc))
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return _fallback_without_separation(str(exc))

    if not vocals_path.exists() or not no_vocals_path.exists():
        vocals_mp3 = stem_dir / "vocals.mp3"
        no_vocals_mp3 = stem_dir / "no_vocals.mp3"
        if vocals_mp3.exists() and no_vocals_mp3.exists():
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(vocals_mp3), str(vocals_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(no_vocals_mp3), str(no_vocals_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            # #region agent log
            _debug_log(
                run_id=run_id,
                hypothesis_id="H5",
                location="modules/separate_audio.py:separate_audio_demucs:fallback_convert",
                message="Converted demucs fallback mp3 stems to wav",
                data={"vocals_wav_exists": vocals_path.exists(), "no_vocals_wav_exists": no_vocals_path.exists()},
            )
            # #endregion

    if not vocals_path.exists() or not no_vocals_path.exists():
        # #region agent log
        _debug_log(
            run_id=run_id,
            hypothesis_id="H4",
            location="modules/separate_audio.py:separate_audio_demucs:output_check",
            message="Demucs completed but expected stems missing",
            data={"stem_dir": str(stem_dir), "stem_dir_exists": stem_dir.exists(), "children": [p.name for p in stem_dir.glob("*")] if stem_dir.exists() else []},
        )
        # #endregion
        return _fallback_without_separation(f"Demucs output missing in {stem_dir}")
    return vocals_path, no_vocals_path
