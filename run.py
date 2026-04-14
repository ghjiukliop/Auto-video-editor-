#!/usr/bin/env python3
"""
SIMPLE ENTRY POINT - Chỉ cần chạy file này!
"""

import sys
import os
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from pipeline import ProductionPipeline, logger

def find_first_video():
    """Tự động tìm video đầu tiên trong input_videos/"""
    input_dir = Path("input_videos")
    if not input_dir.exists():
        input_dir.mkdir(parents=True)
    
    video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv'}
    for file in sorted(input_dir.iterdir()):
        if file.suffix.lower() in video_extensions:
            return str(file)
    
    return None

def main():
    # Parse args
    if len(sys.argv) < 2:
        # Không có argument → tự động tìm video
        video_file = find_first_video()
        if not video_file:
            print("""
╔════════════════════════════════════════════════╗
║     YOUTUBE AUTOMATION - PRODUCTION PIPELINE   ║
╚════════════════════════════════════════════════╝

❌ KHÔNG TÌM THẤY VIDEO!

Cách sử dụng:
  1️⃣  Đặt video vào: C:\\YoutubeAutomation\\input_videos\\
      → Sau đó chạy: python run.py
      
  2️⃣  Hoặc nhập file cụ thể:
      → python run.py movie.mp4
      → python run.py C:\\path\\to\\video.mp4

Options:
  python run.py video.mp4 -o output_folder
  python run.py video.mp4 -w work_folder
  python run.py video.mp4 -o output -w temp

Pipeline sẽ tự động:
  ✅ Tách audio
  ✅ Tách phụ đề (STT)
  ✅ Dịch + kiểm tra (max 3 lần)
  ✅ Chuyển phụ đề → audio (TTS)
  ✅ Merge tất cả thành audio unified

Thời gian: ~3-4 phút
Output: {video_name}_final.wav
""")
            sys.exit(1)
        print(f"✅ Tìm thấy video: {video_file}")
    else:
        video_file = sys.argv[1]
    output_dir = "output"
    work_dir = None
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "-o" and i + 1 < len(sys.argv):
            output_dir = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "-w" and i + 1 < len(sys.argv):
            work_dir = sys.argv[i + 1]
            i += 2
        else:
            i += 1
    
    # Run
    try:
        pipeline = ProductionPipeline(
            video_path=video_file,
            output_dir=output_dir,
            work_dir=work_dir
        )
        success = pipeline.run()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
