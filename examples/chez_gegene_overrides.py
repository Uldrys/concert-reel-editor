"""
Manual override example for Chez Gégène 2 (Category 1).

Context: musicians enter the frame from the right edge around source time 58s
and walk leftward through the vineyard. The auto-tracker initially produced a
right-then-left wobble before they appeared, which looked like the camera was
"searching" for them.

The override below holds the camera on the right (cx=0.78) for the entire
paysage section 40-58s, then only drifts LEFT 58-67s as they walk through.
"""


def cx_override(t_src):
    """Return (cx, zoom) override or None if not overridden at time t_src (in source time)."""
    if 40.0 <= t_src <= 67.5:
        if t_src < 58.0:
            # Hold position on the right throughout the paysage and entry
            return 0.78, 1.0
        elif t_src <= 67.0:
            # Smoothstep drift from 0.78 to 0.46 over 58-67s
            f = (t_src - 58.0) / 9.0
            f = f * f * (3 - 2 * f)
            return 0.78 - f * 0.32, 1.0
        else:
            return 0.46, 1.0
    return None
