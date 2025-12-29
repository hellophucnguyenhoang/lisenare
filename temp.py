from pathlib import Path
p = Path("data/file.txt")

print(p.absolute())
print(p.resolve())
print(Path.cwd())
print(Path.home())
print(p.exists())
print(p.is_file())
print(p.is_dir())
print(__file__)
BASE = Path(__file__).parent
print(BASE)