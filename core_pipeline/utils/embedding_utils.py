"""
HY-TUTOR: Embedding Compression Utilities
Compresses large embedding arrays to reduce storage and memory usage.

This module provides utilities for:
- Compressing 3072-dimensional embeddings (float64 -> float32 + base64)
- Decompressing embeddings back to original format
- Validating embedding data

Storage Reduction:
- Original: 3072 float64 values = 24,576 bytes per embedding
- Compressed: 3072 float32 values encoded in base64 ≈ 12,288 bytes
- Reduction: ~50% storage savings
"""

import json
import base64
import numpy as np
from pathlib import Path
from typing import List, Optional, Union, Any
from dataclasses import dataclass


@dataclass
class EmbeddingInfo:
    """Metadata about an embedding."""
    original_dtype: str = "float64"
    compressed_dtype: str = "float32"
    dimension: int = 3072
    compression_ratio: float = 0.5


# Global embedding configuration
EMBEDDING_CONFIG = EmbeddingInfo()


def compress_embedding(embedding: List[float]) -> str:
    """
    Compress a list of float values to a base64-encoded string.
    
    Uses float32 precision (4 bytes per value) instead of Python's default float64 (8 bytes).
    Then encodes as base64 for JSON-safe storage.
    
    Args:
        embedding: List of float values (typically 3072 dimensions)
        
    Returns:
        Base64-encoded string representation of the compressed embedding
        
    Example:
        >>> emb = [0.1, 0.2, 0.3] * 1024  # 3072 values
        >>> compressed = compress_embedding(emb)
        >>> len(compressed) < len(str(emb))  # Much smaller!
    """
    if not embedding:
        return ""
    
    # Convert to numpy array with float32 precision
    arr = np.array(embedding, dtype=np.float32)
    
    # Convert to bytes and base64 encode
    compressed_bytes = base64.b64encode(arr.tobytes())
    
    return compressed_bytes.decode('utf-8')


def decompress_embedding(compressed: str) -> List[float]:
    """
    Decompress a base64-encoded embedding back to a list of floats.
    
    Args:
        compressed: Base64-encoded string from compress_embedding()
        
    Returns:
        List of float values (float64 precision)
        
    Raises:
        ValueError: If compressed string is empty or invalid
    """
    if not compressed or compressed == "":
        return []
    
    try:
        # Decode base64 to bytes
        compressed_bytes = base64.b64decode(compressed.encode('utf-8'))
        
        # Convert bytes to numpy array (float32)
        arr = np.frombuffer(compressed_bytes, dtype=np.float32)
        
        # Convert to Python list of float64
        return arr.tolist()
    except Exception as e:
        raise ValueError(f"Failed to decompress embedding: {e}")


def compress_embedding_field(data: dict, field_name: str = "chunk_embedding") -> dict:
    """
    Compress embedding fields in a dictionary.
    
    Args:
        data: Dictionary containing embedding data
        field_name: Name of the field to compress (default: "chunk_embedding")
        
    Returns:
        New dictionary with compressed embeddings
        
    Example:
        >>> data = {"chunk_index": 0, "chunk_embedding": [0.1, 0.2, ...]}
        >>> compressed_data = compress_embedding_field(data)
    """
    if not data:
        return data
    
    result = data.copy()
    
    # Handle single embedding field
    if field_name in result and isinstance(result[field_name], list):
        result[field_name] = compress_embedding(result[field_name])
        result[f"{field_name}_compressed"] = True
        result[f"{field_name}_original_dtype"] = EMBEDDING_CONFIG.original_dtype
    
    # Handle lists of embeddings (e.g., advanced_elements)
    if "advanced_elements" in result and isinstance(result["advanced_elements"], list):
        new_elements = []
        for element in result["advanced_elements"]:
            elem_copy = element.copy()
            if "element_embedding" in elem_copy and isinstance(elem_copy["element_embedding"], list):
                elem_copy["element_embedding"] = compress_embedding(elem_copy["element_embedding"])
                elem_copy["element_embedding_compressed"] = True
            new_elements.append(elem_copy)
        result["advanced_elements"] = new_elements
    
    return result


def decompress_embedding_field(data: dict, field_name: str = "chunk_embedding") -> dict:
    """
    Decompress embedding fields in a dictionary.
    
    Args:
        data: Dictionary containing compressed embedding data
        field_name: Name of the field to decompress
        
    Returns:
        New dictionary with decompressed embeddings
    """
    if not data:
        return data
    
    result = data.copy()
    
    # Handle single embedding field
    if f"{field_name}_compressed" in result and result.get(f"{field_name}_compressed") is True:
        if field_name in result and isinstance(result[field_name], str):
            result[field_name] = decompress_embedding(result[field_name])
        del result[f"{field_name}_compressed"]
        if f"{field_name}_original_dtype" in result:
            del result[f"{field_name}_original_dtype"]
    
    # Handle lists of embeddings
    if "advanced_elements" in result and isinstance(result["advanced_elements"], list):
        new_elements = []
        for element in result["advanced_elements"]:
            elem_copy = element.copy()
            if "element_embedding_compressed" in elem_copy and elem_copy.get("element_embedding_compressed") is True:
                if "element_embedding" in elem_copy and isinstance(elem_copy["element_embedding"], str):
                    elem_copy["element_embedding"] = decompress_embedding(elem_copy["element_embedding"])
                del elem_copy["element_embedding_compressed"]
            new_elements.append(elem_copy)
        result["advanced_elements"] = new_elements
    
    return result


def process_file_with_compression(file_path: Path, compress: bool = True, backup: bool = True) -> bool:
    """
    Process a JSON file to compress or decompress all embedding fields.
    
    Args:
        file_path: Path to the JSON file
        compress: True to compress, False to decompress
        backup: Whether to create a backup before modifying
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not file_path.exists():
            print(f"[WARNING] File not found: {file_path}")
            return False
        
        # Create backup
        if backup:
            backup_path = file_path.with_suffix('.bak')
            with open(file_path, 'r') as f:
                backup_data = f.read()
            with open(backup_path, 'w') as f:
                f.write(backup_data)
        
        # Load data
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Process based on operation
        if compress:
            processed_data = _compress_all_embeddings(data)
            print(f"[COMPRESSION] Processed {file_path.name}")
        else:
            processed_data = _decompress_all_embeddings(data)
            print(f"[DECOMPRESSION] Processed {file_path.name}")
        
        # Save processed data
        with open(file_path, 'w') as f:
            json.dump(processed_data, f, indent=4)
        
        # Clean up backup on success
        if backup:
            file_path.with_suffix('.bak').unlink()
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to process {file_path}: {e}")
        return False


def _compress_all_embeddings(data: Any) -> Any:
    """Recursively compress all embedding fields in a data structure."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key.endswith("_embedding") and isinstance(value, list):
                result[key] = compress_embedding(value)
                result[f"{key}_compressed"] = True
            elif key == "advanced_elements" and isinstance(value, list):
                result[key] = [_compress_embedding_element(elem) for elem in value]
            else:
                result[key] = _compress_all_embeddings(value)
        return result
    elif isinstance(data, list):
        return [_compress_all_embeddings(item) for item in data]
    else:
        return data


def _decompress_all_embeddings(data: Any) -> Any:
    """Recursively decompress all embedding fields in a data structure."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key.endswith("_embedding") and isinstance(value, str):
                # Check if this field was compressed
                if f"{key}_compressed" in data and data[f"{key}_compressed"] is True:
                    result[key] = decompress_embedding(value)
                else:
                    result[key] = value
            elif key == "advanced_elements" and isinstance(value, list):
                result[key] = [_decompress_embedding_element(elem) for elem in value]
            else:
                result[key] = _decompress_all_embeddings(value)
        
        # Remove compression markers
        for marker_key in [k for k in result.keys() if k.endswith("_compressed") or k.endswith("_original_dtype")]:
            del result[marker_key]
        
        return result
    elif isinstance(data, list):
        return [_decompress_all_embeddings(item) for item in data]
    else:
        return data


def _compress_embedding_element(element: dict) -> dict:
    """Compress embedding in a single element dictionary."""
    result = element.copy()
    for key, value in element.items():
        if key.endswith("_embedding") and isinstance(value, list):
            result[key] = compress_embedding(value)
            result[f"{key}_compressed"] = True
    return result


def _decompress_embedding_element(element: dict) -> dict:
    """Decompress embedding in a single element dictionary."""
    result = element.copy()
    for key, value in element.items():
        if key.endswith("_embedding") and isinstance(value, str):
            if f"{key}_compressed" in element and element[f"{key}_compressed"] is True:
                result[key] = decompress_embedding(value)
        # Remove compression markers
        if key.endswith("_compressed") or key.endswith("_original_dtype"):
            del result[key]
    return result


def calculate_storage_savings(data: dict) -> dict:
    """
    Calculate potential storage savings from embedding compression.
    
    Args:
        data: Dictionary containing embedding data
        
    Returns:
        Dictionary with savings information
    """
    original_size = 0
    compressed_size = 0
    embedding_count = 0
    
    def count_size(obj):
        nonlocal original_size, compressed_size, embedding_count
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key.endswith("_embedding") and isinstance(value, list):
                    embedding_count += 1
                    original_size += len(value) * 8  # float64 = 8 bytes
                    compressed_size += len(compress_embedding(value))
                else:
                    count_size(value)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict) and "element_embedding" in item:
                    embedding_count += 1
                    if isinstance(item["element_embedding"], list):
                        original_size += len(item["element_embedding"]) * 8
                        compressed_size += len(compress_embedding(item["element_embedding"]))
                count_size(item)
    
    count_size(data)
    
    return {
        "embedding_count": embedding_count,
        "original_size_bytes": original_size,
        "compressed_size_bytes": compressed_size,
        "savings_bytes": original_size - compressed_size,
        "savings_percentage": ((original_size - compressed_size) / original_size * 100) if original_size > 0 else 0
    }


# Convenience exports
__all__ = [
    'EmbeddingInfo',
    'EMBEDDING_CONFIG',
    'compress_embedding',
    'decompress_embedding',
    'compress_embedding_field',
    'decompress_embedding_field',
    'process_file_with_compression',
    'calculate_storage_savings',
]
