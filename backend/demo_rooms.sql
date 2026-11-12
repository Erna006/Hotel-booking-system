INSERT INTO rooms (number, room_type, capacity, price_per_night, currency)
VALUES
    ('101', 'standard', 2, 29000, 'KZT'),
    ('202', 'deluxe', 2, 38500, 'KZT'),
    ('203', 'studio', 2, 44000, 'KZT'),
    ('304', 'family', 4, 52000, 'KZT'),
    ('401', 'suite', 2, 62000, 'KZT'),
    ('402', 'residence', 4, 79000, 'KZT')
ON CONFLICT (number) DO NOTHING;
