import rasterio
from rasterio.crs import CRS
from rasterio.warp import transform
from geopy.geocoders import Nominatim

def get_image_location(image_path):
    with rasterio.open(image_path) as src:
        bounds = src.bounds
        center_x = (bounds.left + bounds.right) / 2
        center_y = (bounds.top + bounds.bottom) / 2
        lon, lat = transform(src.crs, CRS.from_epsg(4326), [center_x], [center_y])
        
        lat_val = lat[0]
        lon_val = lon[0]
        
        # Get place name from coordinates
        geolocator = Nominatim(user_agent="satellite-analyzer")
        location = geolocator.reverse(f"{lat_val}, {lon_val}", language="ar")
        
        if location:
            place_name = location.address
        else:
            place_name = f"{lat_val:.4f}N, {lon_val:.4f}E"
        
        print(f"Coordinates: {lat_val:.4f}N, {lon_val:.4f}E")
        print(f"Place name (Arabic): {place_name}")
        return place_name

get_image_location("sample.tif")
