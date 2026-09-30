"""Render canonical text and Graphviz-laid-out DSU forests."""
from __future__ import annotations

import argparse
import csv
import io
import math
import random
import subprocess

from PIL import Image, ImageDraw, ImageFont

from gen.visual_checks import check_image, check_layout
from visdsr import ROOT, canonical, config, digest, read_tasks


FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def wrap_canonical(value: str, width: int = 52) -> list[str]:
    """Wrap only after commas, without changing the canonical character stream."""
    parts = value.split(",")
    lines = []
    current = ""
    for index, part in enumerate(parts):
        token = part + ("," if index < len(parts) - 1 else "")
        if current and len(current) + len(token) > width:
            lines.append(current)
            current = token
        else:
            current += token
    if current:
        lines.append(current)
    return lines


def text_image(value: str, canvas: int) -> Image.Image:
    image = Image.new("RGB", (canvas, canvas), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(MONO, 27)
    lines = wrap_canonical(value)
    for i, line in enumerate(lines):
        x, y = 48, 48 + i * 42
        box = draw.textbbox((x, y), line, font=font)
        if box[2] > canvas - 48 or box[3] > canvas - 48:
            raise ValueError("rendered text clips canvas")
        draw.text((x, y), line, font=font, fill="black")
    return image


def layout(state: dict[str, str], canvas: int) -> tuple[dict[str, tuple[float, float]], list[tuple[str, str]]]:
    edges = [(node, parent) for node, parent in state.items() if node != parent]
    source = ["digraph G {", 'graph [rankdir=BT, nodesep=0.06, ranksep=0.60, margin=0, pad=0];',
              'node [shape=circle, fixedsize=true, width=0.8333, height=0.8333];']
    source += [f'"{node}";' for node in state]
    source += [f'"{a}" -> "{b}";' for a, b in edges]
    source.append("}")
    result = subprocess.run(["dot", "-Tplain"], input="\n".join(source), text=True,
                            capture_output=True, timeout=10, check=True)
    nodes = {}
    for line in result.stdout.splitlines():
        bits = line.split()
        if bits and bits[0] == "node":
            nodes[bits[1]] = (float(bits[2]) * 72, -float(bits[3]) * 72)
    if set(nodes) != set(state):
        raise ValueError("Graphviz returned an incomplete layout")
    min_x, max_x = min(x for x, _ in nodes.values()), max(x for x, _ in nodes.values())
    min_y, max_y = min(y for _, y in nodes.values()), max(y for _, y in nodes.values())
    if max_x - min_x + 80 > canvas or max_y - min_y + 80 > canvas:
        raise ValueError("Graphviz layout exceeds fixed canvas")
    dx = canvas / 2 - (min_x + max_x) / 2
    dy = canvas / 2 - (min_y + max_y) / 2
    positions = {label: (x + dx, y + dy) for label, (x, y) in nodes.items()}
    check_layout(set(state), positions, edges, canvas)
    return positions, edges


def diagram_image(state: dict[str, str], canvas: int) -> Image.Image:
    positions, edges = layout(state, canvas)
    image = Image.new("RGB", (canvas, canvas), "white")
    draw = ImageDraw.Draw(image)
    radius = 30
    for a, b in edges:
        x1, y1 = positions[a]
        x2, y2 = positions[b]
        dx, dy = x2 - x1, y2 - y1
        distance = math.hypot(dx, dy)
        ux, uy = dx / distance, dy / distance
        start = (x1 + ux * radius, y1 + uy * radius)
        end = (x2 - ux * radius, y2 - uy * radius)
        draw.line((start, end), fill="black", width=3)
        wing = 10
        draw.polygon([end, (end[0] - ux * wing - uy * wing / 2,
                            end[1] - uy * wing + ux * wing / 2),
                           (end[0] - ux * wing + uy * wing / 2,
                            end[1] - uy * wing - ux * wing / 2)], fill="black")
    font = ImageFont.truetype(FONT, 29)
    for label, (x, y) in positions.items():
        draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                     fill="white", outline="black", width=3)
        box = draw.textbbox((0, 0), label, font=font)
        if box[2] - box[0] > 2 * radius - 12 or box[3] - box[1] > 2 * radius - 12:
            raise ValueError(f"node label {label} does not fit inside its circle")
        draw.text((x - (box[2] - box[0]) / 2 - box[0],
                   y - (box[3] - box[1]) / 2 - box[1]), label, font=font, fill="black")
    return image


def render(split: str, dry_run: bool = False, limit: int | None = None) -> None:
    tasks = read_tasks(split)
    if limit is not None:
        tasks = tasks[:limit]
    if dry_run:
        print(f"would render {len(tasks)} tasks / {2 * len(tasks)} images")
        return
    canvas = config()["render"]["canvas"]
    folder = ROOT / "data" / split
    image_folder = folder / "img"
    image_folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for number, task in enumerate(tasks, 1):
        names = [f"img_{2 * number - 1:05d}.png", f"img_{2 * number:05d}.png"]
        images = [text_image(canonical(task["initial"]), canvas),
                  diagram_image(task["initial"], canvas)]
        hashes = []
        for name, image in zip(names, images, strict=True):
            check_image(image, canvas)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            content = buffer.getvalue()
            (image_folder / name).write_bytes(content)
            hashes.append(digest(content))
        rows.append({"task_id": task["id"], "text_image": names[0], "diagram_image": names[1],
                     "text_sha256": hashes[0], "diagram_sha256": hashes[1]})
    with (folder / "manifest.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]) if rows else
                                ["task_id", "text_image", "diagram_image", "text_sha256", "diagram_sha256"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"rendered {len(rows)} tasks in {image_folder}")


def contact_sheet(split: str, count: int, seed: int) -> None:
    files = sorted((ROOT / "data" / split / "img").glob("img_*.png"))
    if not files:
        raise ValueError("no images to sample; run gen.render first")
    chosen = random.Random(seed).sample(files, min(count, len(files)))
    sheet = Image.new("RGB", (5 * 210, math.ceil(len(chosen) / 5) * 235), "white")
    draw = ImageDraw.Draw(sheet)
    for i, path in enumerate(chosen):
        with Image.open(path) as source:
            image = source.copy()
        image.thumbnail((200, 200))
        x, y = (i % 5) * 210, (i // 5) * 235
        sheet.paste(image, (x, y))
        draw.text((x + 4, y + 205), path.name, fill="black")
    target = ROOT / "data" / split / "contact_sheet.png"
    sheet.save(target)
    print(target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["pilot", "main"], required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--qa", action="store_true", help="export a 20-image contact sheet")
    args = parser.parse_args()
    if args.qa:
        contact_sheet(args.split, 20, config()[f"{args.split}_seed"])
    else:
        render(args.split, args.dry_run, args.limit)


if __name__ == "__main__":
    main()
