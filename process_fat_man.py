#!/usr/bin/env python3
"""
Process Fat Man through complete pipeline
"""

import sys

sys.path.insert(0, ".")

from theblackbox_integration import TheBlackboxIntegration
from samedaysuits_api import (
    SameDaySuitsAPI,
    Order,
    CustomerMeasurements,
    GarmentType,
    FitType,
)
import json

print("=" * 70)
print("PROCESSING: Fat Man (Size XXL) - Light Jacket")
print("=" * 70)

# Load and process fat man scan
blackbox = TheBlackboxIntegration()
scan_file = "scans/SCAN-FAT-MAN-20260131015812.json"
scan_data = blackbox.load_scan(scan_file)

print(f"\nCustomer: {scan_data.customer_id}")
print(
    f"Measurements: Chest {scan_data.measurements.chest_cm}cm, Waist {scan_data.measurements.waist_cm}cm, Hip {scan_data.measurements.hip_cm}cm"
)

# Create order
order = blackbox.create_order_from_scan(
    scan_data=scan_data,
    garment_type="jacket",
    fit_type="regular",
)

print(f"Order ID: {order['order_id']}")
print("\nProcessing through pipeline (this may take 30-60 seconds)...")

# Process through API
api = SameDaySuitsAPI()

order_obj = Order(
    order_id=order["order_id"],
    customer_id=order["customer_id"],
    garment_type=GarmentType(order["garment_type"]),
    fit_type=FitType(order["fit_type"]),
    measurements=CustomerMeasurements(
        chest_cm=order["measurements"]["chest_cm"],
        waist_cm=order["measurements"]["waist_cm"],
        hip_cm=order["measurements"]["hip_cm"],
        shoulder_width_cm=order["measurements"].get("shoulder_width_cm"),
        arm_length_cm=order["measurements"].get("arm_length_cm"),
        inseam_cm=order["measurements"].get("inseam_cm"),
        neck_cm=order["measurements"].get("neck_cm"),
        source="theblackbox",
    ),
)

result = api.process_order(order_obj)

if result.success:
    print(f"\n[SUCCESS] Production complete!")
    print(f"  PLT File: {result.plt_file}")
    print(f"  Fabric Length: {result.fabric_length_cm:.1f} cm")
    print(f"  Fabric Utilization: {result.fabric_utilization:.1f}%")
    print(f"  Piece Count: {result.piece_count}")

    # Save result
    output_info = {
        "customer_type": "FAT_MAN",
        "order_id": result.order_id,
        "plt_file": str(result.plt_file),
        "metadata_file": str(result.metadata_file),
        "fabric_length_cm": result.fabric_length_cm,
        "fabric_utilization": result.fabric_utilization,
        "piece_count": result.piece_count,
    }

    with open("FAT_MAN_RESULT.json", "w") as f:
        json.dump(output_info, f, indent=2)

    print(f"\nResult saved to: FAT_MAN_RESULT.json")
else:
    print(f"\n[FAILED] {result.errors}")

print("=" * 70)
