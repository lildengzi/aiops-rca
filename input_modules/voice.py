import os
import tempfile
import subprocess
import sys


def _check_libs():
    """检查可用的语音库"""
    libs = {"av": False, "pydub": False, "sr": False}
    
    try:
        import av
        libs["av"] = True
    except Exception:
        pass
    
    try:
        from pydub import AudioSegment
        libs["pydub"] = True
    except Exception:
        pass
    
    try:
        import speech_recognition as sr
        libs["sr"] = True
    except Exception:
        pass
    
    return libs


LIBS = _check_libs()


class VoiceInputBackend:
    """语音输入后端"""
    
    _model_cache = None
    
    @classmethod
    def get_whisper_model(cls):
        """获取 Whisper 模型（带缓存）"""
        if cls._model_cache is not None:
            return cls._model_cache
        
        if not LIBS["av"]:
            return None
        
        try:
            from faster_whisper import WhisperModel
            cls._model_cache = WhisperModel("base", device="cpu", compute_type="int8")
            return cls._model_cache
        except Exception as e:
            return None
    
    def transcribe_with_faster_whisper(self, audio_path) -> str:
        """使用 faster-whisper 转写"""
        if not LIBS["av"]:
            return None
        
        try:
            model = self.get_whisper_model()
            if model is None:
                return None
            
            segments, _ = model.transcribe(audio_path, beam_size=5)
            text_parts = [seg.text for seg in segments if seg.text]
            return "".join(text_parts).strip()
        except Exception:
            return None
    
    def transcribe_with_pydub(self, audio_path) -> str:
        """使用 pydub + speech_recognition 转写"""
        if not (LIBS["pydub"] and LIBS["sr"]):
            return None
        
        try:
            from pydub import AudioSegment
            import speech_recognition as sr
            
            sound = AudioSegment.from_file(audio_path)
            sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            
            tmp_wav = audio_path.rsplit(".", 1)[0] + "_16k.wav"
            sound.export(tmp_wav, format="wav")
            
            recognizer = sr.Recognizer()
            with sr.AudioFile(tmp_wav) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data, language="zh-CN")
            
            os.unlink(tmp_wav)
            return text if text else None
        except Exception:
            return None
    
    def transcribe_with_whisper_cli(self, audio_path) -> str:
        """使用 whisper CLI（备选方案）"""
        try:
            if not os.path.exists(audio_path):
                return None
            
            try:
                from pydub import AudioSegment
                sound = AudioSegment.from_file(audio_path)
                tmp_wav = audio_path.rsplit(".", 1)[0] + "_16k.wav"
                sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                sound.export(tmp_wav, format="wav")
            except Exception:
                tmp_wav = audio_path.replace(".webm", ".wav")
            
            result = subprocess.run(
                ["whisper", "-f", "txt", "--model", "base", tmp_wav],
                capture_output=True, text=True, timeout=120
            )
            
            if tmp_wav != audio_path and os.path.exists(tmp_wav):
                os.unlink(tmp_wav)
            
            return result.stdout.strip() if result.stdout else None
        except Exception:
            return None
    
    def check_dependencies(self) -> dict:
        """检查依赖状态"""
        issues = []
        
        if not LIBS["av"]:
            issues.append(f"faster-whisper需要av库（Python {sys.version_info.major}.{sys.version_info.minor} Windows DLL不兼容���")
        
        return {
            "av_available": LIBS["av"],
            "pydub_available": LIBS["pydub"],
            "sr_available": LIBS["sr"],
            "issues": issues if issues else None,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        }
    
    def process_audio(self, audio_bytes: bytes) -> dict:
        """处理音频字节"""
        if not audio_bytes:
            return {"success": False, "error": "音频数据为空"}
        
        deps = self.check_dependencies()
        if deps["issues"]:
            return {
                "success": False, 
                "error": "语音功能暂不可用（Python " + deps["python_version"] + " Windows兼容性限制）\n请使用文本输入。"
            }
        
        audio_path = None
        try:
            suffix = ".webm"
            if b"RIFF" in audio_bytes[:4]:
                suffix = ".wav"
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode="wb") as tmp:
                tmp.write(audio_bytes)
                audio_path = tmp.name
            
            methods = [
                self.transcribe_with_faster_whisper,
                self.transcribe_with_pydub,
                self.transcribe_with_whisper_cli,
            ]
            
            for method in methods:
                text = method(audio_path)
                if text:
                    return {"success": True, "text": text}
            
            return {"success": False, "error": "识别失败，请使用文本输入"}

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