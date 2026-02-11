# via_stitching_plugin

Small KiCad ActionPlugin (skeleton) that adds a toolbar button and a dialog.

## Icon
The plugin includes `via_icon.png` — a 64×64 icon with a green background, gold/yellow ring, and black center dot to resemble a via. You can convert this to any format KiCad prefers or replace it with your own icon.

## Installation
1. Copy the `via_stitching_plugin` folder into one of KiCad's plugin folders, or add its parent folder to KiCad's plugin search paths. Typical user plugin paths on Linux:
   - ~/.local/share/kicad/9.0/scripting/plugins/  (adjust for KiCad version)

2. Restart KiCad and open the PCB editor. The plugin appears under Tools (and as a toolbar button if supported).

## Notes
- This is a UI skeleton only: clicking "Go!" currently shows a summary dialog. Implementations of via stitching will be added next.
