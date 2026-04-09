import shutil
from pathlib import Path
from typing import Iterable, List


def ensure_directories(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def list_mp4_files(input_folder: Path) -> List[Path]:
    if not input_folder.exists():
        return []
    return sorted([p for p in input_folder.glob("*.mp4") if p.is_file()])


def output_video_path(output_folder: Path, input_video: Path) -> Path:
    return output_folder / f"{input_video.stem}_processed.mp4"


def is_already_processed(output_folder: Path, input_video: Path) -> bool:
    return output_video_path(output_folder, input_video).exists()


def create_video_temp_dir(temp_root: Path, input_video: Path) -> Path:
    work_dir = temp_root / input_video.stem
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def cleanup_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
