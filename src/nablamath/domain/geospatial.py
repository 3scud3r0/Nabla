"""Spherical distances, WGS84/Web Mercator transforms and raster NDVI."""
import math

EARTH_RADIUS_M = 6371008.8
MERCATOR_RADIUS_M = 6378137.0
MERCATOR_LATITUDE_LIMIT = 85.0511287798066


def _coordinate(longitude, latitude):
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (longitude,latitude)):
        raise ValueError('Coordinates must be finite numbers')
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise ValueError('Longitude/latitude outside WGS84 range')
    return math.radians(longitude), math.radians(latitude)


def haversine(first, second, *, radius=EARTH_RADIUS_M):
    if len(first) != 2 or len(second) != 2 or not math.isfinite(radius) or radius <= 0:
        raise ValueError('Require two (longitude,latitude) pairs and a positive radius')
    lon1, lat1 = _coordinate(*first); lon2, lat2 = _coordinate(*second)
    a = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 2*radius*math.asin(math.sqrt(min(1,max(0,a))))


def to_web_mercator(longitude, latitude):
    lon, lat = _coordinate(longitude, latitude)
    if abs(latitude) > MERCATOR_LATITUDE_LIMIT:
        raise ValueError('Latitude outside EPSG:3857 extent')
    return MERCATOR_RADIUS_M*lon, MERCATOR_RADIUS_M*math.log(math.tan(math.pi/4+lat/2))


def from_web_mercator(x, y):
    limit = MERCATOR_RADIUS_M*math.pi
    if any(not math.isfinite(v) or abs(v) > limit+1e-6 for v in (x,y)):
        raise ValueError('Coordinate outside EPSG:3857 extent')
    return math.degrees(x/MERCATOR_RADIUS_M), math.degrees(2*math.atan(math.exp(y/MERCATOR_RADIUS_M))-math.pi/2)


def ndvi(near_infrared, red, *, nodata=None):
    """Return a NumPy raster; zero denominators and optional nodata become NaN."""
    try:
        import numpy as np
    except ImportError as exc:
        raise ImportError('Install nablamath[research] for raster processing') from exc
    nir, red = np.asarray(near_infrared,dtype=float), np.asarray(red,dtype=float)
    if nir.shape != red.shape or nir.size > 10000000:
        raise ValueError('Bands require matching shapes within the raster budget')
    valid = np.isfinite(nir) & np.isfinite(red) & ((nir+red) != 0)
    if nodata is not None:
        valid &= (nir != nodata) & (red != nodata)
    result = np.full(nir.shape, np.nan)
    np.divide(nir-red, nir+red, out=result, where=valid)
    return result
