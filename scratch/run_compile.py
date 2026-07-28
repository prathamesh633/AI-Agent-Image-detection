import sys
import os
from agents.vision_agent.detector import detect_with_gemini_free
from core.diagram_ir.assembly import assemble_diagram_ir
from core.drawio.compiler import generate_xml

key = 'AIzaSyDUau91NA6UvCVgcpq9uIv2oiJBPhIxMsE'
img_path = 'sample architecture.png'
out_path = 'sample_architecture.drawio'

print("Extracting sample architecture via Gemini...")
data = detect_with_gemini_free(img_path, key)
print("Assembling IR...")
ir = assemble_diagram_ir(data)
print("Generating XML...")
xml = generate_xml(ir)

with open(out_path, 'w', encoding='utf-8') as f:
    f.write(xml)

print(f"SUCCESS: Written {out_path}")
