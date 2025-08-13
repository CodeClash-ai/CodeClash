import logging


def assert_zero_exit_code(
    result: dict, *, logger: logging.Logger | None = None
) -> dict:
    if result.get("returncode", 0) != 0:
        msg = f"Command failed with exit code {result.get('returncode')}:\n{result.get('output')}"
        if logger is not None:
            logger.error(msg)
        raise RuntimeError(msg)
    return result
