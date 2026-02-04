# BlenderChat

Chat with Claude AI to control Blender via natural language.

## Installation

Requires **Blender 4.2+**.

### Production (Install from ZIP)

1. Zip the `blender_chat/` folder:
   ```
   zip -r blender_chat.zip blender_chat/
   ```
2. In Blender: **Edit > Preferences > Add-ons > Install…** → select `blender_chat.zip`.
3. Enable the **BlenderChat** checkbox.
4. Click **Install Dependencies** if prompted (installs the `anthropic` package).
5. Set your API key in the addon preferences.

### Development (Symlink)

Symlink the `blender_chat/` folder into Blender's addons directory so edits take effect immediately:

```bash
# macOS
ln -s "$(pwd)/blender_chat" ~/Library/Application\ Support/Blender/4.2/scripts/addons/blender_chat

# Linux
ln -s "$(pwd)/blender_chat" ~/.config/blender/4.2/scripts/addons/blender_chat

# Windows (run as Administrator)
mklink /D "%APPDATA%\Blender Foundation\Blender\4.2\scripts\addons\blender_chat" "%cd%\blender_chat"
```

Then enable in **Edit > Preferences > Add-ons** and use **F3 > Reload Scripts** (or restart Blender) after changes.

The chat panel appears in **View3D > Sidebar > Chat** (press `N` to toggle the sidebar).

## Reference Links

 - Blender Source Code: https://projects.blender.org/blender/blender
 - Blender Python API: https://docs.blender.org/api/current/index.html    
  - Offline Blender Documentation: https://developer.blender.org/docs/contribute/build_instructions/

  ## License

  Apache 2.0, by SpaceHendrix