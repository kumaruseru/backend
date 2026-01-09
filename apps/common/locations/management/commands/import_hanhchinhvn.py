"""Management command to import Vietnamese administrative units from hanhchinhvn library."""
from django.core.management.base import BaseCommand, CommandError
from apps.common.locations.services import LocationService


class Command(BaseCommand):
    help = 'Import provinces, districts, and wards from hanhchinhvn library'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Delete existing data before import',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show current database statistics',
        )

    def handle(self, *args, **options):
        # Show stats if requested
        if options['stats']:
            stats = LocationService.get_statistics()
            self.stdout.write(self.style.SUCCESS(
                f"Current database: "
                f"{stats['provinces']} provinces, "
                f"{stats['districts']} districts, "
                f"{stats['wards']} wards"
            ))
            return

        self.stdout.write(self.style.NOTICE('Starting import from hanhchinhvn library...'))
        
        # Dry run - just count without importing
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN - No data will be saved'))
            try:
                from hanhchinhvn import iter_all_provinces, iter_all_districts, iter_all_wards
                
                province_count = sum(1 for _ in iter_all_provinces())
                district_count = sum(1 for _ in iter_all_districts())
                ward_count = sum(1 for _ in iter_all_wards())
                
                self.stdout.write(f"Found {province_count} provinces")
                self.stdout.write(f"Found {district_count} districts")
                self.stdout.write(f"Found {ward_count} wards")
                self.stdout.write(self.style.SUCCESS('Dry run completed. Use without --dry-run to import.'))
                
            except ImportError:
                raise CommandError('hanhchinhvn library not installed. Run: pip install hanhchinhvn')
            return

        # Actual import
        if options['force']:
            self.stdout.write(self.style.WARNING('FORCE mode - existing data will be deleted'))
        
        try:
            counts = LocationService.import_all_locations(force=options['force'])
            self.stdout.write(self.style.SUCCESS(
                f"Successfully imported: "
                f"{counts['provinces']} provinces, "
                f"{counts['districts']} districts, "
                f"{counts['wards']} wards"
            ))
            
            # Show final stats
            stats = LocationService.get_statistics()
            self.stdout.write(self.style.SUCCESS(
                f"Total in database: "
                f"{stats['provinces']} provinces, "
                f"{stats['districts']} districts, "
                f"{stats['wards']} wards"
            ))
            
        except ImportError as e:
            raise CommandError(str(e))
        except Exception as e:
            raise CommandError(f'Import failed: {e}')
