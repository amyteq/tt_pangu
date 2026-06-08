"""Database helper modules for the worker / agent layer.

Thin, intent-revealing wrappers over `tools.kca.db.get_conn()` so worker
code and tests can read / write specific tables without re-implementing
connection plumbing.
"""
