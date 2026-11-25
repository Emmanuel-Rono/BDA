"""Opt-in real local-model extraction and configured Spree reconciliation check."""
import json
from pathlib import Path
import tempfile
import time
from fastapi.testclient import TestClient
from app.main import create_app
from app.settings import Settings, ROOT
from app.model import LocalModel


def main():
    settings = Settings.from_env()
    captures = []
    class RecordingModel(LocalModel):
        def structured(self, messages, schema):
            result = super().structured(messages, schema)
            captures.append(result.model_dump())
            return result
    with tempfile.TemporaryDirectory() as directory:
        settings.data_dir = Path(directory)
        with TestClient(create_app(settings, model=RecordingModel(settings))) as client:
            headers = {'Authorization': 'Bearer ' + settings.api_token}
            prefix = 'live-' if settings.mode == 'live' else ''
            files = {'invoice': ('invoice.txt', (ROOT / ('examples/' + prefix + 'invoice.txt')).read_bytes()),
                     'packing_slip': ('packing-slip.txt', (ROOT / ('examples/' + prefix + 'packing-slip.txt')).read_bytes())}
            start = time.perf_counter()
            response = client.post('/v1/jobs', headers=headers, files=files)
            response.raise_for_status()
            report = response.json()
            report['measured_seconds'] = round(time.perf_counter() - start, 2)
            (ROOT / 'reports').mkdir(exist_ok=True)
            (ROOT / 'reports/real-model-smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            (ROOT / 'reports/model-extractions.json').write_text(json.dumps(captures, indent=2), encoding='utf-8')
            print(json.dumps({'status': report['status'], 'mode': settings.mode, 'seconds': report['measured_seconds'],
                              'error': report['error'], 'outcome': (report['result'] or {}).get('outcome')}))
            assert report['status'] == 'needs_review', 'Real extraction failed; inspect reports/real-model-smoke.json'
            assert any(item['code'] == 'quantity_difference' for item in report['result']['discrepancies'])
            duplicate = client.post('/v1/jobs', headers=headers, files=files).json()
            assert duplicate['id'] == report['id'] and duplicate['duplicate']
            reviewed = client.post('/v1/reports/' + report['id'] + '/review', headers=headers,
                                  json={'decision': 'approve', 'note': 'Demo evidence checked; no stock change.', 'version': 1})
            assert reviewed.json()['status'] == 'approved'


if __name__ == '__main__':
    main()
