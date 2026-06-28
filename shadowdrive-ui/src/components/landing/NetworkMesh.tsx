"use client";
import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface NetworkMeshProps {
  scrollProgress: React.MutableRefObject<number>;
  mousePosition: React.MutableRefObject<{x: number, y: number}>;
}

export default function NetworkMesh({ scrollProgress, mousePosition }: NetworkMeshProps) {
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
  const NODE_COUNT = isMobile ? 80 : 200;

  const groupRef = useRef<THREE.Group>(null);
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const starsRef = useRef<THREE.Points>(null);

  // Generate random galaxy configuration on every mount
  const config = useMemo(() => {
    return {
      // Galaxy shape
      coreSize: 20 + Math.random() * 20, // How wide the central bulge is
      diskThickness: 10 + Math.random() * 20, // How thick the outer disk is
      // Nodes
      nodeShape: Math.random() > 0.5 ? 'sphere' : 'scatter',
      // Motion & View
      // Keep tilt between 22.5 and 67.5 degrees to avoid edge-on lines
      tiltX: Math.PI / 8 + Math.random() * (Math.PI / 4), 
      tiltZ: (Math.random() - 0.5) * (Math.PI / 6),
      spinSpeedY: (Math.random() > 0.5 ? 1 : -1) * (0.005 + Math.random() * 0.015),
      nodeSpinSpeed: (Math.random() > 0.5 ? 1 : -1) * (0.01 + Math.random() * 0.03),
    };
  }, []);

  // Initialize Background Stars
  const STAR_COUNT = isMobile ? 3000 : 8000;
  const { starPositions, starColors } = useMemo(() => {
    const positions = new Float32Array(STAR_COUNT * 3);
    const colors = new Float32Array(STAR_COUNT * 3);
    const colorThree = new THREE.Color();

    for (let i = 0; i < STAR_COUNT; i++) {
      // Smooth lenticular galaxy distribution (no arms, no spokes, no lines)
      // Clustered heavily in the center, tapering smoothly outwards
      const u = Math.random();
      const radius = Math.pow(u, 1.5) * 180;
      const theta = Math.random() * Math.PI * 2;
      
      const x = radius * Math.cos(theta);
      const z = radius * Math.sin(theta);
      
      // Y distribution: Central bulge + flat disk tapering off
      const bulge = Math.exp(-radius / config.coreSize) * 40; 
      const disk = config.diskThickness * Math.exp(-radius / 100);
      const y = (Math.random() - 0.5) * (bulge + disk);

      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;

      // Strictly brand compliant: ONLY #00ff88 to match foreground nodes perfectly
      colorThree.setHex(0x00ff88);
      
      // Random dimming for variety, but hue never changes
      // Core stars are brighter, outer stars are dimmer
      let intensity = 0.1 + Math.random() * 0.9;
      if (radius < 40) {
        intensity = 0.5 + Math.random() * 0.5; // Core is brighter
      }
      
      colors[i * 3] = colorThree.r * intensity;
      colors[i * 3 + 1] = colorThree.g * intensity;
      colors[i * 3 + 2] = colorThree.b * intensity;
    }
    return { starPositions: positions, starColors: colors };
  }, [STAR_COUNT]);

  // Initialize nodes (fibonacci sphere)
  const nodeData = useMemo(() => {
    const data = [];
    const phi = Math.PI * (3 - Math.sqrt(5));
    const radius = 15;
    for (let i = 0; i < NODE_COUNT; i++) {
      let basePosition = new THREE.Vector3();
      
      if (config.nodeShape === 'sphere') {
        const y = 1 - (i / (NODE_COUNT - 1)) * 2;
        const radiusAtY = Math.sqrt(1 - y * y);
        const theta = phi * i;
        basePosition.set(
          Math.cos(theta) * radiusAtY * radius,
          y * radius,
          Math.sin(theta) * radiusAtY * radius
        );
      } else {
        // Scatter
        basePosition.set(
          (Math.random() - 0.5) * 30,
          (Math.random() - 0.5) * 20,
          (Math.random() - 0.5) * 30
        );
      }

      data.push({
        id: i,
        position: basePosition.clone(),
        basePosition: basePosition.clone(),
        // Smoothed velocity for damping
        smoothVelocity: new THREE.Vector3(),
        driftSpeed: 0.2 + Math.random() * 0.6,
        driftOffset: Math.random() * Math.PI * 2,
      });
    }
    return data;
  }, [NODE_COUNT, config.nodeShape]);

  const dummy = useMemo(() => new THREE.Object3D(), []);
  const targetPos = useMemo(() => new THREE.Vector3(), []);
  const mouseWorldPos = useMemo(() => new THREE.Vector3(), []);

  // Reusable vectors to avoid allocation inside the loop
  const _clusterOffset = useMemo(() => new THREE.Vector3(), []);
  const _repulse = useMemo(() => new THREE.Vector3(), []);
  const _delta = useMemo(() => new THREE.Vector3(), []);

  let frameCount = 0;

  useFrame((state) => {
    if (!meshRef.current || !groupRef.current) return;
    frameCount++;
    const time = state.clock.elapsedTime;

    const scroll = scrollProgress.current;
    const convergeFactor = Math.pow(scroll, 2);

    // Global rotation for the foreground nodes
    groupRef.current.rotation.y = time * config.nodeSpinSpeed;
    groupRef.current.rotation.x = time * (config.nodeSpinSpeed * 0.5);

    // Rotate and converge the background starfield independently based on config & scroll
    if (starsRef.current) {
      starsRef.current.rotation.x = config.tiltX; 
      starsRef.current.rotation.z = config.tiltZ;
      // Spin faster as we scroll down
      starsRef.current.rotation.y = time * config.spinSpeedY + convergeFactor * Math.PI;
      
      // Converge the entire galaxy by scaling it down
      const starScale = 1 - (convergeFactor * 0.85);
      starsRef.current.scale.setScalar(starScale);
    }
    mouseWorldPos.set(mousePosition.current.x * 20, mousePosition.current.y * 15, 0);

    for (let i = 0; i < NODE_COUNT; i++) {
      const node = nodeData[i];

      // ── Morph logic (scroll-driven shape) ──
      if (scroll >= 0.0 && scroll < 0.25) {
        targetPos.copy(node.basePosition).multiplyScalar(1.5);
      } else if (scroll >= 0.25 && scroll < 0.5) {
        if (i < NODE_COUNT / 3) {
          _clusterOffset.set(-15, 0, 0);
          targetPos.copy(node.basePosition).multiplyScalar(0.5).add(_clusterOffset);
        } else {
          targetPos.copy(node.basePosition).multiplyScalar(1.5);
        }
      } else if (scroll >= 0.5 && scroll < 0.75) {
        if (i >= NODE_COUNT / 3 && i < (NODE_COUNT * 2) / 3) {
          targetPos.copy(node.basePosition).multiplyScalar(0.5);
        } else {
          targetPos.copy(node.basePosition).multiplyScalar(1.5);
        }
      } else if (scroll >= 0.75 && scroll < 0.9) {
        if (i >= (NODE_COUNT * 2) / 3) {
          _clusterOffset.set(15, 0, 0);
          targetPos.copy(node.basePosition).multiplyScalar(0.5).add(_clusterOffset);
        } else {
          targetPos.copy(node.basePosition).multiplyScalar(1.5);
        }
      } else {
        targetPos.set(0, 0, 0);
      }

      // ── Ambient drift (gentle sinusoidal floating) ──
      targetPos.x += Math.sin(time * node.driftSpeed + node.driftOffset) * 1.5;
      targetPos.y += Math.cos(time * node.driftSpeed * 0.7 + node.driftOffset + 1) * 1.0;
      targetPos.z += Math.sin(time * node.driftSpeed * 0.5 + node.driftOffset + 2) * 1.0;

      // ── Boids-lite: SOFT separation only (no alignment) ──
      // Uses inverse-square falloff so force fades gently instead of snapping on/off.
      // Separation radius is much smaller than line-connection radius (2.5 vs 5)
      // so connected nodes are NOT in the separation zone → no jitter.
      let sepX = 0, sepY = 0, sepZ = 0;
      const SEP_RADIUS_SQ = 6.25; // 2.5²  — much smaller than connection radius (5² = 25)

      for (let j = 0; j < NODE_COUNT; j++) {
        if (i === j) continue;
        const other = nodeData[j];
        const dx = node.position.x - other.position.x;
        const dy = node.position.y - other.position.y;
        const dz = node.position.z - other.position.z;
        const distSq = dx * dx + dy * dy + dz * dz;

        if (distSq < SEP_RADIUS_SQ && distSq > 0.001) {
          // Soft inverse-square falloff: weaker at edges, stronger at core
          const invSq = 1.0 / distSq;
          sepX += dx * invSq;
          sepY += dy * invSq;
          sepZ += dz * invSq;
        }
      }

      // Very gentle separation force (0.08) — enough to prevent overlap, not enough to cause jitter
      targetPos.x += sepX * 0.08;
      targetPos.y += sepY * 0.08;
      targetPos.z += sepZ * 0.08;

      // ── Mouse repulsion ──
      const distToMouse = node.position.distanceTo(mouseWorldPos);
      if (distToMouse < 5) {
        _repulse.subVectors(node.position, mouseWorldPos).normalize().multiplyScalar((5 - distToMouse) * 0.5);
        targetPos.add(_repulse);
      }

      // ── Smooth interpolation with velocity damping ──
      // Compute desired delta, then damp the velocity so changes are gradual.
      _delta.subVectors(targetPos, node.position);
      // Exponential smoothing on the velocity itself (0.08 blend)
      node.smoothVelocity.lerp(_delta, 0.08);
      // Apply damped velocity (scaled down for stability)
      node.position.add(node.smoothVelocity.clone().multiplyScalar(0.04));

      // Update instance matrix
      dummy.position.copy(node.position);
      dummy.updateMatrix();
      meshRef.current.setMatrixAt(i, dummy.matrix);
    }
    meshRef.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <>
      <group ref={groupRef}>
        <instancedMesh ref={meshRef} args={[undefined, undefined, NODE_COUNT]}>
          <icosahedronGeometry args={[0.06, 0]} />
          <meshBasicMaterial color="#00ff88" transparent opacity={0.6} />
        </instancedMesh>
      </group>
      
      <points ref={starsRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[starPositions, 3]}
          />
          <bufferAttribute
            attach="attributes-color"
            args={[starColors, 3]}
          />
        </bufferGeometry>
        <pointsMaterial 
          size={0.2} 
          vertexColors={true}
          transparent 
          opacity={0.8} 
          sizeAttenuation={true} 
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>
    </>
  );
}
