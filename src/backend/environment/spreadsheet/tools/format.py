"""Excel formatting helpers."""

from typing import Any, Dict

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side


class ExcelFormatter:
    """Formatting helpers for ranges and cells."""

    def __init__(self, workbook, reader):
        self.workbook = workbook
        self.reader = reader

    def apply_formatting(self, sheet_name: str, range_ref: str,
                         format_dict: Dict[str, Any]) -> str:
        """Apply visual formatting to range of cells."""
        try:
            sheet = self.reader.get_sheet(sheet_name)

            if ':' in range_ref:
                cell_range = sheet[range_ref]
                cells = []
                for row in cell_range:
                    if hasattr(row, '__iter__'):
                        cells.extend(row)
                    else:
                        cells.append(row)
            else:
                cells = [sheet[range_ref]]

            for cell in cells:
                if 'fill_color' in format_dict:
                    color = self._parse_color(format_dict['fill_color'])
                    cell.fill = PatternFill(
                        start_color=color, end_color=color, fill_type='solid'
                    )

                font_kwargs = {}
                if 'font_color' in format_dict:
                    font_kwargs['color'] = self._parse_color(format_dict['font_color'])
                if 'font_size' in format_dict:
                    font_kwargs['size'] = format_dict['font_size']
                if 'font_name' in format_dict:
                    font_kwargs['name'] = format_dict['font_name']
                if 'bold' in format_dict:
                    font_kwargs['bold'] = format_dict['bold']
                if 'italic' in format_dict:
                    font_kwargs['italic'] = format_dict['italic']
                if 'underline' in format_dict:
                    font_kwargs['underline'] = 'single' if format_dict['underline'] else None

                if font_kwargs:
                    cell.font = Font(**font_kwargs)

                if 'border' in format_dict:
                    border_style = format_dict['border']
                    side = Side(style=border_style)
                    cell.border = Border(left=side, right=side, top=side, bottom=side)

                if 'alignment' in format_dict:
                    horizontal = format_dict['alignment']
                    cell.alignment = Alignment(horizontal=horizontal)

            message = f"✅ Applied formatting to {range_ref} in sheet '{sheet_name}'"
            print(message)
            return message

        except Exception as e:
            error_msg = f"❌ Error applying formatting: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    def _parse_color(self, color: str) -> str:
        """Convert color names to hex format."""
        color_names = {
            'red': 'FF0000', 'green': '00FF00', 'blue': '0000FF',
            'yellow': 'FFFF00', 'orange': 'FFA500', 'purple': '800080',
            'pink': 'FFC0CB', 'brown': 'A52A2A', 'black': '000000',
            'white': 'FFFFFF', 'gray': '808080', 'grey': '808080'
        }

        if color.startswith('#'):
            return color[1:]
        if color.lower() in color_names:
            return color_names[color.lower()]
        return color
