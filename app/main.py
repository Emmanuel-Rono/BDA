import hashlib
import json
from pathlib import Path
from threading import Lock
from fastapi import Depends, File, UploadFile
from .documents import MAX_BYTES, read_document
from .errors import AppError
from .extraction import extract
from .model import LocalModel
from .reconcile import reconcile
from .settings import Settings
from .spree import Spree
from .storage import Storage
from .web import shell


def create_app(settings=None, spree=None, model=None):
    settings = settings or Settings.from_env()
    storage = Storage(settings.data_dir / 'bda.sqlite3')
    spree, model = spree or Spree(settings), model or LocalModel(settings)
    app, auth = shell('BDA | Commerce Document Intelligence Agent', settings, storage, spree, model)
    with storage.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS uploads (hash TEXT, store_id TEXT, mode TEXT, job_id TEXT, PRIMARY KEY(hash,store_id,mode))')
    upload_lock = Lock()

    @app.post('/v1/jobs', dependencies=[Depends(auth)])
    def process(invoice: UploadFile = File(), packing_slip: UploadFile = File()):
        invoice_bytes, packing_bytes = invoice.file.read(MAX_BYTES + 1), packing_slip.file.read(MAX_BYTES + 1)
        inv_source = read_document(invoice.filename or '', invoice_bytes)
        pack_source = read_document(packing_slip.filename or '', packing_bytes)
        pair_hash = hashlib.sha256((inv_source['hash'] + ':' + pack_source['hash']).encode()).hexdigest()
        # This demo runs one server process. A short lock covers only the claim;
        # slow model inference runs outside it. The database also enforces uniqueness.
        with upload_lock:
            with storage.connect() as db:
                old = db.execute('SELECT job_id FROM uploads WHERE hash=? AND store_id=? AND mode=?',
                                 (pair_hash, settings.store_id, settings.mode)).fetchone()
            if old:
                return {**storage.get(old['job_id'], settings.store_id), 'duplicate': True}
            record = storage.create(settings.store_id, settings.mode, 'reconciliation')
            with storage.connect() as db:
                db.execute('INSERT INTO uploads VALUES (?,?,?,?)', (pair_hash, settings.store_id, settings.mode, record['id']))
        uploads = settings.data_dir / 'uploads'
        uploads.mkdir(exist_ok=True)
        for source, content, filename in ((inv_source, invoice_bytes, invoice.filename), (pack_source, packing_bytes, packing_slip.filename)):
            suffix = '.pdf' if (filename or '').lower().endswith('.pdf') else '.txt'
            (uploads / (source['hash'] + suffix)).write_bytes(content)
        try:
            inv = extract(inv_source['pages'], model)
            pack = extract(pack_source['pages'], model)
            reference = inv.order_reference.value
            if not reference or reference != pack.order_reference.value:
                raise AppError('reference_mismatch', 'Documents need the same explicit order reference; no guessing is permitted.')
            order = spree.get_order(reference)
            comparison = reconcile(inv, pack, order)
            record.update(status='needs_review', result={**comparison, 'order_reference': reference,
                'order': order, 'invoice': inv.model_dump(), 'packing_slip': pack.model_dump(),
                'sources': [{'id': inv_source['hash'], 'filename': Path(invoice.filename or '').name, 'pages': inv_source['pages']},
                            {'id': pack_source['hash'], 'filename': Path(packing_slip.filename or '').name, 'pages': pack_source['pages']}],
                'model': settings.model, 'review_notice': 'Approval saves this report only. Extracted values and source pages remain unchanged.'})
        except AppError as error:
            record.update(status='failed', error={'code': error.code, 'message': error.message})
        except Exception:
            record.update(status='failed', error={'code': 'internal_error', 'message': 'Unexpected document processing failure; inspect server logs.'})
        return storage.save(record)

    return app
