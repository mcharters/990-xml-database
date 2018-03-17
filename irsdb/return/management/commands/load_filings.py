import csv
import os
import requests

from django.core.management.base import BaseCommand
from filing.models import Filing
from django.conf import settings
from datetime import datetime

from irsx.settings import INDEX_DIRECTORY
from irsx.file_utils import stream_download
from irsx.xmlrunner import XMLRunner

from schemas.model_accumulator import Accumulator


# this is how many we process; there's a separate batch size
# in model accumulator for how many are processed
BATCH_SIZE = 200


class Command(BaseCommand):
    help = '''
    Enter the filings, one by one.
    Loading is done in bulk, though status on the filings is updated one at a time.
   
    '''

    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument('year', nargs='+', type=int)

    def setup(self):
        # get an XMLRunner -- this is what actually does the parsing
        self.xml_runner = XMLRunner()
        self.accumulator = Accumulator()


    def process_sked(self, sked):
        """ Enter just one schedule """ 
        print("Processing schedule %s" % sked['schedule_name'])
        for part in sked['schedule_parts'].keys():
            partname = part
            partdata = sked['schedule_parts'][part]
            #print(partname, partdata)
            self.accumulator.add_model(partname, partdata)

        for groupname in sked['groups'].keys():
            for groupdata in sked['groups'][groupname]:
                self.accumulator.add_model(groupname, groupdata)


    def run_filing(self, filing):

        object_id = filing.object_id

        parsed_filing = self.xml_runner.run_filing(object_id)
        if not parsed_filing:
            print("Skipping filing %s(filings with pre-2013 filings are skipped)\n row details: %s" % (filing, metadata_row))
            return None
        
        schedule_list = parsed_filing.list_schedules()
        print("sked list is %s" % schedule_list)

        result = parsed_filing.get_result()
        keyerrors = parsed_filing.get_keyerrors()
        has_keyerrors = len(keyerrors) > 0
        if has_keyerrors:
            filing.has_keyerrors = True
            filing.error_details = str(keyerrors)
            filing.save()
            

        for sked in result:
            self.process_sked(sked)


    def handle(self, *args, **options):
        self.setup()
        print("options are %s" % options)

        while True:
                
            filings=Filing.objects.all().exclude(parse_complete=True)[:100]
            if not filings:
                break

            object_id_list = [f.object_id for f in filings]

            # record that processing has begun
            Filing.objects.filter(object_id__in=object_id_list).update(parse_started=True)

            for filing in filings:
                print("Handling id %s" % filing.object_id)
                parsed_filing = self.run_filing(filing)
                keyerrors = parsedFiling.get_keyerrors()
                has_keyerrors = len(keyerrors) > 0
                if has_keyerrors:
                    # If we find keyerrors--xpaths that are missing from our spec, note it
                    filing.error_details = str(keyerrors)
                    filing.key_error_count = len(keyerrors)
                    filing.has_keyerrors = has_keyerrors
                    filing.save()


            self.accumulator.commit_all()
            # record that all are complete
            Filing.objects.filter(object_id__in=object_id_list).update(process_time=datetime.now(), parse_complete=True)

