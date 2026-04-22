import os
import tempfile
from PIL import Image
import io
import numpy as np


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}


class ImageInputBackend:
    """图像/图表输入后端 - 纯业务逻辑"""
    
    def analyze_chart(self, image_path, filename) -> dict:
        """分析图表图像"""
        try:
            img = Image.open(image_path)
            img_rgb = img.convert("RGB")
            w, h = img_rgb.size
            pixels = np.array(img_rgb)
            
            result = {
                "filename": filename,
                "size": f"{w}x{h}",
                "chart_type": "unknown",
                "data_points": [],
                "trend": "unknown",
                "max_value": 0,
                "min_value": 0,
                "avg_value": 0,
                "description": ""
            }
            
            chart_type = self._detect_chart_type(pixels, w, h)
            result["chart_type"] = chart_type
            
            if chart_type == "bar":
                data = self._analyze_bar(pixels, w, h)
            else:
                data = self._analyze_line(pixels, w, h)
            
            result.update(data)
            result["description"] = self._generate_desc(result)
            
            return result
            
        except Exception as e:
            return {"filename": filename, "error": str(e), "description": f"分析失败: {str(e)}"}
    
    def _detect_chart_type(self, pixels, w, h) -> str:
        gray = np.mean(pixels, axis=2)
        bar_score = 0
        line_score = 0
        for i in range(w // 20):
            if i * 10 < w:
                diff = np.abs(np.diff(gray[:, i * 10]))
                if np.any(diff > 30):
                    bar_score += 1
        for i in range(h // 20):
            if i * 10 < h:
                diff = np.abs(np.diff(gray[i * 10, :]))
                if np.any(diff > 30):
                    line_score += 1
        return "bar" if bar_score > line_score else "line"
    
    def _analyze_bar(self, pixels, w, h) -> dict:
        gray = np.mean(pixels, axis=2)
        ml, mr = int(w * 0.1), int(w * 0.95)
        mt, mb = int(h * 0.1), int(h * 0.9)
        chart = gray[mt:mb, ml:mr]
        
        bw = chart.shape[1] // 10
        heights = []
        for i in range(10):
            region = chart[:, i * bw:(i + 1) * bw]
            if region.size == 0:
                heights.append(0)
                continue
            bar_bottom = region[region.shape[0] - 5:, :]
            avg_bottom = np.mean(bar_bottom)
            top_idx = np.where(region < avg_bottom * 0.9)
            bar_h = region.shape[0] - np.min(top_idx[0]) if len(top_idx[0]) > 0 else 0
            heights.append(bar_h)
        
        heights = np.array(heights)
        max_h = np.max(heights) + 1
        if max_h > 0:
            heights = heights / max_h * 100
        
        return self._make_data_result(heights)
    
    def _analyze_line(self, pixels, w, h) -> dict:
        gray = np.mean(pixels, axis=2).astype(float)
        ml, mr = int(w * 0.1), int(w * 0.95)
        mt, mb = int(h * 0.1), int(h * 0.9)
        chart = gray[mt:mb, ml:mr]
        
        values = []
        for i in range(10):
            x = int(chart.shape[1] * (i + 0.5) / 10)
            if x < chart.shape[1]:
                col = chart[:, x]
                nonzero = col[col < 250]
                if len(nonzero) > 0:
                    y = np.argmin(nonzero)
                    values.append((1 - y / len(col)) * 100)
                else:
                    values.append(0)
        
        while len(values) < 10:
            values.insert(0, 0)
        
        values = np.array(values[:10])
        return self._make_data_result(values)
    
    def _make_data_result(self, values) -> dict:
        return {
            "y_axis": "数值",
            "data_points": [{"time": f"t-{9-i}", "value": round(float(v), 1)} for i, v in enumerate(values)],
            "max_value": round(float(np.max(values)), 1),
            "min_value": round(float(np.min(values)), 1),
            "avg_value": round(float(np.mean(values)), 1),
            "trend": self._get_trend(values)
        }
    
    def _get_trend(self, values) -> str:
        if len(values) < 2:
            return "unknown"
        first = np.mean(values[:len(values)//2])
        second = np.mean(values[len(values)//2:])
        diff = second - first
        if abs(diff) < 10:
            return "stable"
        return "increasing" if diff > 0 else "decreasing"
    
    def _generate_desc(self, analysis) -> str:
        if "error" in analysis:
            return analysis["description"]
        
        parts = [
            f"文件: {analysis['filename']}",
            f"类型: {analysis['chart_type']}",
            f"X轴: 时间戳",
            f"Y轴: {analysis['y_axis']}"
        ]
        
        if analysis["data_points"]:
            pts = ", ".join([f"{p['time']}:{p['value']}" for p in analysis["data_points"][:5]])
            parts.append(f"数据: [{pts}]")
        
        if analysis["max_value"]:
            parts.append(f"最大值: {analysis['max_value']}")
            parts.append(f"趋势: {analysis['trend']}")
        
        return "[图表分析] " + ", ".join(parts) + "."
    
    def create_session_state(self):
        """初始化 session state"""
        return {
            "image_description": "",
            "chart_analysis": None
        }