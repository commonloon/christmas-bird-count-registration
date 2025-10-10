# Updated by Claude AI on 2025-10-10
"""
CSV Security Utilities

Provides protection against CSV formula injection attacks where malicious input
could be executed as formulas when CSV files are opened in Excel/LibreOffice.
"""


def escape_csv_formula(value):
    """
    Prevent CSV formula injection by escaping dangerous prefixes.

    When CSV files are opened in spreadsheet applications like Excel or LibreOffice Calc,
    cells starting with certain characters are interpreted as formulas and executed.
    This can lead to code execution if malicious input is exported to CSV.

    Dangerous characters at start of cell:
    - = (equals): Formula prefix in most spreadsheet applications
    - + (plus): Alternative formula prefix in some applications
    - - (minus): Alternative formula prefix in some applications
    - @ (at sign): Formula prefix in some applications
    - \\t (tab): Can trigger command execution in some contexts
    - \\r (carriage return): Can trigger command execution in some contexts

    Protection method:
    Prefix dangerous values with a single quote ('). Spreadsheet applications treat
    this as "force text format" and display the value literally without executing it.
    The single quote itself is not displayed in the cell.

    Examples:
        >>> escape_csv_formula("=SUM(1+1)")
        "'=SUM(1+1)"

        >>> escape_csv_formula("John Smith")
        "John Smith"

        >>> escape_csv_formula("+cmd|'/c calc'!A1")
        "'+cmd|'/c calc'!A1"

        >>> escape_csv_formula(123)
        123

    Args:
        value: Any value to be written to CSV (string, number, boolean, None, etc.)

    Returns:
        If value is a string starting with a dangerous character, returns the string
        prefixed with a single quote. Otherwise returns the value unchanged.

    Security Note:
        This function should be applied to ALL user-controlled data before writing to CSV,
        even if the input has already been sanitized, as a defense-in-depth measure.
    """
    # Only process string values
    if not isinstance(value, str):
        return value

    # Empty strings are safe
    if len(value) == 0:
        return value

    # Check if first character is dangerous
    if value[0] in ('=', '+', '-', '@', '\t', '\r'):
        # Prefix with single quote to neutralize formula execution
        return "'" + value

    # Value is safe
    return value
