# 🎨 India Post Mascot Generation Plan

This document outlines the plan to fulfill your requirements: visually "graphifying" the project architecture and leveraging the newly configured `orshot` MCP server to generate the mascot.

## Proposed Changes & Steps

### 1. Graphify the Project
I will analyze the context from `design.md` and the `additional_design-info-reference` folder, and generate a comprehensive `mermaid` graph. This graph will map out the relationships between:
- Core Themes (Trust, Inclusivity, Digital Innovation, etc.)
- Deliverables (Mascot Design, Concept Note, Brand Character)
- References (Emotional vectors and art directions defined in `add-info*.md`)

I will output this graph into a new Markdown artifact for you to view in the IDE.

### 2. Output Directory Setup
I will create the target output directory at `C:\Users\Dell\OneDrive\Desktop\Post-mascot\` if it doesn't already exist.

### 3. Mascot Generation via `@mcp:orshot`
Since the `orshot` MCP server is configured via HTTP SSE, I will execute a Python automation script using the `mcp` Python SDK (which is already installed in your environment). 

The script will:
- Connect to `https://mcp.orshot.com/mcp` using your API key.
- Synthesize a comprehensive design prompt using the guidelines from `design.md` and the visual poetry/storytelling concepts from the reference folder.
- Invoke the `orshot_create_template_design` (or the appropriate Orshot generation tool) to create the Mascot design.
- Save the resulting output(s) to the `Post-mascot` folder.

> [!WARNING]
> **Orshot Capability Note**
> Based on the Orshot API documentation, it primarily acts as a "visual content generation platform" for building and rendering structured templates/layouts. If Orshot requires a base image to work with, I may need to use my native AI image generation tool first to create the base mascot illustration, and then use Orshot to layout the final branded assets/posters. 

## Open Questions

1. **Orshot capabilities**: Do you expect Orshot to purely generate the raw character illustration from scratch, or do you want me to generate the illustration using my built-in image generator and then use Orshot to create branded social media templates (like an India Post campaign poster) featuring that mascot?
2. **Visual Style**: Based on the references, the preferred style leans towards dynamic vector illustrations with bold Indian cultural motifs. Are there any specific colors (other than India Post red/yellow) you want heavily emphasized?

## Verification Plan

- [ ] Verify the Mermaid diagram renders correctly and captures the full project scope.
- [ ] Ensure the Python MCP script successfully connects to `orshot` and triggers the design tool.
- [ ] Verify the final image/template is successfully downloaded to `C:\Users\Dell\OneDrive\Desktop\Post-mascot\`.

Please review this plan. If you agree, click **Proceed** and I will begin the execution!
