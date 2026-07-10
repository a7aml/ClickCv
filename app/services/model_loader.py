"""
services/model_loader.py

Centralized model loading to prevent duplicate loading.
Models are loaded once at app startup and shared across all services.
"""

from keybert import KeyBERT
from sentence_transformers import SentenceTransformer

# Global model instances
_sentence_transformer = None
_keybert_model = None


def preload_models():
    """
    Load all NLP models at application startup.
    
    Called from app/__init__.py create_app() function.
    This eliminates cold-start penalty on first analysis request.
    """
    global _sentence_transformer, _keybert_model
    
    print("🔄 Pre-loading NLP models...")
    
    # Load SentenceTransformer first
    if _sentence_transformer is None:
        print("  ↳ Loading SentenceTransformer (all-MiniLM-L6-v2)...")
        _sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2")
        print("  ✓ SentenceTransformer loaded")
    
    # Load KeyBERT (will reuse the SentenceTransformer model internally)
    if _keybert_model is None:
        print("  ↳ Loading KeyBERT...")
        _keybert_model = KeyBERT(model=_sentence_transformer)
        print("  ✓ KeyBERT loaded")
    
    print("✅ All NLP models pre-loaded successfully\n")


def get_sentence_transformer() -> SentenceTransformer:
    """
    Get the shared SentenceTransformer instance.
    
    Returns:
        SentenceTransformer model instance
    """
    global _sentence_transformer
    
    if _sentence_transformer is None:
        print("⚠️  SentenceTransformer not pre-loaded, loading now...")
        _sentence_transformer = SentenceTransformer("all-MiniLM-L6-v2")
    
    return _sentence_transformer


def get_keybert_model() -> KeyBERT:
    """
    Get the shared KeyBERT instance.
    
    Returns:
        KeyBERT model instance
    """
    global _keybert_model
    
    if _keybert_model is None:
        print("⚠️  KeyBERT not pre-loaded, loading now...")
        # Ensure SentenceTransformer is loaded first
        st_model = get_sentence_transformer()
        _keybert_model = KeyBERT(model=st_model)
    
    return _keybert_model