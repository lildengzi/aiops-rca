
import os
from dotenv import load_dotenv

load_dotenv()

LLM_CONFIG = {
    "api_key": os.getenv("OPENAI_API_KEY", "9825eed2-e8d8-40a6-8fd1-cfeb016a086e"),
    "base_url": os.getenv("OPENAI_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
    "model": os.getenv("LLM_MODEL", "doubao-seed-2-0-code-preview-260215"),
    "temperature": 0.1,
    "max_tokens": 4096,
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# 经验库：离线样例数据（用于离线分析和知识参考）
FAULT_DATA_MAP = {
    "cpu": os.path.join(DATA_DIR, "data1.csv"),
    "delay": os.path.join(DATA_DIR, "data2.csv"),
    "disk": os.path.join(DATA_DIR, "data3.csv"),
    "loss": os.path.join(DATA_DIR, "data4.csv"),
    "mem": os.path.join(DATA_DIR, "data5.csv"),
}

# 实时数据目录：simulator 生成的实时监测数据写入此目录
REALTIME_DATA_DIR = os.path.join(os.path.dirname(__file__), "realtime_data")


SERVICE_TOPOLOGY = {
    "frontend": {
        "description": "前端Web服务，接收所有用户请求",
        "dependencies": [
            "adservice", "cartservice", "checkoutservice",
            "currencyservice", "productcatalogservice",
            "recommendationservice", "shippingservice"
        ],
        "type": "web",
    },
    "cartservice": {
        "description": "购物车服务，管理用户购物车",
        "dependencies": ["redis"],
        "type": "application",
    },
    "checkoutservice": {
        "description": "结算服务，处理订单结算流程",
        "dependencies": [
            "cartservice", "currencyservice", "emailservice",
            "paymentservice", "productcatalogservice", "shippingservice"
        ],
        "type": "application",
    },
    "recommendationservice": {
        "description": "推荐服务，为用户提供商品推荐",
        "dependencies": ["productcatalogservice"],
        "type": "application",
    },
    "productcatalogservice": {
        "description": "商品目录服务，管理商品信息",
        "dependencies": [],
        "type": "application",
    },
    "currencyservice": {
        "description": "货币转换服务",
        "dependencies": [],
        "type": "application",
    },
    "paymentservice": {
        "description": "支付服务，处理支付请求",
        "dependencies": [],
        "type": "application",
    },
    "shippingservice": {
        "description": "物流服务，计算运费和物流信息",
        "dependencies": [],
        "type": "application",
    },
    "emailservice": {
        "description": "邮件服务，发送订单确认邮件",
        "dependencies": [],
        "type": "application",
    },
    "adservice": {
        "description": "广告服务，提供广告内容",
        "dependencies": [],
        "type": "application",
    },
    "redis": {
        "description": "Redis缓存，为购物车服务提供数据存储",
        "dependencies": [],
        "type": "middleware",
    },
    "main": {
        "description": "主节点/基础设施节点",
        "dependencies": [],
        "type": "infrastructure",
    },
}

ANOMALY_CONFIG = {
    "z_score_threshold": 3.0,       # Z-Score 异常阈值
    "window_size": 60,              # 滑动窗口大小（秒）
    "min_anomaly_duration": 10,     # 最小异常持续时间（秒）
    "correlation_threshold": 0.7,   # 相关性阈值
}

WORKFLOW_CONFIG = {
    "max_iterations": 5,            # 最大 ReAct 迭代次数
    "convergence_threshold": 0.8,   # 收敛置信度阈值
}

METRIC_CATEGORIES = {
    "resource": ["cpu", "mem"],
    "performance": ["latency", "latency-50", "latency-90"],
    "traffic": ["load", "workload"],
    "error": ["error"],
}

