import os

# 1. Rename files if present
if os.path.exists("sample architecture.png"):
    os.rename("sample architecture.png", "sample_architecture.png")

if os.path.exists("sample_architecture.drawio"):
    os.rename("sample_architecture.drawio", "sample_architecture.drawio")

# 2. Replace sample/sample in files
for root, dirs, files in os.walk("."):
    if ".git" in root or "venv" in root or "__pycache__" in root:
        continue
    for f in files:
        if f.endswith((".json", ".py", ".md", ".drawio", ".txt")):
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8") as file:
                    content = file.read()
                if "sample" in content or "sample" in content or "sample" in content:
                    new_content = content.replace("sample", "sample").replace("sample", "sample").replace("sample", "sample")
                    with open(path, "w", encoding="utf-8") as file:
                        file.write(new_content)
            except Exception:
                pass
