#!/usr/bin/env python3
"""
🚀 QUICK START - SRT Translator Optimized
Hướng dẫn bắt đầu nhanh nhất
"""

import os
import sys
import subprocess
from pathlib import Path


def print_header(text):
    """In header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def step_1_install_deps():
    """Bước 1: Cài đặt dependencies"""
    print_header("BƯỚC 1: CÀI ĐẶT DEPENDENCIES")
    
    print("""
Chạy lệnh sau để cài tất cả packages cần thiết:

    pip install -r requirements-translator.txt

Hoặc cài thủ công:

    pip install google-generativeai pysubs2 edge-tts python-dotenv
""")
    
    response = input("Bạn có muốn cài đặt ngay? (y/n): ").strip().lower()
    return response == "y"


def step_2_api_key():
    """Bước 2: Setup API Key"""
    print_header("BƯỚC 2: SETUP GOOGLE API KEY")
    
    print("""
⚠️  BẮT BUỘC: Bạn cần API Key từ Google Gemini

Các bước:
1. Truy cập: https://ai.google.dev/
2. Click "Get API key" hoặc "Create API key"
3. Copy API key
4. Đặt vào biến môi trường hoặc file config

=== OPTION A: Biến môi trường (KHUYẾN KHÍCH) ===

Windows PowerShell:
    [Environment]::SetEnvironmentVariable("GOOGLE_API_KEY", "YOUR_KEY_HERE", "User")

Linux/Mac:
    export GOOGLE_API_KEY="YOUR_KEY_HERE"
    echo 'export GOOGLE_API_KEY="YOUR_KEY_HERE"' >> ~/.bashrc
    source ~/.bashrc

=== OPTION B: Sửa trong script ===

Mở file: srt_translator_optimized.py
Tìm dòng: CONFIG = { ... "api_key": "YOUR_API_KEY_HERE", ...}
Thay bằng: CONFIG = { ... "api_key": "YOUR_ACTUAL_KEY", ...}

""")
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        print(f"✅ Tìm thấy GOOGLE_API_KEY: {api_key[:30]}...")
        return True
    else:
        print("❌ Chưa tìm thấy API Key")
        return False


def step_3_prepare_input():
    """Bước 3: Chuẩn bị file input"""
    print_header("BƯỚC 3: CHUẨN BỊ FILE INPUT.SRT")
    
    input_file = Path("input.srt")
    
    if input_file.exists():
        size_mb = input_file.stat().st_size / (1024 * 1024)
        lines = len(input_file.read_text(encoding="utf-8", errors="ignore").split("\n"))
        print(f"✅ File input.srt tìm thấy!")
        print(f"   - Kích thước: {size_mb:.1f} MB")
        print(f"   - Dòng: {lines}")
        return True
    else:
        print(f"""
❌ Chưa tìm thấy file input.srt

Các bước:
1. Sao chép file .srt của bạn vào thư mục này
2. Đặt tên là: input.srt
   Hoặc
3. Sửa config trong srt_translator_optimized.py:
   CONFIG["input_srt"] = "đường/dẫn/file.srt"
""")
        return False


def step_4_choose_config():
    """Bước 4: Chọn config"""
    print_header("BƯỚC 4: CHỌN CẤU HÌNH")
    
    print("""
Chọn cấu hình phù hợp:

1️⃣  DEFAULT (Cân bằng - Khuyến khích)
    - Tốc độ: Trung bình
    - Chất lượng: Tốt
    - Dùng cho: Phim chiếu rạp, file thường

2️⃣  SPEED (Nhanh - Ưu tiên tốc độ)
    - Tốc độ: Rất nhanh
    - Chất lượng: Bình thường
    - Dùng cho: File siêu dài (10000+ dòng)

3️⃣  QUALITY (Chất lượng cao)
    - Tốc độ: Chậm
    - Chất lượng: Xuất sắc
    - Dùng cho: Phim lịch sử, tài liệu

4️⃣  MALE VOICE (Giọng nam)
    - Chọn nếu muốn giọng Nam Minh thay vì Hoài My
    - Config khác giống DEFAULT

5️⃣  SMALL FILE (File nhỏ)
    - Chọn nếu file SRT nhỏ (<1000 dòng)
    - Dùng config riêng để tránh overhead
""")
    
    choice = input("Chọn config (1-5, default=1): ").strip() or "1"
    
    configs = {
        "1": "CONFIG_DEFAULT",
        "2": "CONFIG_SPEED",
        "3": "CONFIG_QUALITY",
        "4": "CONFIG_MALE_VOICE",
        "5": "CONFIG_SMALL_FILE",
    }
    
    return configs.get(choice, "CONFIG_DEFAULT")


def step_5_run():
    """Bước 5: Chạy script"""
    print_header("BƯỚC 5: CHẠY SCRIPT")
    
    print("""
Chạy lệnh:

    python srt_translator_optimized.py

Chờ cho đến khi xong. Bạn có thể:
- Nhìn vào process.log để xem tiến độ chi tiết
- Bấm Ctrl+C để dừng (sẽ tiếp tục lần tới từ dòng cuối)
- Check progress.json để xem checkpoint

Kết quả output:
- translated_final.srt: File SRT đã dịch
- output_audio/: Thư mục chứa MP3 (line_00000.mp3, etc)
- process.log: Nhật ký chi tiết
- progress.json: Checkpoint tiến độ
""")


def show_advanced_options():
    """Hiển thị tuỳ chọn nâng cao"""
    print_header("TUỲ CHỌN NÂNG CAO (Optional)")
    
    print("""
📝 Tuỳ chỉnh cấu hình trong srt_translator_optimized.py:

CONFIG = {
    "api_key": "YOUR_KEY",                    # API Key
    "model": "gemini-1.5-flash",              # Mô hình (flash=nhanh, pro=chất lượng)
    "voice": "vi-VN-HoaiMyNeural",            # Giọng (Hoài My, Nam Minh, etc)
    "input_srt": "input.srt",                 # File input
    "output_srt": "translated_final.srt",     # File output
    "audio_folder": "output_audio",           # Thư mục audio
    "batch_size": 35,                         # Dòng/batch (20-50)
    "tts_concurrent": 6,                      # Task TTS đồng thời (3-10)
    "checkpoint_file": "progress.json",       # Checkpoint file
    "log_file": "process.log",                # Log file
}

💡 Tips:
- Tăng batch_size lên 50 nếu muốn nhanh hơn
- Giảm tts_concurrent xuống 3 nếu bị rate-limit
- Dùng gemini-1.5-pro nếu muốn chất lượng tốt nhất (nhưng tốn tiền)

🔍 Debug:
- Kiểm tra process.log để thấy dòng nào lỗi
- Run: python test_checkpoint.py để test checkpoint feature
- Run: python setup_dependencies.py để check dependencies

📞 Nếu gặp vấn đề:
- Xem SRT_TRANSLATOR_README.md
- Xem config_examples.py để hiểu ý nghĩa từng config
""")


def main():
    """Main flow"""
    
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║    🎬 SRT Translator Optimized - QUICK START GUIDE v1.0             ║
║                                                                      ║
║    5 bước đơn giản để bắt đầu dịch SRT Trung → Việt                ║
╚══════════════════════════════════════════════════════════════════════╝
""")
    
    # Bước 1: Cài dependencies
    if not step_1_install_deps():
        print("\n⚠️  Hãy cài dependencies trước: pip install -r requirements-translator.txt")
        sys.exit(1)
    
    # Cài dependencies
    response = input("\nCài đặt bây giờ? (y/n): ").strip().lower()
    if response == "y":
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements-translator.txt"],
            check=False
        )
    
    # Bước 2: Setup API Key
    if not step_2_api_key():
        print("\n❌ Vui lòng setup API Key trước khi tiếp tục!")
        sys.exit(1)
    
    # Bước 3: Chuẩn bị input
    if not step_3_prepare_input():
        print("\n❌ Vui lòng chuẩn bị file input.srt trước!")
        sys.exit(1)
    
    # Bước 4: Chọn config
    selected_config = step_4_choose_config()
    print(f"\n✅ Đã chọn: {selected_config}")
    
    # Bước 5: Chạy
    step_5_run()
    
    # Tuỳ chọn nâng cao
    response = input("\n\nBạn có muốn xem tuỳ chọn nâng cao? (y/n): ").strip().lower()
    if response == "y":
        show_advanced_options()
    
    # Tóm tắt
    print_header("✅ CẤU HÌNH HOÀN THÀNH")
    
    print(f"""
Khởi chạy lệnh:

    python srt_translator_optimized.py

File tham khảo:
- 📖 SRT_TRANSLATOR_README.md      (Hướng dẫn chi tiết)
- ⚙️  config_examples.py            (Các ví dụ cấu hình)
- 🧪 test_checkpoint.py            (Demo checkpoint feature)
- 🔧 setup_dependencies.py          (Check dependencies)

Chúc bạn thành công! 🚀
""")


if __name__ == "__main__":
    main()
