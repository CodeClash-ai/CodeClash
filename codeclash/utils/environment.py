def assert_zero_exit_code(result: dict) -> dict:
    if result.get("returncode", 0) != 0:
        msg = f"Command failed with exit code {result.get('returncode')}:\n{result.get('output')}"
        raise RuntimeError(msg)
    return result
