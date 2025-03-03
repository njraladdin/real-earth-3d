import React, { useRef, useEffect } from 'react';
import { useThree, useFrame, useLoader } from '@react-three/fiber';
import * as THREE from 'three';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader';
import { Sky } from 'three/examples/jsm/objects/Sky';

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
export const SkyWithSun = () => {
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