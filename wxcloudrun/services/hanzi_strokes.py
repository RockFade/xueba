from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_DATA_URL = "https://cdn.jsdelivr.net/npm/hanzi-writer-data@latest/{char}.json"


def ensure_deps() -> None:
    try:
        import cairosvg  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency. Install with: pip install cairosvg pillow"
        ) from exc


def load_char_data(char: str, data_dir: Path | None, cache_dir: Path | None) -> dict:
    if data_dir:
        local = data_dir / f"{char}.json"
        if local.exists():
            return json.loads(local.read_text(encoding="utf-8"))

    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached = cache_dir / f"{char}.json"
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))

    url = DEFAULT_DATA_URL.format(char=urllib.parse.quote(char))
    with urllib.request.urlopen(url) as resp:
        payload = resp.read().decode("utf-8")

    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{char}.json").write_text(payload, encoding="utf-8")

    return json.loads(payload)


def build_svg(paths: list[tuple[str, str]], size: int) -> bytes:
    scale = size / 1024
    baseline = 900 * scale
    path_nodes = "\n".join(
        f'    <path d="{path_data}" fill="{color}"/>' for path_data, color in paths
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">
  <g transform="translate(0, {baseline}) scale({scale}, -{scale})">
{path_nodes}
  </g>
</svg>"""
    return svg.encode("utf-8")


def render_png(paths: list[tuple[str, str]], out_path: Path, size: int) -> None:
    import cairosvg
    from PIL import Image

    png_bytes = cairosvg.svg2png(bytestring=build_svg(paths, size), output_width=size, output_height=size)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    image.save(out_path)


def sanitize_stroke_name(char: str, index: int, total: int) -> str:
    return f"{char}_{index + 1:02d}_of_{total:02d}.png"


def parse_groups(value: str) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = {}
    if not value:
        return groups

    for item in value.split(","):
        name, sep, range_text = item.partition(":")
        if not sep or not name.strip() or not range_text.strip():
            raise SystemExit(f"Invalid group syntax: {item}. Expected name:1-4 or name:1+2+3.")

        indexes: list[int] = []
        for part in range_text.split("+"):
            part = part.strip()
            if "-" in part:
                start_text, end_text = part.split("-", 1)
                start = int(start_text)
                end = int(end_text)
                indexes.extend(range(start, end + 1))
            else:
                indexes.append(int(part))

        groups[name.strip()] = [index - 1 for index in indexes]

    return groups


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Export Hanzi Writer strokes to transparent PNGs.")
    parser.add_argument("char", help="Target Chinese character, for example: 明")
    parser.add_argument("-o", "--output", default="output", help="Output directory")
    parser.add_argument("--size", type=int, default=512, help="PNG edge size in pixels")
    parser.add_argument("--data-dir", type=Path, default=None, help="Local directory containing <char>.json files")
    parser.add_argument("--cache-dir", type=Path, default=Path("cache"), help="Directory for downloaded JSON cache")
    parser.add_argument(
        "--mode",
        choices=("single", "cumulative"),
        default="single",
        help="single renders each stroke alone; cumulative renders stroke 1..n",
    )
    parser.add_argument("--color", default="#000000", help="Stroke color for normal exports")
    parser.add_argument("--full-color", default=None, help="Color for the complete character export")
    parser.add_argument("--highlight-color", default="#ff8a00", help="Color for group highlight exports")
    parser.add_argument(
        "--groups",
        default="",
        help="Export full-canvas component layers, for example: ri:1-4,yue:5-8",
    )
    parser.add_argument("--full", action="store_true", help="Also export the complete character on a full canvas")
    args = parser.parse_args(argv)

    ensure_deps()

    char = args.char.strip()
    if not char:
        raise SystemExit("char cannot be empty")

    data = load_char_data(char, args.data_dir, args.cache_dir)
    strokes = data.get("strokes")
    if not strokes:
        raise SystemExit(f"No strokes found for {char}")

    out_dir = Path(args.output) / char
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.full:
        full_color = args.full_color or args.color
        render_png([(stroke, full_color) for stroke in strokes], out_dir / f"{char}_full.png", args.size)

    groups = parse_groups(args.groups)
    for name, stroke_indexes in groups.items():
        group_paths: list[tuple[str, str]] = []
        for stroke_index in stroke_indexes:
            if stroke_index < 0 or stroke_index >= len(strokes):
                raise SystemExit(f"Group {name} references missing stroke {stroke_index + 1}")
            group_paths.append((strokes[stroke_index], args.highlight_color))

        render_png(group_paths, out_dir / f"{char}_{name}_high.png", args.size)

    cumulative: list[str] = []
    if not groups:
        for index, stroke in enumerate(strokes):
            if args.mode == "single":
                target_paths = [(stroke, args.color)]
            else:
                cumulative.append(stroke)
                target_paths = [(path, args.color) for path in cumulative]

            filename = sanitize_stroke_name(char, index, len(strokes))
            render_png(target_paths, out_dir / filename, args.size)

    meta_path = out_dir / "meta.json"
    meta_path.write_text(
        json.dumps(
            {"char": char, "stroke_count": len(strokes), "groups": groups},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Exported PNG files to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
