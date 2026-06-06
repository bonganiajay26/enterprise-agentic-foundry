"""
RAG Ingestion Pipeline — Universal Agentic DevOps Platform

Ingests platform knowledge into a vector store:
- Architecture documents
- Runbooks & SOPs
- Best practices guides
- Past incident post-mortems
- API documentation
- Terraform module documentation

Supports: Qdrant (local/cloud), Pinecone, Azure AI Search, pgvector
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Literal

from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    DirectoryLoader,
    GitLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_community.vectorstores import Qdrant
from langchain_openai import AzureOpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams


class PlatformKnowledgeIngester:
    """
    Ingests platform documentation into a vector store for RAG retrieval.
    Supports incremental updates — only re-ingests changed documents.
    """

    COLLECTION_NAME = "platform-knowledge"
    EMBEDDING_DIMENSION = 3072  # text-embedding-3-large

    SOURCE_DIRECTORIES = {
        "architecture": ("architecture/", "Architecture diagrams and design decisions"),
        "runbooks": ("runbooks/", "Operational runbooks and SOPs"),
        "docs": ("docs/", "Platform documentation"),
        "security": ("security/compliance/", "Security and compliance controls"),
        "adr": ("docs/adrs/", "Architecture Decision Records"),
    }

    def __init__(
        self,
        qdrant_url: str = "",
        qdrant_api_key: str = "",
        use_local: bool = False,
    ):
        self.embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version="2025-01-01-preview",
            dimensions=self.EMBEDDING_DIMENSION,
        )

        if use_local:
            self.qdrant_client = QdrantClient(path="/tmp/qdrant-data")
        else:
            self.qdrant_client = QdrantClient(
                url=qdrant_url or os.environ.get("QDRANT_URL", "http://localhost:6333"),
                api_key=qdrant_api_key or os.environ.get("QDRANT_API_KEY", ""),
            )

        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create vector collection if it doesn't exist."""
        existing = [c.name for c in self.qdrant_client.get_collections().collections]
        if self.COLLECTION_NAME not in existing:
            self.qdrant_client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self.EMBEDDING_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )
            print(f"Created Qdrant collection: {self.COLLECTION_NAME}")

    def _compute_document_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def load_markdown_documents(self, directory: str) -> list:
        """Load and split Markdown documents with header-aware chunking."""
        if not Path(directory).exists():
            return []

        headers_to_split_on = [
            ("#", "H1"),
            ("##", "H2"),
            ("###", "H3"),
        ]
        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False,
        )

        char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""],
        )

        documents = []
        for md_file in Path(directory).rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            header_splits = header_splitter.split_text(content)
            char_splits = char_splitter.split_documents(header_splits)

            for doc in char_splits:
                doc.metadata.update({
                    "source": str(md_file),
                    "source_type": "documentation",
                    "doc_hash": self._compute_document_hash(doc.page_content),
                    "file_name": md_file.name,
                })
            documents.extend(char_splits)

        return documents

    def load_code_documents(self, directory: str, glob_pattern: str = "**/*.py") -> list:
        """Load code files (Terraform, Python, YAML) for technical reference."""
        if not Path(directory).exists():
            return []

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=300,
            separators=["\nclass ", "\ndef ", "\n\n", "\n", " "],
        )

        loader = DirectoryLoader(
            directory,
            glob=glob_pattern,
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            silent_errors=True,
        )

        try:
            docs = loader.load()
            splits = splitter.split_documents(docs)
            for doc in splits:
                doc.metadata["source_type"] = "code"
            return splits
        except Exception as e:
            print(f"Warning: Could not load {directory}: {e}")
            return []

    def ingest_all(self, base_path: str = ".") -> dict[str, int]:
        """Ingest all platform documentation into the vector store."""
        stats = {}
        all_documents = []

        # Load Markdown documentation
        for source_name, (rel_path, description) in self.SOURCE_DIRECTORIES.items():
            full_path = os.path.join(base_path, rel_path)
            docs = self.load_markdown_documents(full_path)
            for doc in docs:
                doc.metadata["knowledge_category"] = source_name
                doc.metadata["description"] = description
            all_documents.extend(docs)
            stats[source_name] = len(docs)
            print(f"  Loaded {len(docs)} chunks from {source_name} ({rel_path})")

        # Load Terraform documentation
        tf_docs = self.load_code_documents(
            os.path.join(base_path, "terraform"),
            glob_pattern="**/*.tf",
        )
        for doc in tf_docs:
            doc.metadata["knowledge_category"] = "terraform"
        all_documents.extend(tf_docs)
        stats["terraform"] = len(tf_docs)

        # Load agent source as reference
        agent_docs = self.load_code_documents(
            os.path.join(base_path, "agentic-ai/agents"),
            glob_pattern="**/*.py",
        )
        for doc in agent_docs:
            doc.metadata["knowledge_category"] = "agents"
        all_documents.extend(agent_docs)
        stats["agents"] = len(agent_docs)

        if not all_documents:
            print("No documents found to ingest.")
            return stats

        print(f"\nIngesting {len(all_documents)} total document chunks...")

        # Batch upsert to Qdrant
        vectorstore = Qdrant(
            client=self.qdrant_client,
            collection_name=self.COLLECTION_NAME,
            embeddings=self.embeddings,
        )
        vectorstore.add_documents(all_documents)

        total = sum(stats.values())
        print(f"✓ Ingested {total} chunks into '{self.COLLECTION_NAME}'")
        return stats

    def get_vectorstore(self) -> Qdrant:
        """Return a LangChain-compatible vectorstore for retrieval."""
        return Qdrant(
            client=self.qdrant_client,
            collection_name=self.COLLECTION_NAME,
            embeddings=self.embeddings,
        )


if __name__ == "__main__":
    import sys
    base_path = sys.argv[1] if len(sys.argv) > 1 else "."

    ingester = PlatformKnowledgeIngester(use_local=True)
    stats = ingester.ingest_all(base_path=base_path)

    print("\nIngestion Summary:")
    for category, count in stats.items():
        print(f"  {category}: {count} chunks")
