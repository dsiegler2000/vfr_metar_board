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