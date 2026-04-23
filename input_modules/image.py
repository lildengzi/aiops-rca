import os
import tempfile
from PIL import Image
import io
import pytesseract
import cv2
import numpy as np


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}


class ImageInputBackend:
    """图像输入后端 - OCR文字识别"""
    
    def analyze_chart(self, image_path, filename) -> dict:
        """识别图片中的文字内容"""
        try:
            img = Image.open(image_path)
            w, h = img.size
            
            # 预处理图像优化OCR识别
            preprocessed = self._preprocess_image(image_path)
            
            # 执行OCR识别
            text = pytesseract.image_to_string(preprocessed, lang='chi_sim+eng')
            
            # 清理文本
            clean_text = self._clean_text(text)
            
            result = {
                "filename": filename,
                "size": f"{w}x{h}",
                "text": clean_text,
                "description": clean_text
            }
            
            return result
            
        except Exception as e:
            return {"filename": filename, "error": str(e), "description": f"文字识别失败: {str(e)}"}
    
    def _preprocess_image(self, image_path) -> Image.Image:
        """图像预处理以提高OCR准确率"""
        # 使用OpenCV进行预处理
        img = cv2.imread(image_path)
        
        # 转为灰度
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 自适应阈值二值化
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # 降噪
        kernel = np.ones((1, 1), np.uint8)
        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
        
        # 转回PIL格式
        return Image.fromarray(opening)
    
    def _clean_text(self, text: str) -> str:
        """清理OCR识别的文本"""
        if not text:
            return "未识别到有效文字"
        
        # 移除多余空白行
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        
        if not lines:
            return "未识别到有效文字"
            
        return "\n".join(lines)
    
    def create_session_state(self):
        """初始化 session state"""
        return {
            "image_description": "",
            "chart_analysis": None
        }