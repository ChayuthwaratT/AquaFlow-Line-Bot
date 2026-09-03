import csv
import uuid
import os


CSV_PATH = os.path.join(
    os.path.dirname(__file__),
    "water_users_registry_20260818.csv"
)


# Load CSV data
_registry = {}

with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)

    for row in reader:
        meter_number = row["เลขผู้ใช้น้ำ"].strip()
        _registry[meter_number] = row


def check_bill_mock(meter_number):

    meter_number = meter_number.strip()

    # Find user
    row = _registry.get(meter_number)

    if row is None:
        return None

    # Determine payment status from CSV
    overdue = row["สถานะ"].strip() == "ค้างจ่าย"

    # Generate a consistent fake bill ID
    bill_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_DNS,
            f"aquaflow-{meter_number}"
        )
    )

    # Mock bill information
    bill = {
        "bill_id": bill_id,
        "amount": 320 if overdue else 280,
        "due_date": "15 กันยายน 2569",
        "status": "ค้างชำระ" if overdue else "จ่ายแล้ว",
        "qr_available": overdue
    }

    return {
        "resident": {
            "meter_number": meter_number,
            "full_name": row["ชื่อผู้ใช้น้ำ"].strip(),
            "address": row["ที่อยู่"].strip()
        },
        "bill": bill
    }