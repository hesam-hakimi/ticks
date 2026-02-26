"""ui.ui_theme

Central place for company_name-like theme constants and CSS.
"""

company_name_GREEN = "#00A651"  # placeholder; update to official company_name green if provided


def css() -> str:
    return f"""
    <style>
    .company-header {{
        background: white;
        border-bottom: 1px solid #e6e6e6;
        padding: 8px 12px;
        display:flex;
        align-items:center;
        gap:12px;
    }}
    .company-badge {{
        display:inline-block;
        padding: 2px 8px;
        border-radius: 999px;
        background: {company_name_GREEN};
        color: white;
        font-size: 12px;
    }}
    .company-muted {{
        color: #4b4b4b;
        font-size: 13px;
    }}
    </style>
    """
