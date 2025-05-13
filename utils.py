"""Unit conversion & other utils"""

def coalesce_int(s, default=0):
    try:
        return int(s)
    except ValueError:
        return default
    
def coalesce_float(s, default=None):
    try:
        return float(s)
    except ValueError:
        return default
    
def coalesce_int_from_float(s, default=0):
    """Safe parse numerical values to int (ex. '2934.123' => 2934)"""
    return coalesce_int(coalesce_float(s, default=default), default=default)

def coalesce(*args):
    for o in args:
        if o is not None:
            return o