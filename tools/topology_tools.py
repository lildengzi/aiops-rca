"""
拓扑感知工具 - 模拟 CMDB MCP 服务
提供服务依赖关系、架构拓扑等信息
"""
import json
from langchain_core.tools import tool
from config import SERVICE_TOPOLOGY


@tool
def lookup_service_topology(service_name: str) -> str:
    """\brief 查询指定服务的拓扑信息（依赖关系与服务描述）
    \param service_name 服务名称
    \return JSON 字符串，包含:
        - description: 服务描述
        - type: 服务类型
        - dependencies: 下游依赖服务列表
        - upstream_services: 上游调用方列表
        - 或错误信息（当服务不在 CMDB 时）"""
    if service_name not in SERVICE_TOPOLOGY:
        return json.dumps({
            "status": "failure",
            "error_message": f"服务 {service_name} 不在CMDB中",
            "available_services": list(SERVICE_TOPOLOGY.keys()),
        })

    info = SERVICE_TOPOLOGY[service_name]
    # 同时获取上游(谁依赖我)
    upstream = [
        svc for svc, detail in SERVICE_TOPOLOGY.items()
        if service_name in detail.get("dependencies", [])
    ]

    return json.dumps({
        "status": "success",
        "service": service_name,
        "description": info["description"],
        "type": info["type"],
        "dependencies": info["dependencies"],
        "upstream_services": upstream,
    }, ensure_ascii=False)


@tool
def get_full_topology() -> str:
    """\brief 获取完整的系统架构拓扑（所有服务及其依赖关系）
    \details 用于整体架构理解和故障传播路径分析
    \return JSON 字符串，包含 total_services 和 topology 列表"""
    topology = []
    for svc, info in SERVICE_TOPOLOGY.items():
        upstream = [s for s, d in SERVICE_TOPOLOGY.items()
                    if svc in d.get("dependencies", [])]
        topology.append({
            "service": svc,
            "type": info["type"],
            "description": info["description"],
            "dependencies": info["dependencies"],
            "upstream": upstream,
        })
    return json.dumps({
        "status": "success",
        "total_services": len(topology),
        "topology": topology,
    }, ensure_ascii=False)


@tool
def find_dependency_path(source: str, target: str) -> str:
    """\brief 查找两个服务之间的依赖路径（广度优先搜索 BFS）
    \param source 起始服务名
    \param target 目标服务名
    \return JSON 字符串，包含:
        - path: 依赖路径列表（服务名序列）
        - path_length: 路径长度
        - message: 未找到路径时的提示信息"""
    if source not in SERVICE_TOPOLOGY or target not in SERVICE_TOPOLOGY:
        return json.dumps({
            "status": "failure",
            "error_message": "服务不存在",
        })

    from collections import deque
    visited = set()
    queue = deque([(source, [source])])

    while queue:
        current, path = queue.popleft()
        if current == target:
            return json.dumps({
                "status": "success",
                "path": path,
                "path_length": len(path),
            })
        if current in visited:
            continue
        visited.add(current)
        for dep in SERVICE_TOPOLOGY.get(current, {}).get("dependencies", []):
            if dep not in visited:
                queue.append((dep, path + [dep]))

    return json.dumps({
        "status": "success",
        "path": [],
        "message": f"未找到从 {source} 到 {target} 的依赖路径",
    })


TOPOLOGY_TOOLS = [lookup_service_topology, get_full_topology, find_dependency_path]
