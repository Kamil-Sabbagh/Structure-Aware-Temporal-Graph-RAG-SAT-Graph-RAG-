"""Baseline RAG system for comparison."""

from .flat_rag import FlatChunkRAG, create_baseline_retriever, BaselineResult

__all__ = ['FlatChunkRAG', 'create_baseline_retriever', 'BaselineResult']
