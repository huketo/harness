import unittest

import invoice
import pricing
import report


class PercentageDiscountContractTests(unittest.TestCase):
    def test_discounted_total_uses_a_fractional_rate(self):
        self.assertEqual(pricing.discounted_total(100.0, 0.15), 85.0)

    def test_discount_rate_boundaries(self):
        self.assertEqual(pricing.discounted_total(50.0, 0.0), 50.0)
        self.assertEqual(pricing.discounted_total(50.0, 1.0), 0.0)
        with self.assertRaises(ValueError):
            pricing.discounted_total(50.0, -0.01)
        with self.assertRaises(ValueError):
            pricing.discounted_total(50.0, 1.01)

    def test_invoice_updates_its_pricing_call(self):
        self.assertEqual(invoice.invoice_total([10.0, 30.0], 0.25), 30.0)

    def test_report_updates_its_invoice_call_and_format(self):
        self.assertEqual(report.render_invoice([19.99, 10.01], 0.1), "Invoice total: $27.00")

    def test_old_public_names_are_removed(self):
        self.assertFalse(hasattr(pricing, "apply_discount"))
        self.assertFalse(hasattr(invoice, "total_after_discount"))
        self.assertFalse(hasattr(report, "render_summary"))


if __name__ == "__main__":
    unittest.main()
