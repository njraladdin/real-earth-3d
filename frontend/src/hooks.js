import { useRef, useState, useEffect } from 'react';
import { useThree, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

let isFPS = true; // Global variable

export const useVelocity = (isPointerLocked) => {
  const ref = useRef({ x: 0, y: 0, z: 0 });

  const updateVelocity = (key, isDown) => {
    const speed = isFPS ? 0.01 : 0.1; // Adjust speed based on isFPS
    const axisMap = {
      q: 'x',
      d: 'x',
      z: 'z',
      s: 'z',
      Control: 'y',
      Shift: 'y',
    };
    const dirMap = {
      q: -1,
      d: 1,
      z: 1,
      s: -1,
      Control: -1,
      Shift: 1,
    };
    const axis = axisMap[key];
    const dir = dirMap[key];
    if (axis) {
      ref.current[axis] = isDown ? dir * speed : 0;
    }
  };

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (['q', 'd', 'z', 's', 'Control', 'Shift'].includes(event.key)) {
        updateVelocity(event.key, true);
      }
    };

    const handleKeyUp = (event) => {
      if (['q', 'd', 'z', 's', 'Control', 'Shift'].includes(event.key)) {
        updateVelocity(event.key, false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  return ref;
};

export const useCameraController = (cubeRef, isPointerLocked) => {
  const { camera } = useThree();
  const [theta, setTheta] = useState(0);
  const [phi, setPhi] = useState(0);
  const velocity = useVelocity(isPointerLocked);

  useEffect(() => {
    // Increase FOV here
    camera.fov = 75; // Set desired FOV value
    camera.updateProjectionMatrix();

    const handleMouseMove = ({ movementX, movementY }) => {
      if (isPointerLocked) {
        setTheta((prev) => prev - movementX * 0.005);
        if (isFPS) {
          setPhi((prev) => prev - movementY * 0.005); // Reversed up/down movement for FPS view
        } else {
          setPhi((prev) => Math.min(Math.max(prev + movementY * 0.005, -Math.PI / 6), Math.PI / 2 - 0.1)); // Limit for third-person view to stop at top view
        }
      }
    };

    const handleMouseDown = (event) => {
      if (event.button === 1) {
        isFPS = !isFPS; // Toggle global isFPS variable
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mousedown', handleMouseDown);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mousedown', handleMouseDown);
    };
  }, [isPointerLocked, camera]);

  useFrame(() => {
    if (cubeRef.current && isPointerLocked) {
      const { x, y, z } = cubeRef.current.position;
      const { x: vx, y: vy, z: vz } = velocity.current;

      if (isFPS) {
        const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion);
        const right = new THREE.Vector3(1, 0, 0).applyQuaternion(camera.quaternion);

        cubeRef.current.position.x += (vx * right.x + vz * forward.x);
        cubeRef.current.position.y += vy;
        cubeRef.current.position.z += (vx * right.z + vz * forward.z);

        camera.position.set(cubeRef.current.position.x, cubeRef.current.position.y, cubeRef.current.position.z);
        camera.rotation.set(phi, theta, 0); // Set pitch and yaw without roll
        camera.rotation.order = 'YXZ'; // Ensure correct rotation order
      } else {
        const radius = 20; // Adjust the radius to keep the camera closer to the character
        const offsetY = y + radius * Math.sin(phi) + 0.5; // Ensure the camera doesn't go below the cube
        const distance = radius * Math.cos(phi);
        camera.position.set(
          x + distance * Math.sin(theta),
          offsetY,
          z + distance * Math.cos(theta)
        );
        camera.lookAt(x, y, z);
      }
    }
  });
};
