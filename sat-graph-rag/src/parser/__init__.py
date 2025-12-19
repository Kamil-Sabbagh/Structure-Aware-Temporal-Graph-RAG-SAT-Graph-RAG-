"""Structural parsing module for legal documents."""

from .models import LegalComponent, ParsedConstitution, AmendmentEvent
from .patterns import detect_component_type, extract_amendments, roman_to_int
from .legal_parser import LegalDocumentParser, parse_constitution
from .amendment_parser import parse_amendment_file, parse_all_amendments

__all__ = [
    "LegalComponent",
    "ParsedConstitution", 
    "AmendmentEvent",
    "detect_component_type",
    "extract_amendments",
    "roman_to_int",
    "LegalDocumentParser",
    "parse_constitution",
    "parse_amendment_file",
    "parse_all_amendments",
]

