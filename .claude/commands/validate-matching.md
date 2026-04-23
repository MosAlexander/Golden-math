Validate matching logic against business rules:

1. Read docs/RULES.md completely
2. Check splink_config.py thresholds match RULES.md
3. Check normalizer_electronics.py PN rules match RULES.md
4. Run tests: `pytest tests/ -v`
5. Report any rule violations found
