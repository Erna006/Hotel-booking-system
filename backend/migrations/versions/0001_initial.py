"""Initial schema. Frozen DDL; independent of future ORM changes."""
from alembic import op
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS btree_gist')
    op.execute("CREATE TYPE user_role AS ENUM ('guest', 'receptionist', 'admin')")
    op.execute("CREATE TYPE booking_status AS ENUM ('pending', 'confirmed', 'cancelled')")
    op.execute("CREATE TYPE payment_status AS ENUM ('pending', 'succeeded', 'failed')")
    op.execute("CREATE TABLE guests (\n\tid UUID NOT NULL, \n\temail VARCHAR(254) NOT NULL, \n\tpassword_hash VARCHAR(255) NOT NULL, \n\tfull_name VARCHAR(200) NOT NULL, \n\trole user_role DEFAULT 'guest' NOT NULL, \n\tis_active BOOLEAN DEFAULT true NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_guest_email CHECK (email = lower(trim(email)) AND position('@' in email) > 1), \n\tCONSTRAINT ck_guest_name CHECK (length(trim(full_name)) > 0), \n\tUNIQUE (email)\n)")
    op.execute("CREATE TABLE rooms (\n\tid UUID NOT NULL, \n\tnumber VARCHAR(20) NOT NULL, \n\troom_type VARCHAR(50) NOT NULL, \n\tcapacity INTEGER NOT NULL, \n\tprice_per_night NUMERIC(12, 2) NOT NULL, \n\tcurrency VARCHAR(3) DEFAULT 'KZT' NOT NULL, \n\tis_active BOOLEAN DEFAULT true NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_room_capacity CHECK (capacity > 0), \n\tCONSTRAINT ck_room_price CHECK (price_per_night > 0), \n\tCONSTRAINT ck_room_labels CHECK (length(trim(number)) > 0 AND length(trim(room_type)) > 0), \n\tCONSTRAINT ck_room_currency CHECK (currency ~ '^[A-Z]{3}$'), \n\tUNIQUE (number)\n)")
    op.execute("CREATE TABLE bookings (\n\tid UUID NOT NULL, \n\tguest_id UUID NOT NULL, \n\troom_id UUID NOT NULL, \n\tcheck_in DATE NOT NULL, \n\tcheck_out DATE NOT NULL, \n\tstatus booking_status DEFAULT 'pending' NOT NULL, \n\ttotal_amount NUMERIC(12, 2) NOT NULL, \n\tcurrency VARCHAR(3) DEFAULT 'KZT' NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_booking_dates CHECK (check_out > check_in), \n\tCONSTRAINT ck_booking_amount CHECK (total_amount > 0), \n\tCONSTRAINT ck_booking_currency CHECK (currency ~ '^[A-Z]{3}$'), \n\tCONSTRAINT excl_booking_room_dates EXCLUDE USING gist (room_id WITH =, daterange(check_in, check_out, '[)') WITH &&) WHERE (status IN ('pending', 'confirmed')), \n\tFOREIGN KEY(guest_id) REFERENCES guests (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(room_id) REFERENCES rooms (id) ON DELETE RESTRICT\n)")
    op.execute('CREATE INDEX ix_bookings_guest_created ON bookings (guest_id, created_at)')
    op.execute("CREATE TABLE payments (\n\tid UUID NOT NULL, \n\tbooking_id UUID NOT NULL, \n\tidempotency_key UUID NOT NULL, \n\tamount NUMERIC(12, 2) NOT NULL, \n\tcurrency VARCHAR(3) DEFAULT 'KZT' NOT NULL, \n\tstatus payment_status DEFAULT 'pending' NOT NULL, \n\tfailure_reason VARCHAR(500), \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_payment_amount CHECK (amount > 0), \n\tCONSTRAINT ck_payment_currency CHECK (currency ~ '^[A-Z]{3}$'), \n\tCONSTRAINT uq_payment_idempotency UNIQUE (idempotency_key), \n\tFOREIGN KEY(booking_id) REFERENCES bookings (id) ON DELETE RESTRICT\n)")
    op.execute('CREATE INDEX ix_payments_booking ON payments (booking_id)')
    op.execute("CREATE UNIQUE INDEX uq_payment_success ON payments (booking_id) WHERE status = 'succeeded'")


def downgrade():
    op.execute('DROP TABLE payments')
    op.execute('DROP TABLE bookings')
    op.execute('DROP TABLE rooms')
    op.execute('DROP TABLE guests')
    op.execute('DROP TYPE payment_status')
    op.execute('DROP TYPE booking_status')
    op.execute('DROP TYPE user_role')
    # Keep btree_gist: other applications in this database may use it.
