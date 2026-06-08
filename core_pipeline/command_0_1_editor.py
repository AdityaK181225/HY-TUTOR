"""
HY-TUTOR: LEVEL 3 SYLLABUS EDITOR (command_0_1_editor.py)
Target Hardware: Asus TUF F15 (RTX 2050 4GB VRAM, 8GB System RAM)
Model Engine: gemini-3.5-flash (or fallback) via Modernized Google GenAI SDK

Mandate: Overacts user chat requests to dynamically edit the Master Syllabus JSON
without destroying the highly specific Domain-Adaptive execution profiles of 
Physics, Chemistry, Biology, or Mathematics.
"""

import os
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from utils.inference import call_gemini
from utils.genai_client import get_default_model
from utils.paths import MASTER_SYLLABUS_PATH
from utils.logging_utils import (
    log_init, log_process, log_success, log_warning, log_error, log_debug
)

def get_domain_specific_schema(subject_name: str) -> tuple[str, str]:
    """
    Returns the exact schema definitions and synthesis guardrails for the active domain.
    This guarantees that modifications do not corrupt subject-specific execution profiles.
    """
    subj_lower = subject_name.lower()
    
    if subj_lower == "physics":
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
    elif subj_lower == "chemistry":
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
    elif subj_lower == "biology":
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
        
    return domain_type, profile_schema

def execute_command_0_1_pipeline(subject_name: str, user_prompt: str):
    log_init("command_0_1_editor", f"Syllabus Editor for {subject_name}")

    # 1. Load Current Syllabus Data
    if not MASTER_SYLLABUS_PATH.exists():
        log_error("command_0_1_editor", f"Master Syllabus not found at {MASTER_SYLLABUS_PATH}")
        sys.exit(1)

    try:
        with open(MASTER_SYLLABUS_PATH, "r", encoding="utf-8") as f:
            full_syllabus = json.load(f)
            
        subject_data = full_syllabus.get(subject_name.lower())
        if not subject_data:
            log_error("command_0_1_editor", f"Subject '{subject_name}' not found in syllabus")
            sys.exit(1)
    except Exception as e:
        log_error("command_0_1_editor", f"Failed parsing syllabus: {e}")
        sys.exit(1)

    # 2. Extract Domain-Specific Schema Lock to safeguard Downstream Miner dependencies
    domain_type, profile_schema = get_domain_specific_schema(subject_name)
    log_process("command_0_1_editor", f"Schema Lock: Subject Domain = {domain_type}")

    # 3. Configure Model
    MODEL_NAME = get_default_model("command_0_1_editor")

    # 4. Build Safe Modification Prompt with Dynamic Profile Locking
    prompt = f"""
    You are the Master Syllabus Editor for the HY-TUTOR system.
    The user wants to modify the following syllabus map for '{subject_name.capitalize()}'.
    
    USER MODIFICATION REQUEST:
    "{user_prompt}"
    
    CURRENT SYLLABUS JSON:
    {json.dumps(subject_data, indent=2)}
    
    CRITICAL STRUCTURAL RULES (SCHEMA PROTECTION ENFORCED):
    1. Apply the user's requested changes cleanly (e.g., adding more detail, highlighting specific mechanics, adjusting topics, or expanding lessons).
    2. You MUST return ONLY a valid, minified JSON object matching the parent schema exactly.
    3. You MUST strictly preserve the root-level variables and types.
    
    4. DOMAIN-SPECIFIC PROFILE SECURITY ENFORCEMENT:
       This subject belongs to the '{domain_type}' category.
       Every atomic chunk inside the modified JSON must strictly use the following keys inside its 'execution_profile' dictionary:
       {profile_schema}
       Do NOT use any other key names, and do NOT remove this profile object from any chunk. All values inside 'execution_profile' must remain valid booleans (or matching string for math_intensity).
    """

    log_process("command_0_1_editor", "Transmitting modification request with Domain-Specific Schema Lock...")

    # 5. Model Inference via Inference Gateway (automatic logging + retries)
    try:
        raw_text, _model_used = call_gemini(
            "command_0_1_editor",
            MODEL_NAME,
            prompt,
            temperature=0.2,
            response_mime_type="application/json",
            max_retries=5,
        )
    except RuntimeError as e:
        log_error("command_0_1_editor", f"Syllabus modification failed after retries: {e}")
        sys.exit(1)

    # Clean and parse response  –  robust multi-stage extraction
    raw_text = raw_text.strip()

    # Stage 1: strip markdown code-fence wrapper (```json ... ``` )
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        if lines[0].startswith("```json") or lines[0].startswith("```"):
            raw_text = "\n".join(lines[1:-1]).strip()

    # Stage 2: direct parse
    modified_json = None
    try:
        modified_json = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError):
        pass  # fall through to Stage 3

    # Stage 3: extract the outermost {…} block (AI sometimes wraps JSON in prose)
    if modified_json is None:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end > start:
            try:
                modified_json = json.loads(raw_text[start:end + 1])
            except (json.JSONDecodeError, ValueError):
                pass

    if modified_json is None:
        preview = raw_text[:300].replace("\n", "\\n")
        log_error(
            "command_0_1_editor",
            f"AI response is not valid JSON. Response preview: {preview!r}"
        )
        sys.exit(1)

    # Save back to file
    full_syllabus[subject_name.lower()] = modified_json
    with open(MASTER_SYLLABUS_PATH, "w", encoding="utf-8") as f:
        json.dump(full_syllabus, f, indent=4)

    log_success("command_0_1_editor", f"{subject_name.capitalize()} syllabus modified and safely overwritten in master ledger")
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        log_error("command_0_1_editor", "Usage: python command_0_1_editor.py <Subject_Name> <User_Prompt>")
        sys.exit(1)
    execute_command_0_1_pipeline(sys.argv[1], sys.argv[2])