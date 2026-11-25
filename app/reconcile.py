"""Exact arithmetic and explicit scope rules. The model never decides discrepancies."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from .errors import AppError


def amount(value):
    if value is None:
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise AppError('invalid_number', 'Expected a plain decimal value; review the extracted number.')
    if not number.is_finite() or number < 0:
        raise AppError('invalid_number', 'Negative or non-finite document values need manual review.')
    return number


def quantities(document):
    totals = defaultdict(Decimal)
    for item in document.line_items:
        quantity = amount(item.quantity.value)
        if not item.sku.value or quantity is None or quantity != quantity.to_integral_value():
            raise AppError('line_incomplete', 'Every line needs a source-backed SKU and a whole-unit quantity.')
        totals[item.sku.value] += quantity
    return totals


def reconcile(invoice, packing, order):
    if order['currency'] != 'USD':
        raise AppError('unsupported_currency', 'This MVP checks USD orders only; other currencies need explicit rounding rules.')
    if invoice.document_type != 'invoice' or packing.document_type != 'packing_slip':
        raise AppError('document_type', 'Upload the invoice first and the packing slip second; unknown documents need review.')
    if invoice.order_reference.value != order['number'] or packing.order_reference.value != order['number']:
        raise AppError('reference_mismatch', 'Both documents must reference the exact matched Spree order number.')
    if invoice.currency.value and invoice.currency.value != order['currency']:
        raise AppError('currency_mismatch', 'Invoice currency differs from the order. No cross-currency comparison was made.')
    ordered = defaultdict(Decimal)
    for item in order['items']:
        if not item['sku'] or item['quantity'] is None:
            raise AppError('order_line_incomplete', 'Spree order lines need SKU and quantity before reconciliation.')
        ordered[item['sku']] += amount(str(item['quantity']))
    invoiced, packed = quantities(invoice), quantities(packing)
    rows, issues = [], []
    for sku in sorted(set(ordered) | set(invoiced) | set(packed)):
        row = {'sku': sku, 'ordered': str(ordered[sku]), 'invoiced': str(invoiced[sku]),
               'packed': str(packed[sku]), 'difference': str(packed[sku] - invoiced[sku])}
        row['status'] = 'match' if ordered[sku] == invoiced[sku] == packed[sku] else 'review'
        rows.append(row)
        if row['status'] == 'review':
            issues.append({'code': 'quantity_difference', 'sku': sku,
                           'message': f"{sku}: ordered {ordered[sku]}, invoiced {invoiced[sku]}, packed {packed[sku]}. Check partial shipments or missing units."})
    for item in invoice.line_items:
        quantity, price, total = amount(item.quantity.value), amount(item.unit_price.value), amount(item.line_total.value)
        if None not in (quantity, price, total) and (quantity * price).quantize(Decimal('0.01')) != total:
            issues.append({'code': 'line_arithmetic', 'sku': item.sku.value, 'message': 'Quantity multiplied by unit price does not equal the written line total.'})
    line_totals = [amount(item.line_total.value) for item in invoice.line_items]
    subtotal = amount(invoice.subtotal.value)
    if line_totals and all(value is not None for value in line_totals) and subtotal is not None:
        if sum(line_totals).quantize(Decimal('0.01')) != subtotal:
            issues.append({'code': 'subtotal_arithmetic', 'message': 'The written subtotal differs from the sum of line totals.'})
    return {'rows': rows, 'discrepancies': issues, 'outcome': 'discrepancies_found' if issues else 'matched',
            'warnings': ['Quantity differences require review; they may represent a partial shipment.',
                         'Invoice grand total is not compared with order total: shipping, discounts and taxes may differ.',
                         'This MVP checks whole units and two-decimal USD line arithmetic. No stock or payment change occurs.']}
