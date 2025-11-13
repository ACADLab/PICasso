"""
Extract Python false code examples from ALL_FALSE_CODE_EXAMPLES.md

Purpose: Parse markdown file to extract "BAD CODE" blocks, problem descriptions, and error types.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional
import json


class FalseExamplesExtractor:
    """Extract false code examples from markdown documentation."""

    def __init__(self, markdown_path: str):
        """
        Initialize extractor.

        Args:
            markdown_path: Path to ALL_FALSE_CODE_EXAMPLES.md
        """
        self.markdown_path = Path(markdown_path)
        self.examples = []

    def extract(self) -> List[Dict]:
        """
        Extract all false code examples from markdown file.

        Returns:
            List of dictionaries containing:
            - problem_name: str
            - error_type: str
            - bad_code: str
            - issues: List[str]
            - fixed_code: Optional[str]
        """
        if not self.markdown_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {self.markdown_path}")

        content = self.markdown_path.read_text()

        # Pattern to match example blocks
        # Format: ## Pattern X: Description
        # Then: ### Example Y: Problem Name
        # Then: **❌ BAD CODE:**
        # Then: ```python ... ```
        # Then: **Issues:**
        # Then: - Issue 1
        # Then: **✅ FIXED CODE:** (optional)
        # Then: ```python ... ```

        pattern = r'### Example \d+:\s*(.+?)\n.*?\*\*❌ BAD CODE:\*\*\s*```python\n(.*?)```'
        matches = re.finditer(pattern, content, re.DOTALL)

        for match in matches:
            problem_name = match.group(1).strip()
            bad_code = match.group(2).strip()

            # Extract issues (lines starting with - after "**Issues:**")
            issues_pattern = r'\*\*Issues:\*\*\s*\n((?:- .+?\n)+)'
            issues_match = re.search(issues_pattern, content[match.end():match.end() + 2000], re.DOTALL)
            issues = []
            if issues_match:
                issues_text = issues_match.group(1)
                issues = [line.strip()[2:] for line in issues_text.split('\n') if line.strip().startswith('-')]

            # Extract fixed code (optional)
            fixed_pattern = r'\*\*✅ FIXED CODE:\*\*\s*```python\n(.*?)```'
            fixed_match = re.search(fixed_pattern, content[match.end():match.end() + 5000], re.DOTALL)
            fixed_code = fixed_match.group(1).strip() if fixed_match else None

            # Determine error type from pattern heading
            pattern_match = re.search(r'## Pattern \d+:\s*(.+?)\n', content[:match.start()], re.DOTALL)
            error_type = pattern_match.group(1).strip() if pattern_match else "Unknown"

            self.examples.append({
                'problem_name': problem_name,
                'error_type': error_type,
                'bad_code': bad_code,
                'issues': issues,
                'fixed_code': fixed_code
            })

        return self.examples

    def save_to_json(self, output_path: str):
        """
        Save extracted examples to JSON file.

        Args:
            output_path: Path to save JSON file
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, 'w') as f:
            json.dump(self.examples, f, indent=2)

    def save_to_yaml(self, output_path: str):
        """
        Save extracted examples to YAML file.

        Args:
            output_path: Path to save YAML file
        """
        import yaml
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, 'w') as f:
            yaml.dump(self.examples, f, default_flow_style=False, indent=2)


if __name__ == "__main__":
    # Example usage
    extractor = FalseExamplesExtractor(
        "../../fin_picasso_framework/ALL_FALSE_CODE_EXAMPLES.md"
    )
    examples = extractor.extract()
    print(f"Extracted {len(examples)} false code examples")
    
    # Save to JSON
    extractor.save_to_json("false_examples.json")
    print("Saved to false_examples.json")

