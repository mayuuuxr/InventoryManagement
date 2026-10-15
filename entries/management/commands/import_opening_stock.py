"""
Bulk-import opening stock from an .xlsx file (one InwardEntry per row).

Two header schemes accepted (first row = header, case-insensitive):
  App:   site | material | qty | date | received_from | time (optional)
  Stock sheet: Material | ... | UOM | In Stock | ... | Location
    (uses In Stock rounded whole, syncs units from UOM, creates unknown
    materials under Uncategorized/Imported, dates everything today)

See entries/importer.py for the full rules. A web UI with preview lives at
Reports -> Import opening stock (admin only).

Example:
    python manage.py import_opening_stock opening.xlsx --user Admin --dry-run
    python manage.py import_opening_stock opening.xlsx --user Admin
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Import opening-stock inward entries from an .xlsx file."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to the .xlsx file.")
        parser.add_argument(
            "--user", required=True,
            help="Username to attribute the rows to (staff see own rows).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Validate everything, save nothing.",
        )

    def handle(self, *args, **options):
        from accounts.models import User
        from entries.importer import parse_workbook, process_rows

        try:
            user = User.objects.get(username=options["user"])
        except User.DoesNotExist:
            raise CommandError(f"Unknown user: {options['user']}")

        try:
            with open(options["file"], "rb") as f:
                header, rows, error = parse_workbook(f)
        except FileNotFoundError:
            raise CommandError(f"File not found: {options['file']}")
        if error:
            raise CommandError(error)

        result = process_rows(header, rows, user,
                              dry_run=options["dry_run"])
        self.stdout.write(
            f"{'DRY RUN — ' if options['dry_run'] else ''}"
            f"created: {result['created']}, "
            f"skipped duplicates: {result['skipped']}, "
            f"errors: {len(result['errors'])}")
        for msg in result["errors"][:20]:
            self.stdout.write(self.style.WARNING("  " + msg))
        if len(result["errors"]) > 20:
            self.stdout.write(f"  ... and {len(result['errors']) - 20} more")
