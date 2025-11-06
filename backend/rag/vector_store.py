"""
Vector Store Management using ChromaDB
Manages 4 collections:
1. installed_nodes - RAG 1: Installed Node-RED nodes
2. approved_flows - RAG 2: User-approved flow solutions
3. feedback_history - RAG 3: Feedback for reinforcement learning
4. documentation - RAG 4: Node-RED best practices and configuration requirements
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Optional, Any
import json
import uuid
from datetime import datetime
from loguru import logger

from backend.config import settings
from backend.rag.embeddings import EmbeddingGenerator


class VectorStoreManager:
    """Manages all vector store operations for the multi-agent system"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialize()
            self._initialized = True

    def _initialize(self):
        """Initialize ChromaDB client and collections"""
        logger.info(f"Initializing ChromaDB at {settings.chroma_persist_dir}")

        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False)
        )

        self.embedding_generator = EmbeddingGenerator()

        # Collection 1: Installed Nodes (RAG 1)
        self.installed_nodes = self.client.get_or_create_collection(
            name="installed_nodes",
            metadata={"description": "Node-RED installed nodes catalog"}
        )

        # Collection 2: Approved Flows (RAG 2)
        self.approved_flows = self.client.get_or_create_collection(
            name="approved_flows",
            metadata={"description": "User-approved flow solutions"}
        )

        # Collection 3: Feedback History (RAG 3)
        self.feedback_history = self.client.get_or_create_collection(
            name="feedback_history",
            metadata={"description": "Flow feedback for reinforcement learning"}
        )

        # Collection 4: Documentation (RAG 4)
        self.documentation = self.client.get_or_create_collection(
            name="documentation",
            metadata={"description": "Node-RED best practices and configuration requirements"}
        )

        logger.info("Vector store initialized successfully")

    # ==================== INSTALLED NODES (RAG 1) ====================

    def add_installed_node(
        self,
        node_type: str,
        package_name: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add an installed node to the catalog"""
        node_id = str(uuid.uuid4())

        # Create searchable text
        search_text = f"{node_type} {package_name} {description}"
        embedding = self.embedding_generator.generate(search_text)

        meta = metadata or {}
        meta.update({
            "node_type": node_type,
            "package_name": package_name,
            "description": description,
            "added_at": datetime.now().isoformat()
        })

        self.installed_nodes.add(
            ids=[node_id],
            embeddings=[embedding],
            documents=[search_text],
            metadatas=[meta]
        )

        logger.info(f"Added installed node: {node_type} ({package_name})")
        return node_id

    def search_installed_nodes(
        self,
        query: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for installed nodes by query"""
        query_embedding = self.embedding_generator.generate(query)

        results = self.installed_nodes.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

        # Format results
        formatted = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                formatted.append({
                    'id': results['ids'][0][i],
                    'node_type': results['metadatas'][0][i].get('node_type'),
                    'package_name': results['metadatas'][0][i].get('package_name'),
                    'description': results['metadatas'][0][i].get('description'),
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })

        return formatted

    def is_node_installed(self, node_type: str) -> bool:
        """Check if a specific node type is installed"""
        results = self.installed_nodes.get(
            where={"node_type": node_type}
        )
        return len(results['ids']) > 0

    # ==================== APPROVED FLOWS (RAG 2) ====================

    def add_approved_flow(
        self,
        user_request: str,
        flow_json: str,
        score: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add an approved flow solution"""
        flow_id = str(uuid.uuid4())

        # Create searchable embedding from user request
        embedding = self.embedding_generator.generate(user_request)

        meta = metadata or {}
        meta.update({
            "user_request": user_request,
            "score": score,
            "created_at": datetime.now().isoformat(),
            "usage_count": 0
        })

        self.approved_flows.add(
            ids=[flow_id],
            embeddings=[embedding],
            documents=[flow_json],
            metadatas=[meta]
        )

        logger.info(f"Added approved flow: {flow_id} (score: {score})")
        return flow_id

    def search_similar_flows(
        self,
        user_request: str,
        n_results: int = 3,
        min_score: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar approved flows"""
        query_embedding = self.embedding_generator.generate(user_request)

        where_filter = None
        if min_score:
            where_filter = {"score": {"$gte": min_score}}

        results = self.approved_flows.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter
        )

        # Format results
        formatted = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                distance = results['distances'][0][i] if 'distances' in results else 1.0
                similarity = 1 - distance  # Convert distance to similarity

                formatted.append({
                    'id': results['ids'][0][i],
                    'user_request': results['metadatas'][0][i].get('user_request'),
                    'flow_json': results['documents'][0][i],
                    'score': results['metadatas'][0][i].get('score'),
                    'similarity': similarity,
                    'usage_count': results['metadatas'][0][i].get('usage_count', 0)
                })

        return formatted

    def increment_flow_usage(self, flow_id: str):
        """Increment usage count for a flow"""
        try:
            result = self.approved_flows.get(ids=[flow_id])
            if result['ids']:
                metadata = result['metadatas'][0]
                metadata['usage_count'] = metadata.get('usage_count', 0) + 1

                self.approved_flows.update(
                    ids=[flow_id],
                    metadatas=[metadata]
                )
                logger.info(f"Incremented usage for flow: {flow_id}")
        except Exception as e:
            logger.error(f"Error incrementing flow usage: {e}")

    # ==================== FEEDBACK HISTORY (RAG 3) ====================

    def add_feedback(
        self,
        session_id: str,
        user_request: str,
        flow_json: str,
        feedback_type: str,
        score: int,
        comments: Optional[str] = None,
        modifications: Optional[str] = None
    ) -> str:
        """Add feedback for reinforcement learning"""
        feedback_id = str(uuid.uuid4())

        # Create searchable text
        search_text = f"{user_request} {comments or ''} {modifications or ''}"
        embedding = self.embedding_generator.generate(search_text)

        metadata = {
            "session_id": session_id,
            "user_request": user_request,
            "feedback_type": feedback_type,
            "score": score,
            "comments": comments,
            "modifications": modifications,
            "created_at": datetime.now().isoformat()
        }

        self.feedback_history.add(
            ids=[feedback_id],
            embeddings=[embedding],
            documents=[flow_json],
            metadatas=[metadata]
        )

        logger.info(f"Added feedback: {feedback_id} (type: {feedback_type}, score: {score})")
        return feedback_id

    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get statistics about feedback"""
        all_feedback = self.feedback_history.get()

        if not all_feedback['ids']:
            return {
                "total_count": 0,
                "average_score": 0,
                "approval_rate": 0
            }

        scores = [m.get('score', 0) for m in all_feedback['metadatas']]
        approvals = sum(1 for m in all_feedback['metadatas'] if m.get('feedback_type') == 'approve')

        return {
            "total_count": len(all_feedback['ids']),
            "average_score": sum(scores) / len(scores) if scores else 0,
            "approval_rate": approvals / len(all_feedback['ids']) if all_feedback['ids'] else 0
        }

    # ==================== DOCUMENTATION (RAG 4) ====================

    def add_documentation(
        self,
        title: str,
        content: str,
        category: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add documentation entry (best practices, configuration requirements, etc.)"""
        doc_id = str(uuid.uuid4())

        # Create searchable text
        search_text = f"{title} {category} {content}"
        embedding = self.embedding_generator.generate(search_text)

        meta = metadata or {}
        meta.update({
            "title": title,
            "category": category,
            "created_at": datetime.now().isoformat()
        })

        self.documentation.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[meta]
        )

        logger.info(f"Added documentation: {title} (category: {category})")
        return doc_id

    def search_documentation(
        self,
        query: str,
        category: Optional[str] = None,
        n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """Search documentation by query"""
        query_embedding = self.embedding_generator.generate(query)

        where_filter = None
        if category:
            where_filter = {"category": category}

        results = self.documentation.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter
        )

        # Format results
        formatted = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                formatted.append({
                    'id': results['ids'][0][i],
                    'title': results['metadatas'][0][i].get('title'),
                    'category': results['metadatas'][0][i].get('category'),
                    'content': results['documents'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })

        return formatted

    # ==================== UTILITY METHODS ====================

    def clear_collection(self, collection_name: str):
        """Clear a specific collection (for testing)"""
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Cleared collection: {collection_name}")
        except Exception as e:
            logger.warning(f"Could not clear collection {collection_name}: {e}")

    def get_collection_count(self, collection_name: str) -> int:
        """Get count of items in a collection"""
        collection = self.client.get_collection(collection_name)
        return collection.count()
