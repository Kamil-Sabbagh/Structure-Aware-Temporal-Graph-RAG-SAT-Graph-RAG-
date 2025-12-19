"""Hierarchical parser for Brazilian legal documents."""

from typing import List, Optional
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
import json
import logging

from .models import LegalComponent, ParsedConstitution, AmendmentEvent
from .patterns import detect_component_type, extract_amendments

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LegalDocumentParser:
    """Parser for Brazilian legal documents (Constitution)."""
    
    # Hierarchy levels for proper nesting
    HIERARCHY = {
        "norm": 0,
        "title": 1,
        "chapter": 2,
        "section": 3,
        "subsection": 4,
        "article": 5,
        "paragraph": 6,
        "item": 7,
        "letter": 8,
    }
    
    def __init__(self):
        self.current_path: List[LegalComponent] = []  # Stack for hierarchy
        self.all_components: List[LegalComponent] = []
        self.stats = {
            "titles": 0,
            "chapters": 0,
            "sections": 0,
            "articles": 0,
            "paragraphs": 0,
            "items": 0,
            "letters": 0,
            "amendments": set(),
        }
    
    def parse_file(self, filepath: str | Path) -> ParsedConstitution:
        """Parse a constitution HTML file."""
        filepath = Path(filepath)
        logger.info(f"Parsing: {filepath}")
        
        content = filepath.read_text(encoding='utf-8')
        soup = BeautifulSoup(content, 'lxml')
        
        # Reset state
        self.current_path = []
        self.all_components = []
        self.stats = {
            "titles": 0,
            "chapters": 0,
            "sections": 0,
            "articles": 0,
            "paragraphs": 0,
            "items": 0,
            "letters": 0,
            "amendments": set(),
        }
        
        # Extract text blocks
        paragraphs = self._extract_paragraphs(soup)
        logger.info(f"Found {len(paragraphs)} text blocks")
        
        # Parse each paragraph
        root_components = []
        
        for i, (text, amendments_in_text) in enumerate(paragraphs):
            component = self._parse_text_block(text, amendments_in_text, i)
            if component:
                # If it's a top-level component (title), add to root
                if component.component_type == "title" and component.parent_id is None:
                    root_components.append(component)
        
        # Build the result
        result = ParsedConstitution(
            components=root_components,
            total_titles=self.stats["titles"],
            total_chapters=self.stats["chapters"],
            total_articles=self.stats["articles"],
            total_amendments_referenced=len(self.stats["amendments"]),
            parse_timestamp=datetime.now().isoformat(),
            source_file=str(filepath),
        )
        
        logger.info(f"Parsing complete: {self.stats}")
        
        return result
    
    def _extract_paragraphs(self, soup: BeautifulSoup) -> List[tuple[str, list]]:
        """Extract text paragraphs from HTML."""
        results = []
        
        for p in soup.find_all(['p', 'div']):
            # Get text content
            text = p.get_text(separator=' ', strip=True)
            if not text or len(text) < 3:
                continue
            
            # Extract amendment markers from the raw HTML
            amendments = extract_amendments(str(p))
            
            results.append((text, amendments))
        
        return results
    
    def _parse_text_block(
        self, 
        text: str, 
        amendments: list,
        line_num: int
    ) -> Optional[LegalComponent]:
        """Parse a single text block into a component."""
        
        # Detect component type
        detection = detect_component_type(text)
        
        if not detection:
            # This is continuation text - append to current component
            if self.current_path:
                current = self.current_path[-1]
                if current.content:
                    current.content = current.content + " " + text
                else:
                    current.content = text
                current.full_text = current.full_text + " " + text
            return None
        
        comp_type, ordering, remaining = detection
        
        # Update stats
        stat_key = comp_type + "s"
        if stat_key in self.stats:
            self.stats[stat_key] += 1
        
        # Track amendments
        for a in amendments:
            self.stats["amendments"].add(a.get("amendment_number"))
        
        # Create component ID
        component_id = self._generate_component_id(comp_type, ordering)
        
        # Find parent
        parent = self._find_parent(comp_type)
        parent_id = parent.component_id if parent else None
        
        # Create component
        component = LegalComponent(
            component_type=comp_type,
            component_id=component_id,
            ordering_id=ordering,
            header=self._extract_header(text, comp_type),
            content=remaining,
            full_text=text,
            parent_id=parent_id,
            depth=self.HIERARCHY.get(comp_type, 0),
            is_original=len(amendments) == 0,
            events=[
                AmendmentEvent(**a) for a in amendments
            ],
            is_revoked=any(a.get("event_type") == "repealed" for a in amendments),
            source_line_start=line_num,
        )
        
        # Add to parent's children
        if parent:
            parent.children.append(component)
        
        # Update stack
        self._update_stack(component)
        
        self.all_components.append(component)
        
        return component
    
    def _extract_header(self, text: str, comp_type: str) -> str:
        """Extract the header portion of the text."""
        if comp_type in ["title", "chapter", "section", "subsection"]:
            # Header is the whole line for structural elements
            return text.strip()
        elif comp_type == "article":
            # Extract "Art. Nº"
            parts = text.split()
            if len(parts) >= 2:
                return f"{parts[0]} {parts[1]}"
            return parts[0] if parts else ""
        elif comp_type == "paragraph":
            parts = text.split()
            if parts:
                if "nico" in text.lower():
                    return "Parágrafo único"
                return f"§ {parts[1]}" if len(parts) > 1 else parts[0]
            return ""
        elif comp_type == "item":
            parts = text.split("-", 1)
            return parts[0].strip() + " -" if parts else ""
        elif comp_type == "letter":
            return text[0] + ")" if text else ""
        return ""
    
    def _generate_component_id(self, comp_type: str, ordering: str) -> str:
        """Generate a unique component ID based on current path."""
        if comp_type == "title":
            return f"tit_{ordering}"
        
        # Build path-based ID
        path_parts = []
        for comp in self.current_path:
            if comp.component_type == "title":
                path_parts.append(f"tit_{comp.ordering_id}")
            elif comp.component_type == "chapter":
                path_parts.append(f"cap_{comp.ordering_id}")
            elif comp.component_type == "section":
                path_parts.append(f"sec_{comp.ordering_id}")
            elif comp.component_type == "article":
                path_parts.append(f"art_{comp.ordering_id}")
            elif comp.component_type == "paragraph":
                path_parts.append(f"par_{comp.ordering_id}")
            elif comp.component_type == "item":
                path_parts.append(f"inc_{comp.ordering_id}")
        
        # Add current component
        type_abbrev = {
            "title": "tit",
            "chapter": "cap",
            "section": "sec",
            "subsection": "subsec",
            "article": "art",
            "paragraph": "par",
            "item": "inc",
            "letter": "ali",
        }
        
        abbrev = type_abbrev.get(comp_type, comp_type[:3])
        path_parts.append(f"{abbrev}_{ordering}")
        
        return "_".join(path_parts)
    
    def _find_parent(self, comp_type: str) -> Optional[LegalComponent]:
        """Find the appropriate parent for a component type."""
        comp_level = self.HIERARCHY.get(comp_type, 0)
        
        # Pop stack until we find a valid parent
        while self.current_path:
            potential_parent = self.current_path[-1]
            parent_level = self.HIERARCHY.get(potential_parent.component_type, 0)
            
            if parent_level < comp_level:
                return potential_parent
            else:
                self.current_path.pop()
        
        return None
    
    def _update_stack(self, component: LegalComponent):
        """Update the component stack with the new component."""
        comp_level = self.HIERARCHY.get(component.component_type, 0)
        
        # Remove components at same or lower level
        while self.current_path:
            top_level = self.HIERARCHY.get(self.current_path[-1].component_type, 0)
            if top_level >= comp_level:
                self.current_path.pop()
            else:
                break
        
        self.current_path.append(component)


def parse_constitution(
    input_file: str = "data/raw/constitution/constituicao.htm",
    output_file: str = "data/intermediate/constitution.json"
) -> ParsedConstitution:
    """Parse the constitution and save to JSON."""
    parser = LegalDocumentParser()
    result = parser.parse_file(input_file)
    
    # Save to JSON
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result.model_dump(mode='json'), f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved parsed constitution to {output_path}")
    
    return result


if __name__ == "__main__":
    parse_constitution()

