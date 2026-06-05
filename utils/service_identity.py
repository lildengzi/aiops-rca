from __future__ import annotations

import re


INFRASTRUCTURE_TOKENS = (
    "queue",
    "rabbitmq",
    "mongo",
    "mysql",
    "-db",
    "istio",
    "gke-",
    "ip-",
    "loadgenerator",
    "exporter",
    "dashboard",
    "redis",
    "session",
)

SERVICE_ALIASES = {
    "frontend": "front-end",
    "front": "front-end",
    "frontend-external": "front-end",
    "frontend-check": "front-end",
    "cart": "carts",
    "cartsservice": "cartservice",
    "payment-service": "paymentservice",
    "shipping-service": "shippingservice",
    "productcatalog-service": "productcatalogservice",
    "recommendation-service": "recommendationservice",
    "currency-service": "currencyservice",
    "email-service": "emailservice",
    "checkout-service": "checkoutservice",
}


def normalize_service_name(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = text.split(".")[0]
    text = text.replace("_", "-")
    text = re.sub(r"-[0-9a-f]{6,}(?:-[a-z0-9]+)?$", "", text)
    text = re.sub(r"-(?=[a-z0-9]*\d)[a-z0-9]{5,}$", "", text)
    return SERVICE_ALIASES.get(text, text)


def is_infrastructure_service(service: str) -> bool:
    text = normalize_service_name(service)
    return any(token in text for token in INFRASTRUCTURE_TOKENS)


def services_equivalent(left: str | None, right: str | None) -> bool:
    left_norm = normalize_service_name(left or "")
    right_norm = normalize_service_name(right or "")
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    pairs = {
        frozenset(("carts", "cartservice")),
        frozenset(("payment", "paymentservice")),
        frozenset(("shipping", "shippingservice")),
        frozenset(("catalogue", "productcatalogservice")),
    }
    return frozenset((left_norm, right_norm)) in pairs
