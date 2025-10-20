'''
PICasso Framework Driver
1. LLM Prompt
	a. User problem description
	b. Append problem description to prompt template + restrictions
2. LLM generates python GDSFactory code
	a. Clean up python code
	b. Ensures python code is clear of syntax errors
3. Placement and Routing
	a. Run placement and routing algorithm
	b. Re-run syntax validation
4. DRC
	a. Run DRC checks and ensure validity
5. SAX compilation
	a. Compile with SAX and extract the S-matrix
6. Optimization
	a. Optical Loss Optimization
		i.   Run algorithm using S-matrix
		ii.  Re-generate python GDS code
		iii. Re-run P&R, DRC, and SAX
7. Output
	a. Optimzied Python GDS code
	b. Optimization metrics: 
		i. Optical loss (dB)

'''