#!/usr/bin/env python3
"""Google Gemini Image Generator.

Generate images from text prompts or edit existing images using Google's Gemini API.
Supports reference images and style templates for consistency.

This script is part of the google-image-gen Claude Code plugin.

Setup:
    1. Get API key from https://aistudio.google.com/apikey
    2. Create ~/.config/google-image-gen/.env with: GOOGLE_AI_API_KEY=your_key_here
       Or export GOOGLE_AI_API_KEY=your_key_here
    3. Run: uv sync (or pip install google-genai python-dotenv pillow)

Tiers:
    The free tier is used by default. Paid usage is opt-in per run with --paid
    (the skill only passes it after the user confirmed). If the free tier is
    unavailable (quota exhausted, billing required) the script exits with
    code 3 and does NOT fall back to the paid model on its own.

    Models can be overridden with GEMINI_IMAGE_MODEL_FREE / GEMINI_IMAGE_MODEL_PAID.

Usage:
    uv run python main.py output.png "A minimal 3D cube on solid black background"
    uv run python main.py output.png "A gear icon" --style my_style.md
    uv run python main.py output.png "cube" "sphere" "pyramid"
    uv run python main.py output.png "Change the background to blue" --edit input.png
    uv run python main.py output.png "Same style but a sphere" --ref style.png
    uv run python main.py output.png "Prompt" --aspect 16:9
    uv run python main.py output.png "Prompt" --paid
    uv run python main.py --cwd /path/to/project output.png "Prompt"

Aspect ratios: 1:1, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9

Exit codes:
    0  all images saved
    1  generation failed (API error, blocked, or no image returned)
    2  invalid input (missing file, bad template, missing API key, ...)
    3  free tier unavailable (quota/billing); ask the user before using --paid
"""
import argparse
import io
import os
import re
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from PIL import Image

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_BAD_INPUT = 2
EXIT_FREE_UNAVAILABLE = 3

DEFAULT_FREE_MODEL = "gemini-3.1-flash-lite-image"
DEFAULT_PAID_MODEL = "gemini-3-pro-image"

MAX_REFERENCES = 14

_QUOTA_MARKERS = (
    "resource_exhausted",
    "quota",
    "billing",
    "free tier",
    "free_tier",
    "limit: 0",
    "paid",
    "permission_denied",
)


class FreeTierUnavailable(Exception):
    """The free tier cannot serve this request (quota exhausted or billing required)."""


class GenerationError(Exception):
    """Generation failed for a reason other than free-tier availability."""


def load_style_template(style_path: Path) -> str:
    """Load a prompt template from a markdown style file.

    Looks for a code block after '## Prompt Template' or '### Template'.
    The template should contain {subject} as a placeholder.

    Raises:
        FileNotFoundError: If style file doesn't exist.
        ValueError: If no prompt template found in file.
    """
    if not style_path.exists():
        raise FileNotFoundError(f"Style file not found: {style_path}")

    content = style_path.read_text(encoding="utf-8")

    # Look for code block after "Prompt Template" or "Template" header
    pattern = (
        r'(?:##?\s*(?:Prompt\s*)?Template)[^\n]*\n+(?:.*?\n)*?```[^\n]*\n(.*?)```'
    )
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)

    if match:
        template = match.group(1).strip()
        # Normalize the placeholder
        return re.sub(
            r'\[YOUR SUBJECT[^\]]*\]|\[SUBJECT\]|\{subject\}',
            '{subject}',
            template,
            flags=re.IGNORECASE,
        )

    raise ValueError(
        f"No prompt template found in {style_path}. "
        "Add a '## Prompt Template' section with a code block."
    )


def apply_style_template(template: str, subject: str) -> str:
    """Apply a subject to a style template.

    Uses plain replacement (not str.format) so other braces in the template,
    e.g. JSON snippets, are left untouched.
    """
    if '{subject}' in template:
        return template.replace('{subject}', subject)
    # If no placeholder, prepend the subject
    return f"{subject}. {template}"


def _load_image(path: Path) -> Image.Image:
    """Open an image fully into memory and release the file handle."""
    with Image.open(path) as img:
        return img.copy()


def _is_quota_error(exc: genai_errors.APIError) -> bool:
    """Whether an API error means the free tier can't serve the request."""
    if exc.code == 429:
        return True
    text = f"{exc.status or ''} {exc.message or ''}".lower()
    if exc.code in (400, 402, 403) and any(m in text for m in _QUOTA_MARKERS):
        return True
    return "resource_exhausted" in text or "limit: 0" in text


def _save_image(data: bytes, output_path: Path) -> None:
    """Save image bytes, converting to the format implied by the file extension."""
    formats = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
    fmt = formats.get(output_path.suffix.lower())
    if fmt is None:
        output_path.write_bytes(data)
        return
    with Image.open(io.BytesIO(data)) as img:
        if fmt == "JPEG" and img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(output_path, format=fmt)


def generate(
    prompt: str,
    output_path: Path,
    model: str,
    images: Optional[list[Image.Image]] = None,
    aspect_ratio: str = "16:9",
    tier: str = "free",
) -> None:
    """Request one image and save it.

    Args:
        prompt: Text prompt (generation or edit instruction).
        output_path: Where to save the image.
        model: Gemini model ID.
        images: Optional input images (the image to edit first, then references).
        aspect_ratio: Requested aspect ratio.
        tier: "free" or "paid"; decides how quota errors are reported.

    Raises:
        FreeTierUnavailable: Quota/billing error while on the free tier.
        GenerationError: Any other failure, including responses without an image.
    """
    client = genai.Client(api_key=os.environ.get("GOOGLE_AI_API_KEY"))
    contents: list = [prompt, *(images or [])]

    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
            ),
        )
    except genai_errors.APIError as exc:
        if tier == "free" and _is_quota_error(exc):
            raise FreeTierUnavailable(f"{exc.code} {exc.status}: {exc.message}") from exc
        raise GenerationError(f"API error {exc.code} {exc.status}: {exc.message}") from exc

    texts: list[str] = []
    candidate = response.candidates[0] if response.candidates else None
    if candidate and candidate.content and candidate.content.parts:
        for part in candidate.content.parts:
            if part.inline_data and part.inline_data.data:
                _save_image(part.inline_data.data, output_path)
                print(f"Image saved to: {output_path} (model: {model})")
                return
            if part.text:
                texts.append(part.text)

    reason = " ".join(texts).strip()
    if not reason and candidate and candidate.finish_reason:
        reason = f"finish_reason={candidate.finish_reason}"
    if not reason and response.prompt_feedback:
        reason = f"prompt_feedback={response.prompt_feedback}"
    raise GenerationError(f"No image returned. {reason}".strip())


def _resolve_path(path: Path, base_dir: Path) -> Path:
    """Resolve a relative path against a base directory."""
    if path.is_absolute():
        return path
    return base_dir / path


def _load_env(script_dir: Path, base_dir: Path) -> None:
    """Load .env files; earlier sources win over later ones."""
    # 1. User home config (primary recommended location)
    home_env = Path.home() / ".config" / "google-image-gen" / ".env"
    if home_env.exists():
        load_dotenv(home_env)

    # 2. Plugin/script directory .env (for development)
    env_path = script_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)

    # 3. User's project directory .env (fallback)
    project_env = base_dir / ".env"
    if project_env.exists():
        load_dotenv(project_env, override=False)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate images using Google Gemini API (free tier by default)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py output.png "A minimal geometric cube"
  python main.py output.png "gear icon" --style my_style.md
  python main.py output.png "cube" "sphere"
  python main.py output.png "Make it green" --edit input.png
  python main.py output.png "Similar style" --ref style.png
  python main.py output.png "Prompt" --paid        # only after user confirmed
  python main.py --cwd /path/to/project output.png "Prompt"

Exit codes: 0 ok, 1 failed, 2 invalid input, 3 free tier unavailable.
        """,
    )
    parser.add_argument("output", help="Output path for the image")
    parser.add_argument("prompts", nargs="+", help="One or more subjects/prompts")
    parser.add_argument("--style", "-s", help="Path to style template .md file")
    parser.add_argument("--edit", "-e", help="Path to input image to edit")
    parser.add_argument(
        "--ref", "-r",
        action="append",
        dest="references",
        help=f"Reference image (repeatable, up to {MAX_REFERENCES})",
    )
    parser.add_argument(
        "--aspect", "-a",
        default="16:9",
        choices=["1:1", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
        help="Aspect ratio (default: 16:9)",
    )
    parser.add_argument(
        "--paid",
        action="store_true",
        help="Use the paid model (may incur charges). Only pass after the user confirmed.",
    )
    parser.add_argument(
        "--cwd",
        help="Base directory for resolving relative paths (default: current directory)",
    )
    return parser


def main() -> int:
    """Main entry point. Returns an exit code (see module docstring)."""
    args = _build_parser().parse_args()

    base_dir = Path(args.cwd) if args.cwd else Path.cwd()
    script_dir = Path(__file__).parent
    _load_env(script_dir, base_dir)

    if not os.environ.get("GOOGLE_AI_API_KEY"):
        print("Error: GOOGLE_AI_API_KEY not found in environment")
        print("Set up your API key using one of these methods:")
        print("  1. Create ~/.config/google-image-gen/.env with: GOOGLE_AI_API_KEY=your_key_here")
        print("  2. Export: export GOOGLE_AI_API_KEY=your_key_here")
        print("Get your API key from: https://aistudio.google.com/apikey")
        return EXIT_BAD_INPUT

    tier = "paid" if args.paid else "free"
    model = (
        os.environ.get("GEMINI_IMAGE_MODEL_PAID") or DEFAULT_PAID_MODEL
        if args.paid
        else os.environ.get("GEMINI_IMAGE_MODEL_FREE") or DEFAULT_FREE_MODEL
    )
    print(f"Tier: {tier} (model: {model})")

    output_path = _resolve_path(Path(args.output), base_dir)

    # Load style template if provided
    prompts = args.prompts
    if args.style:
        style_path = _resolve_path(Path(args.style), base_dir)
        # If resolved path doesn't exist, also check relative to script directory
        if not style_path.exists() and (script_dir / args.style).exists():
            style_path = script_dir / args.style
        try:
            template = load_style_template(style_path)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}")
            return EXIT_BAD_INPUT
        print(f"Loaded style template from: {style_path}")
        prompts = [apply_style_template(template, p) for p in prompts]

    # Load input images up front so bad paths fail before any API call
    input_images: list[Image.Image] = []
    if args.edit:
        if len(prompts) > 1:
            print("Error: --edit accepts exactly one prompt")
            return EXIT_BAD_INPUT
        edit_path = _resolve_path(Path(args.edit), base_dir)
        if not edit_path.exists():
            print(f"Error: Input image not found: {edit_path}")
            return EXIT_BAD_INPUT
        input_images.append(_load_image(edit_path))

    ref_paths = [_resolve_path(Path(r), base_dir) for r in args.references or []]
    missing = [p for p in ref_paths if not p.exists()]
    if missing:
        for p in missing:
            print(f"Error: Reference image not found: {p}")
        return EXIT_BAD_INPUT
    if len(input_images) + len(ref_paths) > MAX_REFERENCES:
        print(f"Error: at most {MAX_REFERENCES} images in total (input + references)")
        return EXIT_BAD_INPUT
    input_images.extend(_load_image(p) for p in ref_paths)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if len(prompts) == 1:
        jobs = [(prompts[0], output_path)]
    else:
        jobs = [
            (p, output_path.parent / f"{output_path.stem}_{i}{output_path.suffix}")
            for i, p in enumerate(prompts, 1)
        ]

    failures = 0
    for i, (prompt, path) in enumerate(jobs, 1):
        if len(jobs) > 1:
            print(f"\nGenerating image {i}/{len(jobs)}...")
        try:
            generate(
                prompt, path, model,
                images=input_images,
                aspect_ratio=args.aspect,
                tier=tier,
            )
        except FreeTierUnavailable as exc:
            print(f"FREE_TIER_UNAVAILABLE: {exc}")
            print("The free tier cannot serve this request right now.")
            print("Do NOT retry with --paid without asking the user first.")
            return EXIT_FREE_UNAVAILABLE
        except GenerationError as exc:
            print(f"Error: {exc}")
            failures += 1

    if failures:
        print(f"\n{failures}/{len(jobs)} image(s) failed.")
        return EXIT_FAILED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
