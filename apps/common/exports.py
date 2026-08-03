"""Shared CSV/Excel/PDF export helpers for dashboard list views.

Usage: build `rows` as a list of dicts (e.g. serializer.data), then call the
export matching the requested `export_format` — see admin_security/views.py's
AdminLogExportView for the calling convention (an APIView.get() that picks
one of these based on an `export_format` query param).

Note: never name that query param `format` — DRF reserves it for its own
content-negotiation (URL_FORMAT_OVERRIDE) and 404s if it doesn't match a
registered renderer.
"""
import csv
import io

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle


def export_rows_as_csv(headers, field_names, rows, filename_prefix):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename_prefix}.csv"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row[field] for field in field_names])
    return response


def export_rows_as_excel(headers, field_names, rows, filename_prefix):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = filename_prefix[:31] or 'Export'
    sheet.append(headers)
    for row in rows:
        sheet.append([row[field] for field in field_names])
    for index, header in enumerate(headers, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = max(len(header) + 4, 18)

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename_prefix}.xlsx"'
    return response


def export_rows_as_pdf(headers, field_names, rows, filename_prefix):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    table_data = [headers] + [
        [str(row[field]) for field in field_names] for row in rows
    ]
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#004030')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
        ])
    )
    doc.build([table])
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename_prefix}.pdf"'
    return response


def export_rows(export_format, headers, field_names, rows, filename_prefix):
    """Dispatches to the right exporter. `export_format` is one of
    'csv' (default), 'excel', 'pdf'."""
    if export_format == 'excel':
        return export_rows_as_excel(headers, field_names, rows, filename_prefix)
    if export_format == 'pdf':
        return export_rows_as_pdf(headers, field_names, rows, filename_prefix)
    return export_rows_as_csv(headers, field_names, rows, filename_prefix)
