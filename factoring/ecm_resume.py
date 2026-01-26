def number_with_digits(n):
    return f"{n}<{len(str(n))}>"


def parse_resume(line):
    """Parse an ECM resume line."""
    IGNORE = ["PROGRAM", "WHO", "TIME", "CHECKSUM"]
    INT = ["N", "B1", "X", "Y", "X0", "Y0"]

    parsed = {}
    for part in line.split(";"):
        part = part.strip()
        if not part:
            continue

        key, value = part.split("=", 1)
        if key in IGNORE:
            continue

        if key in INT:
            if value.startswith("0x"):
                value = int(value, 16)
            else:
                value = int(value)

        assert key not in parsed, f"Duplicate key: {key}"
        parsed[key] = value

    return parsed
