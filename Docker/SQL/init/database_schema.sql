CREATE TABLE providers (
    id INTEGER PRIMARY KEY,
    provider_name VARCHAR(32) UNIQUE NOT NULL
);

CREATE TABLE taxi_zones (
    id INTEGER PRIMARY KEY,
    zone_name VARCHAR(64) NOT NULL
);

CREATE TABLE trips (
    id INTEGER PRIMARY KEY,
    provider_id INTEGER REFERENCES providers(id),
    pu_location_id INTEGER REFERENCES taxi_zones(id),
    do_location_id INTEGER REFERENCES taxi_zones(id),
    request_datetime TIMESTAMP NOT NULL,
    on_scene_datetime TIMESTAMP,
    pickup_datetime TIMESTAMP NOT NULL,
    dropoff_datetime TIMESTAMP NOT NULL,
    trip_miles NUMERIC(12,3),
    trip_time NUMERIC(12,3),
    base_passenger_fare DECIMAL(10,2),
    tolls DECIMAL(10,2),
    bcf DECIMAL(10,2),
    sales_tax DECIMAL(10,2),
    congestion_surcharge DECIMAL(10,2),
    airport_fee DECIMAL(10,2),
    tips DECIMAL(10,2),
    driver_pay DECIMAL(10,2),
    cbd_congestion_fee DECIMAL(10,2),
    shared_request_flag BOOLEAN,
    shared_match_flag BOOLEAN,
    access_a_ride_flag BOOLEAN,
    wav_request_flag BOOLEAN,
    wav_match_flag BOOLEAN
);

FOREIGN KEY (XXX) REFERENCES taxi_zones(id), FOREIGN KEY (XXX) REFERENCES taxi_zones(id), FOREIGN KEY (XXX) REFERENCES providers(id),