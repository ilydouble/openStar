"""Helpers for loading split domain dotenv files into process env."""

from __future__ import annotations

from dotenv import load_dotenv

from .base import all_domain_env_files


def load_domain_dotenvs(*, override: bool = False) -> None:
    for env_file in all_domain_env_files():
        load_dotenv(env_file, override=override)
