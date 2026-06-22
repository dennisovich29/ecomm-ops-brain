"""Shared pytest fixtures for all test scopes."""
from __future__ import annotations

import os
import pytest

# Set required env vars before any app import so Settings validation passes
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
