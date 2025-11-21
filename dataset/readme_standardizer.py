#
# This object standardizes the format of dataset readme, check naming of spreadsheet ids
#

import re

class ReadmeStandardizer:
    def __init__(self, filepath: str):
        self.filepath = filepath

        

    def standardize_indexes(self, pattern_string: str, write_back: bool = True) -> str:
        """
        Read file at `filepath`, renumber occurrences of the pattern
        sequentially in order of appearance, and return the new content.
        If write_back is True, overwrite the file with new content.
        """
        pattern = re.compile(rf'\[{pattern_string}(\d+)\]')


        with open(self.filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # iterate matches and build new content piece by piece
        new_parts = []
        last_end = 0
        count = 1

        for m in pattern.finditer(content):
            start, end = m.start(), m.end()
            # append text between last match and this match unchanged
            new_parts.append(content[last_end:start])
            # append replaced bracket with sequential index
            new_parts.append(f"[{pattern_string}{count}]")
            count += 1
            last_end = end

        # append remaining tail
        new_parts.append(content[last_end:])

        new_content = ''.join(new_parts)

        if write_back:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)

        return new_content


if __name__ == "__main__":
    std = ReadmeStandardizer("DatasetV1.md")
    std.standardize_indexes("outputfile")
    std.standardize_indexes("spreadsheet")