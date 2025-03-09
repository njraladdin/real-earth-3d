import { TextureLoader } from 'three';
import EXIF from 'exif-js';

// Map utility functions for coordinate transformations and calculations
const MapUtils = {
  fetchTileData: async ({ zoom, x, y }, apiKey) => ({
    texture: await new TextureLoader().loadAsync(`https://api.maptiler.com/maps/hybrid/${zoom}/${x}/${y}.jpg?key=${apiKey}`)
  }),

  latLngToTileNumber: ({ lat, lng }, zoom) => {
    const n = 2 ** zoom;
    return { x: Math.floor(n * ((lng + 180) / 360)), y: Math.floor(n * (1 - Math.log(Math.tan(lat * Math.PI / 180) + 1 / Math.cos(lat * Math.PI / 180)) / Math.PI) / 2), zoom };
  },

  tileNumberToLatLng: ({ x, y }, zoom) => {
    const n = 2 ** zoom;
    const lon = (x / n) * 360 - 180;
    const lat = Math.atan(Math.sinh(Math.PI * (1 - 2 * y / n))) * 180 / Math.PI;
    return { lat, lng: lon };
  },

  extractGpsFromExif: (imageFile) => {
    return new Promise((resolve, reject) => {
      EXIF.getData(imageFile, function () {
        try {
          // Check if GPS data exists
          if (!EXIF.getTag(this, "GPSLatitude") || !EXIF.getTag(this, "GPSLongitude")) {
            return reject(new Error("No GPS data found in image"));
          }

          // Get the GPS data
          const latArray = EXIF.getTag(this, "GPSLatitude");
          const lngArray = EXIF.getTag(this, "GPSLongitude");
          const latRef = EXIF.getTag(this, "GPSLatitudeRef") || "N";
          const lngRef = EXIF.getTag(this, "GPSLongitudeRef") || "E";

          if (!latArray || !lngArray) {
            return reject(new Error("Invalid GPS data format"));
          }

          // Convert to decimal degrees
          const latDecimal = latArray[0] + latArray[1] / 60 + latArray[2] / 3600;
          const lngDecimal = lngArray[0] + lngArray[1] / 60 + lngArray[2] / 3600;

          // Apply reference (N/S, E/W)
          const lat = (latRef === "N") ? latDecimal : -latDecimal;
          const lng = (lngRef === "E") ? lngDecimal : -lngDecimal;

          resolve({ lat, lng });
        } catch (err) {
          console.error("Error parsing EXIF data:", err);
          reject(new Error("Error parsing EXIF data"));
        }
      });
    });
  },

  localPositionToGps: (x, z, refLat, refLng) => {
    // Earth's radius in meters
    const R = 6371000;
    
    // Convert reference lat/lng to radians
    const refLatRad = refLat * (Math.PI / 180);
    const refLngRad = refLng * (Math.PI / 180);
    
    // Calculate angular distance (in radians)
    // No scaling factor here - use actual distance
    const dLat = z / R;  // north-south movement
    const dLng = x / (R * Math.cos(refLatRad));  // east-west movement
    
    // Calculate new coordinates
    const newLat = refLat + dLat * (180 / Math.PI);
    const newLng = refLng + dLng * (180 / Math.PI);
    
    return { lat: newLat, lng: newLng };
  },
  
  // Convert from GPS coordinates to local position
  gpsToLocalPosition: (lat, lng, refLat, refLng) => {
    // Earth's radius in meters
    const R = 6371000;
    
    // Convert to radians
    const latRad = lat * (Math.PI / 180);
    const lngRad = lng * (Math.PI / 180);
    const refLatRad = refLat * (Math.PI / 180);
    const refLngRad = refLng * (Math.PI / 180);
    
    // Calculate differences
    const dLat = latRad - refLatRad;
    const dLng = lngRad - refLngRad;
    
    // Convert to meters
    // For latitude: 1 radian ≈ Earth's radius in meters
    const z = dLat * R;  // north-south distance
    
    // For longitude: need to account for the cosine of latitude
    const x = dLng * R * Math.cos(refLatRad);  // east-west distance
    
    return { x, z };
  }
};

export default MapUtils; 