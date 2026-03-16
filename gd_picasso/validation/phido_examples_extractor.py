"""
Extract failed YAML examples from external repository.

Purpose: Extract YAML examples from external sources that failed DRC, routing, or functional validation.
"""

import yaml
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class YAMLExamplesExtractor:
    """Extract YAML examples from external repository."""

    def __init__(self, repo_root: str):
        """
        Initialize extractor.

        Args:
            repo_root: Path to external repository root
        """
        self.repo_root = Path(repo_root)
        self.examples = []

    def extract(self) -> List[Dict]:
        """
        Extract YAML examples from external repository.

        Returns:
            List of dictionaries containing:
            - file_path: str
            - yaml_content: str
            - format: str ('external' or 'gdsfactory')
        """
        # Look for YAML files in PhotonicsAI/Photon/
        photon_dir = self.repo_root / "PhotonicsAI" / "Photon"
        
        if not photon_dir.exists():
            logger.warning(f"External repository Photon directory not found: {photon_dir}")
            return []

        # Find all YAML files
        yaml_files = list(photon_dir.glob("*.yaml"))
        
        for yaml_file in yaml_files:
            try:
                content = yaml_file.read_text()
                yaml_data = yaml.safe_load(content)
                
                # Determine format (external format uses 'nodes' and 'edges', GDSFactory uses 'instances' and 'routes')
                if 'nodes' in yaml_data or 'CIRCUIT_' in yaml_file.stem:
                    format_type = 'external'
                else:
                    format_type = 'gdsfactory'
                
                self.examples.append({
                    'file_path': str(yaml_file),
                    'yaml_content': content,
                    'format': format_type,
                    'name': yaml_file.stem
                })
                
            except Exception as e:
                logger.error(f"Error reading {yaml_file}: {e}")

        return self.examples

    def save_examples(self, output_dir: str):
        """
        Save extracted examples to output directory.

        Args:
            output_dir: Directory to save examples
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for i, example in enumerate(self.examples):
            # Save YAML content
            output_file = output_path / f"{example['name']}.yaml"
            with open(output_file, 'w') as f:
                f.write(example['yaml_content'])
            
            # Save metadata
            metadata_file = output_path / f"{example['name']}_metadata.yaml"
            metadata = {
                'file_path': example['file_path'],
                'format': example['format'],
                'name': example['name']
            }
            with open(metadata_file, 'w') as f:
                yaml.dump(metadata, f, default_flow_style=False)


if __name__ == "__main__":
    # Example usage
    extractor = YAMLExamplesExtractor("../../external-repo")
    examples = extractor.extract()
    print(f"Extracted {len(examples)} YAML examples from external repository")
    
    # Save examples
    extractor.save_examples("external_failed_examples")
    print("Saved examples to external_failed_examples/")

