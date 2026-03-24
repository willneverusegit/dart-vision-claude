"""Root conftest — pytest collection configuration."""

# scripts/ contains CLI tools, not pytest tests.
# Exclude them from automatic test collection.
collect_ignore_glob = ["scripts/*"]
