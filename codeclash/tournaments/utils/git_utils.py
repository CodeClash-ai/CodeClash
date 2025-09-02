from codeclash.utils.log import get_logger


def filter_git_diff(text: str) -> str:
    """Return a git diff with any file sections mentioning binary content removed."""
    logger = get_logger(__name__)
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    block: list[str] = []
    in_block = False
    prelude_copied = False

    def is_binary_block(bl: list[str]) -> bool:
        for ln in bl:
            s = ln.strip()
            if ln.startswith("Binary files "):
                return True
            if s == "GIT binary patch":
                return True
        return False

    def extract_file_path_from_block(bl: list[str]) -> str:
        """Extract file path from a git diff block."""
        for ln in bl:
            if ln.startswith("diff --git "):
                # Format: "diff --git a/path/to/file b/path/to/file"
                parts = ln.strip().split()
                if len(parts) >= 4:
                    # Remove 'a/' prefix from the file path
                    return parts[2][2:] if parts[2].startswith("a/") else parts[2]
        return "unknown file"

    for ln in lines:
        if ln.startswith("diff --git "):
            if in_block:
                if is_binary_block(block):
                    file_path = extract_file_path_from_block(block)
                    logger.warning(f"Binary file detected in diff: {file_path}")
                else:
                    out.extend(block)
                block = []
            else:
                if not prelude_copied:
                    prelude_copied = True
            in_block = True
        if in_block:
            block.append(ln)
        else:
            out.append(ln)

    if in_block and block:
        if is_binary_block(block):
            file_path = extract_file_path_from_block(block)
            logger.warning(f"Binary file detected in diff: {file_path}")
        else:
            out.extend(block)

    return "".join(out)
