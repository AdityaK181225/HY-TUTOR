"""
HY-TUTOR: LEVEL 3 HYBRID SYLLABUS BUILDER (command_0_syllabus.py)
Target Hardware: Asus TUF F15 (RTX 2050 4GB VRAM, 8GB System RAM)
Model Engine: gemini-3.5-flash (or fallback) via Modernized Google GenAI SDK

Synthesizes CBSE Guidelines, NCERT Indexes, and Reference Manual TOCs into
a completely new, unified conceptual "Hybrid Textbook" with dedicated micro-chunks.
Includes Domain-Adaptive Templates for Physics, Chemistry, Biology, and Mathematics.
"""

import os
import sys
import json
import time
from dotenv import load_dotenv
from pathlib import Path
from utils.inference import call_gemini
from utils.genai_client import get_default_model

# Load environment variables (Gemini API Key)
from utils.paths import (
    CONFIG_DIR, RAW_SOURCES_DIR, METADATA_DIR, 
    MASTER_SYLLABUS_PATH, CBSE_GUIDELINES_DIR
)
from utils.logging_utils import log_debug, log_process, log_success, log_warning, log_error

load_dotenv(dotenv_path=CONFIG_DIR / ".env")

# Set model to the requested gemini-3.5-flash as default fallback
MODEL_NAME = get_default_model("command_0_syllabus")

# Base Paths (Aligned with standardized metadata storage location)
OUTPUT_JSON_PATH = MASTER_SYLLABUS_PATH

# Ensure target metadata directory exists
METADATA_DIR.mkdir(parents=True, exist_ok=True)


def read_specific_mapping_file(subject_name: str, filename: str) -> str:
    """
    Reads a specific mapping file exclusively from the isolated cbse_guidelines folder.
    This respects the Blueprint's Level 3 quarantine mandate. All initial UI uploads
    are routed here for syllabus generation.
    """
    target_file = CBSE_GUIDELINES_DIR / subject_name.lower() / filename
    if not target_file.exists():
        log_debug("command_0_syllabus", f"Mapping file absent: {target_file}")
        return ""

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()
            log_debug("command_0_syllabus", f"Successfully loaded {filename}")
            return f"\n\n--- SOURCE: {filename} ---\n\n{content}"
    except Exception as e:
        log_error("command_0_syllabus", f"Failed to read {filename}: {e}")
        return ""


def build_prompt(subject_name: str, cbse_text: str, ncert_text: str, ref_text: str, exemplar_text: str) -> str:
    """Constructs the deep-research prompt payload with specialized Domain-Adaptive compile templates."""
    
    subject_lower = subject_name.lower()
    
    # Define Domain-Specific profile schema prompts to force-steer JSON validation
    if subject_lower == "physics":
        domain_type = "STEM_HARD_SCIENCE"
        profile_schema = """
        "execution_profile": {
            "math_intensity": "HIGH/MEDIUM/LOW",
            "requires_calculus_derivation": true/false,
            "has_circuit_analysis": true/false,
            "requires_vector_geometry": true/false,
            "has_wave_diagrams": true/false
        }
        """
        domain_synthesis_instructions = """
        For PHYSICS, synthesize NCERT's conceptual frameworks with advanced competitive shortcuts from the Reference TOC 
        (e.g., integrating complex coordinate geometry systems, shortcut formulas for torque or circuit optimization, 
        and vector calculus applications). Keep atomic chunks focused on clean physical milestones.
        """
    elif subject_lower == "chemistry":
        domain_type = "STEM_MOLECULAR_CHEMISTRY"
        profile_schema = """
        "execution_profile": {
            "math_intensity": "HIGH/MEDIUM/LOW",
            "has_organic_mechanisms": true/false,
            "requires_stoichiometric_balancing": true/false,
            "has_molecular_orbital_theory": true/false,
            "has_thermodynamic_calculations": true/false
        }
        """
        domain_synthesis_instructions = """
        For CHEMISTRY, separate Physical, Inorganic, and Organic tracks. Ensure advanced competitive concepts 
        (e.g., stereochemical mechanisms, thermodynamic derivations, molecular orbital symmetries, and ligand field theory) 
        receive dedicated chunks instead of being mashed with basic concepts.
        """
    elif subject_lower == "biology":
        domain_type = "STEM_BIOMEDICAL_SCIENCES"
        profile_schema = """
        "execution_profile": {
            "math_intensity": "LOW",
            "requires_morphology_memorization": true/false,
            "has_biochemical_pathways": true/false,
            "requires_diagram_drawing": true/false,
            "has_taxonomic_classifications": true/false
        }
        """
        domain_synthesis_instructions = """
        For BIOLOGY, synthesize anatomical, physiological, or biochemical indexes. Focus on separating complex physiological pathways 
        (e.g., Kreb's Cycle, DNA Replication steps, ecological energy profiles) into sequential, isolated chunks 
        so the student is tested on granular mechanistic sequences rather than massive chapters at once.
        """
    else:  # Default to Mathematics
        domain_type = "STEM_PURE_MATHEMATICS"
        profile_schema = """
        "execution_profile": {
            "math_intensity": "HIGH/MEDIUM/LOW",
            "requires_3d_spatial_reasoning": true/false,
            "has_heavy_algebraic_manipulation": true/false,
            "requires_graph_sketching": true/false,
            "requires_rigorous_proof": true/false
        }
        """
        domain_synthesis_instructions = """
        For MATHEMATICS, compile a virtual "ideal book" where complex reference-only sub-topics (such as Cramer's Rule, 
        Echelon form, complex matrix classifications, or advanced integral reduction formulas) are mapped to dedicated, 
        isolated chunks instead of being packed into basic NCERT chapters.
        """

    return f"""
    You are the Master Syllabus Builder and lead Deep-Research Architect for the HY-TUTOR system.
    Your task is to act as an elite curriculum designer and synthesize raw data into a completely new, 
    custom-engineered "Hybrid Book" for the subject: {subject_name.capitalize()}.

    You have been provided with 3 to 4 distinct input files:
    1. CBSE Guidelines: Defines core scope, boundaries, and mandatory theoretical targets.
    2. NCERT Indexes (TOC): Defines the standard academic foundation.
    3. Reference Manuals (TOC): Contains high-tier, competitive shortcuts, and advanced extensions.
    4. NCERT Exemplars (Optional): Advanced problem-solving types.

    CRITICAL INSTRUCTIONS FOR HYBRID SYLLABUS SYNTHESIS:
    
    1. BYPASS CHAPTER NUMBER MISMATCHES (SEMANTIC ALIGNMENT):
       Do NOT rely on matching chapters by their chapter numbers. Publishers and boards label chapters differently 
       (e.g., Matrices is Unit 1 in CBSE, Chapter 3 in NCERT, and Chapter 3/4 in Reference Manuals).
       Instead, parse the files conceptually and match them SEMANTICALLY by topic name.
       Merge all data referring to the same core domain under a single, unified system chapter ID (e.g., "CH_12_03").
       
    2. THE HYBRIDIZATION PROTOCOL (FORGE A NEW BOOK):
       You are creating a new, customized pedagogical pathway. Combine the basic foundations of NCERT with the 
       advanced conceptual depth of the Reference Manuals.
       - Do NOT condense or compress. If the Reference Manual includes highly tested advanced sections that are completely 
         absent from NCERT, you MUST create a DEDICATED, ISOLATED chunk for each of these topics.
       - Ensure every distinct topic from the Reference Manual is mapped as its own operational `chunk_index` in logical 
         progressive order (from basic definitions, to operations, to advanced competitive methods).
       - Maintain a high-resolution sequence of 5 to 15 atomic chunks per major chapter.
       - If a topic from the reference manual is extreme college-level bloat completely outside competitive boundaries, 
         still catalog it but tag its profile as "NON_ESSENTIAL_EXTENSION".

    3. DOMAIN-ADAPTIVE MAPPING MANDATE:
       You must compile this syllabus under the '{domain_type}' subject domain.
       {domain_synthesis_instructions}

    RAW DATA INPUTS:
    === CBSE GUIDELINES ===
    {cbse_text if cbse_text else "NO DATA PROVIDED."}
    
    === NCERT INDEXES ===
    {ncert_text if ncert_text else "NO DATA PROVIDED."}
    
    === REFERENCE MANUALS ===
    {ref_text if ref_text else "NO DATA PROVIDED."}
    
    === NCERT EXEMPLARS ===
    {exemplar_text if exemplar_text else "NO DATA PROVIDED."}

    OUTPUT FORMAT MANDATE:
    You must return ONLY a valid, minified JSON object matching the exact schema below. Do not include markdown formatting.
    Notice that core_milestones must be highly detailed sentences, not single words.

    SCHEMA TEMPLATE:
    {{
        "subject": "{subject_name.capitalize()}",
        "subject_domain": "{domain_type}",
        "class_level": 12,
        "total_chapters": 0,
        "chapters": {{
            "CH_12_03": {{
                "chapter_name": "Matrices",
                "global_sequence_index": 3,
                "cross_grade_prerequisites": [
                    {{
                        "subject": "{subject_name.capitalize()}",
                        "chapter_id": "CH_11_XX",
                        "topic": "Prerequisite Concept",
                        "critical_for": "Why it is mathematically required"
                    }}
                ],
                "atomic_chunks": [
                    {{
                        "chunk_index": 0,
                        "chunk_id": "CH_12_03_C0",
                        "topic": "Concept and Notation of Matrices (NCERT 3.1 & 3.2)",
                        "core_milestones": [
                            "Define a matrix, its order, and element addressing notation.",
                            "Understand construction of matrices based on element rules."
                        ],
                        {profile_schema},
                        "competitive_track_focus": "Understanding basic rectangular arrays and dimension definitions."
                    }}
                    // CONTINUE GENERATING DEDICATED GRANULAR CHUNKS AS DETAILED IN THE HYBRIDIZATION PROTOCOL
                ]
            }}
        }}
    }}
    """


def execute_command_0(subject_name: str):
    log_process("command_0_syllabus", f"HY-TUTOR: COMMAND 0 INITIALIZED for {subject_name}")

    # 1. Ingest Raw Streams (Strictly from the isolated cbse_guidelines folder where the UI uploaded them)
    log_process("command_0_syllabus", "Scanning isolated syllabus mapping directory...")
    cbse_data = read_specific_mapping_file(subject_name, "cbse.md")
    ncert_data = read_specific_mapping_file(subject_name, "ncert_toc.md")
    ref_data = read_specific_mapping_file(subject_name, "reference_toc.md")
    exemplar_data = read_specific_mapping_file(subject_name, "exemplar_toc.md")

    if not cbse_data or not ncert_data or not ref_data:
        log_error("command_0_syllabus", "Missing baseline files. Command 0 requires CBSE, NCERT TOC, and Reference TOC to deeply map the blueprint.")
        sys.exit(1)

    # 2. Compile Payload
    log_process("command_0_syllabus", "Compiling Custom Hybrid Book Ingestion prompt payload...")
    prompt = build_prompt(subject_name, cbse_data, ncert_data, ref_data, exemplar_data)

    # 3. Model Inference via Inference Gateway (automatic logging + retries)
    log_process("command_0_syllabus", f"Transmitting to Google AI Studio ({MODEL_NAME}) via Inference Gateway...")

    try:
        raw_text, _model_used = call_gemini(
            "command_0_syllabus",
            MODEL_NAME,
            prompt,
            temperature=0.1,
            response_mime_type="application/json",
            max_retries=5,
        )
    except RuntimeError as e:
        log_error("command_0_syllabus", f"Command 0 Master Syllabus Builder failed after retries: {e}")
        sys.exit(1)

    # Clean markdown block if present
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        if lines[0].startswith("json") or lines[0].startswith(""):
            raw_text = "\n".join(lines[1:-1])

    try:
        json_payload = json.loads(raw_text.strip())
    except json.JSONDecodeError as e:
        log_error("command_0_syllabus", f"Failed to parse AI response as JSON: {e}")
        sys.exit(1)

    # 4. Data Target Output (Subject-domain directory in-place merging)
    log_process("command_0_syllabus", f"Writing in-depth unified map to {MASTER_SYLLABUS_PATH}...")
    
    final_data = {}
    if MASTER_SYLLABUS_PATH.exists():
        try:
            with open(MASTER_SYLLABUS_PATH, "r", encoding="utf-8") as f:
                final_data = json.load(f)
        except json.JSONDecodeError:
            log_warning("command_0_syllabus", "Existing Master_Subject_Syllabus.json is corrupted. Re-initializing.")

    # Nest the new subject data cleanly under its lowercase subject key to support multi-subject isolation
    final_data[subject_name.lower()] = json_payload

    with open(MASTER_SYLLABUS_PATH, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4)

    log_success("command_0_syllabus", f"{subject_name} customized hybrid syllabus mapped and saved successfully")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        log_error("command_0_syllabus", "Usage: python command_0_syllabus.py <Subject_Name>")
        log_error("command_0_syllabus", "Example: python command_0_syllabus.py Physics")
        sys.exit(1)
        
    target_subject = sys.argv[1]
    execute_command_0(target_subject)