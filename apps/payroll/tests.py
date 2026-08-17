from datetime import date
from django.test import SimpleTestCase

from payroll.services import PayrollCalculatorService


class PayrollBenefitDaysRuleTests(SimpleTestCase):
    def test_holiday_without_biometric_does_not_count(self):
        period = type('Period', (), {
            'start_date': date(2026, 7, 1),
            'end_date': date(2026, 7, 31),
        })()
        service = PayrollCalculatorService.__new__(PayrollCalculatorService)
        service.period = period

        holiday_dates = {date(2026, 7, 20)}
        absent_dates_map = {}
        worked_holidays_map = {}

        count = service._count_valid_benefit_days(1, holiday_dates, absent_dates_map, worked_holidays_map)

        self.assertEqual(count, 22)

    def test_holiday_with_biometric_counts_once(self):
        period = type('Period', (), {
            'start_date': date(2026, 7, 1),
            'end_date': date(2026, 7, 31),
        })()
        service = PayrollCalculatorService.__new__(PayrollCalculatorService)
        service.period = period

        holiday_dates = {date(2026, 7, 20)}
        absent_dates_map = {}
        worked_holidays_map = {1: {date(2026, 7, 20)}}

        count = service._count_valid_benefit_days(1, holiday_dates, absent_dates_map, worked_holidays_map)

        self.assertEqual(count, 23)
