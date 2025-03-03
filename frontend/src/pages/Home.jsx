import React, { useRef, useEffect, useState, forwardRef, Suspense, useMemo } from 'react';
import { Canvas, useFrame, useThree, useLoader } from '@react-three/fiber';

import { TextureLoader, Vector3 } from 'three';
import { Text, Edges, Splat } from '@react-three/drei';
import { ref, uploadBytesResumable, getDownloadURL, deleteObject } from 'firebase/storage';
import { storage } from '../firebaseConfig';
import { useVelocity, useCameraController } from '../hooks';
import { db } from '../firebaseConfig';
import { doc, setDoc, getDoc, getDocs, deleteDoc, updateDoc, collection } from 'firebase/firestore';
import * as THREE from 'three';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader';
import EXIF from 'exif-js';
import { Skybox, SkyWithSun } from '../components/SkyComponents';



//Config module 
const Config = { API_KEY: '5bpPlOMeEXIFV9UuKHrW', CHUNK_SIZE: 10, 
  INITIAL_POSITION: { lat: 33.80358961071113, lng: 10.951546694824309 }, ZOOM_LEVEL: 20, 
VOID_MODE: true, SHOW_BOUNDARIES: false };


// Utilities module
const Utils = {
  fetchTileData: async ({ zoom, x, y }) => ({
    texture: await new TextureLoader().loadAsync(`https://api.maptiler.com/maps/hybrid/${zoom}/${x}/${y}.jpg?key=${Config.API_KEY}`)
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
  
  // New utility function to convert from local position back to GPS coordinates
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

// Convert Components object members to individual React components

const Cube = forwardRef(({ onMove, camera, isPointerLocked }, ref) => {
  const velocity = useVelocity(isPointerLocked, onMove);
  useFrame(() => {
    if (ref.current && isPointerLocked) {
      const direction = new Vector3().copy(camera.getWorldDirection(new Vector3())).setY(0).normalize();
      ref.current.position.addScaledVector(direction, velocity.current.z);
      ref.current.position.addScaledVector(new Vector3(-direction.z, 0, direction.x), velocity.current.x);
      ref.current.rotation.y = Math.atan2(-direction.x, -direction.z);
      onMove(ref.current.position);
    }
  });
  return (
    <mesh ref={ref} position={[0, 1, 0]}>
      <boxGeometry args={[0.07, 0.1, 0.05]} />
      <meshStandardMaterial color="red" />
    </mesh>
  );
});

const Platform = React.memo(({ position, texture }) => (
  <mesh position={position}>
    <boxGeometry args={[10, 1, 10]} />
    <meshStandardMaterial
      map={texture}
      color={!texture ? 'grey' : '#8D6E63'}
      transparent={false}
      opacity={1}
      depthWrite={true}
    />
    <mesh position={[0, 0.01, 0]}>
      <boxGeometry args={[10, 0.1, 10]} />
      <meshStandardMaterial
        color="#8D6E63"
        roughness={0.9}
        metalness={1.05}
        depthWrite={true}
      />
    </mesh>
    <Edges color="black" />
    <Text
      position={[0, 0.51, 0]}
      rotation={[-Math.PI / 2, 0, 0]}
      fontSize={0.5}
      color="black"
      anchorX="center"
      anchorY="middle"
    >
      {`${position[0] / Config.CHUNK_SIZE},${position[2] / Config.CHUNK_SIZE}`}
    </Text>
  </mesh>
), (prevProps, nextProps) => {
  return (
    prevProps.position === nextProps.position &&
    prevProps.texture === nextProps.texture
  );
});

const Slider = ({ label, value, onChange, min, max, step }) => {
  const handleFineAdjustment = (increment) => {
    const newValue = parseFloat(value) + increment;
    // Ensure the new value stays within bounds
    if (newValue >= parseFloat(min) && newValue <= parseFloat(max)) {
      onChange({ target: { value: newValue } });
    }
  };

  return (
    <div className="mt-2">
      <div className="flex items-center justify-between mb-1">
        <label className="block text-sm">{label}</label>
        <div className="flex gap-1">
          <button
            className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded"
            onClick={() => handleFineAdjustment(-0.1)}
            title="Decrease by 0.1"
          >
            -0.1
          </button>
          <button
            className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded"
            onClick={() => handleFineAdjustment(-0.01)}
            title="Decrease by 0.01"
          >
            -0.01
          </button>
          <button
            className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded"
            onClick={() => handleFineAdjustment(0.01)}
            title="Increase by 0.01"
          >
            +0.01
          </button>
          <button
            className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded"
            onClick={() => handleFineAdjustment(0.1)}
            title="Increase by 0.1"
          >
            +0.1
          </button>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={onChange}
          className="w-full"
        />
        <span className="text-xs w-12 text-right">{value.toFixed(3)}</span>
      </div>
    </div>
  );
};

const SplatManager = ({
  playerPosition,
  onSplatSelection,
  selectedSplat,
  onTeleport,
  onSplatListUpdate
}) => {
  const [uploadingSplat, setUploadingSplat] = useState(false);
  const [nearbySplats, setNearbySplats] = useState([]);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const lastFetchPosition = useRef(null);

  useEffect(() => {
    // Only fetch if we've moved significantly (e.g., more than 100 meters)
    const shouldFetch = !lastFetchPosition.current ||
      Math.abs(lastFetchPosition.current.lat - playerPosition.lat) > 0.001 ||
      Math.abs(lastFetchPosition.current.lng - playerPosition.lng) > 0.001;

    if (!shouldFetch) return;

    const fetchNearbySplats = async () => {
      try {
        const splatsSnapshot = await getDocs(collection(db, 'splats'));
        const splatsData = splatsSnapshot.docs.map(doc => ({
          id: doc.id,
          ...doc.data()
        }));

        setNearbySplats(splatsData);
        lastFetchPosition.current = playerPosition;

        if (selectedSplat && !selectedSplat._editing) {
          const updatedSplat = splatsData.find(splat => splat.id === selectedSplat.id);
          if (updatedSplat) {
            onSplatSelection({
              ...updatedSplat,
              _editing: true
            });
          }
        }
      } catch (error) {
        console.error("Error fetching splats:", error);
      }
    };

    fetchNearbySplats();
  }, [Math.floor(playerPosition.lat * 1000), Math.floor(playerPosition.lng * 1000)]); // Only update when position changes significantly

  const handleUploadSplat = async (splatFile, coordinates, shouldTeleport = true) => {
    setUploadingSplat(true);

    try {
      // Generate unique ID for the splat
      const splatId = Date.now().toString();

      // Upload to Firebase storage
      const splatRef = ref(storage, `splats/${splatId}/${splatFile.name}`);
      const uploadTask = uploadBytesResumable(splatRef, splatFile);

      // Wait for upload to complete
      await uploadTask;

      // Get the download URL
      const downloadURL = await getDownloadURL(splatRef);

      // Create a new document in the splats collection
      const newSplat = {
        id: splatId,
        name: splatFile.name,
        url: downloadURL,
        coordinates: coordinates,
        position: [0, 1, 0],
        rotation: [0, 0, 0],
        scale: [0.5, 0.5, 0.5],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };

      await setDoc(doc(db, 'splats', splatId), newSplat);

      // Update local state
      setNearbySplats(prev => [...prev, newSplat]);
      
      // Notify parent component about the new splat
      if (onSplatListUpdate) {
        onSplatListUpdate([...nearbySplats, newSplat]);
      }

      // Add to local state and select it
      onSplatSelection(newSplat);

      // Only teleport if the flag is true
      if (shouldTeleport) {
        onTeleport(coordinates);
      }

      return newSplat;
    } catch (error) {
      console.error("Error uploading splat:", error);
      throw error;
    } finally {
      setUploadingSplat(false);
    }
  };

  const handleSplatSelection = (splat) => {
    onSplatSelection(splat);
  };

  const deleteSplat = async (splatId) => {
    if (!window.confirm("Are you sure you want to delete this splat?")) return;

    try {
      const splatToDelete = nearbySplats.find(splat => splat.id === splatId);

      // Delete from Firebase Storage if it's a Firebase URL
      if (splatToDelete.url.includes('firebasestorage.googleapis.com')) {
        try {
          const fileRef = ref(storage, splatToDelete.url);
          await deleteObject(fileRef);
        } catch (storageError) {
          console.error("Error deleting from storage:", storageError);
        }
      }

      // Delete from Firestore
      await deleteDoc(doc(db, 'splats', splatId));

      // Update local state
      const updatedSplats = nearbySplats.filter(splat => splat.id !== splatId);
      setNearbySplats(updatedSplats);
      
      // Notify parent component about the deleted splat
      if (onSplatListUpdate) {
        onSplatListUpdate(updatedSplats);
      }

      // If the deleted splat was selected, deselect it
      if (selectedSplat && selectedSplat.id === splatId) {
        onSplatSelection(null);
      }

    } catch (error) {
      console.error("Error deleting splat:", error);
      alert("Failed to delete splat. Please try again.");
    }
  };

  return (
    <>
      <div className="absolute top-5 right-5 z-10 bg-white p-5 rounded-xl shadow-xl w-96 h-[90vh] flex flex-col">
        <div className="flex justify-between items-center mb-4 pb-3 border-b border-gray-100">
          <h2 className="font-medium text-gray-800">
            <span className="text-sm text-gray-500">Nearby Splats</span><br />
            {nearbySplats.length} found
          </h2>
          <button
            className="bg-blue-500 hover:bg-blue-600 text-white rounded-md px-3 py-2 text-sm transition-colors duration-200"
            onClick={() => setIsUploadModalOpen(true)}
            disabled={uploadingSplat}
          >
            {uploadingSplat ? 'Uploading...' : 'Upload Splat'}
          </button>
        </div>

        <div className="flex-grow overflow-y-auto pr-1 space-y-3">
          {nearbySplats.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 text-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 22V12h6v10" />
              </svg>
              <p>No splats found nearby.<br />Upload a splat file to view 3D content.</p>
            </div>
          ) : (
            nearbySplats.map((splat) => (
              <div
                key={splat.id}
                className={`p-3 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors ${selectedSplat && selectedSplat.id === splat.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                  }`}
                onClick={() => handleSplatSelection(splat)}
              >
                <div className="flex justify-between items-center">
                  <div>
                    <div className="font-medium text-sm">{splat.name || `Splat ${splat.id}`}</div>
                    <div className="text-xs text-gray-500">
                      {new Date(splat.createdAt).toLocaleDateString()}
                    </div>
                    <div className="text-xs text-gray-500">
                      Lat: {splat.coordinates?.lat.toFixed(4)}, Lng: {splat.coordinates?.lng.toFixed(4)}
                    </div>
                  </div>
                  <div className="flex items-center">
                    {selectedSplat && selectedSplat.id === splat.id && (
                      <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-md mr-2">
                        Selected
                      </span>
                    )}
                    <button
                      className="text-red-500 hover:text-red-700 bg-white rounded-full p-1 hover:bg-red-50 transition-colors"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteSplat(splat.id);
                      }}
                      title="Delete Splat"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUpload={handleUploadSplat}
        playerPosition={playerPosition}
      />
    </>
  );
};

const SceneController = ({ onMove, onRotate, onCameraMove, isPointerLocked, isClickingScene }) => {
  const cubeRef = useRef();
  const { camera } = useThree();

  useCameraController(cubeRef, isPointerLocked && isClickingScene);

  useFrame(() => {
    if (isPointerLocked) {
      const direction = new Vector3();
      camera.getWorldDirection(direction);

      const rotation = {
        x: Math.atan2(direction.y, Math.sqrt(direction.x * direction.x + direction.z * direction.z)),
        y: Math.atan2(direction.x, direction.z),
        z: 0
      };

      onRotate(rotation);
      
      // Update camera position
      onCameraMove({
        x: camera.position.x,
        y: camera.position.y,
        z: camera.position.z
      });
    }
  });

  return <Cube ref={cubeRef} onMove={onMove} camera={camera} isPointerLocked={isPointerLocked} />;
};

const SplatModel = React.memo(({ splatData, cameraPosition, isSelected, showBoundary }) => {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const { camera } = useThree();
  const groupRef = useRef();
  const boundingBoxRef = useRef(new THREE.Box3());
  const [isPlayerInside, setIsPlayerInside] = useState(false);

  const splatUrl = splatData?.url;

  // Use the position from props, defaulting to [0,0,0] since the group is already positioned
  const position = splatData?.position || [0, 0, 0];
  const rotation = splatData?.rotation || [0, 0, 0];
  const scale = splatData?.scale ?
    (Array.isArray(splatData.scale) ? splatData.scale : [splatData.scale, splatData.scale, splatData.scale]) :
    [0.5, 0.5, 0.5];

  // Calculate the bounding box dimensions based on scale
  const boundingBoxSize = useMemo(() => {
    // Create dimensions that better match the actual splat volume
    // We use different multipliers for each dimension to account for typical splat shapes
    return [
      Math.max(...scale) * 2.0, // width (X)
      Math.max(...scale) * 2.0, // height (Y)
      Math.max(...scale) * 2.0  // depth (Z)
    ];
  }, [scale]);

  // Only check URL validity once when the URL changes
  useEffect(() => {
    if (!splatUrl) {
      setIsLoading(false);
      return;
    }

    // For blob URLs or if we've already loaded this URL, skip the check
    if (splatUrl.startsWith('blob:') || !isLoading) {
      setIsLoading(false);
      return;
    }

    fetch(splatUrl, { method: 'HEAD' })
      .then(response => {
        if (response.ok) {
          setIsLoading(false);
        } else {
          setError('Splat file not found. Please convert your PLY file to SPLAT format.');
          setIsLoading(false);
        }
      })
      .catch(err => {
        setError(`Error loading splat file: ${err.message}`);
        setIsLoading(false);
      });
  }, [splatUrl]); // Only depend on URL changes, not other props

  // Update the bounding box and check if camera is inside in each frame
  useFrame(() => {
    if (groupRef.current) {
      // Get the world position of the splat center
      const splatWorldPosition = new THREE.Vector3();
      groupRef.current.getWorldPosition(splatWorldPosition);
      
      // Create a world matrix that includes the group's transformations
      const worldMatrix = new THREE.Matrix4();
      groupRef.current.updateMatrixWorld();
      worldMatrix.copy(groupRef.current.matrixWorld);
      
      // Create the bounding box in local space
      const halfWidth = boundingBoxSize[0] / 2;
      const halfHeight = boundingBoxSize[1] / 2;
      const halfDepth = boundingBoxSize[2] / 2;
      
      // Set the bounding box min and max points
      boundingBoxRef.current.min.set(-halfWidth, -halfHeight, -halfDepth);
      boundingBoxRef.current.max.set(halfWidth, halfHeight, halfDepth);
      
      // Transform the bounding box to world space
      boundingBoxRef.current.applyMatrix4(worldMatrix);
      
      // Check if camera is inside the bounding box
      const isInside = boundingBoxRef.current.containsPoint(camera.position);
      
      // Only update state if it changed to avoid unnecessary re-renders
      if (isInside !== isPlayerInside) {
        setIsPlayerInside(isInside);
      }
      
      // Calculate distance from camera to splat center for regular sorting
      const distanceToCamera = camera.position.distanceTo(splatWorldPosition);
      
      // Store both values on the group for sorting
      groupRef.current.userData.distanceToCamera = distanceToCamera;
      groupRef.current.userData.isPlayerInside = isInside;
      
      // Set render order based on whether camera is inside the bounding box
      // Higher render order means it renders on top
      if (isInside) {
        groupRef.current.renderOrder = 1000; // High priority if camera is inside
      } else {
        // For splats the camera is not inside, sort by distance (farther = lower priority)
        // We use a negative value to ensure splats that contain the camera always render on top
        groupRef.current.renderOrder = -Math.floor(distanceToCamera * 10);
      }
    }
  });

  if (!splatUrl) {
    return (
      <Text
        position={[0, 1, 0]}
        fontSize={0.1}
        color="blue"
        anchorX="center"
        anchorY="middle"
      >
        No splat model available.
        Upload a splat file to view 3D content.
      </Text>
    );
  }

  if (error) {
    return (
      <Text
        position={[0, 1, 0]}
        fontSize={0.1}
        color="red"
        anchorX="center"
        anchorY="middle"
      >
        {error}
      </Text>
    );
  }

  return (
    <group ref={groupRef}>
      {isSelected && (
        <>
          {/* Selection indicator - glowing sphere around the splat */}
          <mesh renderOrder={1000}>
            <sphereGeometry args={[Math.max(...scale) * 1.2, 32, 32]} />
            <meshBasicMaterial 
              color="#4285F4" 
              transparent={true} 
              opacity={0.15} 
              depthWrite={false}
              depthTest={false}
              side={THREE.DoubleSide}
            />
          </mesh>
          
          {/* Selection label above the splat */}
          <Text
            position={[0, Math.max(...scale) * 1.5, 0]}
            fontSize={0.2}
            color="#4285F4"
            anchorX="center"
            anchorY="middle"
            backgroundColor="rgba(255,255,255,0.7)"
            padding={0.1}
            borderRadius={0.05}
          >
            SELECTED
          </Text>
        </>
      )}

      {/* Visualization of the bounding box */}
      {showBoundary && (
        <>
          {/* Bounding box wireframe */}
          <mesh visible={true}>
            <boxGeometry args={boundingBoxSize} />
            <meshBasicMaterial 
              color={isPlayerInside ? "rgba(0, 255, 0, 0.2)" : "rgba(255, 0, 0, 0.2)"} 
              wireframe={true} 
              transparent={true} 
              opacity={0.5} 
              depthWrite={false}
            />
          </mesh>
          
          {/* Bounding box faces */}
          <mesh visible={true}>
            <boxGeometry args={boundingBoxSize} />
            <meshBasicMaterial 
              color={isPlayerInside ? "#00ff00" : "#ff0000"} 
              transparent={true} 
              opacity={0.05} 
              depthWrite={false}
              side={THREE.DoubleSide}
            />
          </mesh>
          
          {/* Add a text label showing the dimensions and status */}
          <Text
            position={[0, boundingBoxSize[1]/2 + 0.3, 0]}
            fontSize={0.15}
            color={isPlayerInside ? "green" : "red"}
            anchorX="center"
            anchorY="middle"
            backgroundColor="rgba(0,0,0,0.5)"
            padding={0.05}
          >
            {`Size: ${boundingBoxSize[0].toFixed(1)}×${boundingBoxSize[1].toFixed(1)}×${boundingBoxSize[2].toFixed(1)} | ${isPlayerInside ? "INSIDE" : "OUTSIDE"}`}
          </Text>
          
          {/* Add corner markers for better visibility */}
          {[
            [1, 1, 1], [1, 1, -1], [1, -1, 1], [1, -1, -1],
            [-1, 1, 1], [-1, 1, -1], [-1, -1, 1], [-1, -1, -1]
          ].map((corner, i) => (
            <mesh 
              key={`corner-${i}`}
              position={[
                corner[0] * boundingBoxSize[0]/2 * 0.99, 
                corner[1] * boundingBoxSize[1]/2 * 0.99, 
                corner[2] * boundingBoxSize[2]/2 * 0.99
              ]}
            >
              <sphereGeometry args={[0.05, 8, 8]} />
              <meshBasicMaterial 
                color={isPlayerInside ? "green" : "red"} 
                transparent={false}
              />
            </mesh>
          ))}
        </>
      )}

      <Splat
        src={splatUrl}
        scale={scale}
        position={position}
        rotation={rotation}
        transparent={true}
        depthWrite={isPlayerInside} // Enable depth writing when camera is inside
        depthTest={true}
        userData={{ 
          centerBased: true,
          isPlayerInside: isPlayerInside
        }}
        sortPoints={true}
      />

      {isLoading && (
        <Text
          position={[0, 1, 0]}
          fontSize={0.2}
          color="black"
          anchorX="center"
          anchorY="middle"
        >
          Loading Splat Model...
        </Text>
      )}
    </group>
  );
}, (prevProps, nextProps) => {
  // Update comparison to include coordinates and selection state
  return (
    prevProps.splatData.url === nextProps.splatData.url &&
    JSON.stringify(prevProps.splatData.coordinates) === JSON.stringify(nextProps.splatData.coordinates) &&
    JSON.stringify(prevProps.splatData.position) === JSON.stringify(nextProps.splatData.position) &&
    JSON.stringify(prevProps.splatData.rotation) === JSON.stringify(nextProps.splatData.rotation) &&
    JSON.stringify(prevProps.splatData.scale) === JSON.stringify(nextProps.splatData.scale) &&
    prevProps.isSelected === nextProps.isSelected &&
    prevProps.showBoundary === nextProps.showBoundary
  );
});

const UploadModal = ({
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

// Add a BoundaryControls component to the App component
const BoundaryControls = ({ showBoundaries, setShowBoundaries }) => {
  return (
    <div className="absolute bottom-5 left-5 z-10 bg-white p-3 rounded-lg shadow-md">
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="showBoundaries"
          checked={showBoundaries}
          onChange={(e) => setShowBoundaries(e.target.checked)}
          className="w-4 h-4"
        />
        <label htmlFor="showBoundaries" className="text-sm font-medium">
          Show Splat Boundaries
        </label>
      </div>
      <div className="text-xs text-gray-500 mt-1">
        Press 'B' key to toggle boundaries
      </div>
    </div>
  );
};

// Main App component remains mostly the same, but now uses the individual components directly
const App = () => {
  const [platforms, setPlatforms] = useState(new Set(['0,0']));
  const [data, setData] = useState({});
  const [currentChunk, setCurrentChunk] = useState('0_0');
  const [isPointerLocked, setIsPointerLocked] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [playerPosition, setPlayerPosition] = useState({ lat: Config.INITIAL_POSITION.lat, lng: Config.INITIAL_POSITION.lng });
  const [playerDirection, setPlayerDirection] = useState({ x: 0, y: 0, z: 0 });
  const [allSplats, setAllSplats] = useState([]);
  const [selectedSplat, setSelectedSplat] = useState(null);
  const [isClickingScene, setIsClickingScene] = useState(false);
  const [cameraPosition, setCameraPosition] = useState({ x: 0, y: 0, z: 0 });
  const [cubeLocalPosition, setCubeLocalPosition] = useState({ x: 0, z: 0 });
  const [showBoundaries, setShowBoundaries] = useState(Config.SHOW_BOUNDARIES);

  const fetchedPlatforms = useRef(new Set());

  // First effect - one-time fetch of splats when component mounts
  useEffect(() => {
    const fetchSplats = async () => {
      try {
        const splatsSnapshot = await getDocs(collection(db, 'splats'));
        const splatsData = splatsSnapshot.docs.map(doc => ({
          id: doc.id,
          ...doc.data()
        }));

        setAllSplats(splatsData.map(splat => {
          if (selectedSplat && splat.id === selectedSplat.id && selectedSplat._editing) {
            return {
              ...splat,
              position: selectedSplat.position,
              rotation: selectedSplat.rotation,
              scale: selectedSplat.scale,
              coordinates: selectedSplat.coordinates,
              _editing: true
            };
          }
          return splat;
        }));
      } catch (error) {
        console.error("Error fetching splats:", error);
      }
    };

    fetchSplats();
  }, []); // Empty dependency array - only runs once on mount

  // Second effect - handle platform data and pointer lock
  useEffect(() => {
    const fetchPlatformData = async pos => {
      // Skip if we've already fetched this platform
      if (fetchedPlatforms.current.has(pos)) return;

      console.log('fetching data for platform ' + pos);
      fetchedPlatforms.current.add(pos);

      const [chunkX, chunkZ] = pos.split(',').map(Number);
      const tile = Utils.latLngToTileNumber(Config.INITIAL_POSITION, Config.ZOOM_LEVEL);
      const tileData = await Utils.fetchTileData({ zoom: Config.ZOOM_LEVEL, x: tile.x + chunkX, y: tile.y + chunkZ });
      
      // Simply store the tile data without any chunk information
      setData(prev => ({ ...prev, [pos]: tileData }));
    };

    // Fetch any new platforms
    platforms.forEach(pos => fetchPlatformData(pos));

    // Handle pointer lock
    const handlePointerLockChange = () => {
      setIsPointerLocked(document.pointerLockElement !== null);
    };

    document.addEventListener('pointerlockchange', handlePointerLockChange);
    return () => document.removeEventListener('pointerlockchange', handlePointerLockChange);
  }, [platforms]);

  const handleCubeMove = ({ x, z }) => {
    // Store the cube's local position for debugging
    setCubeLocalPosition({ x, z });
    
    // Convert cube's 3D position to GPS coordinates
    // using INITIAL_POSITION as the reference point
    const { lat, lng } = Utils.localPositionToGps(
      x, 
      z, 
      Config.INITIAL_POSITION.lat, 
      Config.INITIAL_POSITION.lng
    );
    
    // Update player's GPS position
    setPlayerPosition({ lat, lng });
    
    // Calculate chunks for loading map tiles
    const chunkX = Math.floor((x + Config.CHUNK_SIZE / 2) / Config.CHUNK_SIZE);
    const chunkZ = Math.floor((z + Config.CHUNK_SIZE / 2) / Config.CHUNK_SIZE);
    const tile = Utils.latLngToTileNumber(Config.INITIAL_POSITION, Config.ZOOM_LEVEL);
    const newChunk = `${tile.x + chunkX}_${tile.y + chunkZ}`;
    
    setCurrentChunk(newChunk);
    setPlatforms(prev => new Set([...prev, `${chunkX},${chunkZ}`, `${chunkX + 1},${chunkZ}`, `${chunkX - 1},${chunkZ}`, `${chunkX},${chunkZ + 1}`, `${chunkX},${chunkZ - 1}`]));
  };

  const handleCameraRotation = (rotation) => {
    setPlayerDirection(rotation);
  };

  const handleSplatSelection = (splat) => {
    setSelectedSplat(splat);
  };

  // Add this new function to handle splat list updates from SplatManager
  const handleSplatListUpdate = (updatedSplats) => {
    setAllSplats(updatedSplats);
  };

  const handleModelChange = (type, value, index) => {
    if (!selectedSplat) return;

    // Create the updated splat object
    const updatedSplat = {
      ...selectedSplat,
      _editing: true,
      [type]: type === 'scale'
        ? [value, value, value]
        : selectedSplat[type].map((v, i) => (i === index ? value : v))
    };

    // Update both states in one batch to prevent flickering
    const updatedAllSplats = allSplats.map(splat =>
      splat.id === selectedSplat.id ? updatedSplat : splat
    );

    setSelectedSplat(updatedSplat);
    setAllSplats(updatedAllSplats);
  };

  const handleCoordinateChange = (lat, lng) => {
    if (!selectedSplat) return;

    // Create a copy of the selected splat with updated coordinates
    // but DO NOT modify the position values
    const updatedSplat = {
      ...selectedSplat,
      _editing: true,
      coordinates: { lat, lng }
    };
    
    // Update both states in one batch to prevent flickering
    const updatedAllSplats = allSplats.map(splat =>
      splat.id === selectedSplat.id ? updatedSplat : splat
    );

    setSelectedSplat(updatedSplat);
    setAllSplats(updatedAllSplats);
  };

  const handleSavePosition = async () => {
    if (!selectedSplat) return;

    setIsSaving(true);
    try {
      const { _editing, ...splatToSave } = selectedSplat;

      // Update in Firestore
      await updateDoc(doc(db, 'splats', selectedSplat.id), {
        position: selectedSplat.position,
        rotation: selectedSplat.rotation,
        scale: selectedSplat.scale,
        coordinates: selectedSplat.coordinates,
        updatedAt: new Date().toISOString()
      });

      // Update local state but maintain the current values
      const updatedSplat = { ...selectedSplat, _editing: false };
      setSelectedSplat(updatedSplat);
      setAllSplats(prev => prev.map(splat =>
        splat.id === selectedSplat.id ? updatedSplat : splat
      ));

    } catch (error) {
      console.error("Error saving position:", error);
      alert('Error saving position data. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const teleportToLocation = (coordinates) => {
    // Set player position to the new coordinates
    setPlayerPosition(coordinates);
    
    // Convert GPS coordinates to local 3D position
    const localPosition = Utils.gpsToLocalPosition(
      coordinates.lat,
      coordinates.lng,
      Config.INITIAL_POSITION.lat,
      Config.INITIAL_POSITION.lng
    );
    
    // Update the cube local position for debugging display
    setCubeLocalPosition({ 
      x: localPosition.x, 
      z: localPosition.z 
    });
    
    // Calculate chunks for loading map tiles
    const chunkX = Math.floor((localPosition.x + Config.CHUNK_SIZE / 2) / Config.CHUNK_SIZE);
    const chunkZ = Math.floor((localPosition.z + Config.CHUNK_SIZE / 2) / Config.CHUNK_SIZE);
    const tile = Utils.latLngToTileNumber(Config.INITIAL_POSITION, Config.ZOOM_LEVEL);
    const newChunk = `${tile.x + chunkX}_${tile.y + chunkZ}`;
    
    setCurrentChunk(newChunk);
    
    // Update platforms to load around this position
    setPlatforms(new Set([
      `${chunkX},${chunkZ}`,
      `${chunkX + 1},${chunkZ}`,
      `${chunkX - 1},${chunkZ}`,
      `${chunkX},${chunkZ + 1}`,
      `${chunkX},${chunkZ - 1}`,
      `${chunkX + 1},${chunkZ + 1}`,
      `${chunkX - 1},${chunkZ - 1}`,
      `${chunkX + 1},${chunkZ - 1}`,
      `${chunkX - 1},${chunkZ + 1}`
    ]));
  };

  // Add these handlers
  const handleSceneMouseDown = (e) => {
    // Only set clicking if the click was on the canvas
    if (e.target.tagName === 'CANVAS') {
      setIsClickingScene(true);
    }
  };

  const handleSceneMouseUp = () => {
    setIsClickingScene(false);
  };

  // Update camera position in SceneController
  const handleCameraMove = (position) => {
    setCameraPosition(position);
  };

  // Add effect to sync global boundary state with keyboard
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'b' || e.key === 'B') {
        setShowBoundaries(prev => !prev);
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="relative flex">
      {/* Geo Location Display with added local position and chunk */}
      <div className="absolute top-10 left-[500px] z-20 bg-white bg-opacity-80 p-3 rounded-lg shadow-md">
        <h3 className="text-sm font-semibold text-gray-700 mb-1">Current Location</h3>
        <div className="text-xs text-gray-600 mb-2">
          <div>Latitude: {playerPosition.lat.toFixed(6)}°</div>
          <div>Longitude: {playerPosition.lng.toFixed(6)}°</div>
          <div className="mt-2 pt-2 border-t border-gray-200">
            <div className="font-semibold text-gray-700">Debug: Local Position</div>
            <div>X: {cubeLocalPosition.x.toFixed(3)}</div>
            <div>Z: {cubeLocalPosition.z.toFixed(3)}</div>
            <div className="mt-1">Chunk: {currentChunk}</div>
            <div>Chunk X: {Math.floor((cubeLocalPosition.x + Config.CHUNK_SIZE / 2) / Config.CHUNK_SIZE)}</div>
            <div>Chunk Z: {Math.floor((cubeLocalPosition.z + Config.CHUNK_SIZE / 2) / Config.CHUNK_SIZE)}</div>
          </div>
        </div>
      </div>

      <SplatManager
        playerPosition={playerPosition}
        onSplatSelection={handleSplatSelection}
        selectedSplat={selectedSplat}
        onTeleport={teleportToLocation}
        onSplatListUpdate={handleSplatListUpdate}
      />

      {selectedSplat && (
        <div className="absolute top-10 left-10 z-10 bg-white p-4 rounded shadow-lg flex flex-col gap-4">
          <h3 className="font-medium">{selectedSplat.name}</h3>

          {/* Add coordinate controls */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-gray-700">Coordinates</h4>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-gray-500">Latitude</label>
                <input
                  type="number"
                  value={selectedSplat.coordinates?.lat || 0}
                  onChange={(e) => handleCoordinateChange(parseFloat(e.target.value), selectedSplat.coordinates?.lng || 0)}
                  step="0.000001"
                  className="w-full px-2 py-1 text-sm border rounded"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500">Longitude</label>
                <input
                  type="number"
                  value={selectedSplat.coordinates?.lng || 0}
                  onChange={(e) => handleCoordinateChange(selectedSplat.coordinates?.lat || 0, parseFloat(e.target.value))}
                  step="0.000001"
                  className="w-full px-2 py-1 text-sm border rounded"
                />
              </div>
            </div>
            <button
              className="w-full px-2 py-1 text-xs bg-blue-50 text-blue-600 rounded hover:bg-blue-100"
              onClick={() => handleCoordinateChange(playerPosition.lat, playerPosition.lng)}
            >
              Use Current Position
            </button>
          </div>

          {/* Existing transform controls */}
          {['position', 'rotation'].map(axis => selectedSplat[axis].map((value, index) => (
            <Slider
              key={`${axis}-${index}`}
              label={`${axis.charAt(0).toUpperCase() + axis.slice(1)} ${['X', 'Y', 'Z'][index]}`}
              value={value}
              onChange={e => handleModelChange(axis, parseFloat(e.target.value), index)}
              min={axis === 'position' ? (index === 1 ? 0 : -5) : -3.14}
              max={axis === 'position' ? (index === 1 ? 15 : 10) : 3.14}
              step="0.1"
            />
          )))}
          <Slider
            label="Scale"
            value={selectedSplat.scale[0]}
            onChange={e => handleModelChange('scale', parseFloat(e.target.value))}
            min="0.1"
            max="10"
            step="0.1"
          />
          <button
            className={`mt-2 px-4 py-2 rounded ${isSaving ? 'bg-gray-500' : 'bg-green-500'} text-white`}
            onClick={handleSavePosition}
            disabled={isSaving}
          >
            {isSaving ? 'Saving...' : 'Save'}
          </button>
        </div>
      )}

      {/* Add the boundary controls */}
      <BoundaryControls 
        showBoundaries={showBoundaries} 
        setShowBoundaries={setShowBoundaries} 
      />

      <Canvas
        camera={{ fov: 70 }}
        style={{ width: '100vw', height: '100vh' }}
        onMouseDown={handleSceneMouseDown}
        onMouseUp={handleSceneMouseUp}
      >
        {Config.VOID_MODE && <color attach="background" args={['#001122']} />}
        <SceneController
          onMove={handleCubeMove}
          onRotate={handleCameraRotation}
          onCameraMove={handleCameraMove}
          isPointerLocked={isPointerLocked}
          isClickingScene={isClickingScene}
        />
        
        {/* Render ground tiles */}
        {!Config.VOID_MODE && [...platforms].filter(pos => data[pos]).map(pos => {
          const [chunkX, chunkZ] = pos.split(',').map(Number);
          return (
            <Platform
              key={`platform-${pos}`}
              position={[chunkX * Config.CHUNK_SIZE, 0, chunkZ * Config.CHUNK_SIZE]}
              texture={data[pos].texture}
            />
          );
        })}

        {/* Render all splats using direct GPS coordinates */}
        {allSplats.map(splat => {
          if (!splat.coordinates) return null;
          
          // Convert GPS coordinates to local 3D position
          const localPos = Utils.gpsToLocalPosition(
            splat.coordinates.lat,
            splat.coordinates.lng,
            Config.INITIAL_POSITION.lat,
            Config.INITIAL_POSITION.lng
          );

          // Apply the splat's position array as an offset to the GPS-based position
          const finalPosition = [
            localPos.x + (splat.position ? splat.position[0] : 0),
            splat.position ? splat.position[1] : 1,
            localPos.z + (splat.position ? splat.position[2] : 0)
          ];

          // Check if this splat is currently selected
          const isSelected = selectedSplat && selectedSplat.id === splat.id;

          return (
            <Suspense key={splat.id} fallback={null}>
              <group 
                position={finalPosition}
                renderOrder={1}
              >
                <SplatModel 
                  splatData={{
                    ...splat,
                    // Override the position with [0,0,0] since we've already positioned the group
                    position: [0, 0, 0]
                  }} 
                  cameraPosition={cameraPosition}
                  isSelected={isSelected}
                  showBoundary={showBoundaries}
                />
              </group>
            </Suspense>
          );
        })}

        {!Config.VOID_MODE && <Skybox hdrPath="/assets/images/sky.hdr" />}
        {Config.VOID_MODE && <SkyWithSun />}
        <directionalLight position={[10, 10, 10]} intensity={1.0} />
        <pointLight position={[0, 10, 0]} intensity={1.5} />
        <ambientLight intensity={1.5 * Math.PI} />
        <directionalLight intensity={1} position={[50, 50, -100]} castShadow />
      </Canvas>
    </div>
  );
};

export default App;
