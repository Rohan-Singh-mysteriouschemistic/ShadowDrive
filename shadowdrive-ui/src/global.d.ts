declare var THREE: {
  Scene: new () => any;
  PerspectiveCamera: new (fov: number, aspect: number, near: number, far: number) => any;
  WebGLRenderer: new (params: { alpha: boolean; antialias: boolean }) => any;
  BufferGeometry: new () => any;
  BufferAttribute: new (array: Float32Array, size: number) => any;
  Points: new (geometry: any, material: any) => any;
  PointsMaterial: new (params: {
    size: number;
    color: number;
    transparent: boolean;
    opacity: number;
    blending: any;
  }) => any;
  AdditiveBlending: number;
  Clock: new () => any;
};
