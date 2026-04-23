Check test coverage for the project:

1. Run `pytest tests/ -v --tb=short`
2. List all functions in src/ that lack corresponding tests
3. Prioritize gaps by risk:
   - HIGH: matching logic, thresholds, PN normalization
   - MEDIUM: category detection, manufacturer resolution
   - LOW: formatting, display helpers
4. Suggest specific test cases for the top 3 gaps
