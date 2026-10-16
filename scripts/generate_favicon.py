import rasterio
from rasterio import features
import numpy as np
from shapely.geometry import shape

input_path = "frontend/src/assets/landing/logo-orange.png"

with rasterio.open(input_path) as src:
    r = src.read(1)
    g = src.read(2)
    b = src.read(3)
    a = src.read(4)

h, w = a.shape
shield_mask = a > 50
solid_shield = np.zeros((h, w), dtype=np.uint8)

for y in range(h):
    xs = np.where(shield_mask[y])[0]
    if len(xs) > 0:
        solid_shield[y, xs[0]:xs[-1]+1] = 1

# Extract solid shield and tree
solid_geom = [shape(geom) for geom, val in features.shapes(solid_shield) if val == 1][0]
tree_mask = (solid_shield == 1) & (~shield_mask)
tree_geom = shape([geom for geom, val in features.shapes(tree_mask.astype(np.uint8)) if val == 1][0])

# Simplify to smooth curves
s_simp = solid_geom.simplify(2.0, preserve_topology=True)
t_simp = tree_geom.simplify(2.0, preserve_topology=True)

# Centering within a square canvas (1024 x 1024)
dim = max(w, h)
# Let's add slight margin (e.g. 5%)
scale = 920.0 / dim
target_size = 1024
x_offset = (target_size - w * scale) / 2
y_offset = (target_size - h * scale) / 2

def coords_to_svg_d(coords):
    parts = []
    for i, (x, y) in enumerate(coords):
        cmd = 'M' if i == 0 else 'L'
        parts.append(f"{cmd}{x * scale + x_offset:.1f} {y * scale + y_offset:.1f}")
    parts.append('Z')
    return ' '.join(parts)

shield_d = coords_to_svg_d(s_simp.exterior.coords)
tree_d = coords_to_svg_d(t_simp.exterior.coords)

svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {target_size} {target_size}" width="100%" height="100%">
  <path d="{shield_d}" fill="#CC6F00" />
  <path d="{tree_d}" fill="#FFFFFF" />
</svg>
'''

output_svg = "frontend/public/favicon.svg"
with open(output_svg, "w", encoding="utf-8") as f:
    f.write(svg_content)

print(f"Generated {output_svg} successfully! File size: {len(svg_content)} bytes")
