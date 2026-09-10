package com.dynafare.api.repository;

import com.dynafare.api.domain.Driver;
import com.dynafare.api.domain.DriverStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * Repository interface for Driver entity management.
 */
@Repository
public interface DriverRepository extends JpaRepository<Driver, UUID> {
    Optional<Driver> findByUserId(UUID userId);
    List<Driver> findByStatus(DriverStatus status);
}
