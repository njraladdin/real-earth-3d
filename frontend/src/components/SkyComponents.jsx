import React, { useRef, useEffect, useState, useMemo } from 'react';
import { useThree, useFrame, useLoader } from '@react-three/fiber';
import * as THREE from 'three';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader';
import { Sky } from 'three/examples/jsm/objects/Sky';
import { Water } from 'three/examples/jsm/objects/Water';

// Traditional skybox using an HDR environment map
export const Skybox = ({ hdrPath }) => {
  const texture = useLoader(RGBELoader, hdrPath);
  texture.mapping = THREE.EquirectangularReflectionMapping;
  return (
    <mesh>
      <sphereGeometry args={[500, 60, 40]} />
      <meshBasicMaterial map={texture} side={THREE.BackSide} />
    </mesh>
  );
};

// Dynamic sky with sun shader from three.js
export const SkyWithSun = ({ onSunPositionChange }) => {
  const { scene, gl } = useThree();
  const skyRef = useRef();
  const sunPosition = useRef(new THREE.Vector3());
  const timeRef = useRef(0);
  
  useEffect(() => {
    if (!skyRef.current) return;
    
    const sky = skyRef.current;
    
    // Set default parameters
    const uniforms = sky.material.uniforms;
    uniforms['turbidity'].value = 10;
    uniforms['rayleigh'].value = 2;
    uniforms['mieCoefficient'].value = 0.005;
    uniforms['mieDirectionalG'].value = 0.8;
    
    // Initial sun position
    updateSunPosition(30, 180);
    
    // Set renderer exposure
    gl.toneMappingExposure = 0.5;
  }, [gl]);
  
  const updateSunPosition = (elevation, azimuth) => {
    if (!skyRef.current) return;
    const uniforms = skyRef.current.material.uniforms;
    
    const phi = THREE.MathUtils.degToRad(90 - elevation);
    const theta = THREE.MathUtils.degToRad(azimuth);
    sunPosition.current.setFromSphericalCoords(1, phi, theta);
    uniforms['sunPosition'].value.copy(sunPosition.current);
    
    // Call the callback if provided
    if (onSunPositionChange) {
      onSunPositionChange(sunPosition.current);
    }
  };
  
  useFrame((state, delta) => {
    // Slowly animate the sun position for a nice effect
    timeRef.current += delta * 0.1; // Slow movement
    const elevation = 20 + 5 * Math.sin(timeRef.current); // Oscillate between 15-25 degrees
    const azimuth = 180 + 15 * Math.sin(timeRef.current * 0.5); // Oscillate between 165-195 degrees
    
    updateSunPosition(elevation, azimuth);
  });
  
  return (
    <primitive 
      object={new Sky()} 
      ref={skyRef}
      scale={450000} 
    />
  );
};

// Ocean water surface with realistic waves and reflections
export const OceanSurface = ({ size = 1000, position = [0, -2, 0], sunPosition, waterOpacity = 0.85 }) => {
  const waterRef = useRef();
  const { scene, gl } = useThree();
  const [waterNormalTexture, setWaterNormalTexture] = useState(null);
  const [waterObject, setWaterObject] = useState(null);
  
  // Get sun direction from the SkyWithSun component if available
  const sunRef = useRef(new THREE.Vector3(0, 1, 0));
  
  // Create water geometry once
  const waterGeometry = useMemo(() => {
    return new THREE.PlaneGeometry(size, size, 20, 20);
  }, [size]);
  
  // Load the water normal texture
  useEffect(() => {
    let isMounted = true;
    const textureLoader = new THREE.TextureLoader();
    
    // Try to load the manually downloaded texture
    textureLoader.load('/assets/textures/waternormals.jpg', 
      // onLoad callback
      (texture) => {
        if (!isMounted) return;
        
        texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
        setWaterNormalTexture(texture);
        
        // Create water object with the loaded texture
        const water = new Water(waterGeometry, {
          textureWidth: 512,
          textureHeight: 512,
          waterNormals: texture,
          sunDirection: sunRef.current,
          sunColor: 0xffffff,
          waterColor: 0x001e0f,
          distortionScale: 3.7,
          fog: false // Disable fog for simplicity
        });
        
        // Rotate to be flat on XZ plane
        water.rotation.x = -Math.PI / 2;
        
        // Set render order to ensure water renders before other objects
        water.renderOrder = -1;
        
        // Make sure water has correct transparency
        water.material.transparent = true;
        water.material.opacity = waterOpacity;
        water.material.depthWrite = false; // Don't write to depth buffer
        
        setWaterObject(water);
      },
      // onProgress callback (not used)
      undefined,
      // onError callback
      (error) => {
        if (!isMounted) return;
        
        console.error("Error loading water normals texture:", error);
        // Fallback to a simple normal map if needed
        console.log("Attempting to create a basic normal map as fallback");
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 512;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#7F7FFF'; // Basic normal map blue
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        const fallbackTexture = new THREE.CanvasTexture(canvas);
        fallbackTexture.wrapS = fallbackTexture.wrapT = THREE.RepeatWrapping;
        setWaterNormalTexture(fallbackTexture);
        
        // Create water object with the fallback texture
        const water = new Water(waterGeometry, {
          textureWidth: 512,
          textureHeight: 512,
          waterNormals: fallbackTexture,
          sunDirection: sunRef.current,
          sunColor: 0xffffff,
          waterColor: 0x001e0f,
          distortionScale: 3.7,
          fog: false // Disable fog for simplicity
        });
        
        // Rotate to be flat on XZ plane
        water.rotation.x = -Math.PI / 2;
        
        // Set render order to ensure water renders before other objects
        water.renderOrder = -1;
        
        // Make sure water has correct transparency
        water.material.transparent = true;
        water.material.opacity = waterOpacity;
        water.material.depthWrite = false; // Don't write to depth buffer
        
        setWaterObject(water);
      }
    );
    
    // Cleanup function
    return () => {
      isMounted = false;
      if (waterNormalTexture) {
        waterNormalTexture.dispose();
      }
      if (waterObject) {
        waterObject.material.dispose();
      }
    };
  }, [waterGeometry, waterOpacity]); // Only recreate if geometry changes
  
  // Update water animation and link to sun
  useFrame((state, delta) => {
    if (waterObject) {
      // Animate water
      waterObject.material.uniforms['time'].value += delta * 0.5;
      
      // Update sun direction if we get it from the scene
      if (sunPosition) {
        sunRef.current.copy(sunPosition);
      } else {
        // Default sun direction if none provided
        const time = state.clock.elapsedTime * 0.1;
        sunRef.current.set(
          Math.sin(time) * 0.2 + 0.1, 
          Math.cos(time * 0.5) * 0.25 + 0.8,
          Math.cos(time) * 0.2
        ).normalize();
      }
      
      if (waterObject.material.uniforms['sunDirection']) {
        waterObject.material.uniforms['sunDirection'].value.copy(sunRef.current);
      }
    }
  });
  
  if (!waterObject) {
    return null; // Don't render until water object is created
  }
  
  return (
    <group position={position}>
      <primitive object={waterObject} ref={waterRef} />
    </group>
  );
}; 