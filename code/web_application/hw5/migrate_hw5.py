from datetime import datetime,timezone
from sqlalchemy import inspect, text

from database import Base, engine
from domain import models  # noqa: F401

'''
this script performs the database migration for Homework 5.
It creates the new restaurant table, adds new columns to the existing
restaurant_inspection table, populates those columns for
existing rows, and enforces the final constraints required by HW5.
expected output: "HW5 database migration completed successfully."
Starting HW5 database migration...
Adding column: inspection_code
Adding column: inspection_date
Adding column: score
Adding column: restaurant_id
Adding column: created_at
Adding column: updated_at
Creating legacy restaurant record...
Adding unique index for inspection_code...
Adding restaurant foreign key...
HW5 database migration completed successfully.
'''

DEFAULT_PERMIT_CODE = "LEGACY-2837"


def existing_columns(connection, table_name):
    inspector = inspect(connection)
    return {
        column["name"]
        for column in inspector.get_columns(table_name)
    }


def add_column_if_missing(connection, columns, name, definition):
    if name not in columns:
        print(f"Adding column: {name}")
        connection.execute(
            text(
                f"ALTER TABLE restaurant_inspection "
                f"ADD COLUMN {name} {definition}"
            )
        )
        columns.add(name)
    else:
        print(f"Column already exists: {name}")


def migrate():
    print("Starting HW5 database migration...")

    # Creates the new restaurant table and leaves existing tables intact.
    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        columns = existing_columns(
            connection,
            "restaurant_inspection",
        )

        # Add new columns as nullable first so existing rows remain valid.
        add_column_if_missing(
            connection,
            columns,
            "inspection_code",
            "VARCHAR(50) NULL",
        )

        add_column_if_missing(
            connection,
            columns,
            "inspection_date",
            "DATETIME NULL",
        )

        add_column_if_missing(
            connection,
            columns,
            "score",
            "INT NULL DEFAULT 0",
        )

        add_column_if_missing(
            connection,
            columns,
            "restaurant_id",
            "INT NULL",
        )

        add_column_if_missing(
            connection,
            columns,
            "created_at",
            "DATETIME NULL",
        )

        add_column_if_missing(
            connection,
            columns,
            "updated_at",
            "DATETIME NULL",
        )

        # Create one parent restaurant for existing HW4 inspection rows.
        result = connection.execute(
            text(
                """
                SELECT id
                FROM restaurant
                WHERE permit_code = :permit_code
                LIMIT 1
                """
            ),
            {
                "permit_code": DEFAULT_PERMIT_CODE,
            },
        )

        restaurant_row = result.first()

        if restaurant_row is None:
            print("Creating legacy restaurant record...")

            connection.execute(
                text(
                    """
                    INSERT INTO restaurant
                        (
                            name,
                            address,
                            permit_code,
                            created_at,
                            updated_at
                        )
                    VALUES
                        (
                            :name,
                            :address,
                            :permit_code,
                            :created_at,
                            :updated_at
                        )
                    """
                ),
                {
                    "name": "Legacy HW4 Restaurants",
                    "address": "Legacy data migrated from HW4",
                    "permit_code": DEFAULT_PERMIT_CODE,
                    "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
                    "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
                },
            )

            result = connection.execute(
                text(
                    """
                    SELECT id
                    FROM restaurant
                    WHERE permit_code = :permit_code
                    LIMIT 1
                    """
                ),
                {
                    "permit_code": DEFAULT_PERMIT_CODE,
                },
            )

            restaurant_row = result.first()

        default_restaurant_id = restaurant_row[0]

        # Populate new columns for existing HW4 inspection records.
        connection.execute(
            text(
                """
                UPDATE restaurant_inspection
                SET inspection_code =
                        CONCAT('INSP-', LPAD(id, 8, '0'))
                WHERE inspection_code IS NULL
                   OR inspection_code = ''
                """
            )
        )

        connection.execute(
            text(
                """
                UPDATE restaurant_inspection
                SET inspection_date = UTC_TIMESTAMP()
                WHERE inspection_date IS NULL
                """
            )
        )

        connection.execute(
            text(
                """
                UPDATE restaurant_inspection
                SET score = 0
                WHERE score IS NULL
                """
            )
        )

        connection.execute(
            text(
                """
                UPDATE restaurant_inspection
                SET restaurant_id = :restaurant_id
                WHERE restaurant_id IS NULL
                """
            ),
            {
                "restaurant_id": default_restaurant_id,
            },
        )

        connection.execute(
            text(
                """
                UPDATE restaurant_inspection
                SET created_at = UTC_TIMESTAMP()
                WHERE created_at IS NULL
                """
            )
        )

        connection.execute(
            text(
                """
                UPDATE restaurant_inspection
                SET updated_at = UTC_TIMESTAMP()
                WHERE updated_at IS NULL
                """
            )
        )

        # Enforce the final HW5 constraints.
        connection.execute(
            text(
                """
                ALTER TABLE restaurant_inspection
                MODIFY inspection_code VARCHAR(50) NOT NULL,
                MODIFY inspection_date DATETIME NOT NULL,
                MODIFY score INT NOT NULL DEFAULT 0,
                MODIFY restaurant_id INT NOT NULL,
                MODIFY created_at DATETIME NOT NULL,
                MODIFY updated_at DATETIME NOT NULL
                """
            )
        )

        # Add a unique index for inspection_code if one does not exist.
        unique_code_index = connection.execute(
            text(
                """
                SHOW INDEX
                FROM restaurant_inspection
                WHERE Column_name = 'inspection_code'
                  AND Non_unique = 0
                """
            )
        ).first()

        if unique_code_index is None:
            print("Adding unique index for inspection_code...")

            connection.execute(
                text(
                    """
                    ALTER TABLE restaurant_inspection
                    ADD CONSTRAINT uq_inspection_code
                    UNIQUE (inspection_code)
                    """
                )
            )
        else:
            print("Unique inspection_code index already exists.")

        # Add the foreign key if it does not already exist.
        foreign_keys = inspect(connection).get_foreign_keys(
            "restaurant_inspection"
        )

        relationship_exists = any(
            foreign_key.get("referred_table") == "restaurant"
            and foreign_key.get("constrained_columns") == ["restaurant_id"]
            for foreign_key in foreign_keys
        )

        if not relationship_exists:
            print("Adding restaurant foreign key...")

            connection.execute(
                text(
                    """
                    ALTER TABLE restaurant_inspection
                    ADD CONSTRAINT fk_inspection_restaurant
                    FOREIGN KEY (restaurant_id)
                    REFERENCES restaurant(id)
                    ON DELETE RESTRICT
                    """
                )
            )
        else:
            print("Restaurant foreign key already exists.")

    print("HW5 database migration completed successfully.")


if __name__ == "__main__":
    migrate()