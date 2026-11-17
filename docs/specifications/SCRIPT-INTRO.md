# SCRIPT-INTRO: Shooting Script for the Intro Loop

**Date:** 2026-11-17
**Requirements:** [REQ-INTRO](../requirements/REQ-INTRO.md)
**Specification:** [SPEC-INTRO](SPEC-INTRO.md). Its shot table holds the
numbers and wins over this script if they differ.

This is the director's script. It says what each shot shows, how the
camera moves, what the viewer should feel and why. Coordinates are map
cells of the 256 map. "Lens" is the vertical field of view in degrees.

## 1. Principles

Each rule comes from a source and drives a choice below.

| # | Rule | Source | Used in |
| --- | --- | --- | --- |
| P1 | Emotion first. Each shot has one feeling. A shot without one is cut. | Murch, *In the Blink of an Eye*, Rule of Six (emotion 51 %, story 23 %, rhythm 10 %, eye-trace 7 %, planarity 5 %, 3-D space 4 %). | Every shot card. |
| P2 | Keep the eye-trace across cuts: the subject sits near frame centre. Break it once, on purpose. | Murch, eye-trace. Sacrifice from the bottom of the list up. | S7. |
| P3 | Contrast raises intensity, affinity lowers it. Build affinity, then spend contrast at the peak. Use it sparingly. | Block, *The Visual Story*, ch. 2 and 9. | Intensity graph, S3 vs S4, S8. |
| P4 | Every move has a function: orientation, pacing, inflection, focalization, reflexive, abstract. | Nielsen, *Camera Movement in Narrative Cinema* (2007), ch. 3. | Function line of each card. |
| P5 | Motivated moves are invisible; unmotivated moves are a stylised choice. | Brown, *Cinematography: Theory and Practice*, camera movement chapter. | S8 is the one reflexive move. |
| P6 | Shot lengths cluster with their neighbours: long with long, short with short. | Cutting, DeLong, Nothelfer, *Psychological Science* 21 (2010). The paper finds no link to audience ratings; this is a tendency, not a recipe. | Shot lengths. |
| P7 | Low angle gives power. The "trunk shot": static, wide, low, a frame inside the frame. | Tarantino analyses (StudioBinder; In Depth Cine; Scene360). | S1, S4. |
| P8 | A slow arc circles like a predator. | In Depth Cine, *6 Trademark Tarantino Shots*. | S6. |
| P9 | The crash zoom is an exclamation mark. It dies with repetition: use it once. | In Depth Cine; tarantinocinema.com. | Deploy. |
| P10 | Dolly zoom: distance × tan(FOV / 2) constant. The dolly makes the depth change; the zoom holds the subject. | Vertigo / Jaws; Weiss, *The Dolly Zoom, From the Inside*. | S8. |
| P11 | Mood intros work best. Avoid the disappointment, repetition and too-long pits. | Calica, *The Rules of the Game: Cutting Cut Scenes* (Gamasutra, 1998). | In-engine shots; variant passes; 59 s loop. |
| P12 | A changed aspect ratio tells the player control is off. | Haigh-Hutchinson, *Fundamentals of Real-Time Camera Design*, GDC 2005. | Letterbox. |
| P13 | Shots are states with a minimum length; an exception exits any state. | He, Cohen, Salesin, *The Virtual Cinematographer*, SIGGRAPH 1996. | Loop state machine; SPACE. |
| P14 | Path coherency: no sudden change of speed inside a shot. | Christie, Olivier, Normand, *Camera Control in Computer Graphics*, CGF 27(8), 2008. | Easing; host checks. |

## 2. Geography

The river runs from the north-west corner (30, 230) to the south-east
corner (230, 10). Water level 7.15. The Terran side is north-east, the
Zerg side south-west. The center X sits in the river.

| Subject | Cell | Ground |
| --- | --- | --- |
| MengskBC, the Pride of Augustgrad | (103.8, 153.2) | 5.6, in water 1.6 deep |
| Center X | (125.3, 118.8) | 3.9, in water |
| Shackled Hybrid | (194.4, 193.1) | 8.8 |
| Overmind | (21.0, 9.0) | 7.1 |
| Greater Nydus Worm | (59.0, 59.0) | 6.1 |
| PsiDecimator | (240.0, 248.0) | 8.3 |
| Hero drop region | (176.7, 174.3), r 12 | 5.4 |
| Bramble used in S4 | (194.8, 165.8) | 7.2 |

## 3. Structure

Eight shots, 59 s a pass. Two movements:

- **Movement I, the world (S1 to S3, 34 s).** Long takes. Awe, then calm.
  Affinity: slow moves, one direction, deep then flat space.
- **Movement II, the threat (S4 to S8, 25 s).** Short takes, getting
  shorter. Dread, menace, shock. Contrast: static against moving, low
  against high, still subject against a swelling world.

Intensity graph (Block). One column is about 2 s.

```
intensity
 high |                                    .-'|        S8 spike
      |                               .--'    |
      |                        ____.-'        |
      |   ___               .-'               |
  low |__/   \_____________/                  |__ (loop) S1
      +-----------------------------------------> time
        S1    S2      S3   S4 S5 S6  S7 S8
        12s   12s     10s  6  4  6   3  6
```

Space alternates on purpose: S1 deep, S2 deep, S3 flat, S4 deep, S5
flat-ish (long lens), S6 deep, S7 deep and distorted, S8 deep to flat.

## 4. Shot cards

### OPEN: From black

Black. The Zerus theme starts. Fade in over 1.5 s into S1. First pass
only.

### S1: THE PRIDE (12 s, awe)

**Picture.** Water fills the frame. The lens sits a hand above the
surface, 14 cells downstream of the battlecruiser, looking up-river to the
north-west. Reeds and ripples are sharp; a grey shape is far behind them.
Then the camera cranes up and back. The horizon drops. The Pride of
Augustgrad rises out of its own reflection and fills the upper frame,
seen from below.

**Camera.** Yaw 135 fixed. Target slides from the water 14 cells
downstream to the hull. Target height from 7.6 to 17. Pitch from 3 down
to -12, so the end looks up. Distance 9 to 34. Lens 38 to 62: a slow
widen that keeps the ship growing as the camera backs off.

**Easing.** Slow in, slow out.

**Function.** Orientation: reveals scale. Inflection: low angle, power
(P7).

**Out.** Hard cut on the widest frame.

### S2: THE LINE (12 s, tension under calm)

**Picture.** Low, chest height, across the center X. The two creep
groups fight in the shallows. The camera tracks sideways along the line
of battle, south-west to north-east, at walking pace. The fight is sharp.
Reeds in front and the far bank behind are soft: the only depth of field
in the intro.

**Camera.** Yaw 135 fixed (looking north-west across the lane). Target
moves 16 cells along the lane, from X − (5.7, 5.7) to X + (5.7, 5.7), at
water height + 1.2. Pitch 6. Distance 16. Lens 50. Depth of field on,
focus at 16.

**Easing.** Linear: a constant-speed track. No start or stop inside the
shot (P14).

**Variant (odd passes).** The track runs north-east to south-west.

**Function.** Orientation: the lane and the river. Pacing: maintains.

**Out.** Hard cut. Depth of field off in the same loop.

### S3: THE MAP (10 s, calm)

**Picture.** Straight down from high above the center X. A long lens
flattens the river, the lanes and the jungle into a map. The frame turns
slowly. Units are ants.

**Camera.** Target the center X at ground height. Pitch 80 (the camera
maximum). Distance 150. Lens 22. Yaw 45 to 75: a 30° roll over 10 s.

**Easing.** Slow in, slow out.

**Function.** Orientation: the whole field. Pacing: slows. This is the
last calm before Movement II. Its flat space is the contrast for S4.

**Out.** Hard cut from the highest, flattest frame to the lowest.

### S4: THE BRAMBLES (6 s, dread)

**Picture.** Inside a bramble on the east side of the Terran base,
camera a step above the ground. Thorns frame the picture on all sides.
Through a gap, 27 cells north, the Shackled Hybrid stands chained. Nothing
moves but the leaves. Someone is watching.

**Camera.** Static. Eye in the bramble at (194.8, 165.8), 1.0 above the
ground. Looks at the Hybrid, 3 above its ground: yaw 90.8, pitch -7.5,
distance 27.5. Lens 70, wide.

**Easing.** None. A static frame: the first stillness after 34 s of
motion (P3).

**Function.** Focalization: an implied presence. Inflection: dread.

**Out.** Hard cut on axis to S5. Same yaw, closer: a cut-in.

### S5: THE SHACKLED (4 s, menace)

**Picture.** The Hybrid, closer, on the same axis as S4. The camera
creeps in. The chains strain.

**Camera.** Target the Hybrid, 4 above its ground. Yaw 90.8. Pitch 8.
Distance 18 to 12. Lens 48 to 44.

**Easing.** Slow in, slow out. A creep, not a push.

**Function.** Inflection: the slow creep-in of a moment of threat (Holben,
*Shot Craft: Tools for Camera Movement*, ASC, 2024).

**Out.** Hard cut across the map.

### S6: THE HIVE (6 s, menace)

**Picture.** The Overmind in the south-west corner, from the north-east, a
little above. The camera arcs around it, slow and even.

**Camera.** Target the Overmind, 3 above its ground. Pitch 18. Distance 22.
Lens 55. Yaw 205 to 245: a 40° arc.

**Easing.** Linear arc, slow in and out over the first and last 10 %.

**Variant (odd passes).** Yaw 245 to 205.

**Function.** Inflection: the predator's circle (P8).

**Out.** Hard cut.

### S7: THE WORM (3 s, shock)

**Picture.** Too close. The Greater Nydus Worm towers over a wide,
distorting lens. The camera tilts up its body. The frame has no centre to
rest on.

**Camera.** Target the worm. Height 6 to 12 above its ground. Yaw 225.
Pitch -20 to -35. Distance 9. Lens 80.

**Easing.** Fast in, slow out.

**Function.** Inflection: magnifies the threat. The one cut that breaks
the eye-trace and the scale of the shot before it (P2). Emotion wins over
eye-trace (Murch).

**Out.** Hard cut.

### S8: THE DECIMATOR (6 s, unease, the spike)

**Picture.** The PsiDecimator in the north-east corner, against the rim
of the jungle and the sky. It holds its size. The world behind it swells
and closes in.

**Camera.** Target the PsiDecimator, 4 above its ground. Yaw 45. Pitch
10. Lens 70 to 24. Distance follows the lens: 14 × tan 35° / tan(FOV / 2),
from 14.0 to 46.1.

**Easing.** Slow in, slow out on the lens. Distance is computed from the
lens each loop (P10).

**Function.** Inflection: unease. Reflexive: the trick shot that ends the
pass.

**Out.** Hard cut to S1: from the tightest, most compressed frame back
to the water.

## 5. Prompt

"Press SPACE to deploy", in the bottom letterbox bar, centred, white. It
fades between full and 45 % over 1.6 s and back. It shows from the first
loop frame to the SPACE press.

## 6. Deploy

1. **SPACE.** The prompt goes in the same loop. The theme fades out.
   No music from here on.
2. **The snap (0.35 s).** Hard cut to a high view over the hero's drop
   point: yaw 225, pitch 55, distance 60, lens 60. Crash zoom: lens 60 to
   12 in 0.3 s, fast in, hard stop. The only crash zoom in the intro (P9).
3. **The ride.** Hard cut to the hero pod, already dropping, as the hero
   drop does it: pod height 40, camera locked to the pod, arm 20.
4. **Touchdown.** Impact, quake, the pod opens. The letterbox slides away
   over 0.5 s. The UI comes back. Tosh stands at the pod. Control is the
   player's.

## 7. Not in this script

- Sound design beyond the theme: none.
- Music after deploy: none (operator, 2026-11-17).
- Text other than the prompt: none.
- Camera roll: none. The quake owns roll.
