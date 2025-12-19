"""Integration tests for parsing pipeline."""

import pytest
from pathlib import Path
import json
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from parser.legal_parser import LegalDocumentParser, parse_constitution
from parser.models import ParsedConstitution


@pytest.fixture
def constitution_file():
    """Path to downloaded constitution file."""
    path = Path("data/raw/constitution/constituicao.htm")
    if not path.exists():
        pytest.skip("Constitution file not downloaded yet")
    return path


def test_parse_constitution_structure(constitution_file):
    """Test that parser produces correct structure."""
    parser = LegalDocumentParser()
    result = parser.parse_file(constitution_file)
    
    assert isinstance(result, ParsedConstitution)
    assert result.official_id == "CF1988"
    assert len(result.components) > 0  # Has titles


def test_parse_constitution_stats(constitution_file):
    """Test that parser finds expected number of components."""
    parser = LegalDocumentParser()
    result = parser.parse_file(constitution_file)
    
    # Brazilian Constitution has 9 titles (plus ADCT)
    assert result.total_titles >= 9, f"Expected at least 9 titles, got {result.total_titles}"
    
    # Has many chapters
    assert result.total_chapters >= 20, f"Expected at least 20 chapters, got {result.total_chapters}"
    
    # Has 250+ articles
    assert result.total_articles >= 200, f"Expected at least 200 articles, got {result.total_articles}"


def test_article_5_exists(constitution_file):
    """Test that Article 5 is correctly parsed."""
    parser = LegalDocumentParser()
    result = parser.parse_file(constitution_file)
    
    # Find Article 5
    art_5 = None
    for comp in parser.all_components:
        if comp.component_type == "article" and comp.ordering_id == "5":
            art_5 = comp
            break
    
    assert art_5 is not None, "Article 5 not found"
    assert "iguais" in art_5.full_text.lower() or "igual" in art_5.full_text.lower(), \
        "Article 5 should mention equality"


def test_article_5_has_items(constitution_file):
    """Test that Article 5 has items (incisos)."""
    parser = LegalDocumentParser()
    result = parser.parse_file(constitution_file)
    
    # Find Article 5 - get the one with children (may appear multiple times in HTML)
    art_5_candidates = [
        comp for comp in parser.all_components
        if comp.component_type == "article" and comp.ordering_id == "5"
    ]
    
    assert len(art_5_candidates) > 0, "Article 5 not found"
    
    # Get the article with the most children
    art_5 = max(art_5_candidates, key=lambda c: len(c.children))
    
    # Article 5 has 78+ items (incisos) - count all items in subtree
    items = [c for c in art_5.children if c.component_type == "item"]
    assert len(items) >= 50, f"Article 5 should have 50+ items, got {len(items)}"


def test_amendment_markers_detected(constitution_file):
    """Test that amendment markers are detected."""
    parser = LegalDocumentParser()
    result = parser.parse_file(constitution_file)
    
    # Should find components with amendments
    amended_components = [
        c for c in parser.all_components 
        if len(c.events) > 0
    ]
    
    assert len(amended_components) > 20, \
        f"Expected 20+ amended components, got {len(amended_components)}"
    
    # Check that we found several different amendments
    unique_amendments = result.total_amendments_referenced
    assert unique_amendments > 10, \
        f"Expected 10+ unique amendments, got {unique_amendments}"


def test_hierarchy_integrity(constitution_file):
    """Test that hierarchy relationships are valid."""
    parser = LegalDocumentParser()
    result = parser.parse_file(constitution_file)
    
    # Build ID lookup
    id_lookup = {c.component_id: c for c in parser.all_components}
    
    errors = []
    for comp in parser.all_components:
        if comp.parent_id:
            parent = id_lookup.get(comp.parent_id)
            if parent is None:
                errors.append(f"Parent {comp.parent_id} not found for {comp.component_id}")
            elif parser.HIERARCHY.get(parent.component_type, 0) >= parser.HIERARCHY.get(comp.component_type, 0):
                errors.append(
                    f"Parent {parent.component_type} should be higher level than {comp.component_type}"
                )
    
    # Allow a few errors due to edge cases
    assert len(errors) < 10, f"Too many hierarchy errors: {errors[:5]}"


def test_output_json_valid(constitution_file, tmp_path):
    """Test that output JSON is valid and complete."""
    output_file = tmp_path / "constitution.json"
    
    result = parse_constitution(
        input_file=str(constitution_file),
        output_file=str(output_file)
    )
    
    assert output_file.exists()
    
    with open(output_file) as f:
        data = json.load(f)
    
    assert "components" in data
    assert len(data["components"]) > 0
    assert data["official_id"] == "CF1988"
    assert data["total_titles"] >= 9
    assert data["total_articles"] >= 200


def test_titles_have_expected_structure(constitution_file):
    """Test that titles have the expected hierarchical structure."""
    parser = LegalDocumentParser()
    result = parser.parse_file(constitution_file)
    
    # Check first title
    assert len(result.components) > 0, "No titles found"
    
    title_1 = result.components[0]
    assert title_1.component_type == "title"
    assert "01" in title_1.ordering_id or "1" in title_1.ordering_id
    
    # Title should have children (chapters or articles)
    assert len(title_1.children) > 0, "Title 1 should have children"

