"""Synthetic QA images only; these are not drone imagery or model outputs."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw

output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
image = Image.new('RGB', (800, 500), '#bed098')
draw = ImageDraw.Draw(image)
draw.rectangle((0, 0, 399, 249), fill='#39634c')
draw.rectangle((400, 250, 799, 499), fill='#c9ad80')
draw.text((30, 30), 'SYNTHETIC QA IMAGE - NOT DRONE DATA', fill='white')
image.save(output / 'landscape.png')
image.save(output / 'landscape.webp')
exif = Image.Exif()
exif[274] = 6
image.save(output / 'orientation6.jpg', exif=exif)
