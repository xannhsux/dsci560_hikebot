"""Helper client to fetch hiking routes from the Waymarked Trails API."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import httpx


DEFAULT_BASE_URL = "https://hiking.waymarkedtrails.org/api/v1"


def fetch_routes(
    base_url: str = DEFAULT_BASE_URL,
    theme: Optional[str] = None,
    bbox: Optional[Sequence[float]] = None,
    limit: Optional[int] = None,
    timeout: float = 20.0,
) -> List[Dict[str, Any]]:
    """Fetch hiking routes from the Waymarked Trails API.

    Parameters
    ----------
    base_url:
        Base URL for the API (e.g. ``https://hiking.waymarkedtrails.org/api/v1``).
    theme:
        Optional theme (``hiking``, ``cycling``, etc.). Some API deployments include
        the theme in the host name already, so this parameter is optional.
    bbox:
        Optional bounding box specified as ``(min_lon, min_lat, max_lon, max_lat)``.
    limit:
        Optional limit on the number of routes to fetch.
    timeout:
        HTTP timeout in seconds.
    """

    params: Dict[str, Any] = {}
    if theme:
        params["theme"] = theme
    if bbox:
        params["bbox"] = ",".join(str(coord) for coord in bbox)
    if limit:
        params["limit"] = limit

    url = f"{base_url.rstrip('/')}/routes"
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()

    if isinstance(payload, dict):
        if "routes" in payload and isinstance(payload["routes"], list):
            records: Iterable[Dict[str, Any]] = payload["routes"]
        elif "features" in payload and isinstance(payload["features"], list):
            records = payload["features"]
        else:
            # assume the dict itself is a GeoJSON feature
            records = [payload]  # type: ignore[list-item]
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError("Unexpected Waymarked Trails payload structure.")

    normalized = [_normalize_route(record) for record in records]
    return [route for route in normalized if route is not None]


def _normalize_route(route: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    props = route.get("properties", route)
    geometry = route.get("geometry")

    route_id = props.get("id") or props.get("wid") or route.get("id")
    name = props.get("name") or props.get("title")
    if not route_id or not name:
        return None

    distance_km = _extract_distance_km(props)
    elevation_gain = _extract_elevation_gain(props)
    location = props.get("region") or props.get("country") or props.get("area") or "Unknown"
    difficulty = _map_difficulty(props.get("difficulty") or props.get("sac_scale"))
    summary = props.get("description") or props.get("details") or ""
    gpx_url = props.get("gpx_url") or props.get("gpx") or props.get("kml_url") or ""
    tags = _extract_tags(props.get("tags") or [])
    lat, lon = _extract_coordinates(props, geometry)

    drive_time = _estimate_drive_time(distance_km)

    return {
        "id": str(route_id),
        "name": str(name),
        "location": str(location),
        "distance_km": distance_km,
        "elevation_gain_m": elevation_gain,
        "difficulty": difficulty,
        "drive_time_min": drive_time,
        "tags": tags,
        "gpx_url": gpx_url,
        "summary": summary,
        "latitude": lat,
        "longitude": lon,
    }


def _extract_distance_km(props: Dict[str, Any]) -> float:
    for key in ("distance_km", "length_km", "distance", "length"):
        value = props.get(key)
        if value is None:
            continue
        try:
            distance = float(value)
        except (TypeError, ValueError):
            continue
        if key.endswith("_m"):
            return distance / 1000.0
        return distance
    # fallback if the API only supplies meters
    meters = props.get("distance_m") or props.get("length_m")
    if meters is not None:
        try:
            return float(meters) / 1000.0
        except (TypeError, ValueError):
            pass
    return 0.0


def _extract_elevation_gain(props: Dict[str, Any]) -> int:
    for key in ("elevation_gain_m", "ascent", "climb", "height_diff_up"):
        value = props.get(key)
        if value is None:
            continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return 0


def _map_difficulty(raw: Any) -> str:
    value = str(raw or "").lower()
    if not value:
        return "moderate"
    if value in {"easy", "grade1", "t1"}:
        return "easy"
    if value in {"hard", "difficult", "grade5", "t4", "t5", "t6"}:
        return "hard"
    return "moderate"


def _extract_tags(raw_tags: Any) -> List[str]:
    allowed = {"dog_friendly", "camping", "water_source", "loop", "summit"}
    tags: List[str] = []
    if isinstance(raw_tags, dict):
        raw_iter: Iterable[str] = raw_tags.keys()
    elif isinstance(raw_tags, list):
        raw_iter = raw_tags
    else:
        raw_iter = []

    for tag in raw_iter:
        lowered = str(tag).lower()
        if "dog" in lowered:
            tags.append("dog_friendly")
        elif "camp" in lowered or "tent" in lowered:
            tags.append("camping")
        elif "water" in lowered:
            tags.append("water_source")
        elif "loop" in lowered or "circuit" in lowered:
            tags.append("loop")
        elif "summit" in lowered or "peak" in lowered:
            tags.append("summit")

    # remove duplicates while preserving order
    seen = set()
    filtered = []
    for tag in tags:
        if tag in allowed and tag not in seen:
            filtered.append(tag)
            seen.add(tag)
    return filtered


def _extract_coordinates(props: Dict[str, Any], geometry: Optional[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float]]:
    lat = props.get("latitude") or props.get("lat")
    lon = props.get("longitude") or props.get("lon")
    if _is_number(lat) and _is_number(lon):
        return float(lat), float(lon)

    center = props.get("center")
    if isinstance(center, (list, tuple)) and len(center) >= 2 and _is_number(center[1]) and _is_number(center[0]):
        return float(center[1]), float(center[0])

    if geometry and isinstance(geometry.get("coordinates"), (list, tuple)):
        coords = geometry["coordinates"]
        coord = _first_coordinate(coords)
        if coord:
            lon_val, lat_val = coord
            return lat_val, lon_val

    return None, None


def _first_coordinate(coords: Any) -> Optional[Tuple[float, float]]:
    if isinstance(coords, (list, tuple)):
        if len(coords) == 2 and _is_number(coords[0]) and _is_number(coords[1]):
            return float(coords[0]), float(coords[1])
        for item in coords:
            coord = _first_coordinate(item)
            if coord:
                return coord
    return None


def _estimate_drive_time(distance_km: float) -> int:
    if distance_km <= 0:
        return 90
    return max(30, int(distance_km * 8))


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False
