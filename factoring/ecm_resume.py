def parse_resume(line):
    """Parse an ECM resume line."""
    IGNORE = ["PROGRAM", "WHO", "TIME"]
    INT = ["N", "B1", "X", "Y", "X0", "Y0", "CHECKSUM"]

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
