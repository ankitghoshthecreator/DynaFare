package com.dynafare.api.repository;

import com.dynafare.api.domain.Trip;
import com.dynafare.api.domain.TripStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

/**
 * Repository interface for Trip entity management.
 */
@Repository
public interface TripRepository extends JpaRepository<Trip, UUID> {
    List<Trip> findByRiderId(UUID riderId);
    List<Trip> findByDriverId(UUID driverId);
    List<Trip> findByStatus(TripStatus status);
}
