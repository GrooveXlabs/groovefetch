"""Vector DB export pipeline for RAG applications."""

from typing import Dict, Any, Optional, List
import json
import hashlib

from .schema import ScrapedResult


class ChromaExporter:
    """Export scraped data to ChromaDB for LLM RAG pipelines.
    
    Usage:
        exporter = ChromaExporter()
        await exporter.export(result, collection="products")
    """
    
    def __init__(self, persist_directory: Optional[str] = None):
        self.persist_directory = persist_directory or "./chroma_db"
        self._client = None
        self._embedding_function = None
    
    def _get_client(self) -> Any:
        """Lazy-load ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
                from chromadb.utils import embedding_functions
                
                self._client = chromadb.PersistentClient(path=self.persist_directory)
                self._embedding_function = embedding_functions.DefaultEmbeddingFunction()
            except ImportError:
                raise ImportError(
                    "ChromaDB not installed. Run: pip install chromadb sentence-transformers"
                )
        return self._client
    
    async def export(
        self,
        result: ScrapedResult,
        collection: str = "default",
        embedding_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Export ScrapedResult to ChromaDB.
        
        Args:
            result: Validated scrape result
            collection: Collection name
            embedding_model: Optional embedding model override
            
        Returns:
            Export metadata
        """
        client = self._get_client()
        
        # Get or create collection
        chroma_collection = client.get_or_create_collection(
            name=collection,
            embedding_function=self._embedding_function,
        )
        
        # Prepare documents
        documents = []
        metadatas = []
        ids = []
        
        for idx, item in enumerate(result.validated):
            # Convert to text representation
            text = self._item_to_text(item)
            doc_id = self._generate_id(result.url, idx, text)
            
            documents.append(text)
            metadatas.append({
                "source_url": result.url,
                "schema": result.schema_name,
                "index": idx,
                **{k: str(v) for k, v in item.model_dump().items() if isinstance(v, (str, int, float, bool))},
            })
            ids.append(doc_id)
        
        # Add to collection
        if documents:
            chroma_collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )
        
        return {
            "collection": collection,
            "documents_added": len(documents),
            "source_url": result.url,
            "schema": result.schema_name,
        }
    
    def _item_to_text(self, item: Any) -> str:
        """Convert a Pydantic model to searchable text."""
        data = item.model_dump()
        parts = []
        for key, value in data.items():
            if value is not None:
                parts.append(f"{key}: {value}")
        return "\n".join(parts)
    
    def _generate_id(self, url: str, index: int, text: str) -> str:
        """Generate deterministic ID for deduplication."""
        content = f"{url}:{index}:{text[:200]}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    async def query(
        self,
        collection: str,
        query_text: str,
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Query a collection.
        
        Args:
            collection: Collection name
            query_text: Query text
            n_results: Number of results
            
        Returns:
            Matching documents with metadata
        """
        client = self._get_client()
        chroma_collection = client.get_collection(name=collection)
        
        results = chroma_collection.query(
            query_texts=[query_text],
            n_results=n_results,
        )
        
        return [
            {
                "document": doc,
                "metadata": meta,
                "distance": dist,
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]
