@echo off
REM SRT Translator Optimized - Run Script for Windows
REM Chạy script dịch SRT Trung -> Việt với tất cả tính năng tối ưu

setlocal enabledelayedexpansion

echo.
echo ========================================================================
echo   SRT Translator Optimized - Interactive Menu
echo.
echo   1. QUICK START     (Setup & hướng dẫn lần đầu)
echo   2. RUN TRANSLATOR  (Chạy dịch SRT)
echo   3. TEST            (Test checkpoint feature)
echo   4. SETUP           (Check dependencies)
echo   5. VIEW LOGS       (Xem file log)
echo   6. VIEW PROGRESS   (Xem progress.json)
echo.
echo ========================================================================
echo.

set /p choice="Chọn tùy chọn (1-6): "

if "%choice%"=="1" (
    echo.
    echo 🚀 Chạy QUICK START...
    echo.
    python QUICK_START.py
    pause
) else if "%choice%"=="2" (
    echo.
    echo 🎬 Chạy SRT Translator...
    echo.
    python srt_translator_optimized.py
    pause
) else if "%choice%"=="3" (
    echo.
    echo 🧪 Chạy Test Checkpoint...
    echo.
    python test_checkpoint.py
    pause
) else if "%choice%"=="4" (
    echo.
    echo 🔧 Chạy Setup Dependencies...
    echo.
    python setup_dependencies.py
    pause
) else if "%choice%"=="5" (
    echo.
    echo 📝 Xem process.log...
    echo.
    if exist "process.log" (
        type process.log
    ) else (
        echo Chưa có process.log - chạy translator trước
    )
    pause
) else if "%choice%"=="6" (
    echo.
    echo 📊 Xem progress.json...
    echo.
    if exist "progress.json" (
        type progress.json
    ) else (
        echo Chưa có progress.json - chạy translator trước
    )
    pause
) else (
    echo ❌ Lựa chọn không hợp lệ
    pause
)

endlocal
