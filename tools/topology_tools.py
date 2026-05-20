from __future__ import annotations

from collections import defaultdict
from typing import Any

from utils.data_loader import CSVDataLoader


SERVICE_TOPOLOGY = {
    "frontend": {
        "description": "Hipster Shop entry web service",
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
    "cartservice": {"description": "Cart application service", "dependencies": ["redis"], "type": "application"},
    "checkoutservice": {
        "description": "Checkout orchestration service",
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
        "description": "Recommendation application service",
        "dependencies": ["productcatalogservice"],
        "type": "application",
    },
    "productcatalogservice": {"description": "Product catalogue service", "dependencies": [], "type": "application"},
    "currencyservice": {"description": "Currency conversion service", "dependencies": [], "type": "application"},
    "paymentservice": {"description": "Payment service", "dependencies": [], "type": "application"},
    "shippingservice": {"description": "Shipping service", "dependencies": [], "type": "application"},
    "emailservice": {"description": "Email service", "dependencies": [], "type": "application"},
    "adservice": {"description": "Advertisement service", "dependencies": [], "type": "application"},
    "redis": {"description": "Redis cache", "dependencies": [], "type": "middleware"},
    "main": {"description": "Infrastructure node", "dependencies": [], "type": "infrastructure"},
    "front-end": {
        "description": "Sock Shop entry web service",
        "dependencies": ["carts", "catalogue", "orders", "payment", "shipping", "user"],
        "type": "web",
    },
    "carts": {"description": "Shopping cart application service", "dependencies": ["carts-db"], "type": "application"},
    "orders": {
        "description": "Order management application service",
        "dependencies": ["orders-db", "payment", "shipping", "user"],
        "type": "application",
    },
    "catalogue": {
        "description": "Product catalogue application service",
        "dependencies": ["catalogue-db"],
        "type": "application",
    },
    "user": {"description": "User account application service", "dependencies": ["user-db"], "type": "application"},
    "payment": {"description": "Payment application service", "dependencies": [], "type": "application"},
    "shipping": {"description": "Shipping application service", "dependencies": [], "type": "application"},
    "queue-master": {"description": "Queue coordination service", "dependencies": ["rabbitmq"], "type": "middleware"},
    "rabbitmq": {"description": "Message broker", "dependencies": [], "type": "middleware"},
    "rabbitmq-exporter": {
        "description": "RabbitMQ metrics exporter",
        "dependencies": ["rabbitmq"],
        "type": "infrastructure",
    },
    "carts-db": {"description": "Cart database", "dependencies": [], "type": "database"},
    "orders-db": {"description": "Order database", "dependencies": [], "type": "database"},
    "catalogue-db": {"description": "Catalogue database", "dependencies": [], "type": "database"},
    "user-db": {"description": "User database", "dependencies": [], "type": "database"},
    "session-db": {"description": "Session database", "dependencies": [], "type": "database"},
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
                    "description": f"Discovered from telemetry: {service}",
                    "dependencies": [],
                    "type": "application",
                },
            )

        reversed_graph: dict[str, list[str]] = defaultdict(list)
        for source, details in topology.items():
            for target in details.get("dependencies", []):
                reversed_graph[target].append(source)

        for service, details in topology.items():
            details["upstreams"] = sorted(reversed_graph.get(service, []))
            details["downstreams"] = sorted(details.get("dependencies", []))
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
