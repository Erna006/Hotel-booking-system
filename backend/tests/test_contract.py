from datetime import date
from uuid import uuid4
import pytest
from pydantic import ValidationError
from backend.schemas import Register, ProfilePatch, RoomPatch, BookingCreate


def test_registration_does_not_allow_privilege_fields():
    data = dict(email=' TEST@Example.com ', password='long-enough-password', full_name=' Test ')
    account = Register(**data)
    assert account.email == 'test@example.com'
    assert account.full_name == 'Test'
    for key, value in [('role', 'admin'), ('is_active', True)]:
        with pytest.raises(ValidationError):
            Register(**data, **{key: value})


@pytest.mark.parametrize('model,body', [(ProfilePatch, {'email': None}), (ProfilePatch, {'full_name': None}),
    (ProfilePatch, {'role': 'admin'}), (RoomPatch, {'price_per_night': '1.001'}),
    (RoomPatch, {'capacity': 0}), (RoomPatch, {'currency': 'usd'}), (RoomPatch, {'is_active': None})])
def test_patch_validation(model, body):
    with pytest.raises(ValidationError):
        model(**body)


@pytest.mark.parametrize('start,end', [(date(2000,1,1),date(2000,1,2)),
    (date(2030,1,1),date(2030,1,1)), (date(2030,1,2),date(2030,1,1))])
def test_invalid_booking_dates(start, end):
    with pytest.raises(ValidationError):
        BookingCreate(room_id=uuid4(), check_in=start, check_out=end)
