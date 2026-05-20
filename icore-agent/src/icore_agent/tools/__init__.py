__all__ = [
    "web_search",
    "http_request",
    "run_python_snippet",
    "read_file",
    "write_file",
    "list_files",
]


def web_search(*args, **kwargs):
    from .web_search import web_search as _web_search

    return _web_search(*args, **kwargs)


def http_request(*args, **kwargs):
    from .http_client import http_request as _http_request

    return _http_request(*args, **kwargs)


def run_python_snippet(*args, **kwargs):
    from .code_executor import run_python_snippet as _run_python_snippet

    return _run_python_snippet(*args, **kwargs)


def read_file(*args, **kwargs):
    from .file_ops import read_file as _read_file

    return _read_file(*args, **kwargs)


def write_file(*args, **kwargs):
    from .file_ops import write_file as _write_file

    return _write_file(*args, **kwargs)


def list_files(*args, **kwargs):
    from .file_ops import list_files as _list_files

    return _list_files(*args, **kwargs)
