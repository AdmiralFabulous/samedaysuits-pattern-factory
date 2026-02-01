#!/usr/bin/env python3
"""
Nesting Worker - Scalable Order Processing Worker

Long-running process that:
1. Polls Redis queue for new orders
2. Processes orders through the production pipeline
3. Handles failures with retry logic
4. Reports health via heartbeat

Features:
- Graceful shutdown on SIGTERM (Docker-friendly)
- Automatic retry with exponential backoff
- Dead-letter queue after 3 failures
- Worker identification for debugging

Usage:
    # Run directly
    python -m src.workers.nesting_worker

    # With custom worker ID
    WORKER_ID=worker-1 python -m src.workers.nesting_worker

    # Scale with Docker Compose
    docker-compose up -d --scale nesting-worker=3

Author: Claude
Date: 2026-01-31
"""

import os
import sys
import signal
import logging
import time
import traceback
from uuid import uuid4
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from scalability.queue_manager import OrderQueue, JobStatus, JobPriority

# Cutter queue integration
try:
    from core.resilient_cutter_queue import (
        ResilientCutterQueue,
        JobPriority as CutterPriority,
    )

    CUTTER_QUEUE_AVAILABLE = True
except ImportError:
    CUTTER_QUEUE_AVAILABLE = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("nesting-worker")


class NestingWorker:
    """
    Scalable worker that processes orders from the Redis queue.

    Each worker instance:
    - Has a unique ID for tracking
    - Polls the queue continuously
    - Processes one order at a time (nesting is CPU-bound)
    - Handles failures with retry logic
    - Reports health via heartbeat
    """

    def __init__(self, worker_id: Optional[str] = None):
        """
        Initialize worker.

        Args:
            worker_id: Unique worker identifier (auto-generated if not provided)
        """
        self.worker_id = (
            worker_id or os.getenv("WORKER_ID") or f"worker-{uuid4().hex[:8]}"
        )
        self.queue = OrderQueue()
        self.shutdown_requested = False
        self.current_order_id = None
        self.orders_processed = 0
        self.orders_failed = 0
        self.start_time = None

        # Import production modules
        self._api = None
        self._Order = None
        self._load_production_modules()

        # Initialize cutter queue (optional - only if available)
        self._cutter_queue = None
        self._init_cutter_queue()

    def _load_production_modules(self):
        """Load production pipeline modules."""
        try:
            from samedaysuits_api import (
                SameDaySuitsAPI,
                Order,
                GarmentType,
                FitType,
                CustomerMeasurements,
            )

            self._api = SameDaySuitsAPI()
            self._Order = Order
            self._GarmentType = GarmentType
            self._FitType = FitType
            self._CustomerMeasurements = CustomerMeasurements
            logger.info("Production modules loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load production modules: {e}")
            raise

    def _init_cutter_queue(self):
        """Initialize connection to resilient cutter queue."""
        if not CUTTER_QUEUE_AVAILABLE:
            logger.info(
                "Cutter queue not available - PLT files will not be auto-queued"
            )
            return

        try:
            cutter_data_dir = Path(os.getenv("CUTTER_DATA_DIR", "./cutter_data"))
            self._cutter_queue = ResilientCutterQueue(cutter_data_dir)
            logger.info(f"Cutter queue initialized at {cutter_data_dir}")
        except Exception as e:
            logger.warning(f"Failed to initialize cutter queue: {e}")
            self._cutter_queue = None

    def _submit_to_cutter_queue(
        self,
        order_id: str,
        result,
        order_data: Dict[str, Any],
    ):
        """
        Submit completed nesting result to cutter queue.

        Args:
            order_id: Order ID
            result: ProcessingResult from API
            order_data: Original order data dict
        """
        if self._cutter_queue is None:
            logger.debug(
                f"Cutter queue not available, skipping submission for {order_id}"
            )
            return

        if not result.plt_file or not Path(result.plt_file).exists():
            logger.warning(
                f"No PLT file for order {order_id}, cannot queue for cutting"
            )
            return

        try:
            # Determine priority based on order data
            priority_str = order_data.get("priority", "normal").lower()
            priority_map = {
                "rush": CutterPriority.RUSH,
                "high": CutterPriority.HIGH,
                "normal": CutterPriority.NORMAL,
                "low": CutterPriority.LOW,
            }
            priority = priority_map.get(priority_str, CutterPriority.NORMAL)

            # Build piece info list (if available from result)
            pieces = []
            if hasattr(result, "pieces") and result.pieces:
                pieces = result.pieces

            # Submit to cutter queue
            job = self._cutter_queue.add_job(
                order_id=order_id,
                plt_file=Path(result.plt_file),
                priority=priority,
                measurements=order_data.get("measurements"),
                pieces=pieces,
                fabric_length_cm=result.fabric_length_cm or 0.0,
            )

            logger.info(
                f"Submitted job {job.job_id} to cutter queue "
                f"(priority: {priority.name}, {result.piece_count} pieces)"
            )

        except Exception as e:
            logger.error(f"Failed to submit order {order_id} to cutter queue: {e}")
            # Don't fail the order - cutting queue is optional enhancement

    def _setup_signal_handlers(self):
        """Setup graceful shutdown handlers."""
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signal gracefully."""
        logger.info(f"Received shutdown signal ({signum}), finishing current order...")
        self.shutdown_requested = True

    def _write_heartbeat_file(self):
        """
        Write heartbeat file for Docker healthcheck.

        Docker healthcheck can verify the worker is alive by checking
        that this file exists and was modified recently.
        """
        try:
            heartbeat_path = Path("/tmp/worker_heartbeat")
            heartbeat_path.write_text(
                f"{self.worker_id}|{datetime.utcnow().isoformat()}|"
                f"processed={self.orders_processed}|failed={self.orders_failed}"
            )
        except Exception as e:
            # Non-fatal - log but don't crash
            logger.debug(f"Failed to write heartbeat file: {e}")

    def run(self):
        """
        Main worker loop.

        Continuously polls the queue and processes orders until shutdown.
        """
        self._setup_signal_handlers()
        self.start_time = datetime.utcnow()

        logger.info(f"Worker {self.worker_id} starting...")
        logger.info(f"Redis available: {self.queue.is_available}")

        if not self.queue.is_available:
            logger.error("Redis not available - worker cannot start")
            return

        while not self.shutdown_requested:
            try:
                # Send heartbeat (Redis + file-based for Docker healthcheck)
                self.queue.worker_heartbeat(self.worker_id)
                self._write_heartbeat_file()

                # Try to get an order
                order_data = self.queue.dequeue(timeout=5)

                if order_data is None:
                    # No orders available, wait briefly
                    continue

                # Process the order
                self._process_order(order_data)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                self.shutdown_requested = True
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                traceback.print_exc()
                time.sleep(5)  # Backoff on unexpected errors

        # Shutdown complete
        self._log_stats()
        logger.info(f"Worker {self.worker_id} shutdown complete")

    def _process_order(self, order_data: Dict[str, Any]):
        """
        Process a single order through the production pipeline.

        Args:
            order_data: Order data from queue
        """
        order_id = order_data.get("order_id", "unknown")
        self.current_order_id = order_id
        start_time = time.time()

        logger.info(f"Processing order {order_id}")
        logger.debug(f"Order data: {order_data}")

        try:
            # Convert dict to Order object
            order = self._create_order_object(order_data)

            # Process through pipeline
            logger.info(f"Starting pipeline for {order_id}...")
            result = self._api.process_order(order)

            processing_time = time.time() - start_time

            if result.success:
                # Mark complete
                self.queue.complete(
                    order_id,
                    {
                        "success": True,
                        "plt_file": str(result.plt_file) if result.plt_file else None,
                        "fabric_length_cm": result.fabric_length_cm,
                        "fabric_utilization": result.fabric_utilization,
                        "piece_count": result.piece_count,
                        "processing_time_ms": result.processing_time_ms,
                        "worker_id": self.worker_id,
                        "completed_at": datetime.utcnow().isoformat(),
                    },
                )

                self.orders_processed += 1
                logger.info(
                    f"Order {order_id} completed: "
                    f"{result.fabric_utilization:.1f}% utilization, "
                    f"{result.piece_count} pieces, "
                    f"{processing_time:.1f}s"
                )

                # Submit to cutter queue for cutting
                self._submit_to_cutter_queue(order_id, result, order_data)
            else:
                # Processing failed
                error_msg = (
                    "; ".join(result.errors) if result.errors else "Unknown error"
                )
                self._handle_failure(order_id, error_msg)

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Order {order_id} exception: {error_msg}")
            traceback.print_exc()
            self._handle_failure(order_id, error_msg)
        finally:
            self.current_order_id = None

    def _create_order_object(self, order_data: Dict[str, Any]):
        """Convert order dict to Order object."""
        # Handle nested measurements
        measurements = order_data.get("measurements", {})
        if isinstance(measurements, dict):
            measurements_obj = self._CustomerMeasurements(
                chest_cm=measurements.get("chest_cm", 100),
                waist_cm=measurements.get("waist_cm", 85),
                hip_cm=measurements.get("hip_cm", 100),
                shoulder_width_cm=measurements.get("shoulder_width_cm"),
                arm_length_cm=measurements.get("arm_length_cm"),
                inseam_cm=measurements.get("inseam_cm"),
                source=measurements.get("source", "queue"),
            )
        else:
            measurements_obj = measurements

        # Parse garment type
        garment_str = order_data.get("garment_type", "tee")
        try:
            garment_type = self._GarmentType(garment_str)
        except ValueError:
            garment_type = self._GarmentType.TEE

        # Parse fit type
        fit_str = order_data.get("fit_type", "regular")
        try:
            fit_type = self._FitType(fit_str)
        except ValueError:
            fit_type = self._FitType.REGULAR

        return self._Order(
            order_id=order_data.get("order_id"),
            customer_id=order_data.get("customer_id", "worker-queue"),
            garment_type=garment_type,
            fit_type=fit_type,
            measurements=measurements_obj,
            quantity=order_data.get("quantity", 1),
            notes=order_data.get("notes", ""),
        )

    def _handle_failure(self, order_id: str, error: str):
        """Handle order processing failure."""
        self.orders_failed += 1
        self.queue.fail(order_id, error)

    def _log_stats(self):
        """Log worker statistics."""
        if self.start_time:
            uptime = (datetime.utcnow() - self.start_time).total_seconds()
            rate = self.orders_processed / (uptime / 3600) if uptime > 0 else 0

            logger.info(
                f"Worker {self.worker_id} stats: "
                f"processed={self.orders_processed}, "
                f"failed={self.orders_failed}, "
                f"uptime={uptime:.0f}s, "
                f"rate={rate:.1f}/hour"
            )


def run_worker(worker_id: Optional[str] = None):
    """
    Entry point for running a worker.

    Args:
        worker_id: Optional worker identifier
    """
    worker = NestingWorker(worker_id)
    worker.run()


# Main entry point
if __name__ == "__main__":
    run_worker()
