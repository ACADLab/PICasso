"""
Enhance Pic_set.txt to match the quality and format of test_problems.txt.

Standardizes:
- Parameter format (adds float specifications)
- Bullet points (standardizes to - or •)
- Ellipsis (replaces … with ...)
- Ensures consistent formatting
"""

import re
from pathlib import Path

def enhance_pic_set(input_file: str = "Pic_set.txt", output_file: str = "Pic_set_enhanced.txt"):
    """Enhance Pic_set.txt with standardized formatting."""
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    enhanced = content
    
    # Replace ellipsis with three dots
    enhanced = enhanced.replace('…', '...')
    
    # Standardize parameter format
    # Pattern: "Parameter = value microns" -> "Parameter = value.0 (description in microns, use as float: value.0)"
    def enhance_parameter(match):
        param_name = match.group(1)
        value = match.group(2)
        unit_text = match.group(3) if len(match.groups()) >= 3 and match.group(3) else 'length'
        
        # Try to convert value to float
        try:
            float_val = float(value)
            # Create description based on parameter name
            if 'DeltaL' in param_name or 'delta' in param_name.lower():
                desc = 'length difference'
            elif 'L' == param_name or 'length' in param_name.lower():
                desc = 'length'
            else:
                desc = unit_text if unit_text != 'length' else 'value'
            
            return f"{param_name} = {float_val} ({desc} in microns, use as float: {float_val})"
        except:
            return match.group(0)  # Return original if can't parse
    
    # Match patterns like "DeltaL = 10 microns" or "L = 10 microns"
    # More flexible pattern that handles optional unit
    enhanced = re.sub(
        r'(\w+)\s*=\s*(\d+(?:\.\d+)?)\s*(?:microns?|um)?\s*$',
        enhance_parameter,
        enhanced,
        flags=re.IGNORECASE | re.MULTILINE
    )
    
    # Standardize spacing specifications
    # "100um spacing" -> "100.0 spacing (use as float: 100.0)"
    enhanced = re.sub(
        r'(\d+(?:\.\d+)?)\s*um\s+spacing',
        lambda m: f"{float(m.group(1))} spacing (use as float: {float(m.group(1))})",
        enhanced,
        flags=re.IGNORECASE
    )
    
    # Keep bullet points as-is (• is fine, just ensure consistency)
    # But we can standardize if needed
    
    # Ensure "IMPORTANT:" notes are preserved
    # (already in good format)
    
    # Save enhanced version
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(enhanced)
    
    print(f"✅ Enhanced file saved to: {output_file}")
    print(f"   Original: {len(content)} chars, Enhanced: {len(enhanced)} chars")
    
    return output_file

if __name__ == "__main__":
    enhance_pic_set()

