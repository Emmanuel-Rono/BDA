"""Explicit document integration check using local inference and configured Spree access."""
import argparse
import json
from pathlib import Path
import tempfile
import time

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import ROOT, Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--invoice', type=Path, help='Invoice PDF or text file')
    parser.add_argument('--packing-slip', type=Path, help='Packing-slip PDF or text file')
    parser.add_argument('--expected-outcome', choices=['matched', 'discrepancies_found'])
    args = parser.parse_args()
    if bool(args.invoice) != bool(args.packing_slip):
        parser.error('Provide both --invoice and --packing-slip.')
    settings = Settings.from_env()
    if args.invoice:
        invoice, packing = args.invoice, args.packing_slip
    elif settings.mode == 'fixture':
        invoice, packing = ROOT / 'examples/invoice.txt', ROOT / 'examples/packing-slip.txt'
    else:
        invoice = settings.data_dir / 'examples/live-invoice.txt'
        packing = settings.data_dir / 'examples/live-packing-slip.txt'
    if not invoice.is_file() or not packing.is_file():
        parser.error('Document files were not found. Supply --invoice and --packing-slip for the target store.')
    files = {'invoice': (invoice.name, invoice.read_bytes()), 'packing_slip': (packing.name, packing.read_bytes())}

    with tempfile.TemporaryDirectory() as directory:
        settings.data_dir = Path(directory)
        with TestClient(create_app(settings)) as client:
            headers = {'Authorization': 'Bearer ' + settings.api_token}
            started = time.perf_counter()
            response = client.post('/v1/jobs', headers=headers, files=files)
            response.raise_for_status()
            report = response.json()
            report['measured_seconds'] = round(time.perf_counter() - started, 2)
            report_path = ROOT / 'reports/integration.json'
            report_path.parent.mkdir(exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
            if report['status'] != 'needs_review':
                raise RuntimeError('Document processing failed. Inspect reports/integration.json.')
            if args.expected_outcome and report['result']['outcome'] != args.expected_outcome:
                raise RuntimeError('The comparison did not return the expected outcome.')
            duplicate = client.post('/v1/jobs', headers=headers, files=files)
            duplicate.raise_for_status()
            if duplicate.json()['id'] != report['id'] or not duplicate.json().get('duplicate'):
                raise RuntimeError('Duplicate upload was not resolved to the original job.')
            review = client.post('/v1/reports/' + report['id'] + '/review', headers=headers,
                                 json={'decision':'approve', 'note':'Integration check: internal report only.', 'version':1})
            review.raise_for_status()
            saved = client.get('/v1/reports/' + report['id'], headers=headers)
            saved.raise_for_status()
            if saved.json()['status'] != 'approved':
                raise RuntimeError('The review decision was not persisted.')
            print(json.dumps({'status':'passed', 'source':settings.mode, 'seconds':report['measured_seconds'],
                              'outcome':report['result']['outcome'], 'report':str(report_path)}))


if __name__ == '__main__':
    main()
