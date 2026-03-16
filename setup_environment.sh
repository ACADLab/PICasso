#!/bin/bash
# Setup script for PICasso environment

echo "🚀 Setting up PICasso environment..."
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📥 Installing packages..."
pip install -r requirements_full.txt

# Check klayout installation
echo ""
echo "🔍 Checking klayout installation..."
if command -v klayout &> /dev/null; then
    klayout_version=$(klayout -v 2>&1 | head -n1)
    echo "✓ KLayout found: $klayout_version"
else
    echo "⚠️  KLayout executable not found in PATH"
    echo "   KLayout Python API will be used for DRC validation"
fi

# Test imports
echo ""
echo "🧪 Testing imports..."
python3 << EOF
import sys
packages = [
    'numpy', 'matplotlib', 'pandas', 'scipy',
    'gdsfactory', 'sax', 'jax',
    'huggingface_hub', 'openai', 'transformers'
]

failed = []
for pkg in packages:
    try:
        __import__(pkg)
        print(f"  ✓ {pkg}")
    except ImportError as e:
        print(f"  ✗ {pkg}: {e}")
        failed.append(pkg)

if failed:
    print(f"\n⚠️  Failed to import: {', '.join(failed)}")
    sys.exit(1)
else:
    print("\n✅ All packages imported successfully!")
EOF

echo ""
echo "✅ Environment setup complete!"
echo ""
echo "To activate this environment, run:"
echo "  source venv/bin/activate"



