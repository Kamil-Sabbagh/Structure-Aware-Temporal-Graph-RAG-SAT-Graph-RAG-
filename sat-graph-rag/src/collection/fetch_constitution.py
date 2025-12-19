"""Fetch the Brazilian Federal Constitution."""

from .scraper import PlanaltoScraper
from pathlib import Path


def fetch_constitution(output_dir: str = "data/raw/constitution") -> dict:
    """
    Fetch all constitution-related pages.
    
    Returns:
        dict with paths to downloaded files
    """
    scraper = PlanaltoScraper(output_dir=output_dir)
    results = {}
    
    # 1. Main constitution page (with amendment markers)
    main_url = f"{scraper.BASE_URL}/constituicao.htm"
    main_content = scraper.fetch(main_url)
    if main_content:
        results["main"] = scraper.save_html(
            main_content, 
            "constituicao.htm"
        )
    
    # 2. Compiled version (current consolidated text)
    compiled_url = f"{scraper.BASE_URL}/ConstituicaoCompilado.htm"
    compiled_content = scraper.fetch(compiled_url)
    if compiled_content:
        results["compiled"] = scraper.save_html(
            compiled_content,
            "constituicao_compilado.htm"
        )
    
    # 3. ADCT (Transitional Provisions) - often on same page but check
    # The ADCT is typically at anchor #adct in the main page
    
    return results


def verify_constitution_download(output_dir: str = "data/raw/constitution") -> bool:
    """Verify that constitution files were downloaded correctly."""
    output_path = Path(output_dir)
    
    main_file = output_path / "constituicao.htm"
    compiled_file = output_path / "constituicao_compilado.htm"
    
    checks = {
        "main_exists": main_file.exists(),
        "compiled_exists": compiled_file.exists(),
        "main_has_content": main_file.stat().st_size > 100000 if main_file.exists() else False,
        "compiled_has_content": compiled_file.stat().st_size > 100000 if compiled_file.exists() else False,
    }
    
    # Content checks
    if main_file.exists():
        content = main_file.read_text(encoding='utf-8')
        checks["has_title_i"] = "TÍTULO I" in content
        checks["has_art_1"] = "Art. 1" in content
        checks["has_art_5"] = "Art. 5" in content
        checks["has_amendments"] = "Emenda Constitucional" in content
    
    all_passed = all(v for v in checks.values() if isinstance(v, bool))
    
    print("Constitution Download Verification:")
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
    
    return all_passed


if __name__ == "__main__":
    fetch_constitution()
    verify_constitution_download()

