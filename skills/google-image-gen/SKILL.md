---
name: google-image-gen
description: >
  Generate images using Google's Gemini API. Use this skill when the user wants
  to generate, create, or edit images with AI. Keywords: image generation,
  create image, generate picture, AI art, edit image, Gemini, icon, render,
  illustration.
allowed-tools: Bash, Read, Glob, AskUserQuestion
---

# Google Image Generation Skill

Generate images from text prompts using Google's Gemini API.

## Free tier first, paid only with confirmation

Every run uses the **free tier by default**. The paid model is a separate switch (`--paid`) and
you must **never** pass `--paid` unless the user has explicitly confirmed it in this conversation
for this request.

### Switching flow

1. Run the command **without** `--paid`.
2. If it exits with code **3** (`FREE_TIER_UNAVAILABLE`), the free tier can't serve the request
   (quota exhausted or billing required). Do not retry with `--paid` on your own.
3. Ask the user with AskUserQuestion, for example: "The free Gemini image tier is unavailable
   (<reason from output>). Switch to the paid model for this image?" Options: use paid once /
   wait and retry free later / cancel.
4. Only on a clear yes, re-run the same command with `--paid` added. Approval covers that request
   only; ask again next time.

Switching to paid without asking is only acceptable when the user already said so in their
original request (e.g. "use the paid model").

### Models

| Tier | Default model                | Override env var           |
|------|------------------------------|----------------------------|
| Free | `gemini-3.1-flash-lite-image`| `GEMINI_IMAGE_MODEL_FREE`  |
| Paid | `gemini-3-pro-image`         | `GEMINI_IMAGE_MODEL_PAID`  |

Note: free quota depends on the user's key and Google's current pricing. The default free model
has worked on a real key, but if it is rejected the script exits with code 3. Users can set
`GEMINI_IMAGE_MODEL_FREE` to any model that has free quota on their key.

## First-Time Setup (Once Per Context)

Run these commands once at the start of a session:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/check_env.sh"
uv sync --project "${CLAUDE_PLUGIN_ROOT}"
```

If the environment check fails, the user needs to configure their API key.
Recommended: Create `~/.config/google-image-gen/.env` with:

```
GOOGLE_AI_API_KEY=your_key_here
```

Get an API key from https://aistudio.google.com/apikey

Alternative: Export as environment variable: `export GOOGLE_AI_API_KEY=your_key`

## Usage

The plugin runs from its own directory. Pass `--cwd "$PWD"` so output files land in the user's
project, not the plugin cache.

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/main.py" --cwd "$PWD" <output_path> "<prompt>" [options]
```

When the user specifies a path like `output.png` or `images/photo.png`, pass it as-is. `--cwd`
resolves it relative to the user's project root. The file format follows the extension
(`.png`, `.jpg`, `.webp`).

## Options

| Option     | Short | Description                                                             |
|------------|-------|-------------------------------------------------------------------------|
| `--style`  | `-s`  | Style template (.md file with `{subject}` placeholder)                  |
| `--ref`    | `-r`  | Reference image (repeatable, max 14 including the edited image)        |
| `--edit`   | `-e`  | Edit existing image instead of generating (exactly one prompt)         |
| `--aspect` | `-a`  | Aspect ratio: `1:1`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9` |
| `--paid`   |       | Use the paid model. Only after user confirmation (see above)           |

Style templates are markdown files with a `## Prompt Template` heading followed by a fenced code
block containing the prompt and a `{subject}` placeholder.

## Exit codes

| Code | Meaning                                                   | What to do                                  |
|------|-----------------------------------------------------------|---------------------------------------------|
| 0    | All images saved                                          | Verify and report                           |
| 1    | Generation failed (API error, blocked, no image returned) | Show the message; adjust the prompt/retry   |
| 2    | Invalid input (missing file, bad template, no API key)    | Fix the input or setup                      |
| 3    | Free tier unavailable                                     | Ask the user before using `--paid`          |

## Examples

In the examples, `RUN` stands for
`uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/main.py" --cwd "$PWD"`.

```bash
# Simple generation
RUN output.png "A red apple on a wooden table"

# Subdirectory and aspect ratio
RUN images/thumb.png "Mountain landscape" --aspect 16:9

# Edit an existing image
RUN output.png "Change the sky to sunset" --edit input.png

# Reference image
RUN output.png "Same style but with a car" --ref reference.png

# Multiple variations -> output_1.png, output_2.png, output_3.png
RUN output.png "cat" "dog" "bird"

# After the user confirmed paid usage
RUN output.png "A red apple on a wooden table" --paid
```

(Write the full command each time; `RUN` is shorthand only.)

## Workflow

1. First use in context: run the setup commands (check_env.sh + uv sync).
2. Generate with the free tier (no `--paid`).
3. Exit code 3: follow the switching flow above.
4. Check the exit code, then use Read on the output file to confirm it is the expected image.
5. Report output paths (and which tier/model was used) to the user.

## Notes

- Existing output files are overwritten. Choose a new name if the user wants to keep the old one.
- With several prompts, a failed image doesn't stop the others; the exit code is 1 if any failed.
- Prompts and images are sent to Google's API.
