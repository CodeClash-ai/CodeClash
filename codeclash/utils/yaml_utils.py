import re
from pathlib import Path


def resolve_includes(yaml_content: str, *, base_dir: Path = Path(".")) -> str:
    """Pre-process YAML content to resolve all !include directives.
    This will take the yaml content as a string and return the same string with all
    !include directives resolved.

    The reason we don't go with pyyaml-include or similar options is that they don't
    support merge keys, see https://github.com/tanbro/pyyaml-include/issues/53 .
    """

    def include_replacer(match):
        indentation = match.group(1)  # Capture the indentation
        prefix = match.group(2)  # What comes before !include (like "<<: " or "key: ")
        include_path = match.group(3)
        full_path = base_dir / include_path

        included_content = full_path.read_text().strip()

        # Handle merge key specially
        if prefix.strip() == "<<:":
            # For merge keys, include the content with proper indentation
            if indentation:
                included_lines = included_content.splitlines()
                indented_lines = [indentation + line if line.strip() else line for line in included_lines]
                return indentation + "<<:\n" + "\n".join(indented_lines)
            else:
                # Indent the included content by 2 spaces for proper merge format
                included_lines = included_content.splitlines()
                indented_lines = ["  " + line if line.strip() else line for line in included_lines]
                return "<<:\n" + "\n".join(indented_lines)
        else:
            # For regular includes, we need to handle indentation properly
            # If the prefix ends with ': ', we need to add a newline and indent the content
            if prefix.strip().endswith(":"):
                # Calculate the indentation for the included content
                content_indent = indentation + "  "  # Add 2 spaces for proper YAML nesting
                included_lines = included_content.splitlines()
                indented_lines = [content_indent + line if line.strip() else line for line in included_lines]
                return indentation + prefix.strip() + "\n" + "\n".join(indented_lines)
            else:
                # For cases where it's not a key assignment, just replace with content
                return indentation + prefix + included_content

    # Pattern to match !include directives with proper capture groups
    # Group 1: indentation, Group 2: prefix (like "<<: " or "key: "), Group 3: file path
    include_pattern = r"^(\s*)(.*?)!include\s+(.+)$"

    # Keep resolving includes until no more are found
    while re.search(include_pattern, yaml_content, re.MULTILINE):
        yaml_content = re.sub(include_pattern, include_replacer, yaml_content, flags=re.MULTILINE)

    return yaml_content
