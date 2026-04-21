"""
Audio Adjuster: Điều chỉnh tốc độ audio để vừa khít với timestamp SRT
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

try:
    import librosa
    import soundfile as sf
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False


class AudioAdjuster:
    """Điều chỉnh âm thanh để vừa với thời lượng cần thiết"""
    
    def __init__(self):
        self.support_speed = LIBROSA_AVAILABLE or PYDUB_AVAILABLE
        if not self.support_speed:
            print("⚠️ Cảnh báo: librosa hoặc pydub không được cài đặt!")
            print("   pip install pydub librosa soundfile")
    
    def parse_srt_timestamps(self, srt_file: str) -> List[Dict]:
        """
        Parse file SRT để lấy (index, duration, text)
        Return: [
            {"index": 1, "start": "00:00:00,000", "end": "00:00:10,000", 
             "duration_ms": 10000, "text": "Lời thoại"},
            ...
        ]
        """
        items = []
        
        with open(srt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Regex: bắt (index, timestamp, text)
        pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\n([\s\S]*?)(?=\n\n|\Z)'
        matches = re.findall(pattern, content)
        
        for idx, start, end, text in matches:
            duration_ms = self._timecode_to_ms(end) - self._timecode_to_ms(start)
            items.append({
                "index": int(idx),
                "start": start,
                "end": end,
                "duration_ms": duration_ms,
                "text": text.strip()
            })
        
        print(f"✅ Parse {len(items)} subtitle từ {Path(srt_file).name}")
        return items
    
    def _timecode_to_ms(self, timecode: str) -> int:
        """Chuyển "00:00:10,500" thành milliseconds"""
        # Format: HH:MM:SS,mmm
        match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', timecode)
        if match:
            h, m, s, ms = map(int, match.groups())
            return h*3600000 + m*60000 + s*1000 + ms
        return 0
    
    def adjust_audio_speed(self, audio_path: str, target_duration_ms: int, 
                          output_path: str) -> bool:
        """
        Điều chỉnh tốc độ audio để vừa khít với thời lượng mục tiêu
        
        audio_path: file audio gốc
        target_duration_ms: thời lượng mục tiêu (ms)
        output_path: file output
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if LIBROSA_AVAILABLE:
                return self._adjust_librosa(audio_path, target_duration_ms, output_path)
            elif PYDUB_AVAILABLE:
                return self._adjust_pydub(audio_path, target_duration_ms, output_path)
            else:
                print("❌ Không có library điều chỉnh audio!")
                return False
        except Exception as e:
            print(f"❌ Lỗi điều chỉnh audio: {str(e)[:100]}")
            return False
    
    def _adjust_librosa(self, audio_path: str, target_duration_ms: int, 
                       output_path: Path) -> bool:
        """Dùng librosa để thay đổi speed"""
        try:
            # Load audio
            y, sr = librosa.load(audio_path, sr=None)
            current_duration_ms = len(y) / sr * 1000
            
            # Tính speed factor
            speed_factor = current_duration_ms / target_duration_ms
            
            # Thay đổi speed
            y_stretched = librosa.effects.time_stretch(y, rate=speed_factor)
            
            # Save
            sf.write(str(output_path), y_stretched, sr)
            
            print(f"✅ Librosa: {Path(audio_path).name} -> {output_path.name} "
                  f"({current_duration_ms:.0f}ms -> {target_duration_ms}ms, "
                  f"speed {speed_factor:.2f}x)")
            return True
        except Exception as e:
            print(f"❌ Librosa error: {e}")
            return False
    
    def _adjust_pydub(self, audio_path: str, target_duration_ms: int, 
                     output_path: Path) -> bool:
        """Dùng pydub để thay đổi speed"""
        try:
            # Load audio (tự detect format)
            audio = AudioSegment.from_file(audio_path)
            current_duration_ms = len(audio)
            
            # Tính speed factor
            speed_factor = current_duration_ms / target_duration_ms
            
            # pydub: speedup/slowdown
            if speed_factor > 1.0:
                # Cần nhanh lên
                audio_adjusted = audio.speedup(playback_speed=speed_factor)
            else:
                # Cần chậm lại (nhưng pydub khó hơn)
                audio_adjusted = audio._spawn(
                    audio.raw_data,
                    overrides={"frame_rate": int(audio.frame_rate * speed_factor)}
                ).set_frame_rate(audio.frame_rate)
            
            # Export
            audio_adjusted.export(str(output_path), format="wav")
            
            print(f"✅ Pydub: {Path(audio_path).name} -> {output_path.name} "
                  f"({current_duration_ms}ms -> {target_duration_ms}ms, "
                  f"speed {speed_factor:.2f}x)")
            return True
        except Exception as e:
            print(f"❌ Pydub error: {e}")
            return False
    
    def batch_adjust(self, srt_file: str, audio_dir: str, output_dir: str) -> List[str]:
        """
        Điều chỉnh tất cả audio theo file SRT
        
        srt_file: file SRT (chứa timing info)
        audio_dir: thư mục chứa audio gốc (0001.wav, 0002.wav, ...)
        output_dir: thư mục output
        """
        # Parse SRT
        subtitles = self.parse_srt_timestamps(srt_file)
        
        audio_dir = Path(audio_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        adjusted_files = []
        print(f"⏱️ Điều chỉnh timing {len(subtitles)} audio files...")
        
        for sub in subtitles:
            idx = sub["index"]
            duration_ms = sub["duration_ms"]
            
            # Tìm file audio tương ứng
            audio_file = audio_dir / f"{idx:04d}.wav"
            if not audio_file.exists():
                print(f"⚠️ Không tìm: {audio_file.name}")
                continue
            
            output_file = output_dir / f"{idx:04d}_adjusted.wav"
            
            if self.adjust_audio_speed(str(audio_file), duration_ms, str(output_file)):
                adjusted_files.append(str(output_file))
        
        print(f"\n✅ Điều chỉnh {len(adjusted_files)}/{len(subtitles)} file thành công")
        return adjusted_files


# ==========================================
# STANDALONE USAGE
# ==========================================
if __name__ == "__main__":
    adjuster = AudioAdjuster()
    
    # Parse SRT
    subs = adjuster.parse_srt_timestamps("input/SrtInput/video.srt")
    
    # Batch adjust
    files = adjuster.batch_adjust(
        srt_file="input/SrtInput/video.srt",
        audio_dir="output/AudioOutput",
        output_dir="output/AudioOutput/adjusted"
    )
