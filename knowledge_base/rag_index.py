"""
RAG(检索增强生成)功能模块
提供语义化知识库检索、向量索引构建能力
"""
import os
from typing import Dict, List, Any

# RAG相关导入（可选，无依赖时自动降级）
try:
    from langchain_community.document_loaders import TextLoader
    from langchain_text_splitters import MarkdownHeaderTextSplitter
    from langchain_community.embeddings import FakeEmbeddings
    from langchain_community.vectorstores import FAISS
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
KNOWLEDGE_BASE_DIR = os.path.join(PROJECT_ROOT, "knowledge_base")


class RAGKnowledgeIndex:
    """RAG向量索引管理器"""
    
    def __init__(self):
        self.vector_store = None
        self._initialize_index()
    
    def _initialize_index(self) -> None:
        """初始化向量索引"""
        if not LANGCHAIN_AVAILABLE:
            return
            
        knowledge_file = os.path.join(KNOWLEDGE_BASE_DIR, "rca_knowledge.md")
        if not os.path.exists(knowledge_file):
            return
            
        try:
            # 加载Markdown知识库
            loader = TextLoader(knowledge_file, encoding='utf-8')
            documents = loader.load()
            
            # 按Markdown标题分段
            headers_to_split_on = [
                ("##", "Header 2"),
                ("###", "Header 3"),
            ]
            splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
            splits = splitter.split_text(documents[0].page_content)
            
            # 构建向量存储（使用轻量FAISS + 本地嵌入，不依赖LLM）
            embeddings = FakeEmbeddings(size=1536)  # 占位，可替换为实际嵌入模型
            self.vector_store = FAISS.from_documents(splits, embeddings)
            
        except Exception:
            # RAG初始化失败不影响原有功能
            self.vector_store = None
    
    def is_available(self) -> bool:
        """检查RAG功能是否可用"""
        return self.vector_store is not None
    
    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        语义检索知识库内容
        返回: [{"content": "...", "metadata": {}, "source": "..."}]
        """
        if not self.vector_store:
            return []
            
        try:
            results = self.vector_store.similarity_search(query, k=top_k)
            return [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "source": "rca_knowledge.md"
                }
                for doc in results
            ]
        except Exception:
            return []
