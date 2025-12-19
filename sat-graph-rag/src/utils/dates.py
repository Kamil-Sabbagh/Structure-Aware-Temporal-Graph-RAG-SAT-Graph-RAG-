"""Date parsing utilities for legal documents."""

import re
from datetime import date
from typing import Optional

from dateutil.parser import parse as dateutil_parse


# Portuguese month names
MONTH_MAP = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


def parse_portuguese_date(date_str: str) -> Optional[date]:
    """Parse a date string in Portuguese format.
    
    Handles formats like:
    - "5 de outubro de 1988"
    - "05/10/1988"
    - "1988-10-05"
    
    Args:
        date_str: Date string to parse
        
    Returns:
        Parsed date or None if parsing fails
    """
    if not date_str:
        return None
    
    date_str = date_str.lower().strip()
    
    # Try Portuguese format: "5 de outubro de 1988"
    pattern = r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})"
    match = re.search(pattern, date_str)
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        year = int(match.group(3))
        
        month = MONTH_MAP.get(month_name)
        if month:
            try:
                return date(year, month, day)
            except ValueError:
                pass
    
    # Try standard date formats
    try:
        parsed = dateutil_parse(date_str, dayfirst=True)
        return parsed.date()
    except Exception:
        pass
    
    return None


def format_date_iso(d: date) -> str:
    """Format a date as ISO string.
    
    Args:
        d: Date to format
        
    Returns:
        ISO formatted date string (YYYY-MM-DD)
    """
    return d.isoformat()


def format_date_portuguese(d: date) -> str:
    """Format a date in Portuguese style.
    
    Args:
        d: Date to format
        
    Returns:
        Portuguese formatted date string
    """
    month_names = [
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
    ]
    return f"{d.day} de {month_names[d.month - 1]} de {d.year}"

