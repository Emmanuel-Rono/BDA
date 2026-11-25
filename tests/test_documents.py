from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.documents import read_document
from app.errors import AppError
from app.extraction import Extraction, validate_evidence
from app.main import create_app
from app.reconcile import amount, reconcile
from app.settings import Settings
from app.spree import Spree
from app.storage import Storage


@pytest.fixture
def settings(tmp_path):
    return Settings(api_token='test-token-not-for-deployment', data_dir=tmp_path)


def field(value, quote=None):
    return {'value': value, 'page': 1 if value is not None else None, 'quote': quote or value}


def document(kind, quantity):
    return Extraction.model_validate({'document_type': kind, 'language': 'en',
        'document_number': field('INV-1007' if kind == 'invoice' else 'PACK-1007'),
        'order_reference': field('DEMO1007'), 'currency': field('USD'),
        'subtotal': field('60.00'), 'tax': field('0.00'), 'total': field('60.00'),
        'line_items': [{'sku': field('TEE-BLU-M'), 'description': field('Everyday Tee'),
                        'quantity': field(str(quantity)), 'unit_price': field('20.00'), 'line_total': field('60.00')}]})


def test_quantity_difference_is_calculated_without_model_judgement(settings):
    report = reconcile(document('invoice', 3), document('packing_slip', 2), Spree(settings).get_order('DEMO1007'))
    assert report['outcome'] == 'discrepancies_found'
    assert report['rows'][0]['difference'] == '-1'
    assert report['discrepancies'][0]['code'] == 'quantity_difference'


def test_matching_quantities_pass(settings):
    report = reconcile(document('invoice', 3), document('packing_slip', 3), Spree(settings).get_order('DEMO1007'))
    assert report['outcome'] == 'matched'


def test_wrong_reference_is_not_guessed(settings):
    invoice = document('invoice', 3)
    invoice.order_reference.value = 'WRONG'
    with pytest.raises(AppError) as error:
        reconcile(invoice, document('packing_slip', 3), Spree(settings).get_order('DEMO1007'))
    assert error.value.code == 'reference_mismatch'


def test_line_arithmetic_is_exact(settings):
    invoice = document('invoice', 3)
    invoice.line_items[0].line_total.value = '59.99'
    report = reconcile(invoice, document('packing_slip', 3), Spree(settings).get_order('DEMO1007'))
    assert 'line_arithmetic' in [issue['code'] for issue in report['discrepancies']]
    assert amount('0.10') + amount('0.20') == Decimal('0.30')


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-1', '1,000.00'])
def test_invalid_numbers_are_rejected(value):
    with pytest.raises(AppError):
        amount(value)


def test_hallucinated_field_quote_is_rejected():
    extraction = document('invoice', 3)
    with pytest.raises(AppError) as error:
        validate_evidence(extraction, [{'page': 1, 'text': 'Nothing supports these invented fields.'}])
    assert error.value.code == 'field_not_grounded'


def test_page_evidence_must_support_every_written_value():
    extraction = document('invoice', 3)
    text = 'INV-1007 DEMO1007 USD 60.00 0.00 TEE-BLU-M Everyday Tee 3 20.00'
    assert validate_evidence(extraction, [{'page': 1, 'text': text}]) == extraction
    extraction.line_items[0].quantity = type(extraction.line_items[0].quantity)(value='30', page=1, quote='3')
    with pytest.raises(AppError):
        validate_evidence(extraction, [{'page': 1, 'text': text}])


def test_unsupported_upload_has_explicit_error():
    with pytest.raises(AppError) as error:
        read_document('scan.png', b'not an extractable text document')
    assert error.value.code == 'file_type'


def test_auth_and_duplicate_jobs_do_not_repeat_inference(settings):
    class Model:
        calls = 0
        def structured(self, messages, schema):
            self.calls += 1
            kind = 'packing_slip' if 'PACKING SLIP' in messages[-1]['content'] else 'invoice'
            return document(kind, 2 if kind == 'packing_slip' else 3)
    model = Model()
    with TestClient(create_app(settings, model=model)) as client:
        assert client.get('/v1/reports').status_code == 401
        headers = {'Authorization': 'Bearer ' + settings.api_token}
        text = 'INV-1007 PACK-1007 DEMO1007 USD 60.00 0.00 TEE-BLU-M Everyday Tee 2 3 20.00'
        files = {'invoice': ('invoice.txt', 'INVOICE ' + text), 'packing_slip': ('packing.txt', 'PACKING SLIP ' + text)}
        first = client.post('/v1/jobs', files=files, headers=headers).json()
        second = client.post('/v1/jobs', files=files, headers=headers).json()
        assert first['status'] == 'needs_review'
        assert second['duplicate'] is True
        assert second['id'] == first['id']
        assert model.calls == 2


def test_review_survives_restart(settings):
    path = settings.data_dir / 'review.sqlite3'
    storage = Storage(path)
    record = storage.create(settings.store_id, 'fixture', 'report')
    record['status'] = 'needs_review'
    storage.save(record)
    storage.review(record['id'], settings.store_id, 'approve', 'Checked source pages', 1)
    assert Storage(path).get(record['id'], settings.store_id)['status'] == 'approved'


def test_non_usd_orders_are_not_compared_with_usd_rules(settings):
    order = Spree(settings).get_order('DEMO1007')
    order['currency'] = 'JPY'
    with pytest.raises(AppError) as error:
        reconcile(document('invoice', 3), document('packing_slip', 3), order)
    assert error.value.code == 'unsupported_currency'


def test_image_only_pdf_requires_ocr():
    from io import BytesIO
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    output = BytesIO()
    writer.write(output)
    with pytest.raises(AppError) as error:
        read_document('scan.pdf', output.getvalue())
    assert error.value.code == 'ocr_required'


def test_native_pdf_preserves_text_page_evidence():
    from io import BytesIO
    from reportlab.pdfgen import canvas
    output = BytesIO()
    pdf = canvas.Canvas(output)
    pdf.drawString(40, 700, 'Order Reference: DEMO1007')
    pdf.save()
    parsed = read_document('invoice.pdf', output.getvalue())
    assert parsed['pages'][0]['page'] == 1
    assert 'Order Reference: DEMO1007' in parsed['pages'][0]['text']
