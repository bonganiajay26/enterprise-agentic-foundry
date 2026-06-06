"""
RAG Retriever — Universal Agentic DevOps Platform

Provides context-aware retrieval for all platform agents.
Supports: hybrid search (dense + sparse), MMR reranking, category filtering.
"""

from __future__ import annotations

import os
from typing import Literal

from langchain.retrievers import ContextualCompressionRetriever, EnsembleRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Qdrant
from langchain_core.documents import Document
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from qdrant_client import QdrantClient

from agentic_ai.rag.ingestion import PlatformKnowledgeIngester


class PlatformKnowledgeRetriever:
    """
    Multi-strategy retriever for platform knowledge base.

    Retrieval strategies:
    - Dense: Semantic similarity via embeddings (handles conceptual queries)
    - Sparse: BM25 keyword search (handles exact technical terms)
    - Hybrid: Ensemble of dense + sparse (best of both)
    - Compressed: LLM-extracted relevant passages (most precise, slower)
    """

    def __init__(self, use_local: bool = False):
        self.ingester = PlatformKnowledgeIngester(use_local=use_local)
        self.vectorstore = self.ingester.get_vectorstore()

    def get_dense_retriever(
        self,
        k: int = 5,
        category_filter: str = "",
    ):
        """Semantic similarity retriever with optional category filtering."""
        search_kwargs = {"k": k}
        if category_filter:
            search_kwargs["filter"] = {"knowledge_category": category_filter}

        return self.vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={
                **search_kwargs,
                "fetch_k": k * 3,
                "lambda_mult": 0.7,
            },
        )

    def get_hybrid_retriever(
        self,
        k: int = 5,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ):
        """Hybrid dense + sparse retriever for best coverage."""
        dense_retriever = self.get_dense_retriever(k=k)

        # Get all docs for BM25 (works best with smaller corpus)
        all_docs = self.vectorstore.similarity_search("", k=1000)
        bm25_retriever = BM25Retriever.from_documents(all_docs, k=k)

        return EnsembleRetriever(
            retrievers=[dense_retriever, bm25_retriever],
            weights=[dense_weight, sparse_weight],
        )

    def get_compressed_retriever(self, k: int = 5):
        """LLM-compressed retriever — extracts only the most relevant passages."""
        llm = AzureChatOpenAI(
            azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version="2025-01-01-preview",
            temperature=0,
        )
        compressor = LLMChainExtractor.from_llm(llm)
        base_retriever = self.get_dense_retriever(k=k * 2)
        return ContextualCompressionRetriever(
            base_compressor=compressor,
            base_retriever=base_retriever,
        )

    def retrieve(
        self,
        query: str,
        strategy: Literal["dense", "hybrid", "compressed"] = "hybrid",
        k: int = 5,
        category: str = "",
    ) -> list[Document]:
        """Retrieve relevant documents for a query."""
        if strategy == "dense":
            retriever = self.get_dense_retriever(k=k, category_filter=category)
        elif strategy == "hybrid":
            retriever = self.get_hybrid_retriever(k=k)
        else:
            retriever = self.get_compressed_retriever(k=k)

        return retriever.invoke(query)

    def format_context(self, documents: list[Document], max_tokens: int = 3000) -> str:
        """Format retrieved documents into a context string for LLM prompts."""
        context_parts = []
        total_chars = 0
        max_chars = max_tokens * 4  # rough token estimate

        for doc in documents:
            source = doc.metadata.get("source", "unknown")
            category = doc.metadata.get("knowledge_category", "general")
            content = doc.page_content.strip()

            if total_chars + len(content) > max_chars:
                break

            context_parts.append(
                f"[{category.upper()} | {source}]\n{content}"
            )
            total_chars += len(content)

        return "\n\n---\n\n".join(context_parts)


def get_rag_context(query: str, category: str = "", k: int = 5) -> str:
    """
    Convenience function: retrieve and format RAG context for a query.
    Use this in agent system prompts or tool implementations.
    """
    retriever = PlatformKnowledgeRetriever(
        use_local=os.environ.get("QDRANT_USE_LOCAL", "true").lower() == "true"
    )
    docs = retriever.retrieve(query, strategy="hybrid", k=k, category=category)
    return retriever.format_context(docs)


if __name__ == "__main__":
    # Test retrieval
    queries = [
        "How do I rollback a failed deployment?",
        "What are the AKS security best practices?",
        "How does the DevOps agent handle production deployments?",
    ]

    retriever = PlatformKnowledgeRetriever(use_local=True)
    for query in queries:
        print(f"\nQuery: {query}")
        print("-" * 50)
        context = get_rag_context(query)
        print(context[:500] + "..." if len(context) > 500 else context)
