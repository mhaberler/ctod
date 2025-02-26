import json

from rio_tiler.io import COGReader

def generate_layer_json(tms, geotiff_path, max_zoom=20):
    """
    Dynamically generate a layer.json for Cesium based on a COG.
    """
    
    with COGReader(geotiff_path) as src:
        
        bounds = src.geographic_bounds
        
        # Cesium always expects all tiles at zoom 0 (startX: 0, endX: 1)
        # With the function available_tiles it is likely it only will return 
        # one tile: startX: 1, endX: 1 for example. So here we skip generating
        # the first zoom level
        available_tiles = [
            [{"startX": 0, "startY": 0, "endX": 1, "endY": 0}]
        ]
        
        # Generate available tiles for zoom levels 1-20
        for zoom in range(1, max_zoom + 1):
            start_x, start_y, end_x, end_y = get_cesium_index_bounds(tms, bounds[0], bounds[1], bounds[2], bounds[3], zoom)
            available_tiles.append([{"startX": start_x, "startY": start_y, "endX": end_x, "endY": end_y}])

        # Generate the layer.json
        layer_json = {
            "tilejson": "2.1.0",
            "name": "CTOD",
            "description": "Cesium Terrain on Demand",
            "version": "1.1.0",
            "format": "quantized-mesh-1.0",
            "attribution": "",
            "schema": "tms",
            "extensions": ["octvertexnormals"],
            "tiles": ["{z}/{x}/{y}.terrain?v={version}"],
            "projection": "EPSG:4326",
            "bounds": [0.00, -90.00, 180.00, 90.00],
            "cogBounds": bounds,
            "available": available_tiles
        }

        return json.dumps(layer_json, indent=2)
    
def get_cesium_index_bounds(
    tms,
    west: float,
    south: float,
    east: float,
    north: float,
    zoom: int,
    truncate: bool = False,
):
    """
    Calculate the tile index bounds for a given bounding box and zoom level.
    """
    
    max_tms_y = tms.minmax(zoom)["y"]["max"]
    ll_epsilon = 1e-11
    
    if truncate:
        west, south = tms.truncate_lnglat(west, south)
        east, north = tms.truncate_lnglat(east, north)

    if west > east:
        bbox_west = (tms.bbox.left, south, east, north)
        bbox_east = (west, south, tms.bbox.right, north)
        bboxes = [bbox_west, bbox_east]
    else:
        bboxes = [(west, south, east, north)]

    for w, s, e, n in bboxes:
        w = max(tms.bbox.left, w)
        s = max(tms.bbox.bottom, s)
        e = min(tms.bbox.right, e)
        n = min(tms.bbox.top, n)

        nw_tile = tms.tile(
            w + ll_epsilon, n - ll_epsilon, zoom
        )
        se_tile = tms.tile(e - ll_epsilon, s + ll_epsilon, zoom)

        min_x = min(nw_tile.x, se_tile.x)
        max_x = max(nw_tile.x, se_tile.x)
        min_y = min(nw_tile.y, se_tile.y)
        max_y = max(nw_tile.y, se_tile.y)
        
        temp_min_y = min_y
        temp_max_y = max_y
        
        # Flip Y Coords for Cesium
        min_y = max_tms_y - temp_max_y
        max_y = max_tms_y - temp_min_y
            
        return min_x, min_y, max_x, max_y