#!/bin/bash
# Quick Demo Runner for Linux/Unix

echo "======================================================================"
echo "PICasso Validation Flow Demo"
echo "======================================================================"
echo ""
echo "This will demonstrate the validation pipeline:"
echo "  1. Messy design generated"
echo "  2. P&R validation catches issues"
echo "  3. Corrector applied"
echo "  4. Clean design passes all checks"
echo ""
echo "Press Enter to start..."
read

python3 demo_validation_flow.py

echo ""
echo "======================================================================"
echo "Demo complete!"
echo "======================================================================"
echo ""
echo "Next steps:"
echo "  1. Set HF API token: export HF_API_TOKEN=your_token"
echo "  2. Run: python3 gen_data_validated.py"
echo ""
echo "Press Enter to exit..."
read
