def filter_git_diff(text: str) -> str:
    """Return a git diff with any file sections mentioning binary content removed."""
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

    for ln in lines:
        if ln.startswith("diff --git "):
            if in_block:
                if not is_binary_block(block):
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
        if not is_binary_block(block):
            out.extend(block)

    return "".join(out)
