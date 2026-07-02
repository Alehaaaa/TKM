import re

with open("TheKeyMachine/sliders/manager.py", "r") as f:
    content = f.read()

# Extract SLIDER_MODE_TOOLTIPS
tooltips_match = re.search(r'SLIDER_MODE_TOOLTIPS\s*=\s*\{([^}]*)\}', content, re.MULTILINE)
if not tooltips_match:
    print("Could not find SLIDER_MODE_TOOLTIPS")
    exit(1)

tooltip_data = tooltips_match.group(1)

# Build a dictionary of key -> helper string
tooltip_dict = {}
for line in tooltip_data.split('\n'):
    line = line.strip()
    if line.startswith('"'):
        parts = line.split(':', 1)
        if len(parts) == 2:
            key = parts[0].strip(' "')
            val = parts[1].strip(', ')
            tooltip_dict[key] = val

# Now, we need to inject `"tooltip_template": helper.foo,` into each mode dictionary
# We'll use regex to find `"key": "some_key",` and append the tooltip line after it.
def replace_mode(m):
    key = m.group(1)
    tooltip_val = tooltip_dict.get(key)
    if tooltip_val:
        return f'"key": "{key}",\n        "tooltip_template": {tooltip_val},'
    return m.group(0)

new_content = re.sub(r'"key":\s*"([^"]+)",', replace_mode, content)

# Remove the SLIDER_MODE_TOOLTIPS dictionary from the bottom
new_content = re.sub(r'SLIDER_MODE_TOOLTIPS\s*=\s*\{[^}]*\}\n*', '', new_content, flags=re.MULTILINE)

# Add get_slider_mode function at the end
new_content += """

def get_slider_mode(key):
    \"\"\"Return the mode dictionary for a given key across all slider types.\"\"\"
    for modes in (TANGENT_MODES, TWEEN_MODES, BLEND_MODES):
        for mode in modes:
            if isinstance(mode, dict) and mode.get("key") == key:
                return mode
    return None
"""

with open("TheKeyMachine/sliders/manager.py", "w") as f:
    f.write(new_content)

print("manager.py updated successfully.")
