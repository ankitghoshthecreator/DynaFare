package com.dynafare.api.repository;

import com.dynafare.api.domain.Quote;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/**
 * Repository interface for Quote entity management.
 */
@Repository
public interface QuoteRepository extends JpaRepository<Quote, UUID> {
    List<Quote> findByRiderId(UUID riderId);
    List<Quote> findByExpiresAtBefore(OffsetDateTime time);
}
