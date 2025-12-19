"""Pydantic models for parsed legal components."""

from datetime import date
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class AmendmentEvent(BaseModel):
    """An event that modified a legal component."""
    
    event_type: Literal["created", "modified", "repealed", "reference"]
    amendment_number: int
    amendment_date: Optional[date] = None
    amendment_date_str: str  # Original string like "2004" or "30.12.2004"
    description: Optional[str] = None  # "Incluído pela EC nº 45"
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "modified",
                "amendment_number": 45,
                "amendment_date": "2004-12-30",
                "amendment_date_str": "30.12.2004",
                "description": "Redação dada pela Emenda Constitucional nº 45, de 2004"
            }
        }


class LegalComponent(BaseModel):
    """A component of the legal document hierarchy."""
    
    # Identity
    component_type: Literal[
        "norm", "title", "chapter", "section", "subsection",
        "article", "paragraph", "item", "letter"
    ]
    component_id: str  # Unique ID like "art_5", "art_5_par_1", "art_5_inc_I"
    ordering_id: str   # For ordering: "01", "05", "I", "a"
    
    # Content
    header: Optional[str] = None  # "TÍTULO I", "Art. 5º"
    subheader: Optional[str] = None  # "Dos Princípios Fundamentais"
    content: Optional[str] = None  # The actual legal text
    full_text: str  # Header + subheader + content combined
    
    # Hierarchy
    parent_id: Optional[str] = None
    children: List["LegalComponent"] = Field(default_factory=list)
    depth: int = 0
    
    # Temporal metadata
    is_original: bool = True  # True if existed in 1988 original
    events: List[AmendmentEvent] = Field(default_factory=list)
    is_revoked: bool = False
    
    # Source tracking
    source_line_start: Optional[int] = None
    source_line_end: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "component_type": "article",
                "component_id": "art_5",
                "ordering_id": "5",
                "header": "Art. 5º",
                "content": "Todos são iguais perante a lei...",
                "full_text": "Art. 5º Todos são iguais perante a lei...",
                "parent_id": "tit_II_cap_I",
                "is_original": True,
                "events": []
            }
        }


# Enable forward references
LegalComponent.model_rebuild()


class ParsedConstitution(BaseModel):
    """The complete parsed constitution."""
    
    name: str = "Constituição da República Federativa do Brasil"
    official_id: str = "CF1988"
    enactment_date: date = Field(default_factory=lambda: date(1988, 10, 5))
    
    # The root contains all top-level titles
    components: List[LegalComponent] = Field(default_factory=list)
    
    # Statistics
    total_titles: int = 0
    total_chapters: int = 0
    total_articles: int = 0
    total_amendments_referenced: int = 0
    
    # Metadata
    parse_timestamp: Optional[str] = None
    source_file: Optional[str] = None

