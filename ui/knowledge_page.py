from __future__ import annotations

import json

import streamlit as st

from knowledge_base.schemas import KnowledgeDocument
from knowledge_base.store import KnowledgeBaseStore
from utils.incident_contract import is_fault_type_label, normalize_fault_code


@st.cache_resource(show_spinner=False)
def _get_store() -> KnowledgeBaseStore:
    return KnowledgeBaseStore()


@st.cache_data(show_spinner=False)
def _list_documents() -> list[dict]:
    return [document.to_dict() for document in _get_store().list_documents()]


def render_knowledge_page() -> None:
    st.title("知识库管理")
    store = _get_store()

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("知识条目")
    with col2:
        if st.button("重建索引", width="stretch"):
            result = store.rebuild_index()
            _list_documents.clear()
            st.success(f"索引已重建：{json.dumps(result, ensure_ascii=False)}")

    documents = [KnowledgeDocument.from_dict(item) for item in _list_documents()]
    if documents:
        selected_id = st.selectbox(
            "选择知识条目",
            options=[document.document_id for document in documents],
            format_func=lambda item: _format_option(item, documents),
        )
        document = next(item for item in documents if item.document_id == selected_id)
        _render_edit_form(store, document)
        st.divider()
    else:
        st.info("当前知识库为空，可以先新增条目或运行 build_knowledge_base.py。")

    st.subheader("新增知识条目")
    _render_create_form(store)

    with st.expander("当前知识文档预览", expanded=False):
        st.dataframe([document.to_dict() for document in documents], width="stretch")



def _render_edit_form(store: KnowledgeBaseStore, document: KnowledgeDocument) -> None:
    st.subheader("编辑知识条目")
    with st.form(f"edit_{document.document_id}"):
        title = st.text_input("标题", value=document.title)
        content = st.text_area("内容", value=document.content, height=160)
        service = st.text_input("根因服务", value=document.service or "", help="填写真实服务名，例如 frontend、currencyservice、ts-auth-service。不要填写 f1/f2 这类故障代码。")
        fault_type = st.text_input("故障模式/代码", value=document.fault_type or "", help="填写 f1/f2/f3 或 cpu、delay、loss 等故障模式。")
        root_cause = st.text_input("根因描述", value=document.root_cause or "", help="通常与根因服务一致；如有代码级描述，可写在这里或 metadata 中。")
        solution = st.text_area("解决建议", value=document.solution or "", height=100)
        source = st.text_input("来源", value=document.source)
        tags = st.text_input("标签（逗号分隔）", value=", ".join(document.tags))
        metadata = st.text_area(
            "元数据（JSON）",
            value=json.dumps(document.metadata, ensure_ascii=False, indent=2),
            height=140,
        )
        submitted = st.form_submit_button("保存修改")
        if submitted:
            payload = _build_document_payload(
                title=title,
                content=content,
                service=service,
                fault_type=fault_type,
                root_cause=root_cause,
                solution=solution,
                source=source,
                tags=tags,
                metadata=metadata,
            )
            if payload is None:
                st.error("元数据必须是合法 JSON。")
                return
            store.update_document(document.document_id, **payload)
            _list_documents.clear()
            st.success("知识条目已更新，请手动重建索引以同步检索结果。")

    if st.button("删除当前条目", key=f"delete_{document.document_id}"):
        store.delete_document(document.document_id)
        _list_documents.clear()
        st.success("知识条目已删除，请手动重建索引。")



def _render_create_form(store: KnowledgeBaseStore) -> None:
    with st.form("create_document"):
        title = st.text_input("标题", value="")
        content = st.text_area("内容", value="", height=160)
        service = st.text_input("根因服务", value="", help="填写真实服务名，例如 frontend、currencyservice、ts-auth-service。不要填写 f1/f2 这类故障代码。")
        fault_type = st.text_input("故障模式/代码", value="", help="填写 f1/f2/f3 或 cpu、delay、loss 等故障模式。")
        root_cause = st.text_input("根因描述", value="", help="通常与根因服务一致；如有代码级描述，可写在这里或 metadata 中。")
        solution = st.text_area("解决建议", value="", height=100)
        source = st.text_input("来源", value="manual")
        tags = st.text_input("标签（逗号分隔）", value="")
        metadata = st.text_area("元数据（JSON）", value="{}", height=140)
        submitted = st.form_submit_button("新增条目")
        if submitted:
            payload = _build_document_payload(
                title=title,
                content=content,
                service=service,
                fault_type=fault_type,
                root_cause=root_cause,
                solution=solution,
                source=source,
                tags=tags,
                metadata=metadata,
            )
            if payload is None:
                st.error("元数据必须是合法 JSON。")
                return
            created = store.add_document(KnowledgeDocument.from_dict(payload))
            _list_documents.clear()
            st.success(f"已新增知识条目：{created.document_id}")



def _build_document_payload(
    *,
    title: str,
    content: str,
    service: str,
    fault_type: str,
    root_cause: str,
    solution: str,
    source: str,
    tags: str,
    metadata: str,
) -> dict | None:
    try:
        metadata_payload = json.loads(metadata or "{}")
    except json.JSONDecodeError:
        return None
    service_value = service.strip()
    fault_type_value = fault_type.strip()
    if service_value and is_fault_type_label(service_value) and not fault_type_value:
        fault_type_value = service_value
        service_value = ""
    fault_code = normalize_fault_code(fault_type_value)
    if service_value:
        metadata_payload.setdefault("root_cause_service", service_value)
    if fault_code:
        metadata_payload.setdefault("fault_code", fault_code)
    metadata_payload.setdefault("contract_schema_version", "service_fault_v1")
    return {
        "title": title.strip(),
        "content": content.strip(),
        "service": service_value or None,
        "fault_type": fault_type_value or None,
        "root_cause_service": service_value or None,
        "fault_code": fault_code,
        "root_cause": root_cause.strip() or None,
        "solution": solution.strip() or None,
        "source": source.strip() or "manual",
        "tags": [item.strip() for item in tags.split(",") if item.strip()],
        "metadata": metadata_payload,
    }



def _format_option(document_id: str, documents: list[KnowledgeDocument]) -> str:
    document = next(item for item in documents if item.document_id == document_id)
    return f"{document.title} ({document.document_id})"
