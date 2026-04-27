from __future__ import annotations

from collections import defaultdict
from typing import Any

from utils.data_loader import CSVDataLoader

SERVICE_TOPOLOGY = {
    "frontend": {
        "description": "前端Web服务，接收所有用户请求",
        "dependencies": [
            "adservice",
            "cartservice",
            "checkoutservice",
            "currencyservice",
            "productcatalogservice",
            "recommendationservice",
            "shippingservice",
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
            "cartservice",
            "currencyservice",
            "emailservice",
            "paymentservice",
            "productcatalogservice",
            "shippingservice",
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


class TopologyToolbox:
    def __init__(self, loader: CSVDataLoader):
        self.loader = loader

    def get_topology_details(self) -> dict[str, dict[str, Any]]:
        metadata = self.loader.get_metadata()
        services = metadata["services"]
        topology = {
            service: {
                "description": details["description"],
                "dependencies": list(details["dependencies"]),
                "type": details["type"],
            }
            for service, details in SERVICE_TOPOLOGY.items()
        }
        for service in services:
            topology.setdefault(
                service,
                {
                    "description": f"Discovered from CSV telemetry: {service}",
                    "dependencies": [],
                    "type": "application",
                },
            )
        return topology

    def get_full_topology(self) -> dict[str, list[str]]:
        topology_details = self.get_topology_details()
        return {
            service: list(details.get("dependencies", []))
            for service, details in topology_details.items()
        }

    def reverse_topology(self) -> dict[str, list[str]]:
        topology = self.get_full_topology()
        reversed_graph: dict[str, list[str]] = defaultdict(list)
        for source, targets in topology.items():
            reversed_graph.setdefault(source, [])
            for target in targets:
                reversed_graph[target].append(source)
        return dict(reversed_graph)
