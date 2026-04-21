"""
Master Pipeline: Toàn bộ luồng xử lý từ SRT dịch -> Video final
Tích hợp: Dịch → TTS → Điều chỉnh timing → Merge audio → Compose video
"""

import sys
from pathlib import Path

# Import modules
from modules.tts_generator import TTSGenerator
from modules.audio_adjuster import AudioAdjuster
from modules.audio_merger import AudioMerger
from modules.video_composer import VideoComposer


class YouTubeAutomationPipeline:
    """Pipeline hoàn chỉnh: Video -> SRT dịch -> Audio TTS -> Video final"""
    
    def __init__(self, config=None):
        """
        config: {
            "tts_service": "gtts" (default) | "google_cloud" | "pyttsx3",
            "language": "vi",
            "output_dir": "output_videos"
        }
        """
        self.config = config or {}
        self.tts_service = self.config.get("tts_service", "gtts")
        self.language = self.config.get("language", "vi")
        self.output_dir = Path(self.config.get("output_dir", "output_videos"))
        
        print("\n" + "="*60)
        print("🎬 YOUTUBE AUTOMATION - FULL PIPELINE")
        print("="*60)
        print(f"TTS Service: {self.tts_service}")
        print(f"Language: {self.language}")
        print("="*60 + "\n")
    
    def process_video(self, video_file: str, srt_file: str) -> bool:
        """
        Xử lý 1 video từ đầu đến cuối - SMART RESUME
        
        AUTO DETECT bước hiện tại:
        1. TTS files tạo xong? → Skip tới Merge
        2. Merged audio tạo xong? → Skip tới Compose
        3. Final video tạo xong? → Skip all
        """
        video_path = Path(video_file)
        srt_path = Path(srt_file)
        
        if not video_path.exists():
            print(f"❌ Video file không tồn tại: {video_file}")
            return False
        
        if not srt_path.exists():
            print(f"❌ SRT file không tồn tại: {srt_file}")
            return False
        
        video_name = video_path.stem
        print(f"\n📽️ Video: {video_name}\n")
        
        # Paths
        tts_dir = Path("output/AudioOutput") / video_name
        merged_audio = tts_dir / "final_merged.wav"
        final_video = self.output_dir / f"{video_name}_final.mp4"
        
        # ===== AUTO DETECT CURRENT STEP =====
        print("🔍 Checking progress...\n")
        
        # Step 1: Check TTS files
        tts_files = sorted(tts_dir.glob("*.wav")) if tts_dir.exists() else []
        tts_files = [f for f in tts_files if not f.name.startswith("final_")]
        
        # Parse expected count
        adjuster = AudioAdjuster()
        try:
            subtitles = adjuster.parse_srt_timestamps(str(srt_path))
            expected_tts = len(subtitles)
        except:
            expected_tts = 0
        
        # Step 2: Check merged audio
        merged_exists = merged_audio.exists() and merged_audio.stat().st_size > 100000
        
        # Step 3: Check final video
        final_exists = final_video.exists() and final_video.stat().st_size > 1000000
        
        # Detect current step
        if final_exists:
            print(f"✅ Video hoàn tất: {final_video.name}")
            return True
        elif merged_exists:
            print(f"⏳ TTS: ✅ Compose: ⏳")
            print(f"   → Bắt đầu STEP 3: Compose video\n")
            current_step = 3
        elif len(tts_files) == expected_tts and expected_tts > 0:
            print(f"⏳ TTS: ✅ Merge: ⏳")
            print(f"   → Bắt đầu STEP 2: Merge audio\n")
            current_step = 2
        else:
            print(f"⏳ TTS: ⏳ Merge: ⏳")
            print(f"   → Bắt đầu STEP 1: TTS\n")
            current_step = 1
        
        # ===== EXECUTE FROM CURRENT STEP =====
        if current_step <= 1:
            print("─"*60)
            print("STEP 1: TTS - Tạo Audio AI từ SRT")
            print("─"*60)
            if not self._step_tts(srt_path, tts_dir):
                print("❌ TTS thất bại!")
                return False
        
        if current_step <= 2:
            print("\n" + "─"*60)
            print("STEP 2: Merge - Ghép tất cả audio lại")
            print("─"*60)
            if not self._step_merge_audio(srt_path, tts_dir, merged_audio, video_file):
                print("❌ Merge audio thất bại!")
                return False
        
        if current_step <= 3:
            print("\n" + "─"*60)
            print("STEP 3: Compose - Ghép video + audio + subtitle")
            print("─"*60)
            if not self._step_compose_video(video_file, str(merged_audio), srt_file, str(final_video)):
                print("❌ Compose video thất bại!")
                return False
        
        print("\n" + "="*60)
        print(f"✅ HOÀN THÀNH! Output: {final_video}")
        print("="*60 + "\n")
        return True
    
    def _step_tts(self, srt_file: Path, output_dir: Path) -> bool:
        """TTS: Tạo audio từ text trong SRT - NHANH"""
        print("🎙️ Đang tạo audio AI...")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Parse SRT để lấy số lượng subtitle
            adjuster = AudioAdjuster()
            subtitles = adjuster.parse_srt_timestamps(str(srt_file))
            
            # Kiểm tra nếu audio đã tạo xong
            expected_count = len(subtitles)
            existing_files = sorted(output_dir.glob("*.wav"))
            
            # Bỏ qua file merged
            existing_files = [f for f in existing_files if not f.name.startswith("final_")]
            
            if len(existing_files) == expected_count:
                print(f"✅ Audio đã tạo xong ({expected_count} files), bỏ qua TTS")
                return True
            elif len(existing_files) > 0:
                print(f"⚠️ Tìm thấy {len(existing_files)} file audio, nhưng cần {expected_count}")
                print(f"   Xóa các file cũ và tạo lại...")
                # Xóa các file cũ (with retry for locked files)
                import time
                for f in existing_files:
                    for attempt in range(3):
                        try:
                            f.unlink()
                            break
                        except (OSError, PermissionError):
                            if attempt < 2:
                                time.sleep(0.5)
                            else:
                                print(f"⚠️ Không xóa được {f.name} (locked)")
            
            # Init TTS
            tts = TTSGenerator(service=self.tts_service, 
                             output_dir=str(output_dir),
                             language=self.language)
            
            # Tạo audio cho từng subtitle
            items = []
            for sub in subtitles:
                items.append({
                    "text": sub["text"],
                    "filename": f"{sub['index']:04d}.wav",
                    "speed": 1.0
                })
            
            # Batch generate với tốc độ tối ưu
            results = tts.batch_generate(items, show_progress=True)
            
            # Check if TTS succeeded
            if len(results) < expected_count * 0.5:  # Less than 50% success
                print(f"⚠️ TTS thất bại quá nhiều ({len(results)}/{expected_count})")
                print(f"   Kiểm tra pyttsx3 fallback...")
                # Try one more time with pyttsx3 explicitly
                tts_fallback = TTSGenerator(service="pyttsx3", 
                                          output_dir=str(output_dir),
                                          language=self.language)
                results = tts_fallback.batch_generate(items, show_progress=False)
            
            print(f"✅ TTS xong! {len(results)}/{expected_count} files")
            return len(results) >= expected_count * 0.8  # Success if >= 80% completed
        except Exception as e:
            print(f"❌ TTS error: {str(e)[:100]}")
            return False
    
    def _step_merge_audio(self, srt_file: Path, input_dir: Path, 
                         output_file: Path, video_file: str = None) -> bool:
        """Merge tất cả audio thành 1 file dài"""
        print("🎵 Merge audio...")
        
        try:
            merger = AudioMerger()
            
            # Lấy tất cả audio files (WAV hoặc MP3) - bỏ qua final_merged
            audio_files = []
            audio_files.extend(sorted(input_dir.glob("*.wav")))
            audio_files.extend(sorted(input_dir.glob("*.mp3")))
            audio_files = [f for f in audio_files if not f.name.startswith("final_")]
            
            if not audio_files:
                print(f"❌ Không tìm audio files (WAV hoặc MP3) ở {input_dir}")
                return False
            
            # Sort by filename (0001, 0002, etc)
            audio_files = sorted(audio_files, key=lambda f: int(f.stem) if f.stem.isdigit() else f.stem)
            
            print(f"🎵 Đang merge {len(audio_files)} file audio...")
            
            success = merger.merge(
                audio_files=[str(f) for f in audio_files],
                srt_file=str(srt_file),
                output_file=str(output_file),
                video_file=video_file
            )
            
            if success:
                print(f"✅ Merge audio xong! ({len(audio_files)} files → {output_file.name})")
            return success
        except Exception as e:
            print(f"❌ Merge error: {str(e)[:100]}")
            return False
    
    def _step_compose_video(self, video_file: str, audio_file: str, 
                           srt_file: str, output_file: str) -> bool:
        """Ghép video + audio + subtitle"""
        print("🎬 Compose video...")
        
        try:
            composer = VideoComposer()
            success = composer.compose_full(
                input_video=video_file,
                audio_file=audio_file,
                srt_file=srt_file,
                output_video=output_file
            )
            return success
        except Exception as e:
            print(f"❌ Compose error: {str(e)[:100]}")
            return False
    
    def process_batch(self, video_dir: str, srt_dir: str) -> dict:
        """
        Xử lý hàng loạt video
        video_dir: thư mục chứa .mp4
        srt_dir: thư mục chứa .srt (dã dịch)
        """
        video_dir = Path(video_dir)
        srt_dir = Path(srt_dir)
        
        results = {"success": 0, "failed": 0, "files": []}
        
        # Tìm tất cả video
        videos = list(video_dir.glob("*.mp4"))
        print(f"\n🔍 Tìm thấy {len(videos)} video file(s)\n")
        
        for i, video_file in enumerate(videos, 1):
            # Tìm SRT tương ứng
            srt_file = srt_dir / f"{video_file.stem}_translated.srt"
            
            if not srt_file.exists():
                print(f"⏭️ [{i}/{len(videos)}] {video_file.name}")
                print(f"   ⚠️ SRT file không tồn tại: {srt_file.name}\n")
                results["failed"] += 1
                continue
            
            print(f"⏳ [{i}/{len(videos)}] Xử lý {video_file.name}...")
            
            if self.process_video(str(video_file), str(srt_file)):
                results["success"] += 1
                results["files"].append({
                    "video": str(video_file),
                    "srt": str(srt_file),
                    "status": "success"
                })
            else:
                results["failed"] += 1
                results["files"].append({
                    "video": str(video_file),
                    "srt": str(srt_file),
                    "status": "failed"
                })
        
        # Summary
        print(f"\n{'='*60}")
        print(f"📊 BATCH SUMMARY")
        print(f"✅ Thành công: {results['success']}")
        print(f"❌ Thất bại: {results['failed']}")
        print(f"{'='*60}\n")
        
        return results


# ==========================================
# CLI USAGE
# ==========================================
if __name__ == "__main__":
    # Tùy chỉnh config
    config = {
        "tts_service": "gtts",      # "gtts" | "google_cloud" | "pyttsx3"
        "language": "vi",
        "output_dir": "output_videos"
    }
    
    pipeline = YouTubeAutomationPipeline(config=config)
    
    # ===== OPTION 1: Xử lý 1 video =====
    if len(sys.argv) > 2:
        video_file = sys.argv[1]
        srt_file = sys.argv[2]
        pipeline.process_video(video_file, srt_file)
    
    # ===== OPTION 2: Batch process =====
    elif len(sys.argv) > 1 and sys.argv[1] == "--batch":
        results = pipeline.process_batch(
            video_dir="input/VideoInput",
            srt_dir="output/SrtOutput"
        )
    
    # ===== OPTION 3: Help =====
    else:
        print("""
        🎬 YOUTUBE AUTOMATION - FULL PIPELINE
        
        Usage:
        
        1. Process 1 video:
           python pipeline_full.py <video_file> <srt_file>
           
           Example:
           python pipeline_full.py "input/VideoInput/video.mp4" "output/SrtOutput/video_translated.srt"
        
        2. Batch process all videos in input/VideoInput:
           python pipeline_full.py --batch
        
        Notes:
        - Video file: input/VideoInput/*.mp4
        - SRT file: output/SrtOutput/*_translated.srt
        - Output: output_videos/*.mp4
        - TTS service: gtts (free), google_cloud (need credentials), pyttsx3 (local)
        """)
