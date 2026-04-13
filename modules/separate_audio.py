import subprocess
import logging
import os
import sys
from pathlib import Path
from typing import Tuple
import soundfile
import torch
import torchaudio

logger = logging.getLogger("video_pipeline")


# Patch torchaudio.save to use soundfile instead of torchcodec
_original_ta_save = torchaudio.save

def _patched_save(filepath, waveform, sample_rate, metadata=None, **kwargs):
    """
    Patched torchaudio.save that uses soundfile instead of torchcodec.
    This avoids the torchcodec DLL loading errors on Windows.
    """
    logger.debug(f"Using patched save with soundfile for {filepath}")
    # waveform is (channels, samples)
    if isinstance(waveform, torch.Tensor):
        waveform = waveform.cpu().numpy()
    
    # soundfile expects (samples, channels)
    if waveform.ndim == 2 and waveform.shape[0] < waveform.shape[1]:
        waveform = waveform.T
    elif waveform.ndim == 1:
        waveform = waveform[:, None]
    
    soundfile.write(str(filepath), waveform, sample_rate)

# Apply the patch to the torchaudio module
torchaudio.save = _patched_save


def separate_audio_demucs(
    input_wav: Path,
    output_dir: Path,
    model_name: str = "htdemucs",
) -> Tuple[Path, Path]:
    """
    Tách lời (vocals) và nhạc nền (no_vocals) bằng Demucs.

    FIX WINDOWS TORCHCODEC DLL CRASH:
    Demucs performs 100% separation but crashes when saving because torchaudio
    tries to use torchcodec (missing libtorchcodec_coreX.dll on Windows).
    Solution: Create wrapper script with patched torchaudio.save.
    """
    if not input_wav.exists():
        raise FileNotFoundError(f"File WAV đầu vào không tồn tại: {input_wav}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Normalize paths for consistency
    input_wav_str = str(input_wav.resolve()).replace('\\', '/')
    output_dir_str = str(output_dir.resolve()).replace('\\', '/')

    # Create temporary wrapper script that runs demucs with patched torchaudio
    wrapper_script = Path("_demucs_wrapper.py")
    wrapper_content = f'''
import sys
import soundfile
import torch
import torchaudio

# Patch torchaudio.save before importing demucs
def patched_save(filepath, waveform, sample_rate, metadata=None, **kwargs):
    if isinstance(waveform, torch.Tensor):
        waveform = waveform.cpu().numpy()
    if waveform.ndim == 2 and waveform.shape[0] < waveform.shape[1]:
        waveform = waveform.T
    elif waveform.ndim == 1:
        waveform = waveform[:, None]
    soundfile.write(str(filepath), waveform, sample_rate)

torchaudio.save = patched_save

# Now import and run demucs
from demucs.separate import main
sys.argv = ['demucs', '--two-stems=vocals', '-n', '{model_name}', '-o', '{output_dir_str}', '{input_wav_str}']
main()
'''
    wrapper_script.write_text(wrapper_content)

    logger.info("--- Đang chạy Demucs tách âm: %s ---", input_wav.name)

    try:
        result = subprocess.run(
            [sys.executable, str(wrapper_script)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        logger.info("✅ Demucs hoàn tất thành công.")
        logger.debug(f"Demucs output: {result.stdout}")
    except subprocess.CalledProcessError as exc:
        logger.error(
            "❌ Demucs thất bại (code %d):\nSTDOUT: %s\nSTDERR: %s",
            exc.returncode, exc.stdout, exc.stderr,
        )
        raise RuntimeError(
            f"Demucs thất bại với code {exc.returncode}.\n"
            f"STDERR: {exc.stderr}"
        ) from exc
    finally:
        # Clean up wrapper script
        wrapper_script.unlink(missing_ok=True)

    stem_dir = output_dir / model_name / input_wav.stem
    vocals_path = stem_dir / "vocals.wav"
    no_vocals_path = stem_dir / "no_vocals.wav"

    missing = []
    if not vocals_path.exists():
        missing.append(f"vocals.wav tại {vocals_path}")
    if not no_vocals_path.exists():
        missing.append(f"no_vocals.wav tại {no_vocals_path}")

    if missing:
        raise FileNotFoundError(
            "Demucs chạy xong nhưng không tìm thấy file output:\n" + "\n".join(missing)
        )

    logger.info("Vocals    : %s", vocals_path)
    logger.info("No-vocals : %s", no_vocals_path)
    return vocals_path, no_vocals_path