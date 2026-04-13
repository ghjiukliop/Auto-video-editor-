#!/bin/bash
# SRT Translator Optimized - Run Script for Linux/Mac
# Chạy script dịch SRT Trung -> Việt với tất cả tính năng tối ưu

clear

echo "========================================================================"
echo "  SRT Translator Optimized - Interactive Menu"
echo ""
echo "  1. QUICK START     (Setup & hướng dẫn lần đầu)"
echo "  2. RUN TRANSLATOR  (Chạy dịch SRT)"
echo "  3. TEST            (Test checkpoint feature)"
echo "  4. SETUP           (Check dependencies)"
echo "  5. VIEW LOGS       (Xem file log)"
echo "  6. VIEW PROGRESS   (Xem progress.json)"
echo ""
echo "========================================================================"
echo ""

read -p "Chọn tùy chọn (1-6): " choice

case $choice in
    1)
        echo ""
        echo "🚀 Chạy QUICK START..."
        echo ""
        python3 QUICK_START.py
        ;;
    2)
        echo ""
        echo "🎬 Chạy SRT Translator..."
        echo ""
        python3 srt_translator_optimized.py
        ;;
    3)
        echo ""
        echo "🧪 Chạy Test Checkpoint..."
        echo ""
        python3 test_checkpoint.py
        ;;
    4)
        echo ""
        echo "🔧 Chạy Setup Dependencies..."
        echo ""
        python3 setup_dependencies.py
        ;;
    5)
        echo ""
        echo "📝 Xem process.log..."
        echo ""
        if [ -f "process.log" ]; then
            cat process.log
        else
            echo "Chưa có process.log - chạy translator trước"
        fi
        ;;
    6)
        echo ""
        echo "📊 Xem progress.json..."
        echo ""
        if [ -f "progress.json" ]; then
            cat progress.json
        else
            echo "Chưa có progress.json - chạy translator trước"
        fi
        ;;
    *)
        echo "❌ Lựa chọn không hợp lệ"
        ;;
esac
