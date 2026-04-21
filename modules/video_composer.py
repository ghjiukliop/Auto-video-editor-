"""
Video Composer: Lồng audio + phụ đề vào video gốc
Xóa audio gốc, thêm audio AI, thêm phụ đề Việt
"""

from pathlib import Path
import subprocess
import json
import re
import threading
from tqdm import tqdm

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class VideoComposer:
    """Ghép video + audio + subtitle"""
    
    def __init__(self):
        # Kiểm tra ffmpeg
        self.ffmpeg_available = self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> bool:
        """Kiểm tra ffmpeg có sẵn không"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _get_video_duration_seconds(self, video_file: str) -> float:
        """Lấy thời lượng video (giây)"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1:noprint_wrappers=1',
                video_file
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return float(result.stdout.strip())
        except:
            return 0.0
    
    def _parse_ffmpeg_time(self, time_str: str) -> float:
        """
        Parse thời gian từ ffmpeg output (HH:MM:SS.ms)
        Return: giây (float)
        """
        try:
            parts = time_str.split(':')
            if len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
                return hours * 3600 + minutes * 60 + seconds
            return 0.0
        except:
            return 0.0
    
    def _run_ffmpeg_with_progress(self, cmd: list, total_duration: float, 
                                 task_name: str = "Processing") -> bool:
        """
        Chạy ffmpeg command với progress bar có phần trăm
        
        Args:
            cmd: ffmpeg command list
            total_duration: tổng thời lượng video (giây)
            task_name: tên task để hiển thị trên progress bar
            
        Return:
            True nếu thành công, False nếu thất bại
        """
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            # Parse output từ ffmpeg (stderr) với progress bar tùy chỉnh
            progress_bar = tqdm(
                total=total_duration,
                unit='s',
                unit_scale=True,
                desc=task_name,
                leave=True,
                bar_format='{desc} | {percentage:3.0f}% [{bar}] {n_fmt}/{total_fmt} | {elapsed}<{remaining}'
            )
            
            current_time = 0.0
            
            def read_stderr():
                """Đọc stderr trong thread riêng để tránh blocking"""
                try:
                    for line in process.stderr:
                        # Tìm pattern: time=HH:MM:SS.ms
                        time_match = re.search(r'time=(\d+:\d+:\d+\.\d+)', line)
                        if time_match:
                            time_str = time_match.group(1)
                            parsed_time = self._parse_ffmpeg_time(time_str)
                            # Cập nhật progress bar với delta thời gian
                            delta = parsed_time - progress_bar.n
                            if delta > 0:
                                progress_bar.update(delta)
                except:
                    pass
            
            # Chạy stderr reading trong thread riêng
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()
            
            # Đợi process hoàn thành (timeout 3600 giây = 1 giờ)
            process.wait(timeout=3600)
            stderr_thread.join(timeout=5)
            
            progress_bar.close()
            
            return process.returncode == 0
            
        except subprocess.TimeoutExpired:
            print(f"❌ FFmpeg timeout (>1 giờ)")
            process.kill()
            return False
        except Exception as e:
            print(f"❌ Lỗi chạy ffmpeg: {str(e)[:100]}")
            try:
                process.kill()
            except:
                pass
            return False
    
    def remove_audio(self, input_video: str, output_video: str) -> bool:
        """Xóa audio gốc từ video"""
        if not self.ffmpeg_available:
            print("❌ ffmpeg không được cài đặt!")
            return False
        
        file_name = Path(input_video).name
        print(f"\n🎬 Xóa audio gốc: {file_name}")
        
        # Lấy duration để show progress bar
        duration = self._get_video_duration_seconds(input_video)
        
        cmd = [
            'ffmpeg',
            '-i', input_video,
            '-c:v', 'copy',
            '-an',  # Xóa audio
            '-y',
            output_video
        ]
        
        try:
            if duration > 0:
                print(f"   ⏱️  Thời lượng video: {duration:.1f} giây")
                success = self._run_ffmpeg_with_progress(cmd, duration, "🎬 Xóa audio")
            else:
                # Fallback: chạy mà không có progress bar
                print("   ⚠️  Không thể lấy thời lượng, xử lý mà không progress bar...")
                result = subprocess.run(cmd, capture_output=True, check=True, timeout=300)
                success = True
            
            if success:
                print(f"✅ Xóa audio xong: {Path(output_video).name}\n")
            return success
        except Exception as e:
            print(f"❌ Lỗi xóa audio: {str(e)[:100]}\n")
            return False
    
    def add_audio(self, video_no_audio: str, audio_file: str, 
                 output_video: str) -> bool:
        """Thêm audio vào video (có progress bar với phần trăm)"""
        if not self.ffmpeg_available:
            print("❌ ffmpeg không được cài đặt!")
            return False
        
        file_name = Path(audio_file).name
        print(f"\n🎵 Thêm audio AI: {file_name}")
        
        # Lấy duration để show progress bar
        duration = self._get_video_duration_seconds(video_no_audio)
        
        cmd = [
            'ffmpeg',
            '-i', video_no_audio,
            '-i', audio_file,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-y',
            output_video
        ]
        
        try:
            if duration > 0:
                print(f"   ⏱️  Thời lượng video: {duration:.1f} giây")
                success = self._run_ffmpeg_with_progress(cmd, duration, "🎵 Lồng audio")
            else:
                # Fallback: chạy mà không có progress bar
                print("   ⚠️  Không thể lấy thời lượng, xử lý mà không progress bar...")
                result = subprocess.run(cmd, capture_output=True, check=True, timeout=300)
                success = True
            
            if success:
                print(f"✅ Thêm audio xong: {Path(output_video).name}\n")
            return success
        except Exception as e:
            print(f"❌ Lỗi thêm audio: {str(e)[:100]}\n")
            return False
    
    def add_subtitle(self, video_with_audio: str, srt_file: str, 
                    output_video: str) -> bool:
        """Thêm phụ đề (subtitle) vào video (có progress bar với phần trăm)"""
        if not self.ffmpeg_available:
            print("❌ ffmpeg không được cài đặt!")
            return False
        
        file_name = Path(srt_file).name
        print(f"\n📝 Thêm phụ đề: {file_name}")
        
        try:
            # Lấy duration để show progress bar
            duration = self._get_video_duration_seconds(video_with_audio)
            
            if duration > 0:
                print(f"   ⏱️  Thời lượng video: {duration:.1f} giây")
            else:
                print("   ⚠️  Không thể lấy thời lượng, xử lý mà không progress bar...")
            
            # Convert path to forward slashes for ffmpeg (required on Windows)
            srt_path = Path(srt_file).resolve()
            srt_path_str = str(srt_path).replace('\\', '/')
            
            # ffmpeg filter để add subtitle
            # Format: subtitles=path/to/file.srt (không dùng quotes)
            cmd = [
                'ffmpeg',
                '-i', video_with_audio,
                '-vf', f"subtitles={srt_path_str}",
                '-c:a', 'copy',
                '-y',
                output_video
            ]
            
            if duration > 0:
                result = self._run_ffmpeg_with_progress(cmd, duration, "📝 Thêm phụ đề")
            else:
                # Fallback: chạy mà không có progress bar
                result = subprocess.run(cmd, capture_output=True, check=False, timeout=300)
                result = result.returncode == 0
            
            if result:
                print(f"✅ Thêm phụ đề xong: {Path(output_video).name}\n")
                return True
            else:
                error_msg = "Không thể thêm phụ đề với ffmpeg filter"
                print(f"❌ {error_msg}")
                
                # Fallback: Copy video mà không phụ đề
                print("⚠️  Fallback: Không thêm phụ đề, chỉ copy video...")
                cmd_copy = [
                    'ffmpeg',
                    '-i', video_with_audio,
                    '-c', 'copy',
                    '-y',
                    output_video
                ]
                
                if duration > 0:
                    success = self._run_ffmpeg_with_progress(cmd_copy, duration, "📋 Copy video")
                else:
                    result_copy = subprocess.run(cmd_copy, capture_output=True, check=True, timeout=300)
                    success = True
                    
                if success:
                    print(f"✅ Video (không phụ đề): {Path(output_video).name}\n")
                return success
        except Exception as e:
            print(f"❌ Lỗi thêm phụ đề: {str(e)[:100]}\n")
            return False
    
    def compose_full(self, input_video: str, audio_file: str, srt_file: str, 
                    output_video: str) -> bool:
        """
        Quy trình hoàn chỉnh (có progress bars với phần trăm):
        1. Xóa audio gốc
        2. Thêm audio AI
        3. Thêm phụ đề
        """
        print("\n" + "="*70)
        print("🎬 BẮT ĐẦU COMPOSE VIDEO (HỖ TRỢ TIẾN ĐỘ PHẦn TRĂM)")
        print("="*70)
        
        try:
            # Kiểm tra files tồn tại
            if not Path(input_video).exists():
                raise FileNotFoundError(f"Video input không tồn tại: {input_video}")
            if not Path(audio_file).exists():
                raise FileNotFoundError(f"Audio file không tồn tại: {audio_file}")
            if not Path(srt_file).exists():
                raise FileNotFoundError(f"SRT file không tồn tại: {srt_file}")
            
            # Lấy thông tin video
            input_path = Path(input_video)
            video_duration = self._get_video_duration_seconds(str(input_video))
            
            print(f"\n📁 Input video: {input_path.name}")
            print(f"📊 Thời lượng: {video_duration:.1f} giây ({video_duration/60:.1f} phút)")
            print(f"🎵 Audio: {Path(audio_file).name}")
            print(f"📝 Phụ đề: {Path(srt_file).name}")
            print(f"\n{'='*70}\n")
            
            output_video = Path(output_video)
            output_video.parent.mkdir(parents=True, exist_ok=True)
            
            # Temp file
            temp_no_audio = output_video.parent / f"{output_video.stem}_no_audio.mp4"
            temp_with_audio = output_video.parent / f"{output_video.stem}_with_audio.mp4"
            
            # Overall progress tracker
            steps = ["Xóa audio gốc", "Lồng audio AI", "Thêm phụ đề"]
            with tqdm(total=len(steps), desc="📊 TỔNG TIẾN ĐỘ", unit="bước", 
                     bar_format='{desc} | {n_fmt}/{total_fmt} [{bar}] {percentage:3.0f}%') as pbar:
                # Step 1: Xóa audio
                print(f"[BƯỚC 1/3] {steps[0]}")
                print("-" * 70)
                if not self.remove_audio(str(input_video), str(temp_no_audio)):
                    raise Exception("Xóa audio thất bại")
                pbar.update(1)
                
                # Step 2: Thêm audio
                print(f"\n[BƯỚC 2/3] {steps[1]}")
                print("-" * 70)
                if not self.add_audio(str(temp_no_audio), audio_file, str(temp_with_audio)):
                    raise Exception("Thêm audio thất bại")
                pbar.update(1)
                
                # Step 3: Thêm subtitle
                print(f"\n[BƯỚC 3/3] {steps[2]}")
                print("-" * 70)
                if not self.add_subtitle(str(temp_with_audio), srt_file, str(output_video)):
                    raise Exception("Thêm phụ đề thất bại")
                pbar.update(1)
            
            # Clean up temp
            temp_no_audio.unlink(missing_ok=True)
            temp_with_audio.unlink(missing_ok=True)
            
            print(f"\n{'='*70}")
            print(f"✅ ✨ VIDEO HOÀN THÀNH THÀNH CÔNG! ✨")
            print(f"{'='*70}")
            print(f"📁 Output: {output_video}")
            print(f"📊 Tổng thời gian: ~{video_duration/60:.1f} phút")
            print(f"{'='*70}\n")
            return True
            
        except Exception as e:
            print(f"\n{'='*70}")
            print(f"🔥 LỖI: {str(e)}")
            print(f"{'='*70}\n")
            return False
    
    def get_video_duration(self, video_file: str) -> float:
        """
        Lấy thời lượng video (giây)
        Public wrapper - backward compatible
        """
        return self._get_video_duration_seconds(video_file)


# ==========================================
# STANDALONE USAGE
# ==========================================
if __name__ == "__main__":
    composer = VideoComposer()
    
    # Example
    composer.compose_full(
        input_video="input/VideoInput/video.mp4",
        audio_file="output/AudioOutput/final_merged.wav",
        srt_file="output/SrtOutput/video_translated.srt",
        output_video="output_videos/video_final.mp4"
    )
