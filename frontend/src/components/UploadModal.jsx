import React, { useState, useRef, useEffect } from 'react';
import EXIF from 'exif-js';

// Importing Utils for GPS extraction
const Utils = {
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
  }
};

export const UploadModal = ({
  isOpen,
  onClose,
  onUpload,
  playerPosition
}) => {
  const [splatFile, setSplatFile] = useState(null);
  const [imageFile, setImageFile] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [useImageGps, setUseImageGps] = useState(false);
  const [coordinates, setCoordinates] = useState(playerPosition);
  const [extractingCoordinates, setExtractingCoordinates] = useState(false);
  const [teleportAfterUpload, setTeleportAfterUpload] = useState(true);

  const splatFileRef = useRef(null);
  const imageFileRef = useRef(null);

  // Update coordinates when player position changes (if using current position)
  useEffect(() => {
    if (!useImageGps) {
      setCoordinates(playerPosition);
    }
  }, [playerPosition, useImageGps]);

  const handleSplatFileSelect = (e) => {
    if (e.target.files.length > 0) {
      setSplatFile(e.target.files[0]);
    }
  };

  const handleImageFileSelect = async (e) => {
    if (e.target.files.length > 0) {
      setImageFile(e.target.files[0]);

      if (useImageGps) {
        try {
          setExtractingCoordinates(true);
          setError(null);
          const gpsData = await Utils.extractGpsFromExif(e.target.files[0]);
          setCoordinates(gpsData);
          setExtractingCoordinates(false);
        } catch (err) {
          setExtractingCoordinates(false);
          setError("Could not extract GPS data from image. Using current position instead.");
          console.error("EXIF extraction error:", err);
          setUseImageGps(false);
          setCoordinates(playerPosition);
        }
      }
    }
  };

  const toggleUseImageGps = (value) => {
    setUseImageGps(value);

    // Reset to player position if switching to current position
    if (!value) {
      setCoordinates(playerPosition);
    } else if (imageFile) {
      // Try to extract GPS from image if already selected
      setExtractingCoordinates(true);
      Utils.extractGpsFromExif(imageFile)
        .then(gpsData => {
          setCoordinates(gpsData);
          setExtractingCoordinates(false);
        })
        .catch(() => {
          setError("Could not extract GPS data from image. Using current position instead.");
          setUseImageGps(false);
          setCoordinates(playerPosition);
          setExtractingCoordinates(false);
        });
    }
  };

  const handleUpload = async () => {
    if (!splatFile) {
      setError("Please select a splat file to upload");
      return;
    }

    setIsLoading(true);
    try {
      await onUpload(splatFile, coordinates, teleportAfterUpload);
      onClose();
    } catch (err) {
      setError(`Upload failed: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white p-6 rounded-lg shadow-xl w-full max-w-md">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">Upload Splat</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-100 text-red-700 rounded-md text-sm">
            {error}
          </div>
        )}

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Splat File</label>
          <div className="flex items-center">
            <button
              onClick={() => splatFileRef.current.click()}
              className="bg-blue-50 border border-blue-300 rounded px-4 py-2 text-sm hover:bg-blue-100"
            >
              Select File
            </button>
            <span className="ml-3 text-sm text-gray-500">
              {splatFile ? splatFile.name : 'No file selected'}
            </span>
            <input
              ref={splatFileRef}
              type="file"
              accept=".splat"
              onChange={handleSplatFileSelect}
              className="hidden"
            />
          </div>
        </div>

        <div className="mb-4">
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={useImageGps}
              onChange={(e) => toggleUseImageGps(e.target.checked)}
              className="form-checkbox h-4 w-4 text-blue-600"
            />
            <span className="ml-2 text-sm text-gray-700">Extract GPS from image</span>
          </label>

          {useImageGps && (
            <div className="mt-2">
              <div className="flex items-center">
                <button
                  onClick={() => imageFileRef.current.click()}
                  className="bg-green-50 border border-green-300 rounded px-4 py-2 text-sm hover:bg-green-100"
                  disabled={extractingCoordinates}
                >
                  {extractingCoordinates ? 'Extracting GPS...' : 'Select Image'}
                </button>
                <span className="ml-3 text-sm text-gray-500">
                  {imageFile ? imageFile.name : 'No image selected'}
                </span>
                <input
                  ref={imageFileRef}
                  type="file"
                  accept="image/jpeg,image/jpg"
                  onChange={handleImageFileSelect}
                  className="hidden"
                />
              </div>
              <p className="mt-1 text-xs text-gray-500">
                Only JPEG images with embedded GPS data are supported
              </p>
            </div>
          )}
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
          <div className="bg-gray-50 border border-gray-200 rounded p-3 text-xs font-mono">
            <div>Using: {useImageGps ? 'Image GPS data' : 'Current position'}</div>
            <div>Lat: {coordinates.lat.toFixed(6)}, Lng: {coordinates.lng.toFixed(6)}</div>
          </div>
        </div>

        <div className="mb-4">
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={teleportAfterUpload}
              onChange={(e) => setTeleportAfterUpload(e.target.checked)}
              className="form-checkbox h-4 w-4 text-blue-600"
            />
            <span className="ml-2 text-sm text-gray-700">Teleport to splat after upload</span>
          </label>
        </div>

        <div className="flex justify-end mt-6">
          <button
            onClick={handleUpload}
            className="px-4 py-2 bg-blue-600 text-white rounded shadow-sm text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            disabled={!splatFile || isLoading}
          >
            {isLoading ? 'Uploading...' : 'Upload Splat'}
          </button>
        </div>
      </div>
    </div>
  );
}; 