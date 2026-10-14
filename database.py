"""SQLite storage for synthetic account data and demo loan applications."""

import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self, demo_customer_id: str) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    customer_id TEXT PRIMARY KEY,
                    masked_account_number TEXT NOT NULL,
                    account_type TEXT NOT NULL,
                    account_status TEXT NOT NULL,
                    available_balance REAL NOT NULL,
                    masked_mobile_number TEXT NOT NULL,
                    kyc_status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS loan_applications (
                    reference TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    loan_amount REAL NOT NULL,
                    tenure_months INTEGER NOT NULL,
                    calculated_emi REAL NOT NULL,
                    interest_rate REAL NOT NULL,
                    purpose TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    submission_key TEXT NOT NULL UNIQUE
                );
                """
            )
            connection.execute(
                """INSERT OR IGNORE INTO accounts
                   (customer_id, masked_account_number, account_type, account_status,
                    available_balance, masked_mobile_number, kyc_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    demo_customer_id,
                    "XXXXXX4821",
                    "Savings",
                    "Active",
                    84250.75,
                    "+91-98XXXXXX42",
                    "Verified",
                ),
            )

    def get_account(self, customer_id: str) -> dict[str, object] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT masked_account_number, account_type, account_status,
                          available_balance, masked_mobile_number, kyc_status
                   FROM accounts WHERE customer_id = ?""",
                (customer_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_application_by_key(self, submission_key: str) -> dict[str, object] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM loan_applications WHERE submission_key = ?",
                (submission_key,),
            ).fetchone()
        return dict(row) if row else None

    def insert_application(self, application: dict[str, object]) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO loan_applications
                   (reference, customer_id, loan_amount, tenure_months, calculated_emi,
                    interest_rate, purpose, submitted_at, status, submission_key)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    application["reference"],
                    application["customer_id"],
                    application["loan_amount"],
                    application["tenure_months"],
                    application["calculated_emi"],
                    application["interest_rate"],
                    application["purpose"],
                    application["submitted_at"],
                    application["status"],
                    application["submission_key"],
                ),
            )