import time
import math
import logging
from morecantile import TileMatrixSet, Tile
from rio_tiler.io import Reader
from rio_tiler.models import ImageData


class CogReader:
    """A reader for a Cloud Optimized GeoTIFF. This class is used to pool readers to 
    avoid opening and closing the same file many times.
    """
    
    def __init__(self, pool, cog: str, tms: TileMatrixSet, unsafe: bool = False):
        self.pool = pool
        self.cog = cog
        self.tms = tms
        self.unsafe = unsafe
        self.last_used = time.time()
        self._set_rio_reader()
        self._set_safe_level()
        self._set_nodata_value()
        
    def close(self):
        """Close the reader."""
        
        self.rio_reader.close()
        
    def download_tile(self, x: int, y: int, z: int, resampling_method="bilinear") -> ImageData:
        """Retrieve an image from a Cloud Optimized GeoTIFF based on a tile index.

        Args:
            tms (TileMatrixSet): The tile matrix set to use.
            x (int): x tile index.
            y (int): y tile index.
            z (int): z tile index.
            geotiff_path (str): Path or URL to the Cloud Optimized GeoTIFF.
            resampling_method (str, optional): RasterIO resampling algorithm. Defaults to "bilinear".

        Returns:
            ImageData: Image data from the Cloud Optimized GeoTIFF.
        """
        
        if z < self.safe_level:
            if not self.unsafe:
                logging.warning(f"Skipping unsafe tile {self.cog} {z,x,y}, generate more overviews or use --unsafe to load anyway")
                return None
            else:
                logging.warning(f"Loading unsafe tile {self.cog} {z,x,y}, consider generating more overviews")
        
        try:

            image_data = self.rio_reader.tile(tile_z=z, tile_x=x, tile_y=y, resampling_method=resampling_method)
            
            # For now set nodata to 0 if nodata is present in the metadata
            # handle this better later
            if self.nodata_value is not None:
                image_data.data[image_data.data == self.nodata_value] = float(0)

            return image_data
        
        except Exception:
            return None       
            
    def return_reader(self):
        """Done with the reader, return it to the pool."""
        
        self.last_used = time.time()
        self.pool.return_reader(self)
        
    def _set_rio_reader(self):
        """Get the reader for the COG."""
        
        self.rio_reader = Reader(self.cog, tms=self.tms)

        
    def _set_safe_level(self):
        """Calculate the safe zoom level to request tiles for. 
        When there are not enough overviews there will be a lot of request to load
        a tile at a low zoom level. This will cause long load times and high memory usage.

        ToDo: This is an estimation, it is not 100% accurate.
        """
        
        self.safe_level = 0
        
        dataset_bounds = self.rio_reader.info().bounds
        dataset_width = self.rio_reader.dataset.width
        dataset_wgs_width = dataset_bounds.right - dataset_bounds.left
        pixels_per_wgs = dataset_width / dataset_wgs_width
        pixels_per_tile_downsampled = 256 * max(self.rio_reader.dataset.overviews(1))
                
        for z in range(0, 24):
            tile_bounds = self.tms.xy_bounds(Tile(x=0, y=0, z=z))
            tile_wgs = tile_bounds.right - tile_bounds.left
            tile_pixels_needed = tile_wgs * pixels_per_wgs
            needed_tiles = math.ceil(tile_pixels_needed / pixels_per_tile_downsampled)
            if needed_tiles == 1:
                self.safe_level = z
                break

    def _set_nodata_value(self):
        """Set the nodata value for the reader."""
        
        reader_info = self.rio_reader.info()
        self.nodata_value = reader_info.nodata_value if hasattr(reader_info, 'nodata_value') else None
