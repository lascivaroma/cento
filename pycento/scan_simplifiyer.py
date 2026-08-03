import re

def simplify_scan(scan):
    """
    >>> simplify_scan("1A1b1c2A2T")
    'DS'
    >>> simplify_scan("3A3T4A4T5A5T6A6X")
    'SSSS'
    >>> simplify_scan("3T4A4b4c5A5b5c6A6X")
    'sDDS'
    >>> simplify_scan("4b4c5A5b5c6A6X")
    'ddDS'
    >>> simplify_scan("1A1b1c2A2T3A3b3c4A")
    'DSDX'
    >>> simplify_scan("5A5b5c6A6X")
    'DS'
    """
    scan = re.sub(r"\dA\d[TX]", "S", scan)
    scan = re.sub(r"\dA\db\dc", "D", scan)
    scan = re.sub(r"\d[TX]", "s", scan)
    scan = re.sub(r"\d[bc]", "d", scan)
    scan = re.sub(r"\dA", "X", scan)
    return scan