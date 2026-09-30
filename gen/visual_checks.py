"""Geometry and image checks for rendered DSU tasks."""
from __future__ import annotations

import math

from PIL import Image


def check_layout(labels: set[str], positions: dict[str, tuple[float, float]],
                 edges: list[tuple[str, str]], canvas: int, radius: float = 30) -> None:
    if set(positions) != labels:
        raise ValueError("missing or duplicate node labels in layout")
    for label, (x, y) in positions.items():
        if not (radius <= x <= canvas - radius and radius <= y <= canvas - radius):
            raise ValueError(f"node {label} is clipped")
    for a in labels:
        for b in labels:
            if a < b and math.dist(positions[a], positions[b]) < radius * 2 + 1:
                raise ValueError(f"nodes {a} and {b} overlap")
    for a, b in edges:
        x1, y1 = positions[a]
        x2, y2 = positions[b]
        length_sq = (x2 - x1) ** 2 + (y2 - y1) ** 2
        for other in labels - {a, b}:
            x, y = positions[other]
            t = max(0.0, min(1.0, ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / length_sq))
            distance = math.dist((x, y), (x1 + t * (x2 - x1), y1 + t * (y2 - y1)))
            if distance < radius + 2:
                raise ValueError(f"edge {a}->{b} intersects unrelated node {other}")


def check_image(image: Image.Image, canvas: int) -> None:
    if image.size != (canvas, canvas) or image.mode != "RGB":
        raise ValueError("render must be an RGB image at the configured canvas size")
