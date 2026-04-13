#!/usr/bin/env python3
"""
🔧 Dependency Checker & Setup Helper
Kiểm tra các package cần thiết và hướng dẫn cài đặt
"""

import sys
import subprocess
from pathlib import Path

def check_and_install_dependencies():
    """Kiểm tra & cài đặt dependencies"""
    
    required_packages = {
        "google-generativeai": "google.generativeai",
        "pysubs2": "pysubs2",
        "edge-tts": "edge_tts",
        "python-dotenv": "dotenv",  # Optional nhưng khuyến khích
    }
    
    missing = []
    installed = []
    
    print("=" * 70)
    print("🔍 KIỂM TRA DEPENDENCIES")
    print("=" * 70)
    
    for package_name, import_name in required_packages.items():
        try:
            __import__(import_name)
            print(f"✅ {package_name:<30} → Đã cài")
            installed.append(package_name)
        except ImportError:
            print(f"❌ {package_name:<30} → CHƯA CÀI")
            missing.append(package_name)
    
    print()
    
    if not missing:
        print("🎉 Tất cả dependencies đã cài đặt!")
        return True
    
    print(f"⚠️  Thiếu {len(missing)} package:")
    for pkg in missing:
        print(f"   - {pkg}")
    
    print()
    response = input("🚀 Bạn có muốn cài đặt ngay không? (y/n): ").strip().lower()
    
    if response == "y":
        print("📦 Đang cài đặt...")
        cmd = [sys.executable, "-m", "pip", "install"] + missing
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Cài đặt thành công!")
            return True
        else:
            print(f"❌ Cài đặt thất bại:\n{result.stderr}")
            return False
    else:
        print("⚠️  Chạy lệnh này để cài đặt:")
        print(f"   pip install {' '.join(missing)}")
        return False


def setup_api_key():
    """Hướng dẫn setup API Key"""
    
    print("\n" + "=" * 70)
    print("🔑 SETUP GOOGLE API KEY")
    print("=" * 70)
    
    print("""
1. Truy cập: https://ai.google.dev/
2. Click "Get API key" (hoặc "Create API key")
3. Copy API key
4. Đặt vào một trong các cách:
   
   A) Biến môi trường (KHUYẾN KHÍCH):
      Windows PowerShell:
      [Environment]::SetEnvironmentVariable("GOOGLE_API_KEY", "YOUR_KEY", "User")
      
      Linux/Mac:
      export GOOGLE_API_KEY="YOUR_KEY"
   
   B) Hoặc sửa thẳng trong script:
      CONFIG["api_key"] = "YOUR_KEY"
""")
    
    # Kiểm tra API key
    import os
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if api_key:
        print(f"✅ Đã tìm thấy GOOGLE_API_KEY: {api_key[:20]}...")
    else:
        print("❌ Chưa tìm thấy GOOGLE_API_KEY. Vui lòng setup.")


def setup_input_file():
    """Kiểm tra input.srt"""
    
    print("\n" + "=" * 70)
    print("📖 SETUP FILE INPUT")
    print("=" * 70)
    
    input_file = Path("input.srt")
    
    if input_file.exists():
        size_mb = input_file.stat().st_size / (1024 * 1024)
        lines = len(input_file.read_text(encoding="utf-8", errors="ignore").split("\n"))
        print(f"✅ File input.srt tìm thấy ({lines} dòng, {size_mb:.1f} MB)")
    else:
        print("""
❌ Chưa tìm thấy input.srt
Hãy:
1. Đặt file SRT cùng thư mục với script
   hoặc
2. Sửa CONFIG["input_srt"] = "đường/dẫn/file.srt" trong script
""")


def main():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║         🎬 SRT Translator Optimized - Setup Helper v1.0              ║
╚══════════════════════════════════════════════════════════════════════╝
""")
    
    # Bước 1: Check dependencies
    deps_ok = check_and_install_dependencies()
    
    if not deps_ok:
        print("\n⚠️  Không thể tiếp tục mà không cài dependencies.")
        sys.exit(1)
    
    # Bước 2: Setup API Key
    setup_api_key()
    
    # Bước 3: Check input file
    setup_input_file()
    
    print("\n" + "=" * 70)
    print("🚀 SETUP HOÀN THÀNH")
    print("=" * 70)
    print("""
Bước tiếp theo:
1. Đảm bảo API Key đã cấu hình (biến env hoặc script)
2. Chuẩn bị input.srt trong thư mục script
3. Chạy: python srt_translator_optimized.py

Tham khảo: SRT_TRANSLATOR_README.md
""")


if __name__ == "__main__":
    main()
