# Google Image Gen Plugin for Claude Code

A Claude Code plugin for generating images using Google's Gemini API.

## What This Plugin Does

This plugin enables Claude Code to generate images using Google's Gemini API. When you ask Claude to create, generate,
or edit images, it will use this plugin automatically.

Features:

- Generate images from text prompts
- Edit existing images with AI
- Use reference images for style consistency
- Support for multiple aspect ratios
- Batch generation of multiple variations

## Requirements

- [uv](https://docs.astral.sh/uv/) package manager
- Google AI API key from [Google AI Studio](https://aistudio.google.com/apikey)

## Installation

### 1. Add the Marketplace & Install

In Claude Code, run:

```
/plugin marketplace add waqasxh/google-image-gen-plugin
/plugin install google-image-gen@google-image-gen
```

### 2. Set Your API Key

**Option A: Config file (recommended)**

```bash
mkdir -p ~/.config/google-image-gen
echo "GOOGLE_AI_API_KEY=your_actual_api_key_here" > ~/.config/google-image-gen/.env
```

**Option B: Environment variable**

```bash
export GOOGLE_AI_API_KEY=your_actual_api_key_here
# Add to your shell profile (~/.zshrc, ~/.bashrc) for persistence
```

### 3. Done

Claude Code will automatically detect and use the plugin when you ask it to generate images.

## Usage Examples

Just ask Claude Code naturally:

### Simple Image Generation

```
Generate an image of a red sports car on a mountain road and save it as car.png
```

```
Create a minimalist logo for a coffee shop, save as logo.png with 1:1 aspect ratio
```

### With Specific Aspect Ratios

```
Generate a YouTube thumbnail showing a coding tutorial, use 16:9 aspect ratio
```

```
Create a phone wallpaper with abstract geometric shapes, aspect ratio 9:16
```

### Editing Existing Images

```
Edit the image input.png and change the background to a sunset sky
```

### Using Reference Images

```
Generate an image in the same style as reference.png but with a cat instead
```

### Multiple Variations

```
Generate 3 variations of app icons: a rocket, a star, and a lightning bolt
```

### With Style Templates

You can create custom style templates as markdown files with a `## Prompt Template` section:

```markdown
## Prompt Template

\```
Minimalist flat design illustration of {subject}.
Clean lines, bold colors, white background.
Modern corporate style, suitable for presentations.
\```
```

Then ask Claude:

```
Generate an image of a laptop using the style template my-style.md
```

## Free vs. Paid (Switching)

The plugin tries the **free tier first** and never uses the paid model on its own.

| Tier | Default model                 | Override env var          |
|------|-------------------------------|---------------------------|
| Free | `gemini-3.1-flash-lite-image` | `GEMINI_IMAGE_MODEL_FREE` |
| Paid | `gemini-3-pro-image`          | `GEMINI_IMAGE_MODEL_PAID` |

- If the free tier can't serve a request (quota exhausted or billing required), the script exits with code `3`.
- Claude then asks you whether to switch to the paid model, and re-runs with `--paid` only if you say yes.
  The approval applies to that request only.
- From the command line, switch manually with `--paid`.

> Free quota for image models depends on your key and Google's current pricing (the pricing page may list no free tier
> for them). In testing, the default free model worked on a real key. If the free attempt is rejected on yours, you'll
> be asked before switching to paid. You can point `GEMINI_IMAGE_MODEL_FREE` at any model with free quota on your key.

## Supported Aspect Ratios

| Ratio  | Use Case                                    |
|--------|---------------------------------------------|
| `1:1`  | Social media posts, profile pictures        |
| `3:4`  | Portrait photos                             |
| `4:3`  | Standard landscape                          |
| `4:5`  | Instagram portrait                          |
| `5:4`  | Large format prints                         |
| `9:16` | Phone wallpapers, Stories, TikTok           |
| `16:9` | YouTube thumbnails, presentations (default) |
| `21:9` | Ultrawide displays, cinematic               |

## Troubleshooting

| Error                         | Cause                 | Solution                                                       |
|-------------------------------|-----------------------|----------------------------------------------------------------|
| `GOOGLE_AI_API_KEY not found` | Missing API key       | Create `~/.config/google-image-gen/.env` with your API key     |
| Exit code `3` / `FREE_TIER_UNAVAILABLE` | Free quota exhausted or billing required | Wait and retry, or confirm switching to paid (`--paid`) |
| `uv: command not found`       | uv not installed      | Install via `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

## Development

### Local Testing

```bash
claude --plugin-dir .
```

### Versioning & Updates

Bump `version` in `plugin.json` (semver) and push to `main`. Claude Code pulls the latest commit from the default
branch — git tags are currently ignored. Optionally tag for your own release tracking:

```bash
git tag 1.1.0 && git push origin 1.1.0
```

Users receive updates via `/plugin update` or automatic update checks.

### Architecture Overview

| Component               | Role                                               |
|-------------------------|----------------------------------------------------|
| `skills/…/SKILL.md`     | Loaded into Claude's context as skill prompt       |
| `main.py`, `scripts/`   | Executed via Bash by Claude                        |
| `${CLAUDE_PLUGIN_ROOT}` | Plugin cache path (where plugin files live)        |
| `--cwd` / working dir   | User's project path (where output files are saved) |

## Credits

This is a fork of [ypfaff/google-image-gen-plugin](https://github.com/ypfaff/google-image-gen-plugin) by Yannick Pfaff
(MIT), which is based on the work
from [AI Engineer Skool's Google Image Gen API Starter](https://github.com/AI-Engineer-Skool/google-image-gen-api-starter).

For more infos, check out the corresponding [video guide](https://youtu.be/NBibgD7I48w?si=ucFFgKFgyx5FxA-0).

## License

[MIT](LICENSE)
