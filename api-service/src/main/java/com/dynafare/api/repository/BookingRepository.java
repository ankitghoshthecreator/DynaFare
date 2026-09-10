package com.dynafare.api.repository;

import com.dynafare.api.domain.Booking;
import com.dynafare.api.domain.BookingStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * Repository interface for Booking entity management.
 */
@Repository
public interface BookingRepository extends JpaRepository<Booking, UUID> {
    Optional<Booking> findByQuoteId(UUID quoteId);
    Optional<Booking> findByTripId(UUID tripId);
    List<Booking> findByStatus(BookingStatus status);
}
