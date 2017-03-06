# -*- coding: utf-8 -*-
from gevent import monkey
monkey.patch_all()

try:
    import urllib3.contrib.pyopenssl
    urllib3.contrib.pyopenssl.inject_into_urllib3()
except ImportError:
    pass

import logging
import logging.config
import os
import argparse
import gevent

from functools import partial
from yaml import load
from gevent.queue import Queue

from openprocurement_client.client import TendersClientSync, TendersClient
from openprocurement.integrations.edr.client import EdrClient
from openprocurement.integrations.edr.databridge.journal_msg_ids import (
    DATABRIDGE_RESTART_WORKER, DATABRIDGE_START)
from openprocurement.integrations.edr.databridge.scanner import Scanner
from openprocurement.integrations.edr.databridge.filter_tender import FilterTenders
from openprocurement.integrations.edr.databridge.edr_handler import EdrHandler
from openprocurement.integrations.edr.databridge.upload_file import UploadFile
from openprocurement.integrations.edr.databridge.utils import journal_context, generate_req_id, Data, create_file

logger = logging.getLogger("openprocurement.integrations.edr.databridge")


class EdrDataBridge(object):
    """ Edr API Data Bridge """

    def __init__(self, config):
        super(EdrDataBridge, self).__init__()
        self.config = config

        api_server = self.config_get('tenders_api_server')
        api_version = self.config_get('tenders_api_version')
        ro_api_server = self.config_get('public_tenders_api_server') or api_server
        buffers_size = self.config_get('buffers_size') or 500
        self.delay = self.config_get('delay') or 15

        # init clients
        self.tenders_sync_client = TendersClientSync('', host_url=ro_api_server, api_version=api_version)
        self.client = TendersClient(self.config_get('api_token'), host_url=api_server, api_version=api_version)
        self.edrApiClient = EdrClient(host=self.config_get('edr_api_server'),
                                      token=self.config_get('edr_api_token'),
                                      port=self.config_get('edr_api_port'))

        # init queues for workers
        self.filtered_tender_ids_queue = Queue(maxsize=buffers_size)  # queue of tender IDs with appropriate status
        self.edrpou_codes_queue = Queue(maxsize=buffers_size)  # queue with edrpou codes (Data objects stored in it)
        # edr_ids_queue - queue with unique identification of the edr object (Data.edr_ids in Data object),
        # received from EDR Api. Later used to make second request to EDR to get detailed info
        self.edr_ids_queue = Queue(maxsize=buffers_size)
        self.upload_file_queue = Queue(maxsize=buffers_size)  # queue with detailed info from EDR (Data.file_content)
        # update_file_queue - queue with document_id (Data.file_content) to update documentType field in file
        self.update_file_queue = Queue(maxsize=buffers_size)

        # blockers
        self.initialization_event = gevent.event.Event()
        self.until_too_many_requests_event = gevent.event.Event()

        self.until_too_many_requests_event.set()

        # dictionary with processing awards/qualifications
        self.processing_items = {}

        # Workers
        self.scanner = partial(Scanner.spawn,
                               tenders_sync_client=self.tenders_sync_client,
                               filtered_tender_ids_queue=self.filtered_tender_ids_queue,
                               delay=self.delay)

        self.filter_tender = partial(FilterTenders.spawn,
                                     tenders_sync_client=self.tenders_sync_client,
                                     filtered_tender_ids_queue=self.filtered_tender_ids_queue,
                                     edrpou_codes_queue=self.edrpou_codes_queue,
                                     processing_items=self.processing_items,
                                     delay=self.delay)

        self.edr_handler = partial(EdrHandler.spawn,
                                   edrApiClient=self.edrApiClient,
                                   edrpou_codes_queue=self.edrpou_codes_queue,
                                   edr_ids_queue=self.edr_ids_queue,
                                   upload_file_queue=self.upload_file_queue,
                                   delay=self.delay)

        self.upload_file = partial(UploadFile.spawn,
                                   client=self.client,
                                   upload_file_queue=self.upload_file_queue,
                                   update_file_queue=self.update_file_queue,
                                   processing_items=self.processing_items,
                                   delay=self.delay)

    def config_get(self, name):
        return self.config.get('main').get(name)

    def _start_jobs(self):
        self.jobs = {'scanner': self.scanner(),
                     'filter_tender': self.filter_tender(),
                     'edr_handler': self.edr_handler(),
                     'upload_file': self.upload_file()}

    def run(self):
        logger.info('Start EDR API Data Bridge', extra=journal_context({"MESSAGE_ID": DATABRIDGE_START}, {}))
        self._start_jobs()
        counter = 0
        try:
            while True:
                gevent.sleep(self.delay)
                if counter == 20:
                    logger.info('Current state: filtered tenders {}; edrpou codes queue {}; edr ids queue {}; Upload file {}; Update file {}'.format(
                        self.filtered_tender_ids_queue.qsize(),
                        self.edrpou_codes_queue.qsize(),
                        self.edr_ids_queue.qsize(),
                        self.upload_file_queue.qsize(),
                        self.update_file_queue.qsize()))
                    counter = 0
                counter += 1
                for name, job in self.jobs.items():
                    if job.dead:
                        logger.warning('Restarting {} worker'.format(name),
                                       extra=journal_context({"MESSAGE_ID": DATABRIDGE_RESTART_WORKER}))
                        self.jobs[name] = gevent.spawn(getattr(self, name))
        except KeyboardInterrupt:
            logger.info('Exiting...')
            gevent.killall(self.jobs, timeout=5)
        except Exception as e:
            logger.error(e)


def main():
    parser = argparse.ArgumentParser(description='Edr API Data Bridge')
    parser.add_argument('config', type=str, help='Path to configuration file')
    parser.add_argument('--tender', type=str, help='Tender id to sync', dest="tender_id")
    params = parser.parse_args()
    if os.path.isfile(params.config):
        with open(params.config) as config_file_obj:
            config = load(config_file_obj.read())
        logging.config.dictConfig(config)
        EdrDataBridge(config).run()
    else:
        logger.info('Invalid configuration file. Exiting...')


if __name__ == "__main__":
    main()
