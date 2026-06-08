# HY-TUTOR Core Pipeline Utilities
# Lazy-import pattern: only import what's needed when it's needed.
# This prevents ImportError when google-genai or chromadb aren't installed.

from .paths import (
    PROJECT_ROOT,
    CONFIG_DIR,
    DATA_LIBRARY,
    METADATA_DIR,
    RAW_SOURCES_DIR,
    CBSE_GUIDELINES_DIR,
    NCERT_TEXTBOOKS_DIR,
    REFERENCE_MANUALS_DIR,
    NCERT_EXEMPLARS_DIR,
    SUBJECT_WORKSPACES_DIR,
    INTERFACE_DIR,
    INTERFACE_ASSETS_DIR,
    CORE_PIPELINE_DIR,
    MASTER_SYLLABUS_PATH,
    GLOBAL_TRACKER_PATH,
    ENV_PATH,
    ENV_SETUP_PATH,
    validate_project_root,
    get_subject_dir,
    get_chapter_path,
    get_subject_workspace,
    get_subject_router_state,
    get_subject_tracker,
    get_subject_active_workspace,
    get_subject_ui_session,
    get_subject_chunk_dir,
    ensure_subject_workspace,
    get_subject_blueprint_path,
    sanitize_path,
    CURRENT_SUBJECT_POINTER,
    set_current_subject,
    get_current_subject,
    resolve_subject,
    SubjectPaths,
)

from .file_utils import (
    FileLock,
    get_lock_path,
    safe_write_json,
    safe_read_json,
    safe_delete,
    clear_directory,
    safe_write_text,
    atomic_directory_clear,
)

from .usage_tracker import (
    log_call,
    track_call,
    get_summary as get_usage_summary,
    reset_log as reset_usage_log,
    USAGE_LOG_PATH,
    PRICING_PER_1K_TOKENS,
    extract_usage_from_response,
    ExtractedUsage,
)

from .update_checker import (
    get_status as get_update_status,
    check_now,
    do_pull,
    format_state_badge as format_update_badge,
    CACHE_PATH as UPDATE_CACHE_PATH,
    CACHE_TTL_SECONDS as UPDATE_CACHE_TTL_SECONDS,
)

# Lazy imports: modules that depend on external packages (numpy, google-genai,
# chromadb) are imported on demand via __getattr__ to avoid ImportError
# when those packages aren't installed yet.


def __getattr__(name):
    """Support lazy imports for modules that require external packages."""
    # genai_client (requires google-genai; openai/anthropic are optional lazy imports)
    _genai_names = {
        'get_genai_client', 'get_openai_client', 'get_anthropic_client',
        'get_default_model', 'get_model_with_fallback',
        'get_model_chain', 'MODEL_FALLBACK_CHAINS', 'check_ollama_health',
        'query_ollama',
    }
    if name in _genai_names:
        from . import genai_client
        return getattr(genai_client, name)

    # recovery (no external deps, but lazy for consistency)
    _recovery_names = {'RecoveryManager', 'RECOVERY_TTL_HOURS', 'MAX_ATTEMPTS'}
    if name in _recovery_names:
        from . import recovery
        return getattr(recovery, name)

    # vector_db (requires chromadb)
    _vdb_names = {'VectorDBManager', 'get_vector_db'}
    if name in _vdb_names:
        from . import vector_db
        return getattr(vector_db, name)

    # embedding_utils (requires numpy)
    _embed_names = {
        'EmbeddingInfo', 'EMBEDDING_CONFIG', 'compress_embedding',
        'decompress_embedding', 'compress_embedding_field',
        'decompress_embedding_field', 'process_file_with_compression',
        'calculate_storage_savings',
    }
    if name in _embed_names:
        from . import embedding_utils
        return getattr(embedding_utils, name)

    # logging_utils (no external deps, but lazy for consistency)
    _log_names = {
        'LogLevel', 'set_colors', 'log_message', 'log_init', 'log_process',
        'log_success', 'log_warning', 'log_error', 'log_critical', 'log_state',
        'log_debug', 'CommandLogger', 'run_with_logging',
    }
    if name in _log_names:
        from . import logging_utils
        return getattr(logging_utils, name)

    raise AttributeError(f"module 'utils' has no attribute '{name}'")


__all__ = [
    # Paths
    'PROJECT_ROOT', 'CONFIG_DIR', 'DATA_LIBRARY', 'METADATA_DIR',
    'RAW_SOURCES_DIR', 'CBSE_GUIDELINES_DIR', 'NCERT_TEXTBOOKS_DIR',
    'REFERENCE_MANUALS_DIR', 'NCERT_EXEMPLARS_DIR', 'SUBJECT_WORKSPACES_DIR',
    'INTERFACE_DIR', 'INTERFACE_ASSETS_DIR', 'CORE_PIPELINE_DIR',
    'MASTER_SYLLABUS_PATH', 'GLOBAL_TRACKER_PATH', 'ENV_PATH', 'ENV_SETUP_PATH',
    'validate_project_root', 'get_subject_dir', 'get_chapter_path',
    'get_subject_workspace', 'get_subject_router_state', 'get_subject_tracker',
    'get_subject_active_workspace', 'get_subject_ui_session', 'get_subject_chunk_dir',
    'ensure_subject_workspace', 'get_subject_blueprint_path', 'sanitize_path',
    'CURRENT_SUBJECT_POINTER', 'set_current_subject', 'get_current_subject',
    'resolve_subject', 'SubjectPaths',

    # File utils
    'FileLock', 'get_lock_path', 'safe_write_json', 'safe_read_json',
    'safe_delete', 'clear_directory', 'safe_write_text', 'atomic_directory_clear',

    # Usage tracker
    'log_call', 'track_call', 'get_usage_summary', 'reset_usage_log',
    'USAGE_LOG_PATH', 'PRICING_PER_1K_TOKENS',
    'extract_usage_from_response', 'ExtractedUsage',

    # Update checker
    'get_update_status', 'check_now', 'do_pull', 'format_update_badge',
    'UPDATE_CACHE_PATH', 'UPDATE_CACHE_TTL_SECONDS',

    # Logging
    'LogLevel', 'set_colors', 'log_message', 'log_init', 'log_process',
    'log_success', 'log_warning', 'log_error', 'log_critical', 'log_state',
    'log_debug', 'CommandLogger', 'run_with_logging',

    # Embeddings
    'EmbeddingInfo', 'EMBEDDING_CONFIG', 'compress_embedding',
    'decompress_embedding', 'compress_embedding_field',
    'decompress_embedding_field', 'process_file_with_compression',
    'calculate_storage_savings',
]
