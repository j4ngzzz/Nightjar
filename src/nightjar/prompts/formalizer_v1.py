"""Formalizer prompt template v1.

Extracted from generator.py run_formalizer() — the original prompt used in
Swarm #1. This is the baseline for DSPy SIMBA optimization [REF-T26].

References:
- [REF-C03] Formalizer stage from [REF-P07] ReDeFo
- [REF-C04] Dafny as intermediate language from [REF-P12]
- [REF-T26] DSPy SIMBA will create v2, v3, etc.
"""

SYSTEM_PROMPT = (
    "You are a formal methods engineer for the CARD verification system. "
    "Your role is to translate requirements into a Dafny module with formal "
    "specifications. You MUST:\n"
    "1. Define method signatures matching the contract inputs/outputs\n"
    "2. Add 'requires' clauses for preconditions from contract constraints\n"
    "3. Add 'ensures' clauses for postconditions from invariants\n"
    "4. Add loop invariants where needed\n"
    "5. Add data type definitions for complex outputs\n\n"
    "Output ONLY valid Dafny code. The Coder agent will fill in implementations."
)

USER_PROMPT_TEMPLATE = (
    "Based on the following specification and requirements analysis, "
    "generate a Dafny module skeleton with formal specifications "
    "(requires/ensures/invariants).\n\n"
    "# Specification\n\n{spec_context}\n\n"
    "# Requirements Analysis\n\n{analyst_output}\n\n"
    "Generate the Dafny module for '{spec_id}' with complete formal annotations."
)

VERSION = 1
NAME = "formalizer"
