"""Integration tests for web scraping."""

import requests
import pytest
from pathlib import Path
import json


URLS_TO_CHECK = [
    "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
    "https://www.planalto.gov.br/ccivil_03/constituicao/ConstituicaoCompilado.htm",
    "https://www.planalto.gov.br/ccivil_03/constituicao/Emendas/Emc/quadro_emc.htm",
]


@pytest.mark.parametrize("url", URLS_TO_CHECK)
def test_url_accessible(url):
    """Test that required URLs are accessible."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    response = requests.get(url, timeout=60, allow_redirects=True, headers=headers)
    assert response.status_code == 200, f"URL not accessible: {url}"


def test_constitution_has_expected_content():
    """Test that constitution page has expected content."""
    url = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm"
    response = requests.get(url, timeout=30)
    response.encoding = 'iso-8859-1'
    content = response.text
    
    # Must contain key markers
    assert "TÍTULO I" in content, "Missing TÍTULO I"
    assert "Art. 1" in content, "Missing Art. 1"
    assert "Art. 5" in content, "Missing Art. 5"
    assert "Emenda Constitucional" in content, "Missing amendment references"


# File-based tests (only run after scraping)

@pytest.fixture
def constitution_dir():
    """Path to constitution data directory."""
    return Path("data/raw/constitution")


@pytest.fixture
def amendments_dir():
    """Path to amendments data directory."""
    return Path("data/raw/amendments")


def test_constitution_files_exist(constitution_dir):
    """Test that constitution files were downloaded."""
    if not constitution_dir.exists():
        pytest.skip("Constitution not downloaded yet")
    
    assert (constitution_dir / "constituicao.htm").exists()
    assert (constitution_dir / "constituicao_compilado.htm").exists()


def test_constitution_file_sizes(constitution_dir):
    """Test that constitution files have reasonable size."""
    main_file = constitution_dir / "constituicao.htm"
    
    if not main_file.exists():
        pytest.skip("Constitution not downloaded yet")
    
    assert main_file.stat().st_size > 500_000, "Constitution file too small"


def test_amendments_metadata_valid(amendments_dir):
    """Test that amendments metadata is valid JSON."""
    metadata_file = amendments_dir / "amendments_metadata.json"
    
    if not metadata_file.exists():
        pytest.skip("Amendments not downloaded yet")
    
    with open(metadata_file) as f:
        data = json.load(f)
    
    assert isinstance(data, list)
    assert len(data) > 100, "Expected 100+ amendments"
    
    # Check structure
    for item in data[:5]:
        assert "number" in item
        assert "date_str" in item
        assert "url" in item


def test_amendment_files_match_metadata(amendments_dir):
    """Test that downloaded amendments match metadata."""
    metadata_file = amendments_dir / "amendments_metadata.json"
    
    if not metadata_file.exists():
        pytest.skip("Amendments not downloaded yet")
    
    with open(metadata_file) as f:
        metadata = json.load(f)
    
    expected_numbers = {item["number"] for item in metadata}
    downloaded_files = list(amendments_dir.glob("emc*.htm"))
    downloaded_numbers = set()
    
    for f in downloaded_files:
        # Extract number from filename "emc123.htm"
        num = int(f.stem.replace("emc", ""))
        downloaded_numbers.add(num)
    
    missing = expected_numbers - downloaded_numbers
    assert len(missing) == 0, f"Missing amendment files: {missing}"

