from pathlib import Path

src = Path("dashboard.py")
lines = src.read_text(encoding="utf-8").splitlines()

counter = 0
new_lines = []
for line in lines:
    if "st.plotly_chart" in line and "key=" not in line:
        counter += 1
        key = f"chart_{counter:03d}"
        stripped = line.rstrip()
        if stripped.endswith(")"):
            line = stripped[:-1] + f', key="{key}")'
        else:
            line = stripped + f'  # KEY NEEDED: chart_{key}'
    new_lines.append(line)

src.write_text("\n".join(new_lines), encoding="utf-8")
print(f"Done. Fixed {counter} charts.")