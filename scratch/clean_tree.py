import os

# 1. Remove sample / sample architecture image and drawio files completely
for filename in [
    "sample architecture.png", 
    "sample_architecture.drawio", 
    "sample_architecture.png", 
    "sample_architecture.drawio"
]:
    if os.path.exists(filename):
        try:
            os.remove(filename)
        except Exception:
            pass

# 2. Replace sample/sample in all code, json, md, txt files
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
