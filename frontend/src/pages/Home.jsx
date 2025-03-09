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
import { SplatManager } from '../components/SplatManager';
import Minimap from '../components/Minimap';
import MapUtils from '../utils/MapUtils';



//Config module 
const Config = { API_KEY: '5bpPlOMeEXIFV9UuKHrW', CHUNK_SIZE: 10, 
  INITIAL_POSITION: { lat: 33.80358961071113, lng: 10.951546694824309 }, ZOOM_LEVEL: 20, 
VOID_MODE: false, SHOW_BOUNDARIES: false };


// Utils module removed and replaced with import from MapUtils

// Convert Components object members to individual React components

const Cube = forwardRef(({ onMove, camera, isPointerLocked, isCameraControlActive, isClickingScene }, ref) => {
  const velocity = useVelocity(isPointerLocked, onMove);
  useFrame(() => {
    if (ref.current && isPointerLocked && (isCameraControlActive || isClickingScene)) {
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

const SceneController = ({ onMove, onRotate, onCameraMove, isPointerLocked, isClickingScene, isCameraControlActive }) => {
  const cubeRef = useRef();
  const { camera } = useThree();

  useCameraController(cubeRef, isPointerLocked && (isCameraControlActive || isClickingScene));

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

  return <Cube ref={cubeRef} onMove={onMove} camera={camera} isPointerLocked={isPointerLocked} isCameraControlActive={isCameraControlActive} isClickingScene={isClickingScene} />;
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
  const [isCameraControlActive, setIsCameraControlActive] = useState(false);
  const [cameraPosition, setCameraPosition] = useState({ x: 0, y: 0, z: 0 });
  const [cubeLocalPosition, setCubeLocalPosition] = useState({ x: 0, z: 0 });
  const [showBoundaries, setShowBoundaries] = useState(Config.SHOW_BOUNDARIES);

  const fetchedPlatforms = useRef(new Set());

  // First effect - one-time fetch of splats when component mounts
  useEffect(() => {
    const fetchSplats = async () => {
      try {
        const splatsSnapshot = await getDocs(collection(db, 'splats'));
        const splatsData = splatsSnapshot.docs.map(doc => {
          const data = doc.data();
          // Ensure hidden property is defined (default to false)
          return {
            id: doc.id,
            ...data,
            hidden: data.hidden !== undefined ? data.hidden : false
          };
        });

        setAllSplats(splatsData.map(splat => {
          if (selectedSplat && splat.id === selectedSplat.id && selectedSplat._editing) {
            return {
              ...splat,
              position: selectedSplat.position,
              rotation: selectedSplat.rotation,
              scale: selectedSplat.scale,
              coordinates: selectedSplat.coordinates,
              hidden: selectedSplat.hidden,
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
      const tile = MapUtils.latLngToTileNumber(Config.INITIAL_POSITION, Config.ZOOM_LEVEL);
      const tileData = await MapUtils.fetchTileData({ zoom: Config.ZOOM_LEVEL, x: tile.x + chunkX, y: tile.y + chunkZ }, Config.API_KEY);
      
      // Simply store the tile data without any chunk information
      setData(prev => ({ ...prev, [pos]: tileData }));
    };

    // Fetch any new platforms
    platforms.forEach(pos => fetchPlatformData(pos));

    // Handle pointer lock
    const handlePointerLockChange = () => {
      const isLocked = document.pointerLockElement !== null;
      setIsPointerLocked(isLocked);
      
      // If pointer lock is lost unexpectedly and camera control was active, turn it off
      if (!isLocked && isCameraControlActive) {
        setIsCameraControlActive(false);
      }
    };

    document.addEventListener('pointerlockchange', handlePointerLockChange);
    return () => document.removeEventListener('pointerlockchange', handlePointerLockChange);
  }, [platforms]);

  const handleCubeMove = ({ x, z }) => {
    // Store the cube's local position for debugging
    setCubeLocalPosition({ x, z });
    
    // Convert cube's 3D position to GPS coordinates
    // using INITIAL_POSITION as the reference point
    const { lat, lng } = MapUtils.localPositionToGps(
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
    const tile = MapUtils.latLngToTileNumber(Config.INITIAL_POSITION, Config.ZOOM_LEVEL);
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
    // Always use the full updated list from the SplatManager
    // since it has the most recent state including hidden changes
    setAllSplats(updatedSplats);
    
    // If the currently selected splat was updated, reflect those changes
    if (selectedSplat) {
      const updatedSelectedSplat = updatedSplats.find(splat => splat.id === selectedSplat.id);
      if (updatedSelectedSplat) {
        setSelectedSplat({
          ...updatedSelectedSplat,
          _editing: selectedSplat._editing
        });
      }
    }
  };

  const handleModelChange = (type, value, index) => {
    if (!selectedSplat) return;

    // Create the updated splat object with the new value
    const updatedSplat = {
      ...selectedSplat,
      _editing: true
    };
    
    // Handle different property types
    if (type === 'scale') {
      // Scale is handled as a uniform value
      updatedSplat.scale = [value, value, value];
    } else if (type === 'hidden') {
      // Visibility toggle - direct boolean value
      updatedSplat.hidden = value;
    } else if (type === 'coordinates') {
      // Coordinates are an object with lat/lng
      updatedSplat.coordinates = value;
    } else if (Array.isArray(selectedSplat[type])) {
      // For array properties (position, rotation) update a specific index
      updatedSplat[type] = selectedSplat[type].map((v, i) => (i === index ? value : v));
    } else {
      // For other properties, just set the value directly
      updatedSplat[type] = value;
    }

    // Update both states in one batch to prevent flickering
    const updatedAllSplats = allSplats.map(splat =>
      splat.id === selectedSplat.id ? updatedSplat : splat
    );

    setSelectedSplat(updatedSplat);
    setAllSplats(updatedAllSplats);
  };

  const handleCoordinateChange = (lat, lng) => {
    if (!selectedSplat) return;
    
    // Use the unified model change function with coordinates
    handleModelChange('coordinates', { lat, lng });
  };

  const handleSavePosition = async () => {
    if (!selectedSplat) return;

    setIsSaving(true);
    try {
      const { _editing, ...splatToSave } = selectedSplat;

      // Update in Firestore with all the editable properties
      await updateDoc(doc(db, 'splats', selectedSplat.id), {
        position: selectedSplat.position,
        rotation: selectedSplat.rotation,
        scale: selectedSplat.scale,
        coordinates: selectedSplat.coordinates,
        hidden: selectedSplat.hidden,
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
    const localPosition = MapUtils.gpsToLocalPosition(
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
    const tile = MapUtils.latLngToTileNumber(Config.INITIAL_POSITION, Config.ZOOM_LEVEL);
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
    // Handle right click for toggling camera control
    if (e.button === 2) { // Right mouse button
      e.preventDefault();
      const newControlState = !isCameraControlActive;
      setIsCameraControlActive(newControlState);
      
      // When toggling camera control on, request pointer lock
      if (newControlState) {
        // Request pointer lock when activating camera control
        e.target.requestPointerLock();
      } else {
        // Exit pointer lock when deactivating camera control
        if (document.pointerLockElement) {
          document.exitPointerLock();
        }
      }
      return;
    }
    
    // For left click, maintain the existing behavior
    if (e.target.tagName === 'CANVAS') {
      setIsClickingScene(true);
      // Request pointer lock for the traditional click-and-drag mode
      if (!document.pointerLockElement) {
        e.target.requestPointerLock();
      }
    }
  };

  const handleSceneMouseUp = () => {
    setIsClickingScene(false);
    // Only exit pointer lock if camera control is not active
    if (!isCameraControlActive && document.pointerLockElement) {
      document.exitPointerLock();
    }
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

  // Add a contextmenu handler to prevent the default browser menu
  const handleContextMenu = (e) => {
    e.preventDefault();
  };

  return (
    <div className="relative flex">
      {/* Camera Control Mode Indicator */}
      <div className="absolute top-4 right-4 z-20 bg-black bg-opacity-70 p-2 rounded-lg shadow-md text-white text-sm">
        <div>
          <div>Camera Control: {isCameraControlActive ? "Active" : "Inactive"}</div>
          <div>Pointer Lock: {isPointerLocked ? "Active" : "Inactive"}</div>
          <div className="text-xs text-gray-400 mt-1">Right-click to toggle camera control</div>
          <div className="text-xs text-gray-400">ESC to exit camera control</div>
        </div>
      </div>
      
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
        onUpdateSplatProperty={handleModelChange}
      />

      {selectedSplat && (
        <div className="absolute top-10 left-10 z-10 bg-white p-4 rounded shadow-lg flex flex-col gap-4">
          <h3 className="font-medium">{selectedSplat.name}</h3>

          {/* Add toggle for visibility */}
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">Visibility</span>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                className="sr-only peer"
                checked={!selectedSplat.hidden}
                onChange={(e) => handleModelChange('hidden', !e.target.checked)}
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              <span className="ml-2 text-sm font-medium text-gray-700">{selectedSplat.hidden ? 'Hidden' : 'Visible'}</span>
            </label>
          </div>

          {/* Existing coordinate controls */}
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
              onClick={() => handleModelChange('coordinates', { lat: playerPosition.lat, lng: playerPosition.lng })}
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

      {/* Add the minimap component - now using the imported version */}
      <Minimap 
        currentChunk={currentChunk}
        platforms={platforms}
        playerPosition={{ 
          x: cubeLocalPosition.x, 
          z: cubeLocalPosition.z 
        }}
        data={data}
        chunkSize={Config.CHUNK_SIZE}
        playerDirection={playerDirection}
      />

      <Canvas
        shadows
        dpr={[1, 1.5]}
        className={isPointerLocked ? 'cursor-none' : ''}
        camera={{ position: [0, 2, 0], fov: 50 }}
        style={{ width: '100vw', height: '100vh' }}
        onMouseDown={handleSceneMouseDown}
        onMouseUp={handleSceneMouseUp}
        onContextMenu={handleContextMenu}
      >
        {Config.VOID_MODE && <color attach="background" args={['#001122']} />}
        <SceneController
          onMove={handleCubeMove}
          onRotate={handleCameraRotation}
          onCameraMove={handleCameraMove}
          isPointerLocked={isPointerLocked}
          isClickingScene={isClickingScene}
          isCameraControlActive={isCameraControlActive}
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
          const localPos = MapUtils.gpsToLocalPosition(
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

          // Skip rendering if splat is marked as hidden
          if (splat.hidden) return null;

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
