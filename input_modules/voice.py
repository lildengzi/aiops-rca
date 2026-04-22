import os
import tempfile
import subprocess


class VoiceInputBackend:
    """语音输入后端 - 纯业务逻辑"""
    
    _model_cache = None
    
    @classmethod
    def get_whisper_model(cls):
        """获取 Whisper 模型（带缓存）"""
        if cls._model_cache is not None:
            return cls._model_cache
        
        try:
            from faster_whisper import WhisperModel
            cls._model_cache = WhisperModel("base", device="cpu", compute_type="int8")
            return cls._model_cache
        except ImportError:
            return None
        except Exception:
            return None
    
    def transcribe_with_faster_whisper(self, audio_path) -> str:
        """使用 faster-whisper 转写"""
        try:
            model = self.get_whisper_model()
            if model is None:
                return None
            
            segments, _ = model.transcribe(audio_path, beam_size=5)
            text_parts = [seg.text for seg in segments if seg.text]
            return "".join(text_parts).strip()
        except Exception:
            return None
    
    def transcribe_with_ffmpeg(self, audio_path) -> str:
        """使用 ffmpeg + whisper 转写（备选方案）"""
        try:
            tmp_wav = audio_path.replace(".webm", "_conv.wav").replace(".m4a", "_conv.wav")
            
            subprocess.run(
                ["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", tmp_wav],
                capture_output=True, timeout=30
            )
            
            if not os.path.exists(tmp_wav):
                return None
            
            try:
                result = subprocess.run(
                    ["whisper", "-f", "txt", "--model", "base", tmp_wav],
                    capture_output=True, text=True, timeout=60
                )
                os.unlink(tmp_wav)
                return result.stdout.strip() if result.stdout else None
            except Exception:
                return None
                
        except Exception:
            return None
    
    def process_audio(self, audio_bytes: bytes) -> dict:
        """处理音频字节"""
        if not audio_bytes:
            return {"success": False, "error": "音频数据为空"}
        
        audio_path = None
        try:
            suffix = ".webm"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode="wb") as tmp:
                tmp.write(audio_bytes)
                audio_path = tmp.name
            
            for method in [self.transcribe_with_faster_whisper, self.transcribe_with_ffmpeg]:
                text = method(audio_path)
                if text:
                    return {"success": True, "text": text}
            
            return {"success": False, "error": "未能识别语音，请确保已安装 faster-whisper: pip install faster-whisper"}
                    
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if audio_path and os.path.exists(audio_path):
                try:
                    os.unlink(audio_path)
                except Exception:
                    pass
    
    def create_session_state(self):
        return {"voice_text": "", "voice_pending": False}