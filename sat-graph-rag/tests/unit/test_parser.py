"""Unit tests for legal document parser."""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from parser.patterns import detect_component_type, extract_amendments, roman_to_int
from parser.models import LegalComponent, AmendmentEvent


class TestPatternDetection:
    """Tests for pattern detection."""
    
    def test_title_detection(self):
        result = detect_component_type("TÍTULO I")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "title"
        assert ordering == "01"
    
    def test_title_with_encoding_variation(self):
        # Test with encoding variation (TITULO instead of TÍTULO)
        result = detect_component_type("TITULO II")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "title"
        assert ordering == "02"
    
    def test_chapter_detection(self):
        result = detect_component_type("CAPÍTULO IV")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "chapter"
        assert ordering == "04"
    
    def test_section_detection(self):
        # Test with standard encoding
        result = detect_component_type("Seção III")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "section"
        assert ordering == "03"
    
    def test_section_with_encoding_variation(self):
        # Test with encoding variation (Seçăo instead of Seção)
        result = detect_component_type("Seçăo V")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "section"
        assert ordering == "05"
    
    def test_article_detection(self):
        result = detect_component_type("Art. 5º Todos são iguais perante a lei")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "article"
        assert ordering == "5"
        assert "iguais" in remaining
    
    def test_article_without_ordinal(self):
        result = detect_component_type("Art. 10 O texto do artigo")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "article"
        assert ordering == "10"
    
    def test_paragraph_detection(self):
        result = detect_component_type("§ 1º As normas definidoras...")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "paragraph"
        assert ordering == "1"
    
    def test_paragraph_unico_detection(self):
        result = detect_component_type("Parágrafo único. Todo o poder emana do povo")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "paragraph"
        assert ordering == "unico"
    
    def test_item_detection(self):
        result = detect_component_type("I - a soberania;")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "item"
        assert ordering == "I"
    
    def test_item_with_dash_variation(self):
        result = detect_component_type("IV – a dignidade da pessoa humana")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "item"
        assert ordering == "IV"
    
    def test_letter_detection(self):
        result = detect_component_type("a) proteção às participações individuais")
        assert result is not None
        comp_type, ordering, remaining = result
        assert comp_type == "letter"
        assert ordering == "a"
    
    def test_plain_text_returns_none(self):
        result = detect_component_type("Este é um texto normal sem marcadores")
        assert result is None


class TestRomanNumerals:
    """Tests for Roman numeral conversion."""
    
    @pytest.mark.parametrize("roman,expected", [
        ("I", 1),
        ("IV", 4),
        ("V", 5),
        ("IX", 9),
        ("X", 10),
        ("XL", 40),
        ("L", 50),
        ("XC", 90),
        ("C", 100),
        ("LXXVIII", 78),
    ])
    def test_roman_to_int(self, roman, expected):
        assert roman_to_int(roman) == expected


class TestAmendmentExtraction:
    """Tests for amendment marker extraction."""
    
    def test_extract_included(self):
        text = "(Incluído pela Emenda Constitucional nº 45, de 2004)"
        amendments = extract_amendments(text)
        assert len(amendments) == 1
        assert amendments[0]["event_type"] == "created"
        assert amendments[0]["amendment_number"] == 45
    
    def test_extract_included_with_encoding_variation(self):
        # Test with encoding variation (Incluído vs Incluído)
        text = "(Incluído pela Emenda Constitucional nş 45, de 2004)"
        amendments = extract_amendments(text)
        assert len(amendments) == 1
        assert amendments[0]["event_type"] == "created"
        assert amendments[0]["amendment_number"] == 45
    
    def test_extract_modified(self):
        text = "(Redação dada pela Emenda Constitucional nº 115, de 2022)"
        amendments = extract_amendments(text)
        assert len(amendments) == 1
        assert amendments[0]["event_type"] == "modified"
        assert amendments[0]["amendment_number"] == 115
    
    def test_extract_modified_with_encoding_variation(self):
        # Test with encoding variation
        text = "(Redaçăo dada pela Emenda Constitucional nş 115, de 2022)"
        amendments = extract_amendments(text)
        assert len(amendments) == 1
        assert amendments[0]["event_type"] == "modified"
        assert amendments[0]["amendment_number"] == 115
    
    def test_extract_repealed(self):
        text = "(Revogado pela Emenda Constitucional nº 32, de 2001)"
        amendments = extract_amendments(text)
        assert len(amendments) == 1
        assert amendments[0]["event_type"] == "repealed"
        assert amendments[0]["amendment_number"] == 32
    
    def test_extract_reference(self):
        text = "(Vide Emenda Constitucional nº 20, de 1998)"
        amendments = extract_amendments(text)
        assert len(amendments) == 1
        assert amendments[0]["event_type"] == "reference"
        assert amendments[0]["amendment_number"] == 20
    
    def test_extract_multiple(self):
        text = """
        (Incluído pela Emenda Constitucional nº 45, de 2004)
        (Redação dada pela Emenda Constitucional nº 115, de 2022)
        """
        amendments = extract_amendments(text)
        assert len(amendments) == 2


class TestLegalComponentModel:
    """Tests for Pydantic models."""
    
    def test_create_article(self):
        article = LegalComponent(
            component_type="article",
            component_id="art_5",
            ordering_id="5",
            content="Todos são iguais perante a lei",
            full_text="Art. 5º Todos são iguais perante a lei",
        )
        assert article.component_type == "article"
        assert article.is_original == True
        assert len(article.events) == 0
    
    def test_article_with_amendment(self):
        event = AmendmentEvent(
            event_type="modified",
            amendment_number=45,
            amendment_date_str="2004",
        )
        article = LegalComponent(
            component_type="article",
            component_id="art_5",
            ordering_id="5",
            content="Modified text",
            full_text="Art. 5º Modified text",
            is_original=False,
            events=[event],
        )
        assert article.is_original == False
        assert len(article.events) == 1
        assert article.events[0].amendment_number == 45
    
    def test_component_with_children(self):
        child = LegalComponent(
            component_type="item",
            component_id="art_5_inc_I",
            ordering_id="I",
            content="a soberania",
            full_text="I - a soberania",
            parent_id="art_5",
        )
        
        article = LegalComponent(
            component_type="article",
            component_id="art_5",
            ordering_id="5",
            content="Text",
            full_text="Art. 5º Text",
            children=[child],
        )
        
        assert len(article.children) == 1
        assert article.children[0].component_id == "art_5_inc_I"

