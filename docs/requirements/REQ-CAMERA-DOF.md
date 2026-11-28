# REQ-CAMERA-DOF: in-game camera depth of field

Scope: the in-game camera, PnC and TPS modes. Not the intro, not the hero drop.
Source: operator, 2026-11-17.

Camera distance range: 1 (minimum zoom) to 40 (maximum zoom).

- R-DOF-1 Near DOF, distance-based. Strength is slight at camera distance 1
  (operator 2026-11-27: near DOF even at the lowest zoom; was 0) and grows
  with distance. Its strongest value is at maximum distance (40).
- R-DOF-2 Near DOF, aim state. While right-click aiming in TPS, near DOF is
  as strong as the R-DOF-1 maximum (distance 40), regardless of the camera
  distance. Only while aiming.
- R-DOF-3 Far DOF, distance-based. Strength is 0 while camera distance < 3,
  and grows with distance. At maximum distance it is comparable in strength
  to the R-DOF-1 maximum near DOF.
- R-DOF-4 No far DOF while aiming.
- R-DOF-5 With both strengths 0, DOF is off. Since R-DOF-1 (2026-11-27)
  this happens only at strength multiplier 0.
- R-DOF-6 One strength multiplier scales the regular camera DOF, near and
  far, not the aim DOF (operator 2026-11-27). Constant
  `c_CAM_DOF_STRENGTH`, default 1.

Verification: the applied state and values are recorded by the test
harness. How the blur looks is an operator check.
